#!/usr/bin/env python3
"""OPS-009.15 — fix executor_role_id for hospital QM template + task 10009.

Run on VPS from app root:

  cd /opt/projects/corpsite/app
  set -a && source .env && set +a
  ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py snapshot
  ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py fix --execute
  ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py verify

Default mode is read-only snapshot (no writes).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

import app.config  # noqa: F401
from app.auth import create_access_token
from app.db.engine import engine

QM_ROLE_CODES = ("QM_HEAD", "QM_HOSP", "QM_AMB")
HOSP_TEMPLATE_ID = 1
AMB_TEMPLATE_ID = 2
HOSP_TASK_ID = 10009
AMB_TASK_ID = 10010
QM_HOSP_LOGIN = "qm_hosp@corp.local"
QM_HEAD_LOGIN = "qm_head@corp.local"
RUN_ID = 39


def _fetch_json(url: str, *, token: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _roles_snapshot(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT role_id, code, name
            FROM public.roles
            WHERE code = ANY(:codes)
            ORDER BY role_id
            """
        ),
        {"codes": list(QM_ROLE_CODES)},
    ).mappings().all()
    return [dict(r) for r in rows]


def _templates_snapshot(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                rt.regular_task_id,
                rt.code,
                rt.title,
                rt.is_active,
                rt.executor_role_id,
                r.code AS executor_role_code,
                r.name AS executor_role_name
            FROM public.regular_tasks rt
            LEFT JOIN public.roles r ON r.role_id = rt.executor_role_id
            WHERE rt.regular_task_id IN (:hosp_id, :amb_id)
            ORDER BY rt.regular_task_id
            """
        ),
        {"hosp_id": HOSP_TEMPLATE_ID, "amb_id": AMB_TEMPLATE_ID},
    ).mappings().all()
    return [dict(r) for r in rows]


def _tasks_snapshot(conn, task_ids: tuple[int, ...]) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                t.task_id,
                t.title,
                t.regular_task_id,
                t.period_id,
                t.executor_role_id,
                er.code AS executor_role_code,
                er.name AS executor_role_name,
                ts.code AS status_code,
                ts.name_ru AS status_name_ru,
                t.due_date,
                t.assignment_scope
            FROM public.tasks t
            JOIN public.task_statuses ts ON ts.status_id = t.status_id
            LEFT JOIN public.roles er ON er.role_id = t.executor_role_id
            WHERE t.task_id = ANY(:ids)
            ORDER BY t.task_id
            """
        ),
        {"ids": list(task_ids)},
    ).mappings().all()
    return [dict(r) for r in rows]


def _user_snapshot(conn, login: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT u.user_id, u.login, u.role_id, u.unit_id, u.is_active,
                   r.code AS role_code, r.name AS role_name
            FROM public.users u
            JOIN public.roles r ON r.role_id = u.role_id
            WHERE lower(u.login) = lower(:login)
            """
        ),
        {"login": login},
    ).mappings().first()
    return dict(row) if row else None


def _other_hosp_tasks(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                t.task_id,
                t.period_id,
                t.executor_role_id,
                er.code AS executor_role_code,
                ts.code AS status_code,
                t.due_date
            FROM public.tasks t
            JOIN public.task_statuses ts ON ts.status_id = t.status_id
            LEFT JOIN public.roles er ON er.role_id = t.executor_role_id
            WHERE t.regular_task_id = :regular_task_id
              AND t.task_id <> :exclude_task_id
            ORDER BY t.task_id
            """
        ),
        {"regular_task_id": HOSP_TEMPLATE_ID, "exclude_task_id": HOSP_TASK_ID},
    ).mappings().all()
    return [dict(r) for r in rows]


