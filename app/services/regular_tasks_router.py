# FILE: app/services/regular_tasks_router.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.auth import decode_and_verify_token
from app.db.engine import engine
from app.security.directory_scope import has_valid_internal_api_token, require_uid
from app.services.regular_tasks_service import (
    run_regular_tasks_catch_up_tx,
    run_regular_tasks_generation_tx,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID

router = APIRouter(prefix="/internal/regular-tasks", tags=["internal-regular-tasks"])

_bearer_optional = HTTPBearer(auto_error=False)


def _require_system_admin(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid != int(SYSTEM_ADMIN_ROLE_ID):
        raise HTTPException(status_code=403, detail="Only ADMIN can run regular tasks")


def _load_user_by_id(user_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_id, role_id, unit_id, is_active, login
                FROM public.users
                WHERE user_id = :uid
                """
            ),
            {"uid": int(user_id)},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    if not bool(row.get("is_active", True)):
        raise HTTPException(status_code=403, detail="User is inactive")
    return dict(row)


def _resolve_runner_user(
    *,
    creds: Optional[HTTPAuthorizationCredentials],
    x_user_id: Optional[str],
    x_internal_api_token: Optional[str],
) -> Dict[str, Any]:
    if has_valid_internal_api_token(x_internal_api_token):
        uid = require_uid(
            authorization=None,
            x_user_id=x_user_id,
            x_internal_api_token=x_internal_api_token,
        )
        return _load_user_by_id(uid)

    token = (creds.credentials or "").strip() if creds else ""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")

    try:
        payload = decode_and_verify_token(token)
        uid = int(str(payload.get("sub") or "0"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if uid <= 0:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    return _load_user_by_id(uid)


def _parse_optional_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_optional_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    return None


@router.post("/run")
def run_regular_tasks(
    payload: Optional[Dict[str, Any]] = None,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_internal_api_token: Optional[str] = Header(default=None, alias="X-Internal-Api-Token"),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Dict[str, Any]:
    """
    Internal endpoint: запускается cron/worker/поддержкой.
    Auth: JWT system admin OR X-Internal-Api-Token + X-User-Id (service account).
    """
    user = _resolve_runner_user(
        creds=creds,
        x_user_id=x_user_id,
        x_internal_api_token=x_internal_api_token,
    )
    _require_system_admin(user)

    payload = payload or {}
    dry_run = bool(payload.get("dry_run", False))
    run_at_local_iso = payload.get("run_at_local_iso")

    run_at_local: Optional[datetime] = None
    if isinstance(run_at_local_iso, str) and run_at_local_iso.strip():
        run_at_local = datetime.fromisoformat(run_at_local_iso.strip())

    with engine.begin() as conn:
        run_id, stats = run_regular_tasks_generation_tx(
            conn,
            run_at_local=run_at_local,
            dry_run=dry_run,
            trigger_source_hint=(
                "automatic"
                if has_valid_internal_api_token(x_internal_api_token)
                else "manual"
            ),
        )

    return {"run_id": int(run_id), "dry_run": dry_run, "stats": stats}


@router.post("/catch-up")
def catch_up_regular_tasks(
    payload: Dict[str, Any] = Body(default_factory=dict),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_internal_api_token: Optional[str] = Header(default=None, alias="X-Internal-Api-Token"),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Dict[str, Any]:
    """
    Catch-up run: one scoped generation pass with force_due for training / recovery.
    Auth: same as POST /run (system admin only).
    """
    user = _resolve_runner_user(
        creds=creds,
        x_user_id=x_user_id,
        x_internal_api_token=x_internal_api_token,
    )
    _require_system_admin(user)

    dry_run = bool(payload.get("dry_run", False))
    preset_raw = str(payload.get("preset") or "").strip().lower()
    if preset_raw not in {"past_week", "past_month", "manual"}:
        raise HTTPException(
            status_code=422,
            detail="preset must be one of: past_week, past_month, manual",
        )

    manual_date = _parse_optional_date(payload.get("run_for_date"))
    if preset_raw == "manual" and manual_date is None:
        raise HTTPException(status_code=422, detail="run_for_date is required when preset=manual")

    schedule_type_raw = payload.get("schedule_type")
    schedule_type: Optional[str] = None
    if schedule_type_raw is not None:
        schedule_type = str(schedule_type_raw).strip().lower() or None
        if schedule_type and schedule_type not in {"weekly", "monthly", "yearly"}:
            raise HTTPException(
                status_code=422,
                detail="schedule_type must be one of: weekly, monthly, yearly",
            )

    org_group_id = _parse_optional_int(payload.get("org_group_id"))
    org_unit_id = _parse_optional_int(payload.get("org_unit_id"))
    executor_role_id = _parse_optional_int(payload.get("executor_role_id"))
    regular_task_id = _parse_optional_int(payload.get("regular_task_id"))

    try:
        with engine.begin() as conn:
            run_id, stats, resolved = run_regular_tasks_catch_up_tx(
                conn,
                preset=preset_raw,
                dry_run=dry_run,
                run_for_date_manual=manual_date,
                schedule_type=schedule_type,
                org_group_id=org_group_id,
                org_unit_id=org_unit_id,
                executor_role_id=executor_role_id,
                regular_task_id=regular_task_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "run_id": int(run_id),
        "dry_run": dry_run,
        "resolved": resolved,
        "stats": stats,
    }
