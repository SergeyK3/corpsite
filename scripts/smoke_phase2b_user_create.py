#!/usr/bin/env python3
"""Phase 2b smoke: user create from employee (API-driven).

Usage:
  export SMOKE_PRIV_LOGIN=admin
  export SMOKE_PRIV_PASSWORD='...'
  export SMOKE_API_BASE=http://46.247.42.47:8000
  ./.venv/bin/python scripts/smoke_phase2b_user_create.py

Optional cleanup:
  ./.venv/bin/python scripts/smoke_phase2b_user_create.py --cleanup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _fail(step: str, detail: str, code: int = 1) -> None:
    print(f"FAIL [{step}] {detail}", file=sys.stderr)
    raise SystemExit(code)


def _ok(step: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"OK   [{step}]{suffix}")


def _login(client: httpx.Client, login: str, password: str) -> str:
    resp = client.post("/auth/login", json={"login": login, "password": password})
    if resp.status_code != 200:
        _fail("login", f"HTTP {resp.status_code}: {resp.text}")
    body = resp.json()
    token = str(body.get("access_token") or "").strip()
    if not token:
        _fail("login", "empty access_token")
    return token


def _privileged_token(*, login: str, password: str, user_id: Optional[int]) -> Tuple[str, str]:
    if password:
        return ("password", password)
    if user_id is not None and user_id > 0:
        from app.auth import create_access_token

        return ("token", create_access_token(int(user_id)))
    _fail(
        "config",
        "Set SMOKE_PRIV_PASSWORD / SMOKE_PRIV_PASSWORD_FILE or SMOKE_PRIV_USER_ID for privileged auth",
    )
    return ("", "")


def _resolve_priv_password() -> str:
    direct = _env("SMOKE_PRIV_PASSWORD")
    if direct:
        return direct
    path = _env("SMOKE_PRIV_PASSWORD_FILE")
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        _fail("config", f"Cannot read SMOKE_PRIV_PASSWORD_FILE: {exc}")
    return ""


def _auth_client(client: httpx.Client, *, mode: str, secret: str) -> str:
    if mode == "password":
        login = _env("SMOKE_PRIV_LOGIN", "admin")
        return _login(client, login, secret)
    return secret


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _get_json(client: httpx.Client, path: str, *, token: str, params: Optional[Dict[str, Any]] = None) -> Any:
    resp = client.get(path, headers=_auth_headers(token), params=params or {})
    if resp.status_code != 200:
        _fail("GET " + path, f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()


def _post_json(client: httpx.Client, path: str, *, token: str, payload: Dict[str, Any], expected: int = 201) -> Any:
    resp = client.post(path, headers=_auth_headers(token), json=payload)
    if resp.status_code != expected:
        _fail("POST " + path, f"HTTP {resp.status_code}: {resp.text}")
    return resp.json() if resp.content else {}


def _pick_position_id(client: httpx.Client, token: str) -> int:
    body = _get_json(client, "/directory/positions", token=token, params={"limit": 5, "offset": 0})
    items = body.get("items") or []
    if not items:
        _fail("positions", "no positions available")
    pid = items[0].get("position_id") or items[0].get("id")
    if pid is None:
        _fail("positions", "position id missing")
    return int(pid)


def _pick_org_unit_id(client: httpx.Client, token: str) -> int:
    body = _get_json(client, "/directory/org-units/tree", token=token)
    items = body.get("items") or []

    def walk(nodes: list) -> Optional[int]:
        for node in nodes:
            uid = node.get("unit_id") or node.get("id")
            if uid is not None:
                try:
                    return int(uid)
                except (TypeError, ValueError):
                    pass
            children = node.get("children") or []
            if children:
                found = walk(children)
                if found is not None:
                    return found
        return None

    unit_id = walk(items)
    if unit_id is None:
        _fail("org-units", "no org unit in tree")
    return unit_id


def _pick_role_id(client: httpx.Client, token: str) -> int:
    body = _get_json(client, "/directory/roles", token=token, params={"limit": 20, "offset": 0})
    items = body.get("items") or []
    for row in items:
        rid = row.get("role_id") or row.get("id")
        if rid is not None:
            return int(rid)
    _fail("roles", "no roles available")
    return 0


def _cleanup(client: httpx.Client, token: str, *, login: str, employee_id: int) -> None:
    from sqlalchemy import text

    from app.db.engine import engine

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.users WHERE lower(login) = lower(:login)"), {"login": login})
        conn.execute(text("DELETE FROM public.employees WHERE employee_id = :eid"), {"eid": int(employee_id)})
    print(f"cleanup: removed user {login!r} and employee_id={employee_id}")


def run_smoke(*, cleanup: bool) -> None:
    base = _env("SMOKE_API_BASE", _env("BACKEND_URL", "http://127.0.0.1:8000"))
    priv_login = _env("SMOKE_PRIV_LOGIN", "admin")
    priv_password = _resolve_priv_password()
    priv_user_id_raw = _env("SMOKE_PRIV_USER_ID")
    priv_user_id = int(priv_user_id_raw) if priv_user_id_raw.isdigit() else None
    priv_mode, priv_secret = _privileged_token(
        login=priv_login,
        password=priv_password,
        user_id=priv_user_id,
    )

    suffix = uuid.uuid4().hex[:8]
    employee_name = f"Smoke2b Employee {suffix}"
    new_login = f"smoke2b_{suffix}"
    new_password = f"Smoke2b!{suffix}"

    state: Dict[str, Any] = {}

    with httpx.Client(base_url=base.rstrip("/"), timeout=30.0) as client:
        # 1. Login privileged user
        priv_token = _auth_client(client, mode=priv_mode, secret=priv_secret)
        if priv_mode == "password":
            _ok("1 login privileged", priv_login)
        else:
            _ok("1 privileged auth", f"JWT for user_id={priv_user_id}")

        me = _get_json(client, "/auth/me", token=priv_token)
        state["priv_me"] = me
        _ok("1b /auth/me privileged", f"user_id={me.get('user_id')}")

        # 2. Personnel list reachable (same API as /directory/personnel UI)
        employees = _get_json(
            client,
            "/directory/employees",
            token=priv_token,
            params={"status": "all", "limit": 5, "offset": 0},
        )
        _ok("2 personnel list", f"total={employees.get('total')}")

        # 3. Create test employee
        org_unit_id = _pick_org_unit_id(client, priv_token)
        position_id = _pick_position_id(client, priv_token)
        employee = _post_json(
            client,
            "/directory/employees",
            token=priv_token,
            payload={
                "full_name": employee_name,
                "org_unit_id": org_unit_id,
                "position_id": position_id,
            },
        )
        employee_id = int(employee["id"])
        state["employee_id"] = employee_id
        _ok("3 create employee", f"id={employee_id} fio={employee.get('fio')}")

        # 4. Open employee card (GET detail)
        detail = _get_json(client, f"/directory/employees/{employee_id}", token=priv_token)
        if detail.get("user") is not None:
            _fail("4 employee card", "expected user=null before create")
        _ok("4 employee card", "user is null")

        # 5. Create user for employee
        role_id = _pick_role_id(client, priv_token)
        created_user = _post_json(
            client,
            "/directory/users",
            token=priv_token,
            payload={
                "employee_id": employee_id,
                "role_id": role_id,
                "login": new_login,
                "password": new_password,
                "is_active": True,
            },
        )
        state["new_user_id"] = created_user.get("user_id")
        _ok("5 create user", f"user_id={created_user.get('user_id')} login={new_login}")

        detail2 = _get_json(client, f"/directory/employees/{employee_id}", token=priv_token)
        linked = detail2.get("user") or {}
        if not linked or linked.get("login") != new_login:
            _fail("5b employee linked user", json.dumps(linked, ensure_ascii=False))
        _ok("5b employee linked user", new_login)

        # 6. Logout (drop privileged token)
        priv_token = ""

        # 7. Login as new user
        new_token = _login(client, new_login, new_password)
        _ok("7 login new user", new_login)

        # 8. /auth/me
        new_me = _get_json(client, "/auth/me", token=new_token)
        if int(new_me.get("user_id") or 0) != int(created_user["user_id"]):
            _fail("8 /auth/me", json.dumps(new_me, ensure_ascii=False))
        _ok("8 /auth/me", f"user_id={new_me.get('user_id')} login={new_me.get('login')}")

        # 9. Directory / Working Contacts / Tasks visibility
        wc = _get_json(client, "/directory/working-contacts", token=new_token, params={"limit": 5})
        _ok("9 working-contacts", f"total={wc.get('total')}")

        try:
            tasks = _get_json(client, "/tasks", token=new_token, params={"limit": 5, "offset": 0})
            _ok("9 tasks", f"total={tasks.get('total', len(tasks.get('items') or []))}")
        except SystemExit:
            resp = client.get("/tasks", headers=_auth_headers(new_token), params={"limit": 5, "offset": 0})
            if resp.status_code in (200, 403):
                _ok("9 tasks", f"HTTP {resp.status_code}")
            else:
                _fail("9 tasks", f"HTTP {resp.status_code}: {resp.text}")

        # Directory root sections via employees (scoped read)
        scoped_employees = _get_json(
            client,
            "/directory/employees",
            token=new_token,
            params={"status": "active", "limit": 5, "offset": 0},
        )
        _ok("9 directory employees", f"total={scoped_employees.get('total')}")

    print("\nPhase 2b smoke: PASS")
    print(json.dumps({
        "employee_id": state.get("employee_id"),
        "employee_name": employee_name,
        "new_login": new_login,
        "new_user_id": state.get("new_user_id"),
    }, ensure_ascii=False))

    if cleanup:
        with httpx.Client(base_url=base.rstrip("/"), timeout=30.0) as client:
            token = _auth_client(client, mode=priv_mode, secret=priv_secret)
            _cleanup(client, token, login=new_login, employee_id=int(state["employee_id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2b smoke: user create from employee")
    parser.add_argument("--cleanup", action="store_true", help="Remove created test employee/user")
    args = parser.parse_args()
    run_smoke(cleanup=args.cleanup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
