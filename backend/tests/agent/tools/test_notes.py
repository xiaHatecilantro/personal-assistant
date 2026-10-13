import json
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.agent.tools.notes as notes_module
from app.agent.tools.base import ToolContext
from app.agent.tools.notes import (
    NOTE_CONTENT_MAX_CHARS,
    NOTE_SEARCH_EXCERPT_CHARS,
    GetNoteInput,
    LintKnowledgeInput,
    SearchNotesInput,
    get_note_tool,
    lint_knowledge_tool,
    search_notes_tool,
)
from app.config import Base
from app.models import Note, User


@pytest.fixture()
def notes_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(username="notes-owner", password_hash="hash")
        other = User(username="notes-other", password_hash="hash")
        session.add_all([owner, other])
        session.flush()
        yield session, owner.id, other.id
    engine.dispose()


def _context(owner_id):
    return ToolContext(
        owner_id=owner_id,
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
    )


def _note(owner_id, title, content, *, category="engineering", pinned=False, updated_at=None):
    return Note(
        owner_id=owner_id,
        title=title,
        content=content,
        category=category,
        tags=json.dumps(["agent"], ensure_ascii=False),
        wikilinks="[]",
        is_pinned=pinned,
        updated_at=updated_at or datetime.now(),
    )


def test_search_notes_is_owner_scoped_filtered_sorted_limited_and_cropped(notes_db):
    session, owner_id, other_id = notes_db
    now = datetime(2026, 9, 30, 12, 0)
    session.add_all(
        [
            _note(owner_id, "older", "agent " + "x" * 500, updated_at=now),
            _note(owner_id, "pinned", "agent design", pinned=True, updated_at=now - timedelta(days=2)),
            _note(owner_id, "newer", "agent runtime", updated_at=now + timedelta(days=1)),
            _note(owner_id, "wrong category", "agent", category="product", pinned=True),
            _note(other_id, "private", "agent secret", pinned=True),
        ]
    )
    session.flush()

    result = search_notes_tool.invoke(
        session,
        _context(owner_id),
        {"query": "agent", "category": "engineering", "limit": 2},
    )

    assert [item.title for item in result.items] == ["pinned", "newer"]
    assert result.count == 2
    assert all(len(item.excerpt) <= NOTE_SEARCH_EXCERPT_CHARS for item in result.items)
    assert all(item.title != "private" for item in result.items)


def test_search_notes_rejects_limit_above_cap_and_extra_identity_fields():
    with pytest.raises(ValidationError):
        SearchNotesInput(query="agent", limit=21)
    with pytest.raises(ValidationError):
        SearchNotesInput.model_validate({"query": "agent", "limit": 2, "owner_id": 1})


@pytest.mark.parametrize(
    ("query", "literal_title", "wildcard_title"),
    [
        ("%", "uses 100% coverage", "uses 100x coverage"),
        ("_", "under_score", "underXscore"),
    ],
)
def test_search_notes_treats_like_wildcards_as_literal_text(
    notes_db, query, literal_title, wildcard_title
):
    session, owner_id, _ = notes_db
    session.add_all(
        [
            _note(owner_id, literal_title, ""),
            _note(owner_id, wildcard_title, ""),
        ]
    )
    session.flush()

    result = search_notes_tool.invoke(
        session,
        _context(owner_id),
        {"query": query, "limit": 10},
    )

    assert [item.title for item in result.items] == [literal_title]


@pytest.mark.parametrize("invalid", ["2", True, 2.0])
def test_note_tool_numeric_inputs_are_strict_integers(invalid):
    with pytest.raises(ValidationError):
        SearchNotesInput(limit=invalid)
    with pytest.raises(ValidationError):
        GetNoteInput(note_id=invalid)


def test_get_note_returns_owner_note_with_bounded_content(notes_db):
    session, owner_id, _ = notes_db
    note = _note(owner_id, "large", "z" * (NOTE_CONTENT_MAX_CHARS + 7))
    session.add(note)
    session.flush()

    result = get_note_tool.invoke(session, _context(owner_id), {"note_id": note.id})

    assert result.found is True
    assert result.note is not None
    assert result.note.content == "z" * NOTE_CONTENT_MAX_CHARS
    assert result.note.content_truncated is True
    assert "owner_id" not in result.note.model_dump()


def test_get_note_does_not_distinguish_missing_from_other_owner(notes_db):
    session, owner_id, other_id = notes_db
    private_note = _note(other_id, "private", "secret")
    session.add(private_note)
    session.flush()

    missing = get_note_tool.invoke(session, _context(owner_id), GetNoteInput(note_id=999_999))
    forbidden = get_note_tool.invoke(
        session,
        _context(owner_id),
        GetNoteInput(note_id=private_note.id),
    )

    assert missing.model_dump() == {"found": False, "note": None}
    assert forbidden == missing


def test_lint_knowledge_is_owner_scoped_deduplicated_and_stably_sorted(notes_db):
    session, owner_id, other_id = notes_db
    alpha = _note(owner_id, "Alpha", "")
    alpha.wikilinks = json.dumps(["Missing Z", "Existing", "Missing A", "Missing A"])
    existing = _note(owner_id, "Existing", "")
    private_target = _note(other_id, "Missing Z", "")
    private_page = _note(other_id, "Private", "")
    private_page.wikilinks = json.dumps(["Invisible issue"])
    session.add_all([alpha, existing, private_target, private_page])
    session.flush()

    result = lint_knowledge_tool.invoke(session, _context(owner_id), LintKnowledgeInput())

    assert result.total_pages == 2
    assert [issue.model_dump() for issue in result.issues] == [
        {"type": "broken_link", "page": "Alpha", "target": "Missing A"},
        {"type": "broken_link", "page": "Alpha", "target": "Missing Z"},
    ]
    assert result.scanned_pages == 2
    assert result.truncated is False


def test_lint_knowledge_bounds_pages_links_and_issues_with_truncation_stats(
    notes_db, monkeypatch
):
    session, owner_id, _ = notes_db
    monkeypatch.setattr(notes_module, "LINT_MAX_SCAN_PAGES", 2)
    monkeypatch.setattr(notes_module, "LINT_MAX_LINKS_PER_NOTE", 2)
    monkeypatch.setattr(notes_module, "LINT_MAX_ISSUES", 1)
    alpha = _note(owner_id, "Alpha", "")
    alpha.wikilinks = json.dumps(["Missing Z", "Missing Y", "Missing X"])
    beta = _note(owner_id, "Beta", "")
    beta.wikilinks = json.dumps(["Missing B"])
    gamma = _note(owner_id, "Gamma", "")
    session.add_all([alpha, beta, gamma])
    session.flush()

    result = lint_knowledge_tool.invoke(session, _context(owner_id), {})

    assert result.total_pages == 3
    assert result.scanned_pages == 2
    assert result.scanned_links == 3
    assert result.skipped_links == 1
    assert len(result.issues) == 1
    assert result.issues[0].model_dump() == {
        "type": "broken_link",
        "page": "Alpha",
        "target": "Missing X",
    }
    assert result.truncated is True
