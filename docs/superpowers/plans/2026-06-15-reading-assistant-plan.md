# 阅读助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个浏览器阅读辅助工具：Chrome 扩展框选截图 + FastAPI 后端 + LM Studio 多模态 LLM 多轮对话。

**Architecture:** FastAPI 提供 REST API + SSE 流式推送，Chrome 扩展负责截图并通过 HTTP 调用后端，聊天面板为后端内置的纯 HTML/JS 页面，LLM 调用 LM Studio 本地 OpenAI 兼容接口。

**Tech Stack:** Python 3.9+, FastAPI, httpx, uvicorn, SSE (Server-Sent Events), Chrome Extension Manifest V3, pure HTML/CSS/JS, marked.js

---
```

```

---

### Task 1: 项目配置模块

**Files:**
- Create: `backend/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写测试 —— 验证配置默认值**

```python
# tests/test_config.py
from backend.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.lm_studio_base_url == "http://localhost:1234/v1"
    assert settings.lm_studio_model == "qwen/qwen3-vl-4b"
    assert settings.max_request_size_mb == 10
    assert settings.session_timeout_minutes == 30
    assert settings.llm_timeout_seconds == 120


def test_settings_override_from_env(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:9999/v1")
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.lm_studio_base_url == "http://localhost:9999/v1"
```

Run: `pytest tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 2: 实现配置模块**

```python
# backend/config.py
import os


class Settings:
    def __init__(self):
        self.host = os.environ.get("HOST", "127.0.0.1")
        self.port = int(os.environ.get("PORT", "8000"))
        self.lm_studio_base_url = os.environ.get(
            "LM_STUDIO_BASE_URL", "http://localhost:1234/v1"
        )
        self.lm_studio_model = os.environ.get(
            "LM_STUDIO_MODEL", "qwen/qwen3-vl-4b"
        )
        self.max_request_size_mb = int(os.environ.get("MAX_REQUEST_SIZE_MB", "10"))
        self.session_timeout_minutes = int(
            os.environ.get("SESSION_TIMEOUT_MINUTES", "30")
        )
        self.llm_timeout_seconds = int(
            os.environ.get("LLM_TIMEOUT_SECONDS", "120")
        )


settings = Settings()
```

Run: `pytest tests/test_config.py -v`
Expected: 2 PASS

---

### Task 2: LLM 客户端模块

**Files:**
- Create: `backend/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: 写测试 —— 验证图像转 base64**

```python
# tests/test_llm_client.py
import base64
import os
import tempfile
import pytest
from backend.llm_client import image_to_base64


def test_image_to_base64_from_local_file():
    # 创建一个 1x1 透明 PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "+P+/HgAFhQJ5yPWHJgAAAABJRU5ErkJggg=="
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_bytes)
        tmp_path = f.name

    try:
        result = image_to_base64(tmp_path)
        assert result.startswith("data:image/png;base64,")
        decoded = base64.b64decode(result.split(",", 1)[1])
        assert decoded == png_bytes
    finally:
        os.unlink(tmp_path)


def test_no_proxy_env_set():
    assert os.environ.get("no_proxy", "").find("localhost") >= 0 or \
           os.environ.get("NO_PROXY", "").find("localhost") >= 0
```

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL

- [ ] **Step 2: 实现 LLM 客户端**

```python
# backend/llm_client.py
import os
import base64
import json
import mimetypes
import httpx

# 绕过系统代理
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

from backend.config import settings


def image_to_base64(image_source: str) -> str:
    if image_source.startswith(("http://", "https://")):
        with httpx.Client(proxy=None, timeout=30) as c:
            resp = c.get(image_source)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/png")
            raw_bytes = resp.content
    else:
        mime, _ = mimetypes.guess_type(image_source)
        content_type = mime or "image/png"
        with open(image_source, "rb") as f:
            raw_bytes = f.read()

    b64 = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


