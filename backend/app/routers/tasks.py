from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_db
from app.models import Task, User
from app.schemas import TaskCreate, TaskResponse, TaskUpdate, TimerUpdate

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _get_owner(user: User | None = Depends(get_current_user)) -> int:
    """未登录返回 1（MVP 兼容），已登录返回真实用户 ID"""
    return user.id if user else 1


OWNER_ID = 1  # MVP 默认值，后续逐步替换为 _get_owner


def _to_response(task: Task) -> dict:
    return {
        "id": task.id,
        "parent_id": task.parent_id,
        "owner_id": task.owner_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "tag": task.tag,
        "task_type": task.task_type,
        "deadline_precision": task.deadline_precision,
        "timer_preset": task.timer_preset,
        "timer_total_seconds": task.timer_total_seconds or 0,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "updated_at": task.updated_at.isoformat() if task.updated_at else "",
    }


@router.get("")
def list_tasks(
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    task_type: str | None = None,
    parent_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Task).where(Task.owner_id == OWNER_ID)
    if parent_id is not None:
        stmt = stmt.where(Task.parent_id == parent_id)
    else:
        stmt = stmt.where(Task.parent_id.is_(None))
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if tag:
        stmt = stmt.where(Task.tag == tag)
    if task_type:
        stmt = stmt.where(Task.task_type == task_type)
    stmt = stmt.order_by(Task.created_at.desc())
    tasks = db.execute(stmt).scalars().all()
    return [_to_response(t) for t in tasks]


@router.post("", status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    task = Task(
        owner_id=OWNER_ID,
        parent_id=body.parent_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status=body.status,
        due_date=body.due_date.isoformat() if body.due_date else None,
        tag=body.tag,
        task_type=body.task_type,
        deadline_precision=body.deadline_precision,
        timer_preset=body.timer_preset,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _to_response(task)


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or task.owner_id != OWNER_ID:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_response(task)


@router.put("/{task_id}")
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or task.owner_id != OWNER_ID:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.title = body.title
    task.description = body.description
    task.priority = body.priority
    task.status = body.status
    task.due_date = body.due_date.isoformat() if body.due_date else None
    task.tag = body.tag
    task.task_type = body.task_type
    task.deadline_precision = body.deadline_precision
    task.timer_preset = body.timer_preset
    db.commit()
    db.refresh(task)
    return _to_response(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or task.owner_id != OWNER_ID:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()


@router.patch("/{task_id}/timer")
def update_timer(task_id: int, body: TimerUpdate, db: Session = Depends(get_db)):
    """每日任务计时：上报累计秒数"""
    task = db.get(Task, task_id)
    if not task or task.owner_id != OWNER_ID:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.task_type != "daily":
        raise HTTPException(status_code=400, detail="仅每日任务支持计时")
    task.timer_total_seconds = body.total_seconds
    db.commit()
    return {"timer_total_seconds": body.total_seconds}


@router.get("/stats/overview")
def get_stats_overview(db: Session = Depends(get_db)):
    base = select(Task).where(
        Task.owner_id == OWNER_ID,
        Task.parent_id.is_(None),
    )
    all_tasks = db.execute(base).scalars().all()

    by_status = {"todo": 0, "in_progress": 0, "done": 0}
    by_priority = {"high": 0, "medium": 0, "low": 0}

    for t in all_tasks:
        if t.status in by_status:
            by_status[t.status] += 1
        if t.priority in by_priority:
            by_priority[t.priority] += 1

    return {
        "total": len(all_tasks),
        "by_status": by_status,
        "by_priority": by_priority,
    }


@router.get("/stats/trend")
def get_stats_trend(db: Session = Depends(get_db)):
    from datetime import date, timedelta

    today = date.today()
    result = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = db.execute(
            select(Task).where(
                Task.owner_id == OWNER_ID,
                Task.status == "done",
                Task.parent_id.is_(None),
                Task.updated_at >= d.isoformat(),
                Task.updated_at < (d + timedelta(days=1)).isoformat(),
            )
        ).scalars().all()
        result.append({"date": d.isoformat(), "count": len(count)})

    return {"daily_completed": result}
