"""SQLAlchemy repository for intake review and transfer audit."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping

from app.db.models.personnel_intake import PersonnelIntakeSectionReview, PersonnelIntakeTransfer
from app.personnel_intake.domain.models import IntakeSectionReviewSnapshot, IntakeTransferSnapshot
from app.personnel_intake.domain.review_status import (
    INTAKE_REVIEW_SECTIONS,
    INTAKE_SECTION_REVIEW_PENDING,
    INTAKE_TRANSFER_STATUS_COMPLETED,
    INTAKE_TRANSFER_STATUS_FAILED,
    INTAKE_TRANSFER_STATUS_PENDING,
)

_REVIEW_COLUMNS = (
    PersonnelIntakeSectionReview.review_id,
    PersonnelIntakeSectionReview.application_id,
    PersonnelIntakeSectionReview.section_code,
    PersonnelIntakeSectionReview.status,
    PersonnelIntakeSectionReview.rework_comment,
    PersonnelIntakeSectionReview.reviewed_by_user_id,
    PersonnelIntakeSectionReview.reviewed_at,
    PersonnelIntakeSectionReview.created_at,
    PersonnelIntakeSectionReview.updated_at,
)

_TRANSFER_COLUMNS = (
    PersonnelIntakeTransfer.transfer_id,
    PersonnelIntakeTransfer.application_id,
    PersonnelIntakeTransfer.status,
    PersonnelIntakeTransfer.result,
    PersonnelIntakeTransfer.transferred_by_user_id,
    PersonnelIntakeTransfer.transferred_at,
    PersonnelIntakeTransfer.sections_transferred,
    PersonnelIntakeTransfer.command_ids,
    PersonnelIntakeTransfer.error_message,
    PersonnelIntakeTransfer.created_at,
    PersonnelIntakeTransfer.updated_at,
)


def _review_from_row(row: RowMapping | dict[str, Any]) -> IntakeSectionReviewSnapshot:
    return IntakeSectionReviewSnapshot(
        review_id=int(row["review_id"]),
        application_id=int(row["application_id"]),
        section_code=str(row["section_code"]),
        status=str(row["status"]),
        rework_comment=row.get("rework_comment"),
        reviewed_by_user_id=(
            int(row["reviewed_by_user_id"]) if row.get("reviewed_by_user_id") is not None else None
        ),
        reviewed_at=row.get("reviewed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _transfer_from_row(row: RowMapping | dict[str, Any]) -> IntakeTransferSnapshot:
    sections = row.get("sections_transferred") or []
    command_ids = row.get("command_ids") or []
    return IntakeTransferSnapshot(
        transfer_id=int(row["transfer_id"]),
        application_id=int(row["application_id"]),
        status=str(row["status"]),
        result=str(row["result"]) if row.get("result") is not None else None,
        transferred_by_user_id=(
            int(row["transferred_by_user_id"])
            if row.get("transferred_by_user_id") is not None
            else None
        ),
        transferred_at=row.get("transferred_at"),
        sections_transferred=[str(s) for s in sections],
        command_ids=[str(c) for c in command_ids],
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlAlchemyPersonnelIntakeReviewRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def ensure_section_reviews(self, application_id: int, *, now: datetime) -> list[IntakeSectionReviewSnapshot]:
        existing = self.list_section_reviews(application_id)
        existing_codes = {row.section_code for row in existing}
        for section_code in INTAKE_REVIEW_SECTIONS:
            if section_code in existing_codes:
                continue
            self._conn.execute(
                pg_insert(PersonnelIntakeSectionReview)
                .values(
                    application_id=int(application_id),
                    section_code=section_code,
                    status=INTAKE_SECTION_REVIEW_PENDING,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["application_id", "section_code"],
                )
            )
        return self.list_section_reviews(application_id)

    def list_section_reviews(self, application_id: int) -> list[IntakeSectionReviewSnapshot]:
        stmt = (
            select(*_REVIEW_COLUMNS)
            .where(PersonnelIntakeSectionReview.application_id == int(application_id))
            .order_by(PersonnelIntakeSectionReview.section_code.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_review_from_row(row) for row in rows]

    def update_section_review(
        self,
        application_id: int,
        section_code: str,
        *,
        status: str,
        reviewed_by_user_id: int,
        reviewed_at: datetime,
        rework_comment: str | None = None,
    ) -> IntakeSectionReviewSnapshot:
        stmt = (
            update(PersonnelIntakeSectionReview)
            .where(
                PersonnelIntakeSectionReview.application_id == int(application_id),
                PersonnelIntakeSectionReview.section_code == section_code,
            )
            .values(
                status=status,
                rework_comment=rework_comment,
                reviewed_by_user_id=int(reviewed_by_user_id),
                reviewed_at=reviewed_at,
                updated_at=reviewed_at,
            )
            .returning(*_REVIEW_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _review_from_row(row)

    def get_transfer(self, application_id: int) -> IntakeTransferSnapshot | None:
        stmt = select(*_TRANSFER_COLUMNS).where(
            PersonnelIntakeTransfer.application_id == int(application_id)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _transfer_from_row(row)

    def list_transfers(self, *, limit: int = 100, offset: int = 0) -> list[IntakeTransferSnapshot]:
        stmt = (
            select(*_TRANSFER_COLUMNS)
            .order_by(PersonnelIntakeTransfer.created_at.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_transfer_from_row(row) for row in rows]

    def ensure_transfer_row(self, application_id: int, *, now: datetime) -> IntakeTransferSnapshot:
        existing = self.get_transfer(application_id)
        if existing is not None:
            return existing
        stmt = (
            pg_insert(PersonnelIntakeTransfer)
            .values(
                application_id=int(application_id),
                status=INTAKE_TRANSFER_STATUS_PENDING,
                created_at=now,
                updated_at=now,
            )
            .returning(*_TRANSFER_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _transfer_from_row(row)

    def mark_transfer_completed(
        self,
        application_id: int,
        *,
        transferred_by_user_id: int,
        transferred_at: datetime,
        sections_transferred: list[str],
        command_ids: list[str],
    ) -> IntakeTransferSnapshot:
        stmt = (
            update(PersonnelIntakeTransfer)
            .where(PersonnelIntakeTransfer.application_id == int(application_id))
            .values(
                status=INTAKE_TRANSFER_STATUS_COMPLETED,
                result="success",
                transferred_by_user_id=int(transferred_by_user_id),
                transferred_at=transferred_at,
                sections_transferred=sections_transferred,
                command_ids=command_ids,
                error_message=None,
                updated_at=transferred_at,
            )
            .returning(*_TRANSFER_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _transfer_from_row(row)

    def mark_transfer_failed(
        self,
        application_id: int,
        *,
        transferred_by_user_id: int,
        failed_at: datetime,
        sections_transferred: list[str],
        command_ids: list[str],
        error_message: str,
    ) -> IntakeTransferSnapshot:
        stmt = (
            update(PersonnelIntakeTransfer)
            .where(PersonnelIntakeTransfer.application_id == int(application_id))
            .values(
                status=INTAKE_TRANSFER_STATUS_FAILED,
                result="failure",
                transferred_by_user_id=int(transferred_by_user_id),
                transferred_at=failed_at,
                sections_transferred=sections_transferred,
                command_ids=command_ids,
                error_message=error_message,
                updated_at=failed_at,
            )
            .returning(*_TRANSFER_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _transfer_from_row(row)

    def reset_transfer_for_retry(self, application_id: int, *, now: datetime) -> IntakeTransferSnapshot:
        stmt = (
            update(PersonnelIntakeTransfer)
            .where(
                PersonnelIntakeTransfer.application_id == int(application_id),
                PersonnelIntakeTransfer.status == INTAKE_TRANSFER_STATUS_FAILED,
            )
            .values(
                status=INTAKE_TRANSFER_STATUS_PENDING,
                result=None,
                error_message=None,
                updated_at=now,
            )
            .returning(*_TRANSFER_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return self.ensure_transfer_row(application_id, now=now)
        return _transfer_from_row(row)
