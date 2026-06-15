import base64
import os
import tempfile
import pytest
from backend.llm_client import image_to_base64


def test_image_to_base64_from_local_file():
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
    from backend.llm_client import LLMClient
    client = LLMClient()
    no_proxy = os.environ.get("no_proxy", "") + os.environ.get("NO_PROXY", "")
    assert "localhost" in no_proxy
    assert "127.0.0.1" in no_proxy
