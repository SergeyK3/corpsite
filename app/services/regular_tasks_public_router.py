# FILE: app/services/regular_tasks_public_router.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged
from app.services.regular_tasks_public_service import (
    create_regular_task_tx,
    get_regular_task_tx,
    list_regular_tasks_tx,
    patch_regular_task_tx,
    set_regular_task_active_tx,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID

router = APIRouter(prefix="/regular-tasks", tags=["regular-tasks"])


def _require_admin_or_privileged(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid == int(SYSTEM_ADMIN_ROLE_ID):
        return

    if is_privileged(user):
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _require_system_admin(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid != int(SYSTEM_ADMIN_ROLE_ID):
        raise HTTPException(status_code=403, detail="Only ADMIN can modify regular tasks")


@router.get("")
def list_regular_tasks(
    status: str = "active",
    q: Optional[str] = None,
    schedule_type: Optional[str] = None,
    executor_role_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_admin_or_privileged(current_user)

    with engine.begin() as conn:
        return list_regular_tasks_tx(
            conn,
            status=status,
            q=q,
            schedule_type=schedule_type,
            executor_role_id=executor_role_id,
            limit=limit,
            offset=offset,
        )


@router.post("")
def create_regular_task(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_system_admin(current_user)

    try:
        with engine.begin() as conn:
            return create_regular_task_tx(
                conn,
                payload=payload,
                created_by_user_id=int(current_user["user_id"]),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{regular_task_id}")
def get_regular_task(
    regular_task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_admin_or_privileged(current_user)

    try:
        with engine.begin() as conn:
            return get_regular_task_tx(conn, regular_task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")


@router.patch("/{regular_task_id}")
def patch_regular_task(
    regular_task_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_system_admin(current_user)

    try:
        with engine.begin() as conn:
            return patch_regular_task_tx(conn, regular_task_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{regular_task_id}/activate")
def activate_regular_task(
    regular_task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_system_admin(current_user)

    try:
        with engine.begin() as conn:
            return set_regular_task_active_tx(conn, regular_task_id, True)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")


@router.post("/{regular_task_id}/deactivate")
def deactivate_regular_task(
    regular_task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_system_admin(current_user)

    try:
        with engine.begin() as conn:
            return set_regular_task_active_tx(conn, regular_task_id, False)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")