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
