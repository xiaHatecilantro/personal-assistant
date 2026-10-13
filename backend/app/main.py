"""FastAPI 应用装配入口：注册中间件、跨域策略、路由和健康检查。"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.checkpoint import open_agent_checkpointer
from app.agent.graph import compile_read_graph, compile_write_graph
from app.agent.model_gateway import OpenAICompatibleModelGateway
from app.agent.runtime import AgentRuntime, READ_GRAPH_VERSION, WRITE_GRAPH_VERSION
from app.config import SessionLocal, get_db
from app.middleware import request_context_middleware
from app.routers import agents, auth, files, notes, tasks
from app.settings import get_settings


settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """在应用生命周期内持有 Checkpointer；后台 Run 不依赖请求连接。"""
    application.state.agent_runtime = None
    # 当前仅部署单个 backend 进程；先纠偏旧进程留下的状态，绝不自动重放执行。
    AgentRuntime(session_factory=SessionLocal, graphs={}).reconcile_startup()
    if not settings.agent_model_api_key:
        yield
        return

    gateway = OpenAICompatibleModelGateway.from_settings(settings)
    async with open_agent_checkpointer() as checkpointer:
        read_graph = compile_read_graph(
            model_gateway=gateway,
            session_factory=SessionLocal,
            checkpointer=checkpointer,
        )
        write_graph = compile_write_graph(
            model_gateway=gateway,
            session_factory=SessionLocal,
            checkpointer=checkpointer,
        )
        runtime = AgentRuntime(
            session_factory=SessionLocal,
            # 冻结在旧 Run 中的版本仍由原拓扑执行，避免部署后静默改写 Checkpoint。
            graphs={READ_GRAPH_VERSION: read_graph, WRITE_GRAPH_VERSION: write_graph},
        )
        application.state.agent_runtime = runtime
        try:
            yield
        finally:
            # 必须先停止使用 Graph/Checkpointer 的任务，再退出其连接上下文。
            await runtime.shutdown()
            application.state.agent_runtime = None


app = FastAPI(title="Personal Assistant API", lifespan=lifespan)
app.middleware("http")(request_context_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(files.router)
app.include_router(agents.router)


@app.get("/")
def root():
    return {"message": "Personal Assistant API", "status": "ok"}


@app.get("/health/live", tags=["health"])
def health_live():
    """存活探针只证明进程能够响应，不依赖外部服务。"""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    """就绪探针实际访问业务数据库，失败时阻止流量进入未就绪实例。"""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