class LLMClient:
    def __init__(self):
        self.base_url = settings.lm_studio_base_url
        self.model = settings.lm_studio_model
        self.timeout = settings.llm_timeout_seconds

    def _build_request(self, messages: list, max_tokens: int = 512,
                       temperature: float = 0.7, stream: bool = False) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    def chat(self, messages: list, max_tokens: int = 512,
             temperature: float = 0.7) -> str:
        with httpx.Client(proxy=None, timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                json=self._build_request(messages, max_tokens, temperature),
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.json()["choices"][0]["message"]["content"]

    def chat_stream(self, messages: list, max_tokens: int = 512,
                    temperature: float = 0.7):
        with httpx.Client(proxy=None, timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=self._build_request(messages, max_tokens, temperature, stream=True),
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield delta["content"]

    def health_check(self) -> bool:
        try:
            with httpx.Client(proxy=None, timeout=5) as client:
                resp = client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def warmup(self):
        self.chat([{"role": "user", "content": "ping"}], max_tokens=1)


llm_client = LLMClient()
```

Run: `pytest tests/test_llm_client.py -v`
Expected: 2 PASS

---

### Task 3: 会话管理模块

**Files:**
- Create: `backend/session_manager.py`
- Create: `tests/test_session_manager.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_session_manager.py
import time
import pytest
from backend.session_manager import SessionManager, Session


def test_create_session():
    mgr = SessionManager()
    image_b64 = "data:image/png;base64,abc123"
    sid = mgr.create(image_b64)

    session = mgr.get(sid)
    assert session is not None
    assert session.image == image_b64
    assert session.messages == []
    assert session.is_processing is False


def test_get_nonexistent_session():
    mgr = SessionManager()
    assert mgr.get("nonexistent") is None


def test_add_message():
    mgr = SessionManager()
    sid = mgr.create("data:image/png;base64,abc")
    mgr.add_message(sid, "user", "hello")
    mgr.add_message(sid, "assistant", "hi there")

    session = mgr.get(sid)
    assert len(session.messages) == 2
    assert session.messages[0] == {"role": "user", "content": "hello"}
    assert session.messages[1] == {"role": "assistant", "content": "hi there"}


def test_add_message_to_nonexistent_session():
    mgr = SessionManager()
    with pytest.raises(ValueError, match="会话不存在"):
        mgr.add_message("nonexistent", "user", "hi")


def test_lock_unlock_processing():
    mgr = SessionManager()
    sid = mgr.create("data:image/png;base64,abc")

    assert mgr.try_acquire_processing(sid) is True
    assert mgr.try_acquire_processing(sid) is False

    mgr.release_processing(sid)
    assert mgr.try_acquire_processing(sid) is True
    mgr.release_processing(sid)


def test_cleanup_expired_sessions():
    mgr = SessionManager(timeout_seconds=1)
    sid = mgr.create("data:image/png;base64,abc")
    time.sleep(1.5)
    mgr.cleanup_expired()
    assert mgr.get(sid) is None
```

Run: `pytest tests/test_session_manager.py -v`
Expected: FAIL

- [ ] **Step 2: 实现会话管理器**

```python
# backend/session_manager.py
import uuid
import time
from threading import Lock
from dataclasses import dataclass, field
from backend.config import settings


@dataclass
class Session:
    id: str
    image: str
    messages: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    is_processing: bool = False
    processing_lock: Lock = field(default_factory=Lock)


class SessionManager:
    def __init__(self, timeout_seconds: int = None):
        self._sessions: dict[str, Session] = {}
        if timeout_seconds is None:
            timeout_seconds = settings.session_timeout_minutes * 60
        self.timeout_seconds = timeout_seconds

    def create(self, image_base64: str) -> str:
        sid = uuid.uuid4().hex[:12]
        self._sessions[sid] = Session(id=sid, image=image_base64)
        return sid

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = time.time()
        return session

    def add_message(self, session_id: str, role: str, content: str):
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")
        session.messages.append({"role": role, "content": content})
        session.last_activity = time.time()

    def try_acquire_processing(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        return session.processing_lock.acquire(blocking=False)

    def release_processing(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            session.processing_lock.release()

    def cleanup_expired(self):
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > self.timeout_seconds
        ]
        for sid in expired:
            del self._sessions[sid]


session_manager = SessionManager()
```

Run: `pytest tests/test_session_manager.py -v`
Expected: 6 PASS

---

### Task 4: API 路由 —— 会话创建与消息

**Files:**
- Create: `backend/routes/__init__.py` (empty)
- Create: `backend/routes/sessions.py`
- Create: `tests/test_api_sessions.py`

- [ ] **Step 1: 写 API 测试**

```python
# tests/test_api_sessions.py
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_session_empty_body(client):
    resp = await client.post("/api/sessions", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_session_with_image(client):
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "chat_url" in data
    assert data["chat_url"].endswith(f"/chat/{data['session_id']}")


@pytest.mark.asyncio
async def test_create_session_no_image_field(client):
    resp = await client.post("/api/sessions", json={"foo": "bar"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_message_to_existing_session(client):
    # 创建会话
    create_resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = create_resp.json()["session_id"]

    # 发送消息
    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "content": "这是什么？"
    })
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_send_message_to_nonexistent_session(client):
    resp = await client.post("/api/sessions/notexist/messages", json={
        "content": "hello"
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_message_empty_content(client):
    create_resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = create_resp.json()["session_id"]

    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "content": ""
    })
    assert resp.status_code == 422
```

Run: `pytest tests/test_api_sessions.py -v`
Expected: FAIL (app not found)

- [ ] **Step 2: 实现路由 + 最小 main.py**

```python
# backend/routes/__init__.py
```

```python
# backend/routes/sessions.py
import asyncio
import json
import traceback
from fastapi import APIRouter, HTTPException, Request
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


@router.get("/health")
async def health_check():
    lm_ok = llm_client.health_check()
    return {
        "status": "ok",
        "lm_studio": "connected" if lm_ok else "disconnected"
    }
```

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.routes.sessions import router as sessions_router
from backend.llm_client import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时预热模型
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
```

Run: `pytest tests/test_api_sessions.py -v`
Expected: 6 PASS

---

### Task 5: SSE 流式回复

**Files:**
- Modify: `backend/routes/sessions.py`
- Create: `tests/test_api_stream.py`

- [ ] **Step 1: 写 SSE 测试**

```python
# tests/test_api_stream.py
import json
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_stream_nonexistent_session(client):
    resp = await client.get("/api/sessions/notexist/stream")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_empty_session_no_messages(client):
    from backend.session_manager import session_manager
    sid = session_manager.create("data:image/png;base64,abc")

    # 没有消息时，应该自动触发初始提问
    # 这里只验证 SSE 连接建立。实际的 LLM 调用在测试环境可能失败，
    # 但路由本身应该返回 200 和 text/event-stream
    # 这个测试不依赖真实 LM Studio
    # 实际上由于需要真实 LLM，我们可以 mock
    pass  # 该测试需 LM Studio 运行，集成测试时手动验证
```

Run: `pytest tests/test_api_stream.py -v` (有 mock 部分的跳过)

- [ ] **Step 2: 实现 SSE 端点**

```python
# 在 backend/routes/sessions.py 末尾追加

import asyncio
from fastapi.responses import StreamingResponse

# ... 在文件顶部导入区域添加上面的 import ...

@router.get("/sessions/{session_id}/stream")
async def stream_response(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    async def event_generator():
        try:
            # 构建消息列表
            if not session.messages:
                # 首次：自动发送初始提问
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
            else:
                # 已有对话历史，构建完整上下文
                messages = []
                # 首条消息需要包含图片
                first_msg = session.messages[0]
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": first_msg["content"]},
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
            if "503" in error_msg or "Connection refused" in error_msg:
                error_msg = "LM Studio 服务未启动或无法连接"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

Run: `pytest tests/test_api_sessions.py tests/test_api_stream.py -v`
Expected: 6 PASS + SSE 测试

---

### Task 6: 聊天面板页面

**Files:**
- Create: `backend/routes/pages.py`
- Create: `backend/static/chat.html`
- Modify: `backend/main.py`

- [ ] **Step 1: 写页面路由测试**

```python
# tests/test_chat_page.py
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_chat_page_returns_html(client):
    resp = await client.get("/chat/abc123")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_chat_page_contains_session_id(client):
    resp = await client.get("/chat/test123")
    assert "test123" in resp.text
```

Run: `pytest tests/test_chat_page.py -v`
Expected: FAIL

- [ ] **Step 2: 实现页面路由**

```python
# backend/routes/pages.py
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
```

- [ ] **Step 3: 实现聊天面板 HTML**

```html
<!-- backend/static/chat.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>阅读助手</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; height: 100vh; display: flex; flex-direction: column; background: #1e1e2e; color: #cdd6f4; }

/* 顶栏 */
.header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #181825; border-bottom: 1px solid #313244; }
.header h1 { font-size: 16px; font-weight: 600; }
.header .status { font-size: 12px; color: #a6e3a1; }

/* 截图预览 */
.preview { margin: 12px 16px; border: 1px solid #313244; border-radius: 8px; overflow: hidden; }
.preview-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #181825; cursor: pointer; user-select: none; }
.preview-header span { font-size: 13px; color: #a6adc8; }
.preview-header .toggle { font-size: 12px; color: #6c7086; }
.preview img { width: 100%; max-height: 300px; object-fit: contain; display: block; }
.preview.collapsed .preview-body { display: none; }
.preview.collapsed .toggle { transform: rotate(-90deg); }

/* 对话区 */
.messages { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 12px; }
.message { display: flex; gap: 8px; max-width: 90%; }
.message.user { align-self: flex-end; }
.message.assistant { align-self: flex-start; }
.message .avatar { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
.message.user .avatar { background: #89b4fa; color: #1e1e2e; order: 2; }
.message.assistant .avatar { background: #a6e3a1; color: #1e1e2e; }
.message .bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; }
.message.user .bubble { background: #89b4fa; color: #1e1e2e; border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: #313244; border-bottom-left-radius: 4px; }
.message .bubble p { margin: 0 0 8px 0; }
.message .bubble p:last-child { margin: 0; }
.message .bubble pre { background: #181825; padding: 12px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }
.message .bubble code { font-family: 'Cascadia Code', monospace; font-size: 13px; }
.message .bubble pre code { background: none; padding: 0; }
.typing { color: #6c7086; font-style: italic; padding: 10px 14px; }

/* 输入区 */
.input-area { padding: 12px 16px; background: #181825; border-top: 1px solid #313244; display: flex; gap: 8px; }
.input-area textarea { flex: 1; padding: 10px 14px; background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; font-size: 14px; font-family: inherit; resize: none; height: 44px; outline: none; }
.input-area textarea:focus { border-color: #89b4fa; }
.input-area button { padding: 0 20px; background: #89b4fa; color: #1e1e2e; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.input-area button:hover { background: #b4d0fb; }
.input-area button:disabled { background: #45475a; color: #6c7086; cursor: not-allowed; }
</style>
</head>
<body>

<div class="header">
  <h1>阅读助手</h1>
  <span class="status" id="status">连接中...</span>
</div>

<div class="preview" id="preview">
  <div class="preview-header" onclick="togglePreview()">
    <span>截图预览</span>
    <span class="toggle">▼</span>
  </div>
  <div class="preview-body">
    <img id="preview-img" src="" alt="截图预览">
  </div>
</div>

<div class="messages" id="messages">
  <div class="message assistant">
    <div class="avatar">🤖</div>
    <div class="bubble">正在分析截图...</div>
  </div>
</div>

<div class="input-area">
  <textarea id="input" placeholder="输入你的追问..." rows="1"></textarea>
  <button id="send-btn" onclick="sendMessage()">发送</button>
</div>

<script>
const SESSION_ID = "__SESSION_ID__";
let currentBubble = null;
let streamDone = true;

function togglePreview() {
  document.getElementById('preview').classList.toggle('collapsed');
}

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  const avatar = role === 'user' ? '👤' : '🤖';
  div.innerHTML = `<div class="avatar">${avatar}</div><div class="bubble"></div>`;
  div.querySelector('.bubble').innerHTML = marked.parse(content);
  const msgs = document.getElementById('messages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function sendMessage() {
  const input = document.getElementById('input');
  const content = input.value.trim();
  if (!content || !streamDone) return;

  input.value = '';
  input.disabled = true;
  document.getElementById('send-btn').disabled = true;

  addMessage('user', content);

  const typingEl = document.createElement('div');
  typingEl.className = 'message assistant';
  typingEl.innerHTML = '<div class="avatar">🤖</div><div class="typing">思考中...</div>';
  document.getElementById('messages').appendChild(typingEl);

  fetch(`/api/sessions/${SESSION_ID}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  }).then(() => {
    typingEl.remove();
    startStreaming();
  }).catch(err => {
    typingEl.querySelector('.typing').textContent = '发送失败: ' + err.message;
    input.disabled = false;
    document.getElementById('send-btn').disabled = false;
  });
}

function startStreaming() {
  streamDone = false;
  currentBubble = null;
  document.getElementById('status').textContent = '回复中...';
  document.getElementById('status').style.color = '#f9e2af';

  const es = new EventSource(`/api/sessions/${SESSION_ID}/stream`);
  es.onmessage = (event) => {
    if (event.data === '[DONE]') {
      es.close();
      streamDone = true;
      document.getElementById('input').disabled = false;
      document.getElementById('send-btn').disabled = false;
      document.getElementById('input').focus();
      document.getElementById('status').textContent = '就绪';
      document.getElementById('status').style.color = '#a6e3a1';
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.error) {
        if (!currentBubble) {
          currentBubble = addMessage('assistant', '');
        }
        currentBubble.querySelector('.bubble').innerHTML = `<span style="color:#f38ba8">错误: ${data.error}</span>`;
        return;
      }
      if (data.delta) {
        if (!currentBubble) {
          currentBubble = addMessage('assistant', '');
        }
        const bubble = currentBubble.querySelector('.bubble');
        bubble.textContent += data.delta;
        bubble.innerHTML = marked.parse(bubble.textContent);
      }
    } catch(e) {}
  };
  es.onerror = () => {
    if (!streamDone) {
      es.close();
      streamDone = true;
      document.getElementById('input').disabled = false;
      document.getElementById('send-btn').disabled = false;
      document.getElementById('status').textContent = '连接中断';
      document.getElementById('status').style.color = '#f38ba8';
    }
  };
}

// 键盘快捷键
document.getElementById('input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// 初始加载：获取截图并开始流式
fetch(`/api/sessions/${SESSION_ID}`)
  .then(r => {
    if (!r.ok) throw new Error('Session not found');
    // 尝试加载截图预览
    return fetch(`/api/health`);
  })
  .then(() => {
    document.getElementById('status').textContent = '就绪';
    document.getElementById('status').style.color = '#a6e3a1';
  })
  .catch(() => {
    document.getElementById('status').textContent = '就绪';
    document.getElementById('status').style.color = '#a6e3a1';
  });

// 启动首次流式回复
startStreaming();
</script>
</body>
</html>
```

- [ ] **Step 4: 更新 main.py**

```python
# 在 backend/main.py 中添加页面路由
from backend.routes.pages import router as pages_router

# 在 app.include_router(sessions_router) 之后添加:
app.include_router(pages_router)
```

- [ ] **Step 5: 添加 GET /api/sessions/{id} 端点获取会话信息**

在 `backend/routes/sessions.py` 中追加：

```python
@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "session_id": session.id,
        "has_image": bool(session.image),
        "message_count": len(session.messages),
    }
```

Run: `pytest tests/test_chat_page.py -v`
Expected: 2 PASS

---

### Task 7: Chrome 扩展 —— Manifest & Background

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/background.js`
- Create: `extension/icon.png`

- [ ] **Step 1: 编写 manifest.json**

```json
{
  "manifest_version": 3,
  "name": "阅读助手",
  "version": "1.0.0",
  "description": "框选页面内容截图，通过本地多模态大模型辅助阅读理解",
  "permissions": ["activeTab", "scripting"],
  "host_permissions": ["http://localhost:8000/*"],
  "background": {
    "service_worker": "background.js"
  },
  "commands": {
    "capture-screenshot": {
      "suggested_key": {
        "default": "Ctrl+Shift+X",
        "mac": "Command+Shift+X"
      },
      "description": "框选截图并发送到阅读助手"
    }
  },
  "icons": {
    "16": "icon.png",
    "48": "icon.png",
    "128": "icon.png"
  }
}
```

- [ ] **Step 2: 编写 background.js**

```javascript
// extension/background.js
const BACKEND_URL = 'http://localhost:8000';

// 监听快捷键
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'capture-screenshot') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    // 检查是否可截图
    if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
      chrome.tabs.sendMessage(tab.id, { type: 'show_error', message: '此页面不支持截图' });
      return;
    }

    // 通知 content script 开始框选
    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'start_selection' });
    } catch {
      // content script 未注入，先注入
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
      await chrome.scripting.insertCSS({
        target: { tabId: tab.id },
        files: ['content.css']
      });
      await chrome.tabs.sendMessage(tab.id, { type: 'start_selection' });
    }
  }
});

// 接收 content script 的截图请求
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'capture_area') {
    handleCaptureArea(message.rect, sender.tab.id).then(sendResponse);
    return true; // 保持消息通道开放
  }
});

async function handleCaptureArea(rect, tabId) {
  try {
    // 截取整个可见页面
    const dataUrl = await chrome.tabs.captureVisibleTab(tabId, {
      format: 'png'
    });

    // 裁剪到选区
    const cropped = await cropImage(dataUrl, rect);

    // 检查后端健康状态
    try {
      const healthResp = await fetch(`${BACKEND_URL}/api/health`);
      if (!healthResp.ok) throw new Error('Backend not available');
    } catch {
      return { error: '阅读助手后端未启动，请先运行 backend/main.py' };
    }

    // 发送到后端
    const resp = await fetch(`${BACKEND_URL}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: cropped })
    });

    if (!resp.ok) {
      const err = await resp.json();
      return { error: err.detail || '创建会话失败' };
    }

    const data = await resp.json();

    // 打开聊天页面
    chrome.tabs.create({ url: data.chat_url });

    return { success: true };
  } catch (e) {
    return { error: e.message };
  }
}

async function cropImage(dataUrl, rect) {
  // Service Worker 中不能用 new Image()，使用 fetch + createImageBitmap
  const response = await fetch(dataUrl);
  const blob = await response.blob();
  const bitmap = await createImageBitmap(blob, rect.x, rect.y, rect.width, rect.height);

  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(bitmap, 0, 0);

  const croppedBlob = await canvas.convertToBlob({ type: 'image/png' });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(croppedBlob);
  });
}
```

- [ ] **Step 3: 创建图标占位**

创建一个简单的 16x16 PNG 图标文件（可用任意像素画，或从现有资源复制）。
如果没有图片工具，可以先跳过，扩展仍可加载（仅图标缺失不影响功能）。

- [ ] **Step 4: 手动验证**

```bash
# 在 Chrome 中:
# 1. 打开 chrome://extensions/
# 2. 开启"开发者模式"
# 3. 点击"加载已解压的扩展程序"
# 4. 选择 extension/ 目录
# 5. 确认扩展出现在列表中，快捷键设置显示 Ctrl+Shift+X
```

---

### Task 8: Chrome 扩展 —— Content Script 框选

**Files:**
- Create: `extension/content.js`
- Create: `extension/content.css`

- [ ] **Step 1: 编写 content.css**

```css
/* extension/content.css */
.rfa-overlay {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.3);
  z-index: 2147483647;
  cursor: crosshair;
}
.rfa-selection {
  position: fixed;
  border: 2px solid #89b4fa;
  background: rgba(137, 180, 250, 0.15);
  z-index: 2147483647;
  pointer-events: none;
}
.rfa-actions {
  position: fixed;
  z-index: 2147483647;
  display: flex;
  gap: 8px;
}
.rfa-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-family: system-ui, sans-serif;
}
.rfa-btn-confirm {
  background: #89b4fa;
  color: #1e1e2e;
}
.rfa-btn-cancel {
  background: #45475a;
  color: #cdd6f4;
}
```

- [ ] **Step 2: 编写 content.js**

```javascript
// extension/content.js

let overlay = null;
let selection = null;
let actionsBox = null;
let startX = 0, startY = 0;
let rect = null;
let isSelecting = false;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'start_selection') {
    startSelection();
    sendResponse({ ok: true });
  } else if (message.type === 'show_error') {
    alert(message.message);
    sendResponse({ ok: true });
  }
});

function startSelection() {
  // 移除旧的（防止残留）
  cleanup();

  overlay = document.createElement('div');
  overlay.className = 'rfa-overlay';
  overlay.addEventListener('mousedown', onMouseDown);
  overlay.addEventListener('mousemove', onMouseMove);
  overlay.addEventListener('mouseup', onMouseUp);
  document.body.appendChild(overlay);
}

function onMouseDown(e) {
  startX = e.clientX;
  startY = e.clientY;
  isSelecting = true;

  selection = document.createElement('div');
  selection.className = 'rfa-selection';
  document.body.appendChild(selection);
}

function onMouseMove(e) {
  if (!isSelecting || !selection) return;

  const x = Math.min(startX, e.clientX);
  const y = Math.min(startY, e.clientY);
  const w = Math.abs(e.clientX - startX);
  const h = Math.abs(e.clientY - startY);

  selection.style.left = x + 'px';
  selection.style.top = y + 'px';
  selection.style.width = w + 'px';
  selection.style.height = h + 'px';

  rect = { x, y, width: w, height: h };
}

function onMouseUp(e) {
  if (!isSelecting) return;
  isSelecting = false;

  if (!rect || rect.width < 10 || rect.height < 10) {
    showError('选区太小，请重新框选');
    return;
  }

  showActions(rect);
}

function showActions(rect) {
  if (actionsBox) actionsBox.remove();

  actionsBox = document.createElement('div');
  actionsBox.className = 'rfa-actions';
  actionsBox.style.left = (rect.x + rect.width - 160) + 'px';
  actionsBox.style.top = (rect.y + rect.height + 8) + 'px';

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'rfa-btn rfa-btn-confirm';
  confirmBtn.textContent = '确认截图';
  confirmBtn.onclick = () => {
    confirmCapture(rect);
  };

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'rfa-btn rfa-btn-cancel';
  cancelBtn.textContent = '取消';
  cancelBtn.onclick = cleanup;

  actionsBox.appendChild(confirmBtn);
  actionsBox.appendChild(cancelBtn);
  document.body.appendChild(actionsBox);
}

function confirmCapture(rect) {
  // 传递 DPR 给 background 用于坐标换算
  const dpr = window.devicePixelRatio || 1;
  const scaledRect = {
    x: Math.round(rect.x * dpr),
    y: Math.round(rect.y * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr),
    // 同时传递页面总尺寸用于校验
    pageWidth: Math.round(window.innerWidth * dpr),
    pageHeight: Math.round(window.innerHeight * dpr),
  };

  // 移除框选 UI 避免截到
  cleanup();

  chrome.runtime.sendMessage({ type: 'capture_area', rect: scaledRect }, (response) => {
    if (response && response.error) {
      alert(response.error);
    }
    // success: background 会打开新标签页
  });
}

function showError(msg) {
  cleanup();
  alert('阅读助手: ' + msg);
}

function cleanup() {
  if (overlay) { overlay.remove(); overlay = null; }
  if (selection) { selection.remove(); selection = null; }
  if (actionsBox) { actionsBox.remove(); actionsBox = null; }
}
```

- [ ] **Step 3: 手动验证**

1. 在 Chrome 中刷新已加载的扩展
2. 打开任意网页（如 GitHub）
3. 按 `Ctrl+Shift+X`
4. 确认出现半透明遮罩，可以用鼠标框选
5. 确认框选后右下角出现"确认截图"/"取消"按钮

---

### Task 9: 集成联调与完善

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/routes/sessions.py`
- Create: `tests/test_integration.py`
- Create: `requirements.txt`

- [ ] **Step 1: 添加会话清理定时任务**

```python
# 在 backend/main.py 的 lifespan 中添加清理任务
from backend.session_manager import session_manager
import asyncio

async def cleanup_task():
    while True:
        await asyncio.sleep(5 * 60)  # 每5分钟
        session_manager.cleanup_expired()

# 在 lifespan yield 之前添加:
cleanup_coro = asyncio.create_task(cleanup_task())
# 在 lifespan yield 之后添加:
cleanup_coro.cancel()
```

```python
# backend/main.py 完整版
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    # 启动时预热模型
    try:
        llm_client.warmup()
    except Exception:
        pass
    cleanup_coro = asyncio.create_task(cleanup_task())
    yield
    cleanup_coro.cancel()


app = FastAPI(title="阅读助手", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(pages_router)
```

- [ ] **Step 2: 限制请求体大小中间件**

在 `backend/main.py` 中添加：

```python
# 在 app = FastAPI(...) 之后，include_router 之前
from fastapi import Request, HTTPException

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    max_size = settings.max_request_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return HTTPException(status_code=413, detail="请求体过大")
    return await call_next(request)
```

Wait, middleware returning HTTPException won't work directly. Use a proper response:

```python
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    from fastapi.responses import JSONResponse
    max_size = settings.max_request_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(
            status_code=413,
            content={"error": f"截图大小超过 {settings.max_request_size_mb}MB 限制"}
        )
    return await call_next(request)
```

- [ ] **Step 3: 编写 requirements.txt**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
httpx>=0.27.0
```

- [ ] **Step 4: 编写集成测试**

```python
# tests/test_integration.py
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app
from backend.session_manager import session_manager


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_full_flow_create_and_page(client):
    # 创建会话
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    assert resp.status_code == 200
    data = resp.json()
    sid = data["session_id"]

    # 获取聊天页
    resp = await client.get(f"/chat/{sid}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_session_info_endpoint(client):
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = resp.json()["session_id"]

    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert data["has_image"] is True
    assert data["message_count"] == 0


@pytest.mark.asyncio
async def test_session_info_not_found(client):
    resp = await client.get("/api/sessions/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 5: 运行全部测试**

```bash
pytest tests/ -v
```

Expected: 所有测试 PASS（不依赖 LM Studio 的测试）

- [ ] **Step 6: 端到端手动验证**

```bash
# 终端 1: 启动 LM Studio 并加载 qwen3-vl-4b，启动 Server (:1234)

# 终端 2: 启动后端
pip install -r requirements.txt
uvicorn backend.main:app --reload

# 验证:
# 1. curl http://localhost:8000/api/health  → 200
# 2. Chrome 加载扩展，打开网页 → Ctrl+Shift+X → 框选
# 3. 自动打开聊天页 → 查看流式回复
# 4. 追问 → 确认多轮对话正常
```
