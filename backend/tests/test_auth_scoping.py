import os
import sys
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = "sqlite:///./test_auth_scoping.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient

from app.config import Base, engine
from app.main import app


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    engine.dispose()
    Path("test_auth_scoping.db").unlink(missing_ok=True)


def register_user(prefix: str) -> dict[str, str]:
    username = f"{prefix}-{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 201
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_tasks_are_scoped_to_authenticated_user():
    alice_headers = register_user("alice")
    bob_headers = register_user("bob")

    alice_task = client.post(
        "/api/v1/tasks",
        json={"title": "Alice task"},
        headers=alice_headers,
    )
    bob_task = client.post(
        "/api/v1/tasks",
        json={"title": "Bob task"},
        headers=bob_headers,
    )

    assert alice_task.status_code == 201
    assert bob_task.status_code == 201

    alice_tasks = client.get("/api/v1/tasks", headers=alice_headers)
    assert alice_tasks.status_code == 200
    assert [task["title"] for task in alice_tasks.json()] == ["Alice task"]

    bob_task_id = bob_task.json()["id"]
    blocked = client.get(f"/api/v1/tasks/{bob_task_id}", headers=alice_headers)
    assert blocked.status_code == 404


def test_note_search_is_scoped_to_authenticated_user():
    alice_headers = register_user("alice")
    bob_headers = register_user("bob")

    client.post(
        "/api/v1/notes",
        json={"title": "Alice note", "content": "shared keyword"},
        headers=alice_headers,
    )
    client.post(
        "/api/v1/notes",
        json={"title": "Bob note", "content": "shared keyword"},
        headers=bob_headers,
    )

    response = client.get(
        "/api/v1/notes",
        params={"search": "shared"},
        headers=alice_headers,
    )

    assert response.status_code == 200
    assert [note["title"] for note in response.json()] == ["Alice note"]


def test_file_roots_require_authentication():
    response = client.get("/api/v1/files/roots")

    assert response.status_code == 401
