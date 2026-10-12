"""密码散列、JWT 签发以及 FastAPI 当前用户认证依赖。"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import User
from app.settings import get_settings

SECRET_KEY = get_settings().jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = get_settings().jwt_expire_minutes

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """使用 bcrypt 的随机盐生成不可逆密码摘要。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    """将用户主键写入标准 ``sub`` 声明，并由服务端控制过期时间。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """统一完成 Bearer Token 校验和用户加载，供所有受保护路由复用。

    Token 只证明签发时的身份；每次请求仍查询用户表，可立即阻止已删除的账号继续访问。
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
