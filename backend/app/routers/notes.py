"""知识笔记、原始材料摄入、文档导入和知识问答接口。

持久化资源始终按当前用户隔离；上传文档视为不可信输入，在独立子进程中解析，模型地址
则必须通过服务端白名单，避免文件解析器和代理请求成为服务器攻击入口。
"""

import asyncio
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_db
from app.models import Note, RawSource, User
from app.services.chat import build_chat_messages, sse_chunk, validate_base_url
from app.services.document_parser import SUPPORTED_EXTENSIONS, parse_document_isolated
from app.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["knowledge"])
_parse_pool = ThreadPoolExecutor(max_workers=2)


# ── Pydantic schemas ──

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    domain: str | None = None
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    domain: str | None = None
    is_pinned: bool = False


class RawIngest(BaseModel):
    title: str
    content: str
    source_url: str | None = None


def _note_out(n: Note) -> dict:
    return {
        "id": n.id, "owner_id": n.owner_id, "title": n.title,
        "content": n.content or "", "category": n.category,
        "tags": json.loads(n.tags) if n.tags else [],
        "wikilinks": json.loads(n.wikilinks) if n.wikilinks else [],
        "source_url": n.source_url, "confidence": float(n.confidence) if n.confidence else None,
        "domain": n.domain, "is_pinned": bool(n.is_pinned),
        "created_at": n.created_at.isoformat() if n.created_at else "",
        "updated_at": n.updated_at.isoformat() if n.updated_at else "",
    }


# ── FILE IMPORT / PARSING ──

@router.post("/knowledge/import")
async def import_file(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
):
    # 入口先限制扩展名与压缩前大小，解析器内部还会限制解压规模、页数和输出字符数。
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"不支持的格式: {ext}。支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    max_upload_size = 50 * 1024 * 1024
    data = await file.read(max_upload_size + 1)
    size = len(data)
    if size > max_upload_size:
        raise HTTPException(413, "文件过大（最大 50MB）")

    try:
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            _parse_pool,
            parse_document_isolated,
            file.filename or "",
            data,
        )
    except TimeoutError as exc:
        raise HTTPException(408, "文档解析超时") from exc
    except Exception as exc:
        raise HTTPException(400, "解析失败，请确认文件未损坏且格式正确") from exc

    title = os.path.splitext(file.filename)[0]
    return {"title": title, "content": content[:50000], "size": size}


# ── NOTES CRUD ──


@router.get("/notes")
def list_notes(
    category: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Note).where(Note.owner_id == current_user.id)
    if search:
        stmt = stmt.where(
            Note.title.contains(search) | Note.content.contains(search)
        )
    else:
        if category:
            stmt = stmt.where(Note.category == category)
        if domain:
            stmt = stmt.where(Note.domain == domain)
        stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
    if search:
        stmt = stmt.order_by(Note.updated_at.desc())

    if tag:
        notes = db.execute(stmt).scalars().all()
        notes = [n for n in notes if tag in (json.loads(n.tags or "[]"))]
    else:
        notes = db.execute(stmt).scalars().all()

    return [_note_out(n) for n in notes]


