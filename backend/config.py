import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError(f"Invalid integer for env var {name}: {os.environ[name]!r}") from None


class Settings:
    host: str
    port: int
    lm_studio_base_url: str
    lm_studio_model: str
    max_request_size_mb: int
    session_timeout_minutes: int
    llm_timeout_seconds: int

    def __init__(self) -> None:
        self.host = os.environ.get("HOST", "127.0.0.1")
        self.port = _int_env("PORT", 8000)
        self.lm_studio_base_url = os.environ.get(
            "LM_STUDIO_BASE_URL", "http://localhost:1234/v1"
        )
        self.lm_studio_model = os.environ.get(
            "LM_STUDIO_MODEL", "qwen/qwen3-vl-4b"
        )
        self.max_request_size_mb = _int_env("MAX_REQUEST_SIZE_MB", 10)
        self.session_timeout_minutes = _int_env("SESSION_TIMEOUT_MINUTES", 30)
        self.llm_timeout_seconds = _int_env("LLM_TIMEOUT_SECONDS", 120)


settings = Settings()
