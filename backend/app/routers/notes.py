import asyncio, hashlib, json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_db
from app.models import Note, RawSource

router = APIRouter(prefix="/api/v1", tags=["knowledge"])

OWNER_ID = 1


# ── Pydantic schemas ──

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    category: str | None = None
    tags: list[str] = []
    source_url: str | None = None
    domain: str | None = None
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    category: str | None = None
    tags: list[str] = []
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


# ── NOTES CRUD ──

@router.get("/notes")
def list_notes(
    category: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    if search:
        stmt = (
            select(Note)
            .where(
                Note.title.contains(search) | Note.content.contains(search)
            )
            .order_by(Note.updated_at.desc())
        )
    else:
        stmt = select(Note).where(Note.owner_id == OWNER_ID)
        if category:
            stmt = stmt.where(Note.category == category)
        if domain:
            stmt = stmt.where(Note.domain == domain)
        stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc())

    if tag:
        notes = db.execute(stmt).scalars().all()
        notes = [n for n in notes if tag in (json.loads(n.tags or "[]"))]
    else:
        notes = db.execute(stmt).scalars().all()

    return [_note_out(n) for n in notes]


@router.post("/notes", status_code=201)
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    note = Note(
        owner_id=OWNER_ID, title=body.title, content=body.content,
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
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or note.owner_id != OWNER_ID:
        raise HTTPException(404, "笔记不存在")
    return _note_out(note)


@router.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or note.owner_id != OWNER_ID:
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
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or note.owner_id != OWNER_ID:
        raise HTTPException(404, "笔记不存在")
    db.delete(note)
    db.commit()


# ── WIKILINK 解析 ──

def _extract_wikilinks(md: str) -> list[str]:
    import re
    return list(set(re.findall(r"\[\[([^\]]+)\]\]", md)))


# ── RAW SOURCE 摄入 ──

@router.post("/knowledge/ingest", status_code=201)
def ingest_raw(body: RawIngest, db: Session = Depends(get_db)):
    h = hashlib.sha256(body.content.encode()).hexdigest()[:16]
    existing = db.execute(
        select(RawSource).where(RawSource.content_hash == h)
    ).scalar()
    if existing:
        raise HTTPException(409, "内容已存在，hash=" + h)

    src = RawSource(
        owner_id=OWNER_ID, title=body.title, content=body.content,
        source_url=body.source_url, content_hash=h,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return {
        "id": src.id, "title": src.title, "content_hash": h,
        "status": src.status,
        "hint": "摄入成功。后续可调用 POST /api/v1/knowledge/compile/{source_id} 让 LLM 蒸馏为 wiki 页面。当前 LLM 未配置，留作入口。",
    }


@router.post("/knowledge/compile/{source_id}")
def compile_source(source_id: int, db: Session = Depends(get_db)):
    """LLM 蒸馏入口（待接入）"""
    src = db.get(RawSource, source_id)
    if not src:
        raise HTTPException(404, "源材料不存在")
    return {
        "status": "not_configured",
        "source_id": src.id,
        "source_title": src.title,
        "content_length": len(src.content),
        "hint": "LLM API 尚未配置。接入后此处将自动调用大模型，将原始内容蒸馏为 1-3 个结构化 wiki 页面。",
    }


@router.get("/knowledge/query")
def query_knowledge(q: str = Query(..., min_length=1)):  # GET with query param
    """向知识库提问（待接入 LLM）"""
    return {
        "status": "not_configured",
        "query": q,
        "hint": "LLM API 尚未配置。接入后将：1) 读取 index.md 定位相关页面 2) 基于 wiki 内容回答 3) 可选地将问答结果回写到 wiki/synthesis/。",
    }


@router.post("/knowledge/lint")
def lint_knowledge(db: Session = Depends(get_db)):
    """健康检查（待接入 LLM）"""
    notes = db.execute(select(Note).where(Note.owner_id == OWNER_ID)).scalars().all()
    issues = []

    # 基础检查（不依赖 LLM）
    for n in notes:
        links = json.loads(n.wikilinks or "[]")
        for link in links:
            found = db.execute(select(Note).where(Note.title == link)).scalar()
            if not found:
                issues.append({"type": "broken_link", "page": n.title, "target": link})

    return {
        "total_pages": len(notes),
        "issues": issues,
        "hint": "基础断链检查完成。接入 LLM 后可检查：孤立页、超大页、冲突内容、新关联建议。",
    }


@router.get("/knowledge/graph")
def knowledge_graph(db: Session = Depends(get_db)):
    """知识图谱（节点 + 边）"""
    notes = db.execute(select(Note).where(Note.owner_id == OWNER_ID)).scalars().all()
    nodes = [{"id": n.id, "title": n.title, "domain": n.domain, "category": n.category} for n in notes]
    edges = []
    for n in notes:
        for link in json.loads(n.wikilinks or "[]"):
            target = next((x for x in notes if x.title == link), None)
            if target:
                edges.append({"source": n.id, "target": target.id, "label": link})
    return {"nodes": nodes, "edges": edges}


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1)
    provider_config: dict | None = None
    file_content: str | None = None
    file_path: str | None = None


def _build_chat_messages(body: ChatMessage, db: Session) -> list[dict]:
    """构造发给 LLM 的 messages 列表，注入知识库上下文"""
    system_parts = ["你是个人知识管理助手。用中文回复，简洁准确。"]
    notes = db.execute(
        select(Note).where(Note.owner_id == OWNER_ID).order_by(Note.updated_at.desc()).limit(20)
    ).scalars().all()
    if notes:
        ctx = "\n".join(f"- [{n.title}] {n.content[:300]}" for n in notes)
        system_parts.append(f"参考知识库片段：\n{ctx}")
    system = "\n\n".join(system_parts)
    user = body.message
    if body.file_content:
        user = f"文件: {body.file_path or '未知'}\n```\n{body.file_content[:5000]}\n```\n\n{body.message}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _sse_chunk(token: str) -> str:
    return f"data: {json.dumps({'token': token})}\n\n"


@router.post("/knowledge/chat")
def chat_with_knowledge(body: ChatMessage, db: Session = Depends(get_db)):
    """AI 对话（SSE 流式，需要前端传入 model_config）"""
    if not body.provider_config or not body.provider_config.get("apiKey"):
        raise HTTPException(400, "请在模型设置中配置 API Key")

    mc = body.provider_config
    client = OpenAI(base_url=mc["baseUrl"], api_key=mc["apiKey"])

    messages = _build_chat_messages(body, db)

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
                        yield _sse_chunk(delta.content)
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception:
                yield _sse_chunk("\n\n[流中断]")
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
    except Exception as e:
        msg = str(e)
        if "401" in msg or "auth" in msg.lower():
            raise HTTPException(401, "API Key 无效或被拒绝")
        raise HTTPException(500, f"LLM 调用失败: {msg[:200]}")
