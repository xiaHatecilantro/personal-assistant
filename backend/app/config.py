import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and os.getenv("DB_PASSWORD"):
    DATABASE_URL = (
        f"mysql+pymysql://root:{os.environ['DB_PASSWORD']}"
        "@localhost:3307/personal_assistant?charset=utf8mb4&ssl_disabled=true"
    )
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL or DB_PASSWORD must be set")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
