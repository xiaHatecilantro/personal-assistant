"""集中读取并校验后端运行配置。

配置值只从环境变量和 ``backend/.env`` 进入应用，业务模块通过 ``get_settings``
消费同一份不可变快照，避免各处自行解析环境变量而产生默认值漂移。
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JWT_SECRET = "dev-secret-key-change-in-production"


def _load_environment() -> None:
    # 先加载后端专用文件，再允许启动目录中的 .env 补充尚未定义的变量。
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
    checkpoint_database_url: str
    agent_model_base_url: str
    agent_model_name: str
    agent_model_api_key: str
    agent_max_steps: int
    agent_run_timeout_seconds: int

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """构造并缓存配置；首次访问时完成跨字段和生产环境安全校验。"""
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
        checkpoint_database_url=os.getenv(
            "CHECKPOINT_DATABASE_URL",
            "postgresql://agent:agent@127.0.0.1:5433/agent_checkpoints",
        ).strip(),
        agent_model_base_url=os.getenv(
            "AGENT_MODEL_BASE_URL",
            "https://api.deepseek.com/v1",
        ).strip(),
        agent_model_name=os.getenv("AGENT_MODEL_NAME", "deepseek-chat").strip(),
        agent_model_api_key=os.getenv("AGENT_MODEL_API_KEY", "").strip(),
        agent_max_steps=int(os.getenv("AGENT_MAX_STEPS", "12")),
        agent_run_timeout_seconds=int(os.getenv("AGENT_RUN_TIMEOUT_SECONDS", "300")),
    )
    if settings.app_env not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    # 开发默认密钥只为降低本地启动门槛，生产环境必须显式覆盖且满足最低强度。
    if settings.is_production and (
        settings.jwt_secret_key == DEFAULT_JWT_SECRET or len(settings.jwt_secret_key) < 32
    ):
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters in production")
    if settings.jwt_expire_minutes <= 0:
        raise RuntimeError("JWT_EXPIRE_MINUTES must be greater than zero")
    if settings.agent_max_steps <= 0:
        raise RuntimeError("AGENT_MAX_STEPS must be greater than zero")
    if settings.agent_run_timeout_seconds <= 0:
        raise RuntimeError("AGENT_RUN_TIMEOUT_SECONDS must be greater than zero")
    return settings
