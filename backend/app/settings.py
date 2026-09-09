import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JWT_SECRET = "dev-secret-key-change-in-production"


def _load_environment() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv()


def _database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured

    password = os.getenv("DB_PASSWORD")
    if password:
        return (
            f"mysql+pymysql://root:{password}"
            "@localhost:3307/personal_assistant?charset=utf8mb4&ssl_disabled=true"
        )
    raise RuntimeError("DATABASE_URL or DB_PASSWORD must be set")


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    jwt_secret_key: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    llm_allowed_base_urls: tuple[str, ...]
    file_allowed_roots: tuple[str, ...]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    _load_environment()
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "").strip() or DEFAULT_JWT_SECRET
    settings = Settings(
        app_env=app_env,
        database_url=_database_url(),
        jwt_secret_key=jwt_secret_key,
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7))),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ),
        llm_allowed_base_urls=tuple(
            url.strip()
            for url in os.getenv(
                "LLM_ALLOWED_BASE_URLS",
                "https://api.deepseek.com/v1,https://api.openai.com/v1",
            ).split(",")
            if url.strip()
        ),
        file_allowed_roots=tuple(
            root.strip()
            for root in os.getenv("FILE_ALLOWED_ROOTS", "").split(os.pathsep)
            if root.strip()
        ),
    )
    if settings.app_env not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    if settings.is_production and (
        settings.jwt_secret_key == DEFAULT_JWT_SECRET or len(settings.jwt_secret_key) < 32
    ):
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters in production")
    if settings.jwt_expire_minutes <= 0:
        raise RuntimeError("JWT_EXPIRE_MINUTES must be greater than zero")
    return settings