@router.post("/notes", status_code=201)
def create_note(
    body: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = Note(
        owner_id=current_user.id, title=body.title, content=body.content,
        category=body.category, tags=json.dumps(body.tags, ensure_ascii=False),
        wikilinks=json.dumps(_extract_wikilinks(body.content), ensure_ascii=False),
        source_url=body.source_url, domain=body.domain,
        is_pinned=1 if body.is_pinned else 0,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _note_out(note)


@router.get("/notes/{note_id}")
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(404, "笔记不存在")
    return _note_out(note)


@router.put("/notes/{note_id}")
def update_note(
    note_id: int,
    body: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(404, "笔记不存在")
    note.title, note.content = body.title, body.content
    note.category, note.domain = body.category, body.domain
    note.source_url, note.is_pinned = body.source_url, 1 if body.is_pinned else 0
    note.tags = json.dumps(body.tags, ensure_ascii=False)
    note.wikilinks = json.dumps(_extract_wikilinks(body.content), ensure_ascii=False)
    db.commit()
    db.refresh(note)
    return _note_out(note)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(404, "笔记不存在")
    db.delete(note)
    db.commit()


# ── WIKILINK 解析 ──

def _extract_wikilinks(md: str) -> list[str]:
    import re
    return list(set(re.findall(r"\[\[([^\]]+)\]\]", md)))


# ── RAW SOURCE 摄入 ──

@router.post("/knowledge/ingest", status_code=201)
def ingest_raw(
    body: RawIngest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 应用层预查提供友好错误，数据库唯一约束处理并发请求下的最终竞争。
    h = hashlib.sha256(body.content.encode()).hexdigest()[:16]
    existing = db.execute(
        select(RawSource).where(
            RawSource.owner_id == current_user.id,
            RawSource.content_hash == h,
        )
    ).scalar()
    if existing:
        raise HTTPException(409, "内容已存在，hash=" + h)

    src = RawSource(
        owner_id=current_user.id, title=body.title, content=body.content,
        source_url=body.source_url, content_hash=h,
    )
    db.add(src)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "内容已存在，hash=" + h) from exc
    db.refresh(src)
    return {
        "id": src.id, "title": src.title, "content_hash": h,
        "status": src.status,
        "hint": "摄入成功。后续可调用 POST /api/v1/knowledge/compile/{source_id} 让 LLM 蒸馏为 wiki 页面。当前 LLM 未配置，留作入口。",
    }


@router.post("/knowledge/compile/{source_id}")
def compile_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """LLM 蒸馏入口（待接入）"""
    src = db.get(RawSource, source_id)
    if not src or src.owner_id != current_user.id:
        raise HTTPException(404, "源材料不存在")
    return {
        "status": "not_configured",
        "source_id": src.id,
        "source_title": src.title,
        "content_length": len(src.content),
        "hint": "LLM API 尚未配置。接入后此处将自动调用大模型，将原始内容蒸馏为 1-3 个结构化 wiki 页面。",
    }


@router.get("/knowledge/query")
def query_knowledge(
    q: str = Query(..., min_length=1),
    _current_user: User = Depends(get_current_user),
):
    """向知识库提问（待接入 LLM）"""
    return {
        "status": "not_configured",
        "query": q,
        "hint": "LLM API 尚未配置。接入后将：1) 读取 index.md 定位相关页面 2) 基于 wiki 内容回答 3) 可选地将问答结果回写到 wiki/synthesis/。",
    }


@router.post("/knowledge/lint")
def lint_knowledge(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """健康检查（待接入 LLM）"""
    notes = db.execute(select(Note).where(Note.owner_id == current_user.id)).scalars().all()
    issues = []

    # 基础检查（不依赖 LLM）
    for n in notes:
        links = json.loads(n.wikilinks or "[]")
        for link in links:
            found = db.execute(
                select(Note).where(
                    Note.owner_id == current_user.id,
                    Note.title == link,
                )
            ).scalar()
            if not found:
                issues.append({"type": "broken_link", "page": n.title, "target": link})

    return {
        "total_pages": len(notes),
        "issues": issues,
        "hint": "基础断链检查完成。接入 LLM 后可检查：孤立页、超大页、冲突内容、新关联建议。",
    }


@router.get("/knowledge/graph")
def knowledge_graph(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """知识图谱（节点 + 边）"""
    notes = db.execute(select(Note).where(Note.owner_id == current_user.id)).scalars().all()
    nodes = [{"id": n.id, "title": n.title, "domain": n.domain, "category": n.category} for n in notes]
    edges = []
    notes_by_title = {note.title: note for note in notes}
    for n in notes:
        for link in json.loads(n.wikilinks or "[]"):
            target = notes_by_title.get(link)
            if target:
                edges.append({"source": n.id, "target": target.id, "label": link})
    return {"nodes": nodes, "edges": edges}


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1)
    provider_config: dict | None = None
    file_content: str | None = None
    file_path: str | None = None


@router.post("/knowledge/chat")
def chat_with_knowledge(
    body: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 对话（SSE 流式，需要前端传入 model_config）"""
    if not body.provider_config or not body.provider_config.get("apiKey"):
        raise HTTPException(400, "请在模型设置中配置 API Key")

    mc = body.provider_config
    try:
        base_url = validate_base_url(mc.get("baseUrl", ""), get_settings().llm_allowed_base_urls)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    client = OpenAI(base_url=base_url, api_key=mc["apiKey"])

    messages = build_chat_messages(
        body.message,
        db,
        current_user.id,
        body.file_content,
        body.file_path,
    )

    try:
        stream = client.chat.completions.create(
            model=mc.get("model", "deepseek-chat"),
            messages=messages,
            stream=True,
            max_tokens=4096,
            temperature=0.7,
        )

        def generate():
            try:
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield sse_chunk(delta.content)
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception:
                yield sse_chunk("\n\n[流中断]")
                yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "auth" in msg.lower():
            raise HTTPException(401, "API Key 无效或被拒绝")
        raise HTTPException(502, "模型服务暂时不可用") from exc
