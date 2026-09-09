import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.routers import files


def test_is_allowed_rejects_sibling_directory_with_same_string_prefix(
    tmp_path: Path,
    monkeypatch,
):
    allowed_root = tmp_path / "allowed"
    sibling = tmp_path / "allowed-private"
    allowed_root.mkdir()
    sibling.mkdir()
    monkeypatch.setattr(files, "ALLOWED_ROOTS", [str(allowed_root)])

    assert files._is_allowed(str(sibling)) is False


def test_is_allowed_rejects_parent_traversal_outside_allowed_root(
    tmp_path: Path,
    monkeypatch,
):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    escaped_path = allowed_root / "nested" / ".." / ".." / "outside.txt"
    monkeypatch.setattr(files, "ALLOWED_ROOTS", [str(allowed_root)])

    assert files._is_allowed(str(escaped_path)) is False


def test_hidden_files_are_rejected_even_inside_allowed_root(tmp_path: Path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    hidden_file = allowed_root / ".env"
    allowed_root.mkdir()
    hidden_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(files, "ALLOWED_ROOTS", [str(allowed_root)])

    assert files._is_allowed(str(hidden_file)) is True
    assert files._contains_hidden_path(str(hidden_file)) is True
