import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from fastapi import APIRouter, Depends, HTTPException, Query
from pathlib import Path

from app.auth import get_current_user
from app.models import User
from app.settings import get_settings

router = APIRouter(prefix="/api/v1/files", tags=["files"])

ALLOWED_ROOTS = list(get_settings().file_allowed_roots)

MAX_DEPTH = 4
MAX_FILES_PER_DIR = 200
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", ".vite", "dist", "$RECYCLE.BIN", "System Volume Information", "Windows", "Program Files", "Program Files (x86)", "ProgramData"}

_pool = ThreadPoolExecutor(max_workers=2)


def _is_allowed(abs_path: str) -> bool:
    try:
        path = Path(abs_path).expanduser().resolve()
        for root in ALLOWED_ROOTS:
            root_path = f"{root}{os.sep}" if len(root) == 2 and root[1] == ":" else root
            allowed_root = Path(root_path).expanduser().resolve()
            if path == allowed_root or allowed_root in path.parents:
                return True
    except (OSError, RuntimeError):
        return False
    return False


def _contains_hidden_path(abs_path: str) -> bool:
    try:
        return any(part.startswith(".") for part in Path(abs_path).resolve().parts)
    except (OSError, RuntimeError):
        return True


def _build_tree(path: str, depth: int = 0) -> list[dict]:
    if depth > MAX_DEPTH:
        return []
    items = []
    try:
        p = Path(path)
        if not p.exists():
            return []
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (PermissionError, OSError):
        return []

    count = 0
    for entry in entries:
        if count >= MAX_FILES_PER_DIR:
            items.append({"name": f"... 还有 {len(entries) - MAX_FILES_PER_DIR} 项省略", "path": "", "type": "file"})
            break
        if entry.name.startswith("."):
            continue
        if entry.name in SKIP_DIRS:
            continue
        if entry.is_symlink():
            continue

        node = {
            "name": entry.name,
            "path": str(entry).replace("\\", "/"),
            "type": "folder" if entry.is_dir() else "file",
        }
        if entry.is_dir() and depth < 2:
            try:
                children = _build_tree(str(entry), depth + 1)
                if children:
                    node["children"] = children
            except Exception:
                node["children"] = []
        items.append(node)
        count += 1
    return items


@router.get("/roots")
def list_roots(_current_user: User = Depends(get_current_user)):
    result = []
    seen = set()
    for r in ALLOWED_ROOTS:
        if r.startswith("~"):
            abs_r = os.path.expanduser(r)
        elif len(r) == 2 and r[1] == ":":
            abs_r = r.upper()  # D:/ → D:/
        else:
            abs_r = r
        if not os.path.isdir(abs_r):
            continue
        p = abs_r.replace("\\", "/").rstrip("/")
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        if ":" in p and len(p.rstrip("/")) <= 3:
            p = p.rstrip("/") + "/"  # 确保 D:/ 格式
            name = p.rstrip("/")
        else:
            name = p.split("/")[-1] or p
        result.append({"name": name, "path": p})
    return result


@router.get("/tree")
def get_tree(
    path: str = Query(...),
    _current_user: User = Depends(get_current_user),
):
    abs_path = os.path.abspath(path)
    if not _is_allowed(abs_path):
        raise HTTPException(403, "无权访问该路径")
    if _contains_hidden_path(abs_path):
        raise HTTPException(403, "不允许访问隐藏目录")
    if not os.path.isdir(abs_path):
        raise HTTPException(404, "目录不存在")

    try:
        future = _pool.submit(_build_tree, abs_path, 0)
        return future.result(timeout=8)
    except FutureTimeout:
        return [{"name": "[加载超时]", "path": "", "type": "folder"}]
    except Exception:
        return []


@router.get("/read")
def read_file(
    path: str = Query(...),
    _current_user: User = Depends(get_current_user),
):
    abs_path = os.path.abspath(path)
    if not _is_allowed(abs_path):
        raise HTTPException(403, "无权访问该路径")
    if _contains_hidden_path(abs_path):
        raise HTTPException(403, "不允许读取隐藏文件")
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "文件不存在")
    size = os.path.getsize(abs_path)
    if size > 2 * 1024 * 1024:
        raise HTTPException(413, "文件过大（超过 2MB）")
    try:
        content = Path(abs_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "无法读取此文件")
    return {
        "path": abs_path.replace("\\", "/"),
        "name": os.path.basename(abs_path),
        "content": content,
        "size": size,
    }
