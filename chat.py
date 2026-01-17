from fastapi import APIRouter, Depends, File, UploadFile, Request, HTTPException
from fastapi.responses import JSONResponse
import redis
from settings import settings
from db.models import User, Message, Prompt
from routes.schemas import Chat, UserMessage, AssistantMessage, ReactionRequest, CommentRequest, FilterResponse
from services.schemas import Attachment
from services import (
    LLMService, UserService,
    PromptService, ChatService, SpeechService,
    FileSearchService, FilterService, RouterService, SessionService, PaymentService
)
from depends.services import (
    get_chat_service, get_prompt_service, get_user_service,
    get_llm_service, get_speech_service, 
    get_filter_service, get_file_search_service, get_router_service, get_file_processor_service,
    get_session_service, get_payment_service
)
from depends.auth import get_current_user
from depends.chat import get_message_data, ensure_token_limit
from utils.logger import get_logger
from utils.tokens import count_tokens
from utils.rate_limiter import (
    per_minute_limiter, per_hour_limiter, daily_limiter, 
    chat_message_limiter, chat_history_limiter, jwt_per_hour_limiter, 
    jwt_chat_history_limiter, jwt_chat_message_limiter, jwt_audio_limiter, jwt_daily_limiter
)
from utils.files.file_processor import generate_preview, FileProcessor

logger = get_logger(__name__)
router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)


#TODO: использоваться пагинацию с динамическим фронтом
@router.get("/list")
async def list_chats(
    request: Request,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    #rate_limit: None = Depends(jwt_per_hour_limiter)
) -> list[Chat]:
    chats = await chat_service.list_user_chats(user.id)
    return [Chat(chat_id=chat.id, model_type=chat.model_type, subject=chat.subject, title=chat.title) for chat in chats]


#TODO: иметь хоть какие-то лимиты сообщений в рамках одного чата
#TODO: иметь хоть какие-то лимиты при получении истории чата
@router.get("/{chat_id}/messages")
async def get_chat_messages(
    request: Request,
    chat_id: int,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    #rate_limit: None = Depends(jwt_chat_history_limiter)
):
    messages, attachments = await chat_service.get_history(chat_id)
    logger.info(f"Getting messages for chat {chat_id}")
    history = []
    for message in messages:
        if message.role == "user":
            message_attachments = await chat_service.get_attachments(message.id)
            history.append(UserMessage(content=message.content, chat_id=message.chat_id, message_id=message.id, files=[i.file_type for i in message_attachments]))
        else:
            reaction = 0 if message.reaction is None else (1 if message.reaction else -1)
            history.append(AssistantMessage(content=message.content, chat_id=message.chat_id, message_id=message.id, reaction=reaction))
    return history


