"""Sysadmin rollout of electronic HIRE approval by department."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_guard import require_sysadmin_api

router = APIRouter(prefix="/hire-approval-rollout", tags=["admin-hire-approval"])


def require_hire_rollout_admin(admin: dict[str, Any] = Depends(require_sysadmin_api)) -> dict[str, Any]:
    with engine.connect() as conn:
        role_code = conn.execute(text("""
            SELECT r.code FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
            WHERE u.user_id=:id AND u.is_active=TRUE
        """), {"id": int(admin["user_id"])}).scalar_one_or_none()
    if role_code not in {"ADMIN", "SYSADMIN"}:
        raise HTTPException(403, "Только системный администратор может менять порядок согласования.")
    return admin


class ModeChangeIn(BaseModel):
    mode: str
    reason: str = Field(min_length=1)


@router.get("")
def list_hire_approval_modes(_admin: dict[str, Any] = Depends(require_hire_rollout_admin)) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT u.unit_id, u.name AS unit_name, u.group_id,
                   COALESCE(m.mode, 'paper') AS mode,
                   (SELECT count(*) FROM public.electronic_hire_applications e
                    JOIN public.personnel_applications a USING (application_id)
                    WHERE a.intended_org_unit_id=u.unit_id
                      AND a.status NOT IN ('completed','cancelled','withdrawn','expired')) AS unfinished_count,
                   (SELECT count(*) FROM public.electronic_hire_applications e
                    JOIN public.personnel_applications a USING (application_id)
                    WHERE a.intended_org_unit_id=u.unit_id
                      AND a.status NOT IN ('completed','cancelled','withdrawn','expired')
                      AND e.approval_mode<>COALESCE(m.mode, 'paper')) AS retained_prior_mode_count
            FROM public.org_units u LEFT JOIN public.hire_approval_unit_modes m USING (unit_id)
            WHERE u.is_active=TRUE ORDER BY u.name, u.unit_id
        """)).mappings().all()
        audits = conn.execute(text("""
            SELECT a.audit_id, a.unit_id, u.name AS unit_name, a.application_id,
                   a.old_mode, a.new_mode, a.changed_at, a.reason,
                   actor.full_name AS changed_by_name
            FROM public.hire_approval_mode_audit a
            JOIN public.org_units u USING (unit_id)
            JOIN public.users actor ON actor.user_id=a.changed_by_user_id
            ORDER BY a.audit_id DESC LIMIT 100
        """)).mappings().all()
    return {"items": [dict(row) for row in rows], "audit": [dict(row) for row in audits]}


@router.put("/{unit_id}")
def change_hire_approval_mode(unit_id: int, body: ModeChangeIn,
                              admin: dict[str, Any] = Depends(require_hire_rollout_admin)) -> dict:
    if body.mode not in {"paper", "electronic"}:
        raise HTTPException(422, "Выберите бумажное или электронное согласование.")
    if not body.reason.strip():
        raise HTTPException(422, "Укажите причину изменения режима.")
    with engine.begin() as conn:
        unit = conn.execute(text("SELECT 1 FROM public.org_units WHERE unit_id=:id AND is_active=TRUE FOR UPDATE"),
                            {"id": unit_id}).scalar_one_or_none()
        if unit is None:
            raise HTTPException(404, "Отделение не найдено или неактивно.")
        old = conn.execute(text("""
            SELECT mode FROM public.hire_approval_unit_modes WHERE unit_id=:id FOR UPDATE
        """), {"id": unit_id}).scalar_one_or_none() or "paper"
        if old == body.mode:
            return {"unit_id": unit_id, "mode": old, "changed": False}
        conn.execute(text("""
            INSERT INTO public.hire_approval_unit_modes (unit_id, mode, updated_by_user_id)
            VALUES (:unit, :mode, :actor)
            ON CONFLICT (unit_id) DO UPDATE SET mode=EXCLUDED.mode,
                updated_by_user_id=EXCLUDED.updated_by_user_id, updated_at=now()
        """), {"unit": unit_id, "mode": body.mode, "actor": int(admin["user_id"])})
        conn.execute(text("""
            INSERT INTO public.hire_approval_mode_audit
                (unit_id, old_mode, new_mode, changed_by_user_id, reason)
            VALUES (:unit, :old, :new, :actor, :reason)
        """), {"unit": unit_id, "old": old, "new": body.mode,
               "actor": int(admin["user_id"]), "reason": body.reason.strip()})
        retained = conn.execute(text("""
            SELECT count(*) FROM public.electronic_hire_applications e
            JOIN public.personnel_applications a USING (application_id)
            WHERE a.intended_org_unit_id=:unit AND e.approval_mode<>:mode
              AND a.status NOT IN ('completed','cancelled','withdrawn','expired')
        """), {"unit": unit_id, "mode": body.mode}).scalar_one()
    return {"unit_id": unit_id, "mode": body.mode, "changed": True,
            "retained_prior_mode_count": int(retained)}
