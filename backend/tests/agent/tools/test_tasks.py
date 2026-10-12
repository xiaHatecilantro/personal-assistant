from datetime import date, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolContext
from app.agent.tools.tasks import GetTaskInput, ListTasksInput, get_task_tool, list_tasks_tool
from app.config import Base
from app.models import Task, User


@pytest.fixture()
def tasks_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(username="tasks-owner", password_hash="hash")
        other = User(username="tasks-other", password_hash="hash")
        session.add_all([owner, other])
        session.flush()
        yield session, owner.id, other.id
    engine.dispose()


def _context(owner_id):
    return ToolContext(
        owner_id=owner_id,
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
    )


def _task(owner_id, title, *, due_date=None, status="todo", created_at=None, parent_id=None):
    return Task(
        owner_id=owner_id,
        parent_id=parent_id,
        title=title,
        priority="medium",
        status=status,
        due_date=due_date,
        task_type="short_term",
        timer_total_seconds=0,
        created_at=created_at or datetime.now(),
        updated_at=created_at or datetime.now(),
    )


def test_list_tasks_is_owner_scoped_filtered_sorted_and_limited(tasks_db):
    session, owner_id, other_id = tasks_db
    now = datetime(2026, 10, 1, 12, 0)
    parent = _task(owner_id, "parent", due_date=date(2026, 10, 4), created_at=now)
    session.add(parent)
    session.flush()
    session.add_all(
        [
            _task(owner_id, "earlier", due_date=date(2026, 10, 2), created_at=now),
            _task(owner_id, "later", due_date=date(2026, 10, 3), created_at=now + timedelta(hours=1)),
            _task(owner_id, "done", due_date=date(2026, 10, 2), status="done"),
            _task(owner_id, "child", due_date=date(2026, 10, 2), parent_id=parent.id),
            _task(other_id, "private", due_date=date(2026, 10, 2)),
        ]
    )
    session.flush()

    result = list_tasks_tool.invoke(
        session,
        _context(owner_id),
        {
            "status": "todo",
            "due_from": "2026-10-02",
            "due_to": "2026-10-03",
            "limit": 2,
        },
    )

    assert [item.title for item in result.items] == ["earlier", "later"]
    assert result.count == 2


def test_list_tasks_rejects_invalid_date_range_limit_and_extra_identity():
    with pytest.raises(ValidationError):
        ListTasksInput(due_from=date(2026, 10, 3), due_to=date(2026, 10, 2))
    with pytest.raises(ValidationError):
        ListTasksInput(limit=21)
    with pytest.raises(ValidationError):
        ListTasksInput.model_validate({"limit": 1, "owner_id": 7})


@pytest.mark.parametrize("invalid", ["2", True, 2.0])
def test_task_tool_numeric_inputs_are_strict_integers_but_iso_dates_remain_valid(invalid):
    with pytest.raises(ValidationError):
        ListTasksInput(limit=invalid)
    with pytest.raises(ValidationError):
        GetTaskInput(task_id=invalid)

    parsed = ListTasksInput(due_from="2026-10-01", due_to="2026-10-02")
    assert parsed.due_from == date(2026, 10, 1)
    assert parsed.due_to == date(2026, 10, 2)


def test_get_task_returns_owned_task_and_ordered_owned_subtask_summaries(tasks_db):
    session, owner_id, other_id = tasks_db
    now = datetime(2026, 10, 1, 12, 0)
    parent = _task(owner_id, "parent", created_at=now)
    session.add(parent)
    session.flush()
    session.add_all(
        [
            _task(owner_id, "second", parent_id=parent.id, created_at=now + timedelta(hours=1)),
            _task(owner_id, "first", parent_id=parent.id, created_at=now),
            _task(other_id, "private-child", parent_id=parent.id, created_at=now),
        ]
    )
    session.flush()

    result = get_task_tool.invoke(session, _context(owner_id), {"task_id": parent.id})

    assert result.found is True
    assert result.task is not None
    assert [child.title for child in result.task.subtasks] == ["first", "second"]
    assert set(result.task.subtasks[0].model_dump()) == {
        "id",
        "title",
        "status",
        "priority",
        "due_date",
    }
    assert "owner_id" not in result.task.model_dump()


def test_get_task_does_not_distinguish_missing_from_other_owner(tasks_db):
    session, owner_id, other_id = tasks_db
    private_task = _task(other_id, "private")
    session.add(private_task)
    session.flush()

    missing = get_task_tool.invoke(session, _context(owner_id), GetTaskInput(task_id=999_999))
    forbidden = get_task_tool.invoke(
        session,
        _context(owner_id),
        GetTaskInput(task_id=private_task.id),
    )

    assert missing.model_dump() == {"found": False, "task": None}
    assert forbidden == missing
