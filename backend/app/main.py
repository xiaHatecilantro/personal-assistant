from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Base, engine
from app.models import Note, RawSource, Task, User  # noqa: F401
from app.routers import auth, files, notes, tasks

app = FastAPI(title="Personal Assistant API")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