@router.post("/new-message")
async def new_message(
    request: Request,
    #rate_limit_minute: None = Depends(jwt_chat_message_limiter),
    #rate_limit_daily: None = Depends(jwt_daily_limiter),
    message: UserMessage = Depends(get_message_data),
    user: User = Depends(get_current_user),
    files: list[UploadFile] = File([]),
    images: list[UploadFile] = File([]),
    chat_service: ChatService = Depends(get_chat_service),
    user_service: UserService = Depends(get_user_service),
    prompt_service: PromptService = Depends(get_prompt_service),
    llm_service: LLMService = Depends(get_llm_service),
    filter_service: FilterService = Depends(get_filter_service),
    file_search_service: FileSearchService = Depends(get_file_search_service),
    router_service: RouterService = Depends(get_router_service),
    file_processor: FileProcessor = Depends(get_file_processor_service),
    session_service: SessionService = Depends(get_session_service),
    #ensure_token_limit: None = Depends(ensure_token_limit)  # TODO: Проверить правильность такого вызова вообще
) -> AssistantMessage:

    if not await user_service.validate_session(user.id):
        return JSONResponse({"error": "Session expired"}, status_code=401)
    
    if message.content.lower() == settings.payment.privileged_passphrase:
        await session_service.add_privileged_user(user.id)
        logger.info(f"User {user.id} is privileged. Request will be processed.")
        return JSONResponse({"message": "Privileged user added"}, status_code=200)
    
    if not await session_service.user_able_to_request(user.id, message.model_type):
        logger.info(f"User {user.id} has reached the limit of requests for this subscription level. Request will not be processed.")
        return JSONResponse({"error": "You've reached the limit of requests for this subscription level"}, status_code=402)

    chat = await chat_service.get_or_create_chat(user.id, message.model_type, message.subject, message.content, message.chat_id)
    
    logger.info(f"New message: {message}")

    model = settings.models.base_model
    if chat.model_type in ("Размышляющая", "Проверка", "ОГЭ/ЕГЭ", "Планирование"):
        model = {
            "Размышляющая": settings.models.thinking_model,
            "Проверка": settings.models.checking_model,
            "ОГЭ/ЕГЭ": settings.models.rag_model,
            "Планирование": settings.models.planning_model
        }[chat.model_type]

    attachments: list[Attachment] | None = None
    model = settings.models.vision_model if images else model
    prompt_subject = chat.subject or message.subject
    if chat.model_type != "Обучающая":
        prompt_subject = chat.model_type
        if prompt_subject == "ОГЭ/ЕГЭ":
            prompt_subject = "RAG"
    prompt_model: Prompt = await prompt_service.get_prompt(prompt_subject)
    logger.info(f"Prompt extracted: {prompt_model.id if prompt_model else 'None'}")
    subject_prompt: str = (prompt_model.prompt if (prompt_model and getattr(prompt_model, "prompt", None)) else "")

    combined_with_files: str = message.content
    if files or images:
        attachments = await file_processor.process_uploaded_files(files=files, images=images, close_after=False)
        combined_with_files += await generate_preview(attachments)
    try:
        decision = await filter_service.filter_message(
            message_content=combined_with_files)
        if not decision.get("allowed", False):
            logger.warning(f"Message rejected by filter: {decision}")
            return JSONResponse(FilterResponse(allowed=False, reason=decision.get("reason", "Причина не указана")).model_dump(), status_code=400)
    except Exception as e:
        logger.error(f"Error filtering message: {e}")
    
    await chat_service.add_user_message(chat.id, combined_with_files, attachments=attachments if attachments else None) 
    # NOTE: At that moment history already includes new message and new attachments
    history: list[Message]
    attachments_history: list[Attachment]
    history, attachments_history = await chat_service.get_history(chat.id)
      
    if chat.model_type == "ОГЭ/ЕГЭ":
        index_name = await router_service.route_query(combined_with_files, subject=chat.subject)
        logger.info(f"Index name: {index_name}")
        fs_answer = await file_search_service.ask(history, index_name=index_name, system_prompt=subject_prompt, attachments=attachments_history)
        if fs_answer:
            new_message = await chat_service.add_assistant_message(chat.id, fs_answer)
            await user_service.increase_messages(user.id)
            return AssistantMessage(chat_id=chat.id, content=fs_answer, subject=chat.subject, message_id=new_message.id)
        prompt: str = subject_prompt
    else:
        prompt: str = subject_prompt

    # Флаг стриминга: при stream=true шлём SSE для всех режимов (вкл. RAG)
    stream = request.query_params.get("stream") == "true"
    stream = True
    if stream:
        async def sse_iter():
            try:
                full_text = ""
                if chat.model_type == "ОГЭ/ЕГЭ":
                    # Настоящий стрим из Responses API
                    async for piece in file_search_service.ask_stream(message.content, system_prompt=subject_prompt):
                        full_text += piece or ""
                        yield f"data: {piece}\n\n"
                    if full_text:
                        await chat_service.add_assistant_message(chat.id, full_text)
                        await user_service.increase_messages(user.id)
                    yield "data: [DONE]\n\n"
                    return
                # Обычный LLM: настоящий стрим с накоплением
                payload = {
                    "model": model,
                    "messages": ( [{"role": "system", "content": prompt}] +
                                   ([{"role": m.role, "content": m.content} for m in history[-settings.config.history_depth:]] if history else []) +
                                   ([{"role": "user", "content": message.content}] if not files else []) )
                }
                async for piece in llm_service.client.chat_completion_stream_iter(payload):
                    full_text += piece or ""
                    yield f"data: {piece}\n\n"
                # Сохраняем в БД перед завершением
                if full_text:
                    await chat_service.add_assistant_message(chat.id, full_text)
                    await user_service.increase_messages(user.id)
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: [DONE]\n\n"
        return StreamingResponse(sse_iter(), media_type="text/event-stream")

    llm_response = await llm_service.generate_response(
        prompt,
        model,
        history,
        attachments=attachments_history
        #router="OpenAI" if model in [settings.models.thinking_model, settings.models.checking_model] else "OpenRouter"
    )
    new_message = await chat_service.add_assistant_message(chat.id, llm_response)
    await user_service.increase_messages(user.id)
    return AssistantMessage(chat_id=chat.id, content=llm_response, subject=chat.subject, message_id=new_message.id)


#TODO: узнать лимиты по API сервера для распознавания речи и сделать обработку ошибок более явной
@router.post("/audio-to-text")
async def convertAudioToText(
        request: Request,
        audio_file: UploadFile = File(...),
        speech_service: SpeechService = Depends(get_speech_service),
        user: User = Depends(get_current_user),
        #rate_limit: None = Depends(jwt_audio_limiter)
) -> JSONResponse:

    try:
        audio_bytes = await audio_file.read()
        text = await speech_service.audio_to_text(audio_bytes)
        return JSONResponse({"transcribed_text": text}, status_code=200)

    except Exception as e:
        logger.error(f"Error converting audio to text: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/reaction")
async def create_reaction(
        request: Request,
        reaction: ReactionRequest,
        chat_service: ChatService = Depends(get_chat_service),
        user: User = Depends(get_current_user)
) -> JSONResponse:
    try:
        await chat_service.create_reaction(reaction.message_id, reaction.reaction, user.id)
    except Exception as e:
        logger.error(f"Error creating reaction: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"message": "Reaction updated"}, status_code=200)


@router.post("/comment")
async def create_comment(
        request: Request,
        comment: CommentRequest,
        chat_service: ChatService = Depends(get_chat_service),
        user: User = Depends(get_current_user)
) -> JSONResponse:
    try:
        await chat_service.create_comment(comment.message_id, comment.comment, user.id)
    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"message": "Comment created"}, status_code=200)