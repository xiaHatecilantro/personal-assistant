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
