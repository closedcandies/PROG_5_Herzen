import os
import redis
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from utils.clients.redis_client import get_redis
from utils.logger import get_logger
from utils.clients.mailing import mailing_client
from routes.schemas import LoginRequest, RegisterRequest, VerifyEmailRequest
from db.models import User
from db.repositories import UserRepository, QuizRepository
from settings import settings
from depends.database import get_user_repository, get_quiz_repository
from depends.auth import get_current_user
from depends.email_verification import get_email_verification_service
from depends.services import get_payment_service
from services.payment import PaymentService
from security import create_access_token, hash_password, verify_password
from utils.rate_limiter import auth_login_limiter, auth_register_limiter, per_hour_limiter, jwt_per_hour_limiter

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

logger = get_logger(__name__)
templates = Jinja2Templates(directory="templates")


@router.post("/login")
async def login(request: Request,
                login_request: LoginRequest,
                user_repository: UserRepository = Depends(get_user_repository),
                quiz_repository: QuizRepository = Depends(get_quiz_repository),
                #rate_limit: None = Depends(auth_login_limiter)
                ):
    logger.info("Login request received")
    user = await user_repository.get_by_login(login_request.email)
    if user is None or not verify_password(login_request.password, user.password):
        logger.warning(f"Incorrect email or password: {login_request.email}")
        return JSONResponse({"error": "Incorrect email or password"}, status_code=401)
    else:
        logger.info(f"User logged in: {user.id}")
        access_token = create_access_token(data={"sub": str(user.id)})

        user_passed_quiz = await quiz_repository.get_user_quiz_answers(user.id)
        response_data = {
            "success": True,
            "redirect_url": "/chat" if user_passed_quiz else "/quiz",
            "message": "Login successful",
        }
        
        response = JSONResponse(content=response_data, status_code=200)
        # Определяем secure флаг на основе окружения
        is_production = os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production"
        response.set_cookie(
            key="access_token_cookie",
            value=access_token,
            httponly=settings.jwt.http_only,
            secure=is_production,  # True в production, False в development
            samesite=settings.jwt.samesite,
            max_age=settings.jwt.token_lifetime
        )
        return response


@router.post("/register/send-code")
async def send_register_code(
    register_request: RegisterRequest,
    user_repository: UserRepository = Depends(get_user_repository),
    verification_service=Depends(get_email_verification_service),
    #rate_limit: None = Depends(auth_register_limiter),
):
    email = register_request.email.lower()
    logger.info(f"Register send-code requested for {email}")

    if await user_repository.get_by_login(email):
        logger.warning(f"User {email} already exists")
        return JSONResponse({"error": "User already exists"}, status_code=400)

    hashed_password = hash_password(register_request.password)
    await verification_service.send_code(email, hashed_password, register_request.name, mailing_client)

    return JSONResponse({"message": "Код отправлен на почту"}, status_code=200)


@router.post("/register/verify")
async def verify_register_code(
    verify_request: VerifyEmailRequest,
    user_repository: UserRepository = Depends(get_user_repository),
    verification_service=Depends(get_email_verification_service),
):
    email = verify_request.email.lower()
    logger.info(f"Verify code for {email}")

    data = verification_service.get_payload(email)
    if not data:
        logger.warning(f"Verification not found or expired for {email}")
        return JSONResponse({"error": "Код не найден или истёк"}, status_code=400)

    attempts = verification_service.record_attempt(email)
    if attempts > settings.verification.max_attempts:
        verification_service.clear(email)
        logger.warning(f"Too many attempts for {email}")
        return JSONResponse({"error": "Превышено число попыток"}, status_code=429)

    if data["code"] != verify_request.code:
        logger.warning(f"Invalid code for {email}")
        return JSONResponse({"error": "Неверный код"}, status_code=400)

    if await user_repository.get_by_login(email):
        verification_service.clear(email)
        logger.warning(f"User {email} already exists during verify")
        return JSONResponse({"error": "User already exists"}, status_code=400)

    user = await user_repository.create(email, data["password"], data["name"])
    verification_service.clear(email)

    logger.info(f"Email verified and user created {email}")
    return JSONResponse({"success": True, "user_id": user.id}, status_code=201)


@router.post("/logout")
async def logout(request: Request,
                current_user: User = Depends(get_current_user)
                ):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token_cookie")
    return response


@router.get("/me")
async def authMe(user: User = Depends(get_current_user),
                payment_service: PaymentService = Depends(get_payment_service),
                 #rate_limit: None = Depends(jwt_per_hour_limiter)
                ) -> JSONResponse:
    subscription_level = await payment_service.get_subscription_status(user.id)
    return JSONResponse({"email": user.login, "name": user.name, "subscription": subscription_level}, status_code=200)

