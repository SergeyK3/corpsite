# FILE: app/tg_bot_internal_router.py
"""OPS-007a — internal bot API (INTERNAL_API_TOKEN + Telegram identity)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.db.engine import engine
from app.security.bot_internal_auth import (
    is_service_account_user,
    require_bot_bound_user,
    require_telegram_user_id_header,
    require_valid_internal_api_token,
    resolve_bound_user_id_from_telegram,
)
from app.services.tasks_router import (
    approve_report,
    get_task,
    list_tasks,
    patch_task,
    reject_report,
    submit_report,
)
from app.services.tasks_service import (
    ensure_task_visible_or_404,
    get_user_role_id,
    load_task_full,
)
from app.task_events import list_my_task_events
from app.tg_bind import resolve_user_id_by_telegram_id, unbind_user_telegram

router = APIRouter(prefix="/internal/bot", tags=["internal-bot"])


class TgResolveResponse(BaseModel):
    user_id: int
    telegram_bound: bool = True


class TgUnbindResponse(BaseModel):
    user_id: int
    applied: bool
    telegram_bound: bool
    employee_id: Optional[int] = None


@router.post("/tg/resolve", response_model=TgResolveResponse)
def bot_tg_resolve(
    _internal: None = Depends(require_valid_internal_api_token),
    tg_user_id: int = Depends(require_telegram_user_id_header),
) -> TgResolveResponse:
    user_id = resolve_bound_user_id_from_telegram(int(tg_user_id))
    return TgResolveResponse(user_id=int(user_id), telegram_bound=True)


@router.post("/tg/unbind", response_model=TgUnbindResponse)
def bot_tg_unbind(
    _internal: None = Depends(require_valid_internal_api_token),
    tg_user_id: int = Depends(require_telegram_user_id_header),
) -> TgUnbindResponse:
    user_id = resolve_user_id_by_telegram_id(int(tg_user_id))
    if user_id is None:
        return TgUnbindResponse(user_id=0, applied=False, telegram_bound=False, employee_id=None)

    from app.auth import _get_user_by_id

    user = _get_user_by_id(int(user_id))
    if user and is_service_account_user(user):
        raise HTTPException(status_code=403, detail="service account not allowed for bot unbind")

    result = unbind_user_telegram(user_id=int(user_id), actor_user_id=int(user_id))
    return TgUnbindResponse(**result)


@router.post("/tg/unbind/{target_tg_user_id}", response_model=TgUnbindResponse)
def bot_tg_unbind_target(
    target_tg_user_id: int = Path(..., ge=1),
    _internal: None = Depends(require_valid_internal_api_token),
    actor_tg_user_id: int = Depends(require_telegram_user_id_header),
) -> TgUnbindResponse:
    """Admin-style unbind: actor Telegram must be bound; clears target tg account."""
    actor_user_id = resolve_bound_user_id_from_telegram(int(actor_tg_user_id))
    target_user_id = resolve_user_id_by_telegram_id(int(target_tg_user_id))
    if target_user_id is None:
        return TgUnbindResponse(user_id=0, applied=False, telegram_bound=False, employee_id=None)

    from app.auth import _get_user_by_id

    target_user = _get_user_by_id(int(target_user_id))
    if target_user and is_service_account_user(target_user):
        raise HTTPException(status_code=403, detail="service account not allowed for bot unbind")

    result = unbind_user_telegram(user_id=int(target_user_id), actor_user_id=int(actor_user_id))
    return TgUnbindResponse(**result)


# ----------------------- Tasks (delegate to JWT handlers with bot user context) -----------------------


@router.get("/tasks")
@router.get("/tasks/")
def bot_list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    scope: Literal["mine", "team"] = Query("mine"),
    executor_role_id: Optional[int] = Query(None, ge=1),
    org_unit_id: Optional[int] = Query(None, ge=1),
    org_group_id: Optional[int] = Query(None, ge=1),
    assignment_scope: Optional[str] = Query(None),
    task_kind: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return list_tasks(
        period_id=period_id,
        status_code=status_code,
        status_filter=status_filter,
        search=search,
        include_archived=include_archived,
        scope=scope,
        executor_role_id=executor_role_id,
        org_unit_id=org_unit_id,
        org_group_id=org_group_id,
        assignment_scope=assignment_scope,
        task_kind=task_kind,
        limit=limit,
        offset=offset,
        user=user,
    )


@router.get("/tasks/{task_id}")
def bot_get_task(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return get_task(task_id=task_id, include_archived=include_archived, user=user)


@router.patch("/tasks/{task_id}")
def bot_patch_task(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return patch_task(payload=payload, task_id=task_id, user=user)


@router.post("/tasks/{task_id}/report")
def bot_submit_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return submit_report(payload=payload, task_id=task_id, user=user)


@router.post("/tasks/{task_id}/approve")
def bot_approve_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return approve_report(payload=payload, task_id=task_id, user=user)


@router.post("/tasks/{task_id}/reject")
def bot_reject_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    return reject_report(payload=payload, task_id=task_id, user=user)


@router.get("/tasks/{task_id}/events")
def bot_task_events(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> List[Dict[str, Any]]:
    current_user_id = int(user["user_id"])
    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)
        task = load_task_full(conn, task_id=int(task_id))
        ensure_task_visible_or_404(
            conn=conn,
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=include_archived,
        )

        rows = conn.execute(
            text(
                """
                SELECT
                  e.audit_id,
                  e.task_id,
                  e.event_type,
                  e.actor_user_id,
                  e.actor_role_id,
                  e.payload,
                  e.created_at
                FROM public.task_events e
                WHERE e.task_id = :task_id
                ORDER BY e.audit_id ASC
                LIMIT :limit
                """
            ),
            {"task_id": int(task_id), "limit": int(limit)},
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    for r in rows:
        items.append(
            {
                "audit_id": int(r["audit_id"]),
                "task_id": int(r["task_id"]),
                "event_type": str(r["event_type"]),
                "actor_user_id": r.get("actor_user_id"),
                "actor_role_id": r.get("actor_role_id"),
                "payload": r.get("payload") or {},
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }
        )
    return items


@router.get("/tasks/me/events")
def bot_list_my_task_events(
    since_audit_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: Dict[str, Any] = Depends(require_bot_bound_user),
) -> Dict[str, Any]:
    token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    return list_my_task_events(
        authorization=None,
        x_user_id=str(int(user["user_id"])),
        x_internal_api_token=token or None,
        since_audit_id=int(since_audit_id),
        limit=int(limit),
    )
