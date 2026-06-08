#!/usr/bin/env python3
"""QM pilot: verify task events and telegram delivery queue state.

Run on VPS after report/approve/reject flow (or after triggering a new action).

Usage:
  export $(grep -v '^#' /etc/corpsite/.env | xargs)
  ./venv/bin/python scripts/pilot/qm_notifications_check.py

Optional:
  TASK_IDS=1,2 INTERNAL_API_TOKEN=... ./venv/bin/python scripts/pilot/qm_notifications_check.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
INTERNAL_API_TOKEN = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
INTERNAL_USER_ID = int(os.environ.get("EVENTS_INTERNAL_API_USER_ID", "1") or "1")
TASK_IDS_RAW = (os.environ.get("TASK_IDS") or "1,2").strip()
PILOT_LOGINS = (
    "qm_head@corp.local",
    "qm_hosp@corp.local",
    "qm_amb@corp.local",
)


def _parse_task_ids(raw: str) -> List[int]:
    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out or [1, 2]


def _request(method: str, path: str, *, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return e.code, payload


class Checker:
    def __init__(self) -> None:
        self.failed = 0

    def ok(self, name: str, details: str = "") -> None:
        suffix = f" {details}" if details else ""
        print(f"[OK]  {name}{suffix}")

    def fail(self, name: str, details: str = "") -> None:
        suffix = f" {details}" if details else ""
        print(f"[FAIL] {name}{suffix}")
        self.failed += 1

    def info(self, name: str, details: str = "") -> None:
        suffix = f" {details}" if details else ""
        print(f"[INFO] {name}{suffix}")


def main() -> int:
    chk = Checker()
    task_ids = _parse_task_ids(TASK_IDS_RAW)

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        chk.fail("psycopg2 available", "install requirements.txt on VPS")
        return 1

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        chk.fail("DATABASE_URL set")
        return 1

    # sqlalchemy URL → psycopg2 dsn (minimal)
    dsn = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)

    chk.info("Config", f"BASE_URL={BASE_URL} internal_user_id={INTERNAL_USER_ID} task_ids={task_ids}")

    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.user_id, u.login, u.telegram_id IS NOT NULL AND trim(u.telegram_id::text) <> '' AS tg_bound
                FROM public.users u
                WHERE lower(u.login) = ANY(%s)
                ORDER BY u.login
                """,
                ([x.lower() for x in PILOT_LOGINS],),
            )
            bindings = cur.fetchall()
            if bindings:
                for row in bindings:
                    status = "bound" if row["tg_bound"] else "NOT bound"
                    chk.info("Telegram bind", f"{row['login']} user_id={row['user_id']} → {status}")
            else:
                chk.fail("Pilot users found in DB")

            bound_count = sum(1 for r in bindings if r["tg_bound"])
            if bound_count == 0:
                chk.fail(
                    "At least one pilot TG binding",
                    "bind qm_head (and executors) before expecting telegram SENT",
                )

            cur.execute(
                """
                SELECT e.audit_id, e.task_id, e.event_type, e.created_at,
                       COUNT(DISTINCT r.user_id) AS recipients,
                       COUNT(DISTINCT d.channel) FILTER (WHERE d.channel IS NOT NULL) AS delivery_channels
                FROM public.task_events e
                LEFT JOIN public.task_event_recipients r ON r.audit_id = e.audit_id
                LEFT JOIN public.task_event_deliveries d ON d.audit_id = e.audit_id
                WHERE e.task_id = ANY(%s)
                GROUP BY e.audit_id, e.task_id, e.event_type, e.created_at
                ORDER BY e.audit_id
                """,
                (task_ids,),
            )
            events = cur.fetchall()
            if events:
                chk.ok("task_events for pilot tasks", f"count={len(events)}")
                for ev in events:
                    chk.info(
                        "Event",
                        f"audit_id={ev['audit_id']} task_id={ev['task_id']} "
                        f"type={ev['event_type']} recipients={ev['recipients']}",
                    )
            else:
                chk.fail("task_events for pilot tasks", "none — run report/approve/reject first")

            cur.execute(
                """
                SELECT d.audit_id, d.user_id, u.login, d.channel, d.status, d.error_code, d.sent_at
                FROM public.task_event_deliveries d
                JOIN public.task_events e ON e.audit_id = d.audit_id
                LEFT JOIN public.users u ON u.user_id = d.user_id
                WHERE e.task_id = ANY(%s)
                ORDER BY d.audit_id, d.user_id, d.channel
                """,
                (task_ids,),
            )
            deliveries = cur.fetchall()
            if deliveries:
                chk.ok("task_event_deliveries rows", f"count={len(deliveries)}")
                tg_pending = sum(1 for d in deliveries if d["channel"] == "telegram" and d["status"] == "PENDING")
                tg_sent = sum(1 for d in deliveries if d["channel"] == "telegram" and d["status"] == "SENT")
                tg_failed = sum(1 for d in deliveries if d["channel"] == "telegram" and d["status"] == "FAILED")
                chk.info(
                    "Telegram deliveries",
                    f"PENDING={tg_pending} SENT={tg_sent} FAILED={tg_failed}",
                )
                if tg_pending == 0 and tg_sent == 0 and bound_count > 0 and events:
                    chk.fail(
                        "telegram delivery rows exist when users bound",
                        "check app/events.py binding lookup (users.telegram_id)",
                    )
                for d in deliveries:
                    if d["channel"] != "telegram":
                        continue
                    chk.info(
                        "TG delivery",
                        f"audit_id={d['audit_id']} {d['login']} status={d['status']} "
                        f"error={d['error_code'] or '-'}",
                    )
            else:
                chk.fail("task_event_deliveries rows", "none")

            supervisor_raw = (os.environ.get("SUPERVISOR_ROLE_IDS") or "").strip()
            if supervisor_raw:
                chk.ok("SUPERVISOR_ROLE_IDS configured", f"({supervisor_raw})")
            else:
                chk.fail("SUPERVISOR_ROLE_IDS configured", "empty — QM_HEAD may miss REPORT_SUBMITTED")

    if INTERNAL_API_TOKEN:
        code, data = _request(
            "GET",
            "/tasks/internal/task-event-deliveries/pending?channel=telegram&cursor_from=0&cursor_user_id=0&limit=10",
            headers={
                "X-User-Id": str(INTERNAL_USER_ID),
                "X-Internal-Api-Token": INTERNAL_API_TOKEN,
            },
        )
        if code == 200 and isinstance(data, dict):
            items = data.get("items") or []
            chk.ok("pending-deliveries endpoint", f"http={code} items={len(items)}")
            for it in items[:5]:
                if isinstance(it, dict):
                    chk.info(
                        "Pending",
                        f"audit_id={it.get('audit_id')} user_id={it.get('user_id')} "
                        f"type={it.get('event_type')} tg_chat={it.get('telegram_chat_id')}",
                    )
        else:
            chk.fail("pending-deliveries endpoint", f"http={code} {json.dumps(data, ensure_ascii=False)}")
    else:
        chk.info("pending-deliveries endpoint", "skipped (INTERNAL_API_TOKEN not set)")

    print()
    if chk.failed == 0:
        print("QM notifications check: ALL PASSED (or INFO-only)")
        print("Next: confirm bot service running and messages arrive in Telegram.")
        return 0
    print("QM notifications check: see [FAIL] lines above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
