import os
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from utils.logger import get_logger
from routes.chat import router as chat_router
from routes.auth import router as auth_router
from routes.prompts import router as prompts_router
from routes.feedback import router as feedback_router
from routes.quiz import router as quiz_router
from routes.payment import payment_router
from depends.auth import get_current_user
from db.models import User
from utils.clients import mailing_client


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App initialized")
    await mailing_client.setup()
    yield
    logger.info("App shutdown")

app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)
api_router = APIRouter(prefix="/api")
api_router.include_router(chat_router)
api_router.include_router(auth_router)
api_router.include_router(prompts_router)
api_router.include_router(feedback_router)
api_router.include_router(quiz_router)
api_router.include_router(payment_router)
app.include_router(api_router)

app.mount("/static", StaticFiles(directory="../static"), name="static")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

templates = Jinja2Templates(directory="templates")


# CORS настройки для production
# В production разрешаем только доверенные домены
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://mentor-dev.ru,https://www.mentor-dev.ru"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


@app.get("/", response_class=HTMLResponse)
async def homePage(request: Request):
    logger.info("Home page requested")
    return templates.TemplateResponse("mobile-app.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def loginPage(request: Request):
    logger.info("Login page requested")
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def registerPage(request: Request):
    logger.info("Register page requested")
    return templates.TemplateResponse("registration.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chatPage(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("chat.html", {"request": request})



'''@app.exception_handler(HTTPException)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})'''


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True
    )
