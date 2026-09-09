from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_db
from app.middleware import request_context_middleware
from app.routers import auth, files, notes, tasks
from app.settings import get_settings

app = FastAPI(title="Personal Assistant API")
settings = get_settings()
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


@app.get("/")
def root():
    return {"message": "Personal Assistant API", "status": "ok"}


@app.get("/health/live", tags=["health"])
def health_live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
