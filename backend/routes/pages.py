from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter()

STATIC_DIR = Path(__file__).parent.parent / "static"


@router.get("/chat/{session_id}", response_class=HTMLResponse)
async def chat_page(session_id: str):
    html_path = STATIC_DIR / "chat.html"
    content = html_path.read_text(encoding="utf-8")
    content = content.replace("__SESSION_ID__", session_id)
    return HTMLResponse(content=content)
