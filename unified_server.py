#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified ASGI server (single port 8080) that mounts:
- OpenAI-compatible API (at /v1/**)
- Protobuf bridge (under /bridge/**)
- Account pool service (under /pool/**)
- Account manager UI and helper APIs at root (keep legacy paths)
"""

import os
import sys
import sqlite3
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse


# Ensure subprojects are importable
ROOT_DIR = Path(__file__).resolve().parent
WARP_MAIN_DIR = ROOT_DIR / "warp2api-main"
POOL_SVC_DIR = ROOT_DIR / "account-pool-service"

if str(WARP_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(WARP_MAIN_DIR))
if str(POOL_SVC_DIR) not in sys.path:
    sys.path.insert(0, str(POOL_SVC_DIR))


def _load_pool_app():
    """Import the account-pool FastAPI app without module name collision."""
    import importlib.util

    main_path = POOL_SVC_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("account_pool_service_main", str(main_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load account-pool-service main module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    # module.app is FastAPI
    return getattr(module, "app")


# Create unified app
app = FastAPI(title="Warp2API Unified Server", version="1.0.0")


# Mount Protobuf bridge under /bridge
try:
    from warp2protobuf.api.protobuf_routes import app as bridge_app
    app.mount("/bridge", bridge_app)
except Exception as e:
    @app.get("/bridge/__error__")
    async def bridge_not_available():
        return {"error": f"Bridge app failed to mount: {e}"}


# Mount Account Pool Service under /pool
try:
    pool_app = _load_pool_app()
    app.mount("/pool", pool_app)
except Exception as e:
    @app.get("/pool/__error__")
    async def pool_not_available():
        return {"error": f"Pool app failed to mount: {e}"}


# Mount OpenAI-compatible app at root (it only serves /v1/**, /healthz, etc.)
try:
    from protobuf2openai.app import app as openai_app
    app.mount("/", openai_app)
except Exception as e:
    @app.get("/__openai_error__")
    async def openai_not_available():
        return {"error": f"OpenAI app failed to mount: {e}"}


# Account Manager: Static UI (serve /manager/account.html)
STATIC_DIR = ROOT_DIR
if (STATIC_DIR / "account.html").exists():
    app.mount("/manager", StaticFiles(directory=str(STATIC_DIR), html=True), name="manager")


# Account Manager APIs at root (keep legacy paths for existing page)
@app.post("/proxy/warp-token")
async def proxy_warp_token(grant_type: str = Form(...), refresh_token: str = Form(...)):
    """Proxy for Warp Secure Token API (used by account.html)."""
    url = os.getenv(
        "WARP_REFRESH_URL",
        "https://app.warp.dev/proxy/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs",
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    }
    data = f"grant_type={grant_type}&refresh_token={refresh_token}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), http2=True) as client:
            resp = await client.post(url, headers=headers, content=data)
        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        return JSONResponse(status_code=resp.status_code, content={"error": resp.text})
    except httpx.RequestError as exc:
        return JSONResponse(status_code=500, content={"error": f"Request failed: {exc}"})


@app.post("/api/test-database")
async def test_database(payload: Dict[str, Any]):
    db_path = payload.get("db_path")
    if not db_path:
        return {"success": False, "error": "数据库路径不能为空"}
    if not Path(db_path).exists():
        return {"success": False, "error": f"数据库文件不存在: {db_path}"}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": "accounts表不存在"}
        cursor.execute("PRAGMA table_info(accounts)")
        columns = cursor.fetchall()
        column_names = ", ".join([col[1] for col in columns])
        conn.close()
        return {"success": True, "table_info": f"包含字段: {column_names}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/import-account")
async def import_account(payload: Dict[str, Any]):
    db_path = payload.get("db_path")
    account = payload.get("account") or {}
    if not db_path or not account:
        return {"success": False, "error": "缺少必要参数"}
    if not Path(db_path).exists():
        return {"success": False, "error": f"数据库文件不存在: {db_path}"}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM accounts WHERE email = ?", (account.get("email"),))
        if cursor.fetchone():
            conn.close()
            return {"success": False, "error": "邮箱已存在"}
        cursor.execute(
            """
            INSERT INTO accounts (email, local_id, id_token, refresh_token, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                account.get("email"),
                account.get("local_id"),
                account.get("id_token"),
                account.get("refresh_token"),
                account.get("status", "available"),
            ),
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "账号导入成功"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.middleware("http")
async def _set_base_urls(request: Request, call_next):
    """Ensure internal components read unified base URLs via env if needed."""
    os.environ.setdefault("POOL_SERVICE_URL", "http://localhost:8080/pool")
    os.environ.setdefault("BRIDGE_BASE_URL", "http://localhost:8080/bridge")
    os.environ.setdefault("USE_POOL_SERVICE", os.getenv("USE_POOL_SERVICE", "true"))
    response = await call_next(request)
    return response


def main():
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()