def _run39_items(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                i.item_id,
                i.regular_task_id,
                i.executor_role_id,
                i.status AS item_status,
                i.meta,
                rt.code AS template_code,
                rol.code AS role_code
            FROM public.regular_task_run_items i
            LEFT JOIN public.regular_tasks rt ON rt.regular_task_id = i.regular_task_id
            LEFT JOIN public.roles rol ON rol.role_id = i.executor_role_id
            WHERE i.run_id = :run_id
            ORDER BY i.item_id
            """
        ),
        {"run_id": RUN_ID},
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = row["meta"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        out.append(
            {
                "item_id": row["item_id"],
                "template_code": row["template_code"],
                "executor_role_id": row["executor_role_id"],
                "role_code": row["role_code"],
                "item_status": row["item_status"],
                "meta_task_id": meta.get("task_id"),
                "meta_dedupe_mode": meta.get("dedupe_mode"),
                "meta_deduped": meta.get("deduped"),
            }
        )
    return out


def _api_mine_active(login: str, api_base: str) -> dict[str, Any]:
    user = None
    with engine.connect() as conn:
        user = _user_snapshot(conn, login)
    if not user:
        return {"error": f"user not found: {login}"}

    token = create_access_token(int(user["user_id"]))
    params = {"scope": "mine", "limit": "200", "offset": "0", "status_filter": "active"}
    url = f"{api_base.rstrip('/')}/tasks?{urllib.parse.urlencode(params)}"
    result: dict[str, Any] = {"url": url, "login": login, "user_role_id": user["role_id"]}
    try:
        body = _fetch_json(url, token=token)
        items = body.get("items") if isinstance(body, dict) else body
        ids = sorted(int(x["task_id"]) for x in (items or []) if x.get("task_id") is not None)
        result["total"] = body.get("total") if isinstance(body, dict) else len(ids)
        result["task_ids"] = ids
        result["contains_10009"] = HOSP_TASK_ID in ids
        result["contains_10010"] = AMB_TASK_ID in ids
    except urllib.error.HTTPError as exc:
        result["http_error"] = exc.code
        result["body"] = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _role_id_by_code(roles: list[dict[str, Any]], code: str) -> Optional[int]:
    for r in roles:
        if r.get("code") == code:
            return int(r["role_id"])
    return None


def build_snapshot(*, api_base: str) -> dict[str, Any]:
    with engine.connect() as conn:
        roles = _roles_snapshot(conn)
        templates = _templates_snapshot(conn)
        tasks = _tasks_snapshot(conn, (HOSP_TASK_ID, AMB_TASK_ID))
        qm_hosp = _user_snapshot(conn, QM_HOSP_LOGIN)
        qm_head = _user_snapshot(conn, QM_HEAD_LOGIN)
        other_hosp = _other_hosp_tasks(conn)
        run39 = _run39_items(conn)

    qm_head_id = _role_id_by_code(roles, "QM_HEAD")
    qm_hosp_id = _role_id_by_code(roles, "QM_HOSP")

    hosp_template = next((t for t in templates if t["regular_task_id"] == HOSP_TEMPLATE_ID), None)
    hosp_task = next((t for t in tasks if t["task_id"] == HOSP_TASK_ID), None)

    return {
        "roles": roles,
        "templates": templates,
        "tasks_10009_10010": tasks,
        "user_qm_hosp": qm_hosp,
        "user_qm_head": qm_head,
        "other_regular_task_1_tasks": other_hosp,
        "run39_items": run39,
        "diagnosis": {
            "qm_head_role_id": qm_head_id,
            "qm_hosp_role_id": qm_hosp_id,
            "template_1_executor_is_qm_head": (
                hosp_template is not None and hosp_template.get("executor_role_code") == "QM_HEAD"
            ),
            "task_10009_executor_is_qm_head": (
                hosp_task is not None and hosp_task.get("executor_role_code") == "QM_HEAD"
            ),
            "qm_hosp_role_matches_qm_hosp_code": (
                qm_hosp is not None and qm_hosp_id is not None and int(qm_hosp["role_id"]) == qm_hosp_id
            ),
        },
        "api_qm_hosp_mine_active": _api_mine_active(QM_HOSP_LOGIN, api_base),
        "api_qm_head_mine_active": _api_mine_active(QM_HEAD_LOGIN, api_base),
    }


def prepare_fix_sql(roles: list[dict[str, Any]]) -> dict[str, Any]:
    qm_head_id = _role_id_by_code(roles, "QM_HEAD")
    qm_hosp_id = _role_id_by_code(roles, "QM_HOSP")
    if qm_head_id is None or qm_hosp_id is None:
        raise RuntimeError("QM_HEAD or QM_HOSP role not found")

    update_template = (
        "UPDATE public.regular_tasks\n"
        f"SET executor_role_id = {qm_hosp_id}\n"
        f"WHERE regular_task_id = {HOSP_TEMPLATE_ID}\n"
        f"  AND executor_role_id = {qm_head_id};"
    )
    update_task = (
        "UPDATE public.tasks\n"
        f"SET executor_role_id = {qm_hosp_id}\n"
        f"WHERE task_id = {HOSP_TASK_ID}\n"
        f"  AND executor_role_id = {qm_head_id};"
    )
    return {
        "qm_head_role_id": qm_head_id,
        "qm_hosp_role_id": qm_hosp_id,
        "sql": {
            "update_regular_tasks": update_template,
            "update_tasks_10009": update_task,
        },
    }


def apply_fix(conn, *, qm_head_id: int, qm_hosp_id: int) -> dict[str, int]:
    rt = conn.execute(
        text(
            """
            UPDATE public.regular_tasks
            SET executor_role_id = :qm_hosp_id
            WHERE regular_task_id = :regular_task_id
              AND executor_role_id = :qm_head_id
            """
        ),
        {
            "qm_hosp_id": qm_hosp_id,
            "regular_task_id": HOSP_TEMPLATE_ID,
            "qm_head_id": qm_head_id,
        },
    )
    tk = conn.execute(
        text(
            """
            UPDATE public.tasks
            SET executor_role_id = :qm_hosp_id
            WHERE task_id = :task_id
              AND executor_role_id = :qm_head_id
            """
        ),
        {"qm_hosp_id": qm_hosp_id, "task_id": HOSP_TASK_ID, "qm_head_id": qm_head_id},
    )
    return {
        "regular_tasks_rows": int(rt.rowcount or 0),
        "tasks_rows": int(tk.rowcount or 0),
    }


def cmd_snapshot(args: argparse.Namespace) -> int:
    out = build_snapshot(api_base=args.api_base)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    with engine.connect() as conn:
        roles = _roles_snapshot(conn)
    payload = prepare_fix_sql(roles)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    before = build_snapshot(api_base=args.api_base)
    with engine.connect() as conn:
        roles = _roles_snapshot(conn)
        fix_plan = prepare_fix_sql(roles)
        qm_head_id = int(fix_plan["qm_head_role_id"])
        qm_hosp_id = int(fix_plan["qm_hosp_role_id"])

        if not args.execute:
            out = {
                "mode": "dry_run",
                "before_diagnosis": before["diagnosis"],
                "prepared_sql": fix_plan["sql"],
                "message": "Pass --execute to apply UPDATEs",
            }
            print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
            return 0

        with conn.begin():
            rowcounts = apply_fix(conn, qm_head_id=qm_head_id, qm_hosp_id=qm_hosp_id)

    after = build_snapshot(api_base=args.api_base)
    out = {
        "mode": "executed",
        "rowcounts": rowcounts,
        "prepared_sql": fix_plan["sql"],
        "before_diagnosis": before["diagnosis"],
        "after_diagnosis": after["diagnosis"],
        "after_api_qm_hosp_mine_active": after["api_qm_hosp_mine_active"],
        "after_templates": after["templates"],
        "after_tasks_10009_10010": after["tasks_10009_10010"],
        "run39_items_unchanged": after["run39_items"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    out = build_snapshot(api_base=args.api_base)
    qm_hosp_api = out["api_qm_hosp_mine_active"]
    hosp_template = next((t for t in out["templates"] if t["regular_task_id"] == HOSP_TEMPLATE_ID), None)
    hosp_task = next((t for t in out["tasks_10009_10010"] if t["task_id"] == HOSP_TASK_ID), None)
    amb_task = next((t for t in out["tasks_10009_10010"] if t["task_id"] == AMB_TASK_ID), None)

    checks = {
        "template_1_executor_is_qm_hosp": hosp_template and hosp_template.get("executor_role_code") == "QM_HOSP",
        "task_10009_executor_is_qm_hosp": hosp_task and hosp_task.get("executor_role_code") == "QM_HOSP",
        "task_10010_unchanged_qm_amb": amb_task and amb_task.get("executor_role_code") == "QM_AMB",
        "qm_hosp_sees_10009_active": bool(qm_hosp_api.get("contains_10009")),
        "qm_hosp_does_not_see_10010": not bool(qm_hosp_api.get("contains_10010")),
        "run39_has_hosp_item": any(
            i.get("meta_task_id") == HOSP_TASK_ID or i.get("template_code") == "QM_PILOT_WEEKLY_HOSP"
            for i in out["run39_items"]
        ),
    }
    out["verification_checks"] = checks
    out["all_checks_pass"] = all(checks.values())
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out["all_checks_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="OPS-009.15 executor_role_id fix")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("snapshot", help="Read-only snapshot (default investigation)")
    sub.add_parser("prepare", help="Print guarded UPDATE SQL only")
    p_fix = sub.add_parser("fix", help="Apply guarded UPDATEs (dry-run unless --execute)")
    p_fix.add_argument("--execute", action="store_true", help="Actually run UPDATEs")
    sub.add_parser("verify", help="Post-fix verification snapshot")

    args = parser.parse_args()
    if args.cmd == "snapshot":
        return cmd_snapshot(args)
    if args.cmd == "prepare":
        return cmd_prepare(args)
    if args.cmd == "fix":
        return cmd_fix(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
