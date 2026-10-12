"""只读知识工具；每条查询都把 ``owner_id`` 写入 SQL 条件。"""

import json
import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolContext, ToolInput, ToolOutput, ToolPermission, ToolSpec
from app.models import Note

NOTE_SEARCH_MAX_LIMIT = 20
NOTE_SEARCH_EXCERPT_CHARS = 300
NOTE_CONTENT_MAX_CHARS = 4000
LINT_MAX_SCAN_PAGES = 200
LINT_MAX_LINKS_PER_NOTE = 50
LINT_MAX_ISSUES = 100


class SearchNotesInput(ToolInput):
    query: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    limit: int = Field(default=10, ge=1, le=NOTE_SEARCH_MAX_LIMIT, strict=True)

    @field_validator("query", "category")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class NoteSummary(ToolOutput):
    id: int
    title: str
    category: str | None
    tags: list[str]
    is_pinned: bool
    excerpt: str
    updated_at: datetime


class SearchNotesOutput(ToolOutput):
    items: list[NoteSummary]
    count: int = Field(ge=0)


def _json_string_list(raw: str | None) -> list[str]:
    try:
        value: Any = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def search_notes(
    session: Session,
    context: ToolContext,
    arguments: SearchNotesInput,
) -> SearchNotesOutput:
    stmt = select(Note).where(Note.owner_id == context.owner_id)
    if arguments.query:
        stmt = stmt.where(
            or_(
                Note.title.contains(arguments.query, autoescape=True),
                Note.content.contains(arguments.query, autoescape=True),
            )
        )
    if arguments.category:
        stmt = stmt.where(Note.category == arguments.category)
    stmt = stmt.order_by(
        Note.is_pinned.desc(),
        Note.updated_at.desc(),
        Note.id.desc(),
    ).limit(arguments.limit)
    notes = session.scalars(stmt).all()
    items = [
        NoteSummary(
            id=note.id,
            title=note.title,
            category=note.category,
            tags=_json_string_list(note.tags),
            is_pinned=bool(note.is_pinned),
            excerpt=(note.content or "")[:NOTE_SEARCH_EXCERPT_CHARS],
            updated_at=note.updated_at,
        )
        for note in notes
    ]
    return SearchNotesOutput(items=items, count=len(items))


search_notes_tool = ToolSpec(
    name="search_notes",
    description="按关键词和分类搜索当前用户的知识笔记。",
    permission=ToolPermission.READ,
    input_model=SearchNotesInput,
    output_model=SearchNotesOutput,
    handler=search_notes,
)


class GetNoteInput(ToolInput):
    note_id: int = Field(gt=0, strict=True)


class NoteDetail(ToolOutput):
    id: int
    title: str
    content: str
    content_truncated: bool
    category: str | None
    tags: list[str]
    wikilinks: list[str]
    source_url: str | None
    confidence: float | None
    domain: str | None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class GetNoteOutput(ToolOutput):
    found: bool
    note: NoteDetail | None


def get_note(
    session: Session,
    context: ToolContext,
    arguments: GetNoteInput,
) -> GetNoteOutput:
    # owner 条件进入同一条查询，使“无记录”和“无权限”在行为上不可区分。
    note = session.scalar(
        select(Note).where(
            Note.id == arguments.note_id,
            Note.owner_id == context.owner_id,
        )
    )
    if note is None:
        return GetNoteOutput(found=False, note=None)

    content = note.content or ""
    detail = NoteDetail(
        id=note.id,
        title=note.title,
        content=content[:NOTE_CONTENT_MAX_CHARS],
        content_truncated=len(content) > NOTE_CONTENT_MAX_CHARS,
        category=note.category,
        tags=_json_string_list(note.tags),
        wikilinks=_json_string_list(note.wikilinks),
        source_url=note.source_url,
        confidence=float(note.confidence) if note.confidence is not None else None,
        domain=note.domain,
        is_pinned=bool(note.is_pinned),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )
    return GetNoteOutput(found=True, note=detail)


get_note_tool = ToolSpec(
    name="get_note",
    description="读取当前用户的一条知识笔记。",
    permission=ToolPermission.READ,
    input_model=GetNoteInput,
    output_model=GetNoteOutput,
    handler=get_note,
)


class LintKnowledgeInput(ToolInput):
    pass


