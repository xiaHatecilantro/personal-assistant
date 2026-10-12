"""发布配置静态契约；不替代实际 Docker/Nginx 部署验收。"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_build_contexts_exclude_local_secrets_and_backend_test_artifacts():
    for component in ("backend", "frontend"):
        patterns = set((ROOT / component / ".dockerignore").read_text().splitlines())
        assert {".env", ".env.*"} <= patterns
    backend_patterns = set((ROOT / "backend/.dockerignore").read_text().splitlines())
    assert {".pytest_cache", ".ruff_cache", "*.db", "*.db-*", "*.sqlite*"} <= backend_patterns
    repository_patterns = set((ROOT / ".gitignore").read_text().splitlines())
    assert {"~$*", ".pytest_cache/", ".ruff_cache/", "*.db", "*.db-*", "*.sqlite*"} <= repository_patterns


def test_nginx_api_proxy_keeps_sse_responses_unbuffered():
    # 忽略注释，避免“注释里写了配置”也让契约假通过。
    config = re.sub(r"#[^\n]*", "", (ROOT / "frontend/nginx.conf").read_text())
    assert re.search(r"proxy_buffering\s+off\s*;", config)
    assert re.search(r"proxy_http_version\s+1\.1\s*;", config)
    assert re.search(r"proxy_read_timeout\s+300s\s*;", config)
