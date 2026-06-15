import json
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend.session_manager import session_manager
from backend.llm_client import llm_client

router = APIRouter(prefix="/api")


class CreateSessionRequest(BaseModel):
    image: str = Field(..., min_length=1)


class CreateSessionResponse(BaseModel):
    session_id: str
    chat_url: str


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest, request: Request):
    if not llm_client.health_check():
        raise HTTPException(
            status_code=503,
            detail="LM Studio 服务未启动，请确认已加载 qwen3-vl-4b 模型"
        )
    sid = session_manager.create(req.image)
    host = request.headers.get("host", "localhost:8000")
    scheme = request.url.scheme
    chat_url = f"{scheme}://{host}/chat/{sid}"
    return CreateSessionResponse(session_id=sid, chat_url=chat_url)


@router.post("/sessions/{session_id}/messages", status_code=204)
async def send_message(session_id: str, req: SendMessageRequest):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    if not session_manager.try_acquire_processing(session_id):
        raise HTTPException(status_code=429, detail="请等待当前回复完成")

    try:
        session_manager.add_message(session_id, "user", req.content)
    finally:
        session_manager.release_processing(session_id)


@router.get("/sessions/{session_id}/stream")
async def stream_response(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    if not session_manager.try_acquire_processing(session_id):
        raise HTTPException(status_code=429, detail="请等待当前回复完成")

    async def event_generator():
        initial_prompt_sent = False
        try:
            if not session.messages:
                initial_prompt = "请详细描述这张截图的内容，帮助我理解。"
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": initial_prompt},
                            {"type": "image_url", "image_url": {"url": session.image}},
                        ]
                    }
                ]
                session_manager.add_message(session_id, "user", initial_prompt)
                initial_prompt_sent = True
            else:
                messages = []
                first_msg = session.messages[0]
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": first_msg.get("content", "")},
                        {"type": "image_url", "image_url": {"url": session.image}},
                    ]
                })
                for msg in session.messages[1:]:
                    messages.append(msg)

            full_content = ""
            for token in llm_client.chat_stream(messages):
                full_content += token
                yield f"data: {json.dumps({'delta': token})}\n\n"
                await asyncio.sleep(0)

            session_manager.add_message(session_id, "assistant", full_content)
            yield "data: [DONE]\n\n"

        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "ConnectError" in error_msg:
                error_msg = "LM Studio 服务未启动或无法连接"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            session_manager.release_processing(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/health")
async def health_check():
    lm_ok = llm_client.health_check()
    return {
        "status": "ok",
        "lm_studio": "connected" if lm_ok else "disconnected"
    }
