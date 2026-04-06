# FastAPI Application
import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers import ai, favorite, news, users, history, upload
from config.db_config import async_engine
from utils.response import ApiResponse, ErrorResponse, ValidationErrorItem, success_response, error_response
from config.cache_config import redis_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await redis_client.close()
        await async_engine.dispose()


app = FastAPI(lifespan=lifespan)


def parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        # 本地默认允许常用开发地址。
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    if raw == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]

# --- 确保 static/uploads 目录存在 ---
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "uploads"), exist_ok=True)

# 挂载静态文件目录，使得可以通过 /static 访问图片等静态资源
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 添加这段配置，允许前端跨域请求 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法（GET, POST, PUT, DELETE等）
    allow_headers=["*"],
)

@app.get("/", response_model=ApiResponse[None])
async def root():
    return success_response(message="Hello World")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    data = None if isinstance(exc.detail, str) else exc.detail
    payload: ErrorResponse[Any] = error_response(exc.status_code, message, data)
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    errors = [ValidationErrorItem(**item) for item in exc.errors()]
    payload: ErrorResponse[list[ValidationErrorItem]] = error_response(422, "Validation Error", errors)
    return JSONResponse(
        status_code=422,
        content=payload.dict(),
    )


app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(upload.router)
app.include_router(ai.router)


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8080"))
    reload_enabled = os.getenv("APP_ENV", "development").lower() == "development"

    uvicorn.run("main:app", host=host, port=port, reload=reload_enabled)