class KnowledgeIssue(ToolOutput):
    type: Literal["broken_link"]
    page: str
    target: str


class LintKnowledgeOutput(ToolOutput):
    total_pages: int = Field(ge=0)
    scanned_pages: int = Field(ge=0)
    scanned_links: int = Field(ge=0)
    skipped_links: int = Field(ge=0)
    issues: list[KnowledgeIssue]
    truncated: bool


def lint_knowledge(
    session: Session,
    context: ToolContext,
    _arguments: LintKnowledgeInput,
) -> LintKnowledgeOutput:
    total_pages = session.scalar(
        select(func.count(Note.id)).where(Note.owner_id == context.owner_id)
    ) or 0
    notes = session.scalars(
        select(Note)
        .where(Note.owner_id == context.owner_id)
        .order_by(Note.title.asc(), Note.id.asc())
        .limit(LINT_MAX_SCAN_PAGES)
    ).all()

    scanned_links: list[tuple[str, str]] = []
    skipped_links = 0
    for note in notes:
        targets = sorted(set(_json_string_list(note.wikilinks)))
        selected_targets = targets[:LINT_MAX_LINKS_PER_NOTE]
        skipped_links += len(targets) - len(selected_targets)
        scanned_links.extend((note.title, target) for target in selected_targets)

    # 目标集合有硬上限，分块查询避免超过 SQLite 等数据库的绑定参数限制。
    target_titles = sorted({target for _, target in scanned_links})
    owned_targets: set[str] = set()
    for offset in range(0, len(target_titles), 500):
        chunk = target_titles[offset : offset + 500]
        owned_targets.update(
            session.scalars(
                select(Note.title).where(
                    Note.owner_id == context.owner_id,
                    Note.title.in_(chunk),
                )
            ).all()
        )

    broken = sorted(
        {(page, target) for page, target in scanned_links if target not in owned_targets}
    )
    selected_issues = broken[:LINT_MAX_ISSUES]
    issues = [
        KnowledgeIssue(type="broken_link", page=page, target=target)
        for page, target in selected_issues
    ]
    truncated = (
        total_pages > len(notes)
        or skipped_links > 0
        or len(broken) > len(selected_issues)
    )
    return LintKnowledgeOutput(
        total_pages=total_pages,
        scanned_pages=len(notes),
        scanned_links=len(scanned_links),
        skipped_links=skipped_links,
        issues=issues,
        truncated=truncated,
    )


lint_knowledge_tool = ToolSpec(
    name="lint_knowledge",
    description="检查当前用户知识笔记中的断链。",
    permission=ToolPermission.READ,
    input_model=LintKnowledgeInput,
    output_model=LintKnowledgeOutput,
    handler=lint_knowledge,
)


class CreateNoteInput(ToolInput):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=20000)
    category: str | None = Field(default=None, max_length=50)
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    source_url: str | None = Field(default=None, max_length=500)
    domain: str | None = Field(default=None, max_length=50)
    is_pinned: bool = Field(default=False, strict=True)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def tags_not_blank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("tags must not contain blank values")
        return values


class CreateNoteOutput(ToolOutput):
    note_id: int


def _requires_approval(
    _session: Session, _context: ToolContext, _arguments: CreateNoteInput
) -> CreateNoteOutput:
    raise ValueError("write tools require a persisted approved tool call")


create_note_tool = ToolSpec(
    name="create_note",
    description="为当前用户创建知识笔记；执行前必须人工审批。",
    permission=ToolPermission.WRITE,
    input_model=CreateNoteInput,
    output_model=CreateNoteOutput,
    handler=_requires_approval,
)


def create_approved_note(
    session: Session, context: ToolContext, arguments: dict[str, Any]
) -> dict[str, int]:
    """仅供审批执行入口调用，事务由上层统一提交。"""
    parsed = CreateNoteInput.model_validate(arguments)
    links = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", parsed.content)))
    note = Note(
        owner_id=context.owner_id,
        title=parsed.title,
        content=parsed.content,
        category=parsed.category,
        tags=json.dumps(parsed.tags, ensure_ascii=False),
        wikilinks=json.dumps(links, ensure_ascii=False),
        source_url=parsed.source_url,
        domain=parsed.domain,
        is_pinned=parsed.is_pinned,
    )
    session.add(note)
    session.flush()
    return CreateNoteOutput(note_id=note.id).model_dump()
