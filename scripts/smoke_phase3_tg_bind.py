#!/usr/bin/env python3
"""Phase 3 smoke: Telegram bind API flow (no bot polling / no real Telegram send).

Usage:
  export SMOKE_API_BASE=http://127.0.0.1:8000
  export SMOKE_LOGIN=smoke_user@corp.local
  export SMOKE_PASSWORD='...'
  export BOT_BIND_TOKEN='...'
  export SMOKE_TG_USER_ID=900000001
  ./.venv/bin/python scripts/smoke_phase3_tg_bind.py

Optional:
  export SMOKE_TG_USERNAME=smoke_test_bot_user
  export SMOKE_PASSWORD_FILE=/path/to/password

Cleanup after run:
  ./.venv/bin/python scripts/smoke_phase3_tg_bind.py --cleanup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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


def _resolve_password() -> str:
    direct = _env("SMOKE_PASSWORD")
    if direct:
        return direct
    path = _env("SMOKE_PASSWORD_FILE")
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        _fail("config", f"Cannot read SMOKE_PASSWORD_FILE: {exc}")
    return ""


def _login(client: httpx.Client, login: str, password: str) -> str:
    resp = client.post("/auth/login", json={"login": login, "password": password})
    if resp.status_code != 200:
        _fail("login", f"HTTP {resp.status_code}: {resp.text}")
    body = resp.json()
    token = str(body.get("access_token") or "").strip()
    if not token:
        _fail("login", "empty access_token")
    return token


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _read_json(resp: httpx.Response) -> Any:
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"message": resp.text}


def _error_code(body: Any) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    code = body.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    detail = body.get("detail")
    if isinstance(detail, dict):
        nested = detail.get("code")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _require_telegram_bound_field(body: Dict[str, Any], *, step: str) -> None:
    if "telegram_bound" not in body:
        _fail(step, f"telegram_bound missing in /auth/me: {json.dumps(body, ensure_ascii=False)}")


def _clear_user_telegram(*, user_id: int, tg_user_id: Optional[int] = None) -> None:
    from sqlalchemy import text

    from app.db.engine import engine

    uid = int(user_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET telegram_id = NULL,
                    telegram_username = NULL
                WHERE user_id = :user_id
                """
            ),
            {"user_id": uid},
        )
        if tg_user_id is not None and int(tg_user_id) > 0:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET telegram_id = NULL,
                        telegram_username = NULL
                    WHERE trim(COALESCE(CAST(telegram_id AS TEXT), '')) = :tg_text
                      AND user_id <> :user_id
                    """
                ),
                {"tg_text": str(int(tg_user_id)), "user_id": uid},
            )


def run_smoke(*, cleanup: bool) -> None:
    base = _env("SMOKE_API_BASE", _env("BACKEND_URL", "http://127.0.0.1:8000"))
    login = _env("SMOKE_LOGIN") or _env("SMOKE_PRIV_LOGIN", "admin")
    password = _resolve_password() or _env("SMOKE_PRIV_PASSWORD")
    bot_bind_token = _env("BOT_BIND_TOKEN")
    tg_user_id_raw = _env("SMOKE_TG_USER_ID")
    tg_username = _env("SMOKE_TG_USERNAME") or None

    if not password:
        _fail(
            "config",
            "Set SMOKE_PASSWORD / SMOKE_PASSWORD_FILE (or SMOKE_PRIV_PASSWORD for fallback)",
        )
    if not bot_bind_token:
        _fail("config", "Set BOT_BIND_TOKEN")
    if not tg_user_id_raw.isdigit() or int(tg_user_id_raw) <= 0:
        _fail("config", "Set SMOKE_TG_USER_ID to a positive integer")

    tg_user_id = int(tg_user_id_raw)
    state: Dict[str, Any] = {}

    with httpx.Client(base_url=base.rstrip("/"), timeout=30.0) as client:
        token = _login(client, login, password)
        _ok("1 login", login)

        me0 = client.get("/auth/me", headers=_auth_headers(token))
        if me0.status_code != 200:
            _fail("2 /auth/me", f"HTTP {me0.status_code}: {me0.text}")
        me0_body = me0.json()
        _require_telegram_bound_field(me0_body, step="2 /auth/me")
        user_id = int(me0_body.get("user_id") or 0)
        if user_id <= 0:
            _fail("2 /auth/me", "user_id missing")
        state["user_id"] = user_id
        _ok("2 /auth/me fields", f"user_id={user_id} telegram_bound={me0_body.get('telegram_bound')}")

        _clear_user_telegram(user_id=user_id, tg_user_id=tg_user_id)
        _ok("2b pre-clean telegram", f"user_id={user_id}")

        me1 = client.get("/auth/me", headers=_auth_headers(token))
        if me1.status_code != 200:
            _fail("3 /auth/me unbound", f"HTTP {me1.status_code}: {me1.text}")
        me1_body = me1.json()
        _require_telegram_bound_field(me1_body, step="3 /auth/me unbound")
        if me1_body.get("telegram_bound") is not False:
            _fail("3 /auth/me unbound", json.dumps(me1_body, ensure_ascii=False))
        _ok("3 /auth/me unbound", "telegram_bound=false")

        bind1 = client.post("/me/tg-bind-code", headers=_auth_headers(token))
        if bind1.status_code != 200:
            _fail("4 POST /me/tg-bind-code", f"HTTP {bind1.status_code}: {bind1.text}")
        bind1_body = bind1.json()
        code = str(bind1_body.get("code") or "").strip()
        expires_at = str(bind1_body.get("expires_at") or "").strip()
        if not code or not expires_at:
            _fail("4 POST /me/tg-bind-code", json.dumps(bind1_body, ensure_ascii=False))
        state["bind_code"] = code
        _ok("4 POST /me/tg-bind-code", f"code={code}")

        bind2 = client.post("/me/tg-bind-code", headers=_auth_headers(token))
        if bind2.status_code != 409:
            _fail("5 duplicate bind code", f"expected HTTP 409, got {bind2.status_code}: {bind2.text}")
        bind2_body = _read_json(bind2)
        dup_code = _error_code(bind2_body)
        if dup_code != "TGBIND_CONFLICT_CODE_EXISTS":
            _fail(
                "5 duplicate bind code",
                f"expected TGBIND_CONFLICT_CODE_EXISTS, got {dup_code!r}: {json.dumps(bind2_body, ensure_ascii=False)}",
            )
        _ok("5 duplicate bind code", "409 TGBIND_CONFLICT_CODE_EXISTS")

        consume_headers = {"X-Bot-Bind-Token": bot_bind_token}
        consume = client.post(
            "/tg/bind/consume",
            headers=consume_headers,
            json={"code": code, "tg_user_id": tg_user_id},
        )
        if consume.status_code != 200:
            _fail("6 POST /tg/bind/consume", f"HTTP {consume.status_code}: {consume.text}")
        consume_body = consume.json()
        if int(consume_body.get("user_id") or 0) != user_id:
            _fail("6 POST /tg/bind/consume", json.dumps(consume_body, ensure_ascii=False))
        _ok("6 POST /tg/bind/consume", f"user_id={user_id}")

        self_bind_headers: Dict[str, str] = {"X-Telegram-User-Id": str(tg_user_id)}
        if tg_username:
            self_bind_headers["X-Telegram-Username"] = tg_username
        self_bind = client.post("/auth/self-bind", headers=self_bind_headers)
        if self_bind.status_code != 200:
            _fail("7 POST /auth/self-bind", f"HTTP {self_bind.status_code}: {self_bind.text}")
        self_bind_body = self_bind.json()
        if int(self_bind_body.get("user_id") or 0) != user_id:
            _fail("7 POST /auth/self-bind", json.dumps(self_bind_body, ensure_ascii=False))
        _ok("7 POST /auth/self-bind", f"user_id={user_id}")

        me2 = client.get("/auth/me", headers=_auth_headers(token))
        if me2.status_code != 200:
            _fail("8 /auth/me bound", f"HTTP {me2.status_code}: {me2.text}")
        me2_body = me2.json()
        _require_telegram_bound_field(me2_body, step="8 /auth/me bound")
        if me2_body.get("telegram_bound") is not True:
            _fail("8 /auth/me bound", json.dumps(me2_body, ensure_ascii=False))
        _ok("8 /auth/me bound", "telegram_bound=true")

    print("\nPhase 3 smoke: PASS")
    print(
        json.dumps(
            {
                "user_id": state.get("user_id"),
                "login": login,
                "tg_user_id": tg_user_id,
                "bind_code": state.get("bind_code"),
            },
            ensure_ascii=False,
        )
    )

    if cleanup:
        _clear_user_telegram(user_id=int(state["user_id"]), tg_user_id=tg_user_id)
        print(f"cleanup: cleared telegram bind for user_id={state['user_id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 smoke: Telegram bind API")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clear telegram_id/telegram_username for smoke user after PASS",
    )
    args = parser.parse_args()
    run_smoke(cleanup=args.cleanup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
