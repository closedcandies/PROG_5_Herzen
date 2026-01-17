from pydantic import BaseModel, Field
from typing import Optional, Annotated, List, Literal
from fastapi import Path


class LoginRequest(BaseModel):
    email: str
    password: str


class Chat(BaseModel):
    chat_id: int
    model_type: str
    subject: str
    title: str


class UserMessage(BaseModel):
    content: str
    role: str = "user"
    model_type: Optional[str] = None
    chat_id: Optional[int] = None
    subject: Optional[str] = None
    message_id: Optional[int] = None
    files: Optional[list[str]] = None


class AssistantMessage(BaseModel):
    content: str
    role: str = "assistant"
    chat_id: Optional[int] = None
    subject: Optional[str] = None
    message_id: Optional[int] = None
    reaction: Optional[Literal[1, 0, -1]] = None


class FilterResponse(BaseModel):
    allowed: bool
    reason: str


class NewChatRequest(BaseModel):
    subject: Annotated[str, Path(title="Название предмета. Используются те же названия, что и на кнопках в меню. Для размышляющей модели используется название 'Размышляющая'")]
    message: str


class NewChatResponse(BaseModel):
    chat_id: int
    subject: str
    title: str
    message: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class SetPromptRequest(BaseModel):
    subject: str
    prompt: str


class PromptOut(BaseModel):
    id: int
    subject: str
    prompt: str

    class Config:
        orm_mode = True


class PromptUpdate(BaseModel):
    prompt: str


class Feedback(BaseModel):
    name: str
    email: str
    message: str

class ReactionRequest(BaseModel):
    reaction: Literal[1, 0, -1] = Field(description="1 - like, -1 - dislike, 0 - no reaction")
    message_id: int


class CommentRequest(BaseModel):
    comment: str
    message_id: int


class PaymentRequest(BaseModel):
    subscription_level: Literal["start", "premium", "mentor+"] = Field(description="CAN BE ONE OF: start, premium, mentor+")


class PaymentLink(BaseModel):
    status: int
    url: str


class PaymentRequest(BaseModel):
    subscription_level: Literal["start", "premium", "mentor+"] = Field(description="CAN BE ONE OF: start, premium, mentor+")


class PaymentLink(BaseModel):
    status: int
    url: str


class QuizAnswers(BaseModel):
    question1: str
    question2: str
    question3: str