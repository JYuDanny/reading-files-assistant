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
    assert settings.llm_max_tokens == -1


def test_settings_override_from_env(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:9999/v1")
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.lm_studio_base_url == "http://localhost:9999/v1"


def test_settings_singleton():
    import backend.config
    from backend.config import settings, Settings
    assert isinstance(settings, Settings)
    import backend.config as bc2
    assert bc2.settings is settings
