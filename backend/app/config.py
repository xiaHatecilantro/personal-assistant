"""SQLAlchemy 引擎、声明式基类和请求级数据库会话。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.settings import get_settings


DATABASE_URL = get_settings().database_url

# SQLite 仅用于本地测试；Web 请求可能跨线程使用同一连接，因此关闭线程归属检查。
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

if DATABASE_URL.startswith("sqlite"):
    # SQLite 默认不执行外键约束，测试环境必须显式开启才能逼近 MySQL 行为。
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    """为一次请求提供一个 Session，异常时回滚并始终释放数据库连接。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
