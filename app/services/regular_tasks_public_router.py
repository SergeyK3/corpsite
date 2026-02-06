# FILE: app/services/regular_tasks_public_router.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from app.db.engine import engine

from app.services.regular_tasks_public_service import (
    create_regular_task_tx,
    get_regular_task_tx,
    list_regular_tasks_tx,
    patch_regular_task_tx,
    set_regular_task_active_tx,
)

router = APIRouter(prefix="/regular-tasks", tags=["regular-tasks"])


@router.get("")
def list_regular_tasks(
    status: str = "active",
    q: Optional[str] = None,
    schedule_type: Optional[str] = None,
    executor_role_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
    # RBAC: пока как у остального MVP — доверяем middleware/заголовку.
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
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
    try:
        with engine.begin() as conn:
            return create_regular_task_tx(conn, payload=payload, created_by_user_id=x_user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # уникальность code и т.п. пусть возвращается как 400 (MVP)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{regular_task_id}")
def get_regular_task(
    regular_task_id: int,
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
    try:
        with engine.begin() as conn:
            return get_regular_task_tx(conn, regular_task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")


@router.patch("/{regular_task_id}")
def patch_regular_task(
    regular_task_id: int,
    payload: Dict[str, Any],
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
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
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
    try:
        with engine.begin() as conn:
            return set_regular_task_active_tx(conn, regular_task_id, True)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")


@router.post("/{regular_task_id}/deactivate")
def deactivate_regular_task(
    regular_task_id: int,
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
):
    try:
        with engine.begin() as conn:
            return set_regular_task_active_tx(conn, regular_task_id, False)
    except KeyError:
        raise HTTPException(status_code=404, detail="regular_task not found")
