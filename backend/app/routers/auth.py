from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import get_db
from app.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=201)
def register(body: RegisterBody, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where(User.username == body.username)
    ).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}
