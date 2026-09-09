import json
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _url_identity(value: str) -> tuple[str, str, int | None, str]:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("模型地址必须是有效的 HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("模型地址不能包含凭据、查询参数或片段")
    return (
        parsed.scheme.lower(),
        parsed.hostname.lower(),
        parsed.port,
        parsed.path.rstrip("/") or "/",
    )


def validate_base_url(base_url: str, allowed_base_urls: tuple[str, ...]) -> str:
    requested = _url_identity(base_url)
    allowed = {_url_identity(value) for value in allowed_base_urls}
    if requested not in allowed:
        raise ValueError("不允许访问该模型地址，请由服务端配置 LLM_ALLOWED_BASE_URLS")
    return base_url.rstrip("/")


def build_chat_messages(
    message: str,
    db: "Session",
    user_id: int,
    file_content: str | None = None,
    file_path: str | None = None,
) -> list[dict[str, str]]:
    from sqlalchemy import select

    from app.models import Note

    system_parts = ["你是个人知识管理助手。用中文回复，简洁准确。"]
    notes = db.execute(
        select(Note).where(Note.owner_id == user_id).order_by(Note.updated_at.desc()).limit(20)
    ).scalars().all()
    if notes:
        context = "\n".join(f"- [{note.title}] {(note.content or '')[:300]}" for note in notes)
        system_parts.append(f"参考知识库片段：\n{context}")
    user_message = message
    if file_content:
        user_message = (
            f"文件: {file_path or '未知'}\n```\n{file_content[:5000]}\n```\n\n{message}"
        )
    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {"role": "user", "content": user_message},
    ]


def sse_chunk(token: str) -> str:
    return f"data: {json.dumps({'token': token})}\n\n"
