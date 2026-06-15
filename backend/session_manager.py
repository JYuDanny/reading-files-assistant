import uuid
import time
from threading import Lock
from dataclasses import dataclass, field
from typing import Optional

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

    def get(self, session_id: str) -> Optional[Session]:
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
