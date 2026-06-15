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
