import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_error_handling.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient

from app.main import app


@app.get("/__test__/unexpected-error", include_in_schema=False)
def raise_unexpected_error():
    raise RuntimeError("sensitive internal detail")


def test_unexpected_error_has_safe_body_and_request_id():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/__test__/unexpected-error")

    assert response.status_code == 500
    assert response.json()["detail"] == "服务器内部错误"
    assert "sensitive" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
