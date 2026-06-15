from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.routes.sessions import router as sessions_router
from backend.routes.pages import router as pages_router
from backend.llm_client import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        llm_client.warmup()
    except Exception:
        pass
    yield


app = FastAPI(title="阅读助手", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(pages_router)
