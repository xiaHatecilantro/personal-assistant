import pytest

from app.settings import DEFAULT_JWT_SECRET, get_settings


def test_production_rejects_default_jwt_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_settings()

    get_settings.cache_clear()


def test_settings_parse_comma_separated_allowlists(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://one.test, https://two.test")
    monkeypatch.setenv("LLM_ALLOWED_BASE_URLS", "https://api.one.test/v1")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.cors_origins == ("https://one.test", "https://two.test")
    assert settings.llm_allowed_base_urls == ("https://api.one.test/v1",)
    get_settings.cache_clear()


def test_production_normalizes_environment_and_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", " production ")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="32 characters"):
        get_settings()

    get_settings.cache_clear()


def test_settings_parse_agent_runtime_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv(
        "CHECKPOINT_DATABASE_URL",
        "postgresql://agent:secret@localhost:5432/agent_checkpoints",
    )
    monkeypatch.setenv("AGENT_MODEL_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("AGENT_MODEL_NAME", "deepseek-chat")
    monkeypatch.setenv("AGENT_MODEL_API_KEY", "agent-secret")
    monkeypatch.setenv("AGENT_MAX_STEPS", "12")
    monkeypatch.setenv("AGENT_RUN_TIMEOUT_SECONDS", "180")
    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.checkpoint_database_url == (
            "postgresql://agent:secret@localhost:5432/agent_checkpoints"
        )
        assert settings.agent_model_base_url == "https://api.deepseek.com/v1"
        assert settings.agent_model_name == "deepseek-chat"
        assert settings.agent_model_api_key == "agent-secret"
        assert settings.agent_max_steps == 12
        assert settings.agent_run_timeout_seconds == 180
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    [
        ("AGENT_MAX_STEPS", "0"),
        ("AGENT_RUN_TIMEOUT_SECONDS", "-1"),
    ],
)
def test_settings_reject_non_positive_agent_runtime_limits(
    monkeypatch,
    environment_name,
    invalid_value,
):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AGENT_MAX_STEPS", "10")
    monkeypatch.setenv("AGENT_RUN_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv(environment_name, invalid_value)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError, match=environment_name):
            get_settings()
    finally:
        get_settings.cache_clear()
