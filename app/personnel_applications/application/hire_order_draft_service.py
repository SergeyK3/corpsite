"""Create draft HIRE personnel order bound to application (WP-PPR-APPLICANT-002)."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ORDER_STATUS_DRAFT,
    ORDER_TYPE_HIRE,
    SOURCE_MODE_DIGITAL,
)
from app.personnel_applications.domain.errors import PersonnelApplicationHireOrderError
from app.personnel_applications.domain.models import HireOrderDraftResult, PersonnelApplicationSnapshot
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.services.personnel_order_hire_from_person_service import validate_hire_person_candidate


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now_utc().date()


def _table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _build_hire_payload(app: PersonnelApplicationSnapshot) -> dict:
    payload: dict = {"person_id": app.person_id}
    if app.intended_org_unit_id is not None:
        payload["org_unit_id"] = int(app.intended_org_unit_id)
    if app.intended_position_id is not None:
        payload["position_id"] = int(app.intended_position_id)
    if app.intended_employment_rate is not None:
        payload["employment_rate"] = float(app.intended_employment_rate)
    if app.intended_org_group_id is not None:
        payload["org_group_id"] = int(app.intended_org_group_id)
    return payload


def _create_draft_hire_order(
    conn: Connection,
    *,
    application_id: int,
    person_id: int,
    payload: dict,
    created_by_user_id: int,
) -> int:
    if not _table_exists(conn, "personnel_orders") or not _table_exists(conn, "personnel_order_items"):
        raise PersonnelApplicationHireOrderError(
            "Personnel orders schema is not available.",
            code="PERSONNEL_ORDERS_UNAVAILABLE",
        )

    validate_hire_person_candidate(conn, person_id)

    order_id = conn.execute(
        text(
            """
            INSERT INTO public.personnel_orders (
                order_number,
                order_date,
                order_type_code,
                status,
                source_mode,
                comment,
                created_by
            )
            VALUES (
                NULL,
                :order_date,
                :order_type_code,
                :status,
                :source_mode,
                :comment,
                :created_by
            )
            RETURNING order_id
            """
        ),
        {
            "order_date": _today(),
            "order_type_code": ORDER_TYPE_HIRE,
            "status": ORDER_STATUS_DRAFT,
            "source_mode": SOURCE_MODE_DIGITAL,
            "comment": f"Draft HIRE order for personnel application #{application_id}",
            "created_by": int(created_by_user_id),
        },
    ).scalar_one()

    conn.execute(
        text(
            """
            INSERT INTO public.personnel_order_items (
                order_id,
                item_number,
                item_type_code,
                employee_id,
                effective_date,
                payload,
                item_status
            )
            VALUES (
                :order_id,
                1,
                :item_type_code,
                NULL,
                :effective_date,
                CAST(:payload AS jsonb),
                :item_status
            )
            """
        ),
        {
            "order_id": int(order_id),
            "item_type_code": ORDER_TYPE_HIRE,
            "effective_date": _today(),
            "payload": json.dumps(payload),
            "item_status": ITEM_STATUS_ACTIVE,
        },
    )
    return int(order_id)


def create_hire_order_draft_for_application(
    conn: Connection,
    *,
    application_id: int,
    created_by_user_id: int,
) -> HireOrderDraftResult:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)

    if app.personnel_order_id is not None:
        if app.status not in {APPLICATION_STATUS_APPROVED, APPLICATION_STATUS_ORDER_DRAFT_CREATED}:
            raise PersonnelApplicationHireOrderError(
                "Application already has a linked personnel order.",
                code="ORDER_ALREADY_LINKED",
            )
        return HireOrderDraftResult(
            application_id=application_id,
            personnel_order_id=int(app.personnel_order_id),
            idempotent_replay=True,
            application_status=app.status,
        )

    if app.status != APPLICATION_STATUS_APPROVED:
        raise PersonnelApplicationHireOrderError(
            f"HIRE draft can only be created after approval (status={app.status}).",
            code="HIRE_DRAFT_NOT_ALLOWED",
        )

    if app.intended_org_unit_id is None or app.intended_position_id is None:
        raise PersonnelApplicationHireOrderError(
            "Intended org unit and position are required to create HIRE draft.",
            code="HIRE_DRAFT_PLACEMENT_REQUIRED",
        )

    payload = _build_hire_payload(app)
    order_id = _create_draft_hire_order(
        conn,
        application_id=application_id,
        person_id=app.person_id,
        payload=payload,
        created_by_user_id=created_by_user_id,
    )

    now = _now_utc()
    updated = app_repo.update_application_fields(
        application_id,
        status=APPLICATION_STATUS_ORDER_DRAFT_CREATED,
        personnel_order_id=order_id,
        now=now,
    )
    return HireOrderDraftResult(
        application_id=application_id,
        personnel_order_id=order_id,
        idempotent_replay=False,
        application_status=updated.status,
    )
