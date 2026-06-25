import hashlib, json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.post("/knowledge/chat")
def chat_with_knowledge(body: ChatMessage, db: Session = Depends(get_db)):
    """AI 对话（待接入 LLM）"""
    notes = db.execute(
        select(Note).where(Note.owner_id == OWNER_ID).order_by(Note.updated_at.desc()).limit(20)
    ).scalars().all()

    context_titles = [n.title for n in notes]

    return {
        "status": "not_configured",
        "reply": (
            f"收到消息：「{body.message}」\n\n"
            "LLM API 尚未配置。接入后可基于你的知识库（"
            + "、".join(context_titles[:5])
            + f"等 {len(notes)} 篇笔记）回答问题。\n\n"
            "配置方式：在 backend/.env 中设置 LLM_PROVIDER 和对应的 API Key。"
        ),
        "context_notes": len(notes),
    }
