import traceback

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.config import settings
from backend.routes.sessions import router as sessions_router
from backend.routes.pages import router as pages_router
from backend.llm_client import llm_client
from backend.session_manager import session_manager


async def cleanup_task():
    while True:
        await asyncio.sleep(5 * 60)
        session_manager.cleanup_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await llm_client.detect_model()
        await llm_client.warmup()
    except Exception as e:
        print(f"[启动] 模型初始化失败: {e}")
    cleanup_coro = asyncio.create_task(cleanup_task())
    yield
    cleanup_coro.cancel()


app = FastAPI(title="阅读助手", lifespan=lifespan)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    max_size = settings.max_request_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(
            status_code=413,
            content={"error": f"截图大小超过 {settings.max_request_size_mb}MB 限制"}
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(pages_router)
