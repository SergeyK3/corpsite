"""Section lifecycle aggregation for composite read (R6 — read-only)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_migration import (
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
)
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
    SectionRecord,
)
from app.ppr.domain.section_repositories import SectionReadRepository
from app.ppr.infrastructure.section_repository import (
    _SECTION_SELECTS,
    _resolve_section,
    _row_to_record,
    section_records_order_by,
)
from app.ppr.read.models import PprSectionAggregation


class PprSectionAggregationReader:
    """Aggregates section records by lifecycle bucket using read repositories."""

    def __init__(self, sections: SectionReadRepository, conn: Connection) -> None:
        self._sections = sections
        self._conn = conn

    def load_section(
        self,
        person_id: int,
        section_code: str,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        active = self._sections.load_active_records(person_id, section_code)
        superseded: tuple[SectionRecord, ...] = ()
        voided: tuple[SectionRecord, ...] = ()
        if include_superseded:
            superseded = self._load_by_lifecycle(person_id, section_code, LIFECYCLE_STATUS_SUPERSEDED)
        if include_voided:
            voided = self._load_by_lifecycle(person_id, section_code, LIFECYCLE_STATUS_VOIDED)
        return PprSectionAggregation(
            section_code=section_code,
            active=active,
            superseded=superseded,
            voided=voided,
        )

    def load_education(
        self,
        person_id: int,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        return self.load_section(
            person_id,
            SECTION_CODE_PPR_EDUCATION,
            include_superseded=include_superseded,
            include_voided=include_voided,
        )

    def load_training(
        self,
        person_id: int,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        return self.load_section(
            person_id,
            SECTION_CODE_PPR_TRAINING,
            include_superseded=include_superseded,
            include_voided=include_voided,
        )

    def load_family(
        self,
        person_id: int,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        return self.load_section(
            person_id,
            SECTION_CODE_PPR_FAMILY,
            include_superseded=include_superseded,
            include_voided=include_voided,
        )

    def load_external_employment(
        self,
        person_id: int,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        return self.load_section(
            person_id,
            SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
            include_superseded=include_superseded,
            include_voided=include_voided,
        )

    def load_military(
        self,
        person_id: int,
        *,
        include_superseded: bool = True,
        include_voided: bool = True,
    ) -> PprSectionAggregation:
        return self.load_section(
            person_id,
            SECTION_CODE_PPR_MILITARY,
            include_superseded=include_superseded,
            include_voided=include_voided,
        )

    def _load_by_lifecycle(
        self,
        person_id: int,
        section_code: str,
        lifecycle_status: str,
    ) -> tuple[SectionRecord, ...]:
        if lifecycle_status == LIFECYCLE_STATUS_ACTIVE:
            return self._sections.load_active_records(person_id, section_code)
        spec = _resolve_section(section_code)
        select_cols = _SECTION_SELECTS[section_code]
        rows = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {select_cols}
                    FROM public.{spec['table']}
                    WHERE person_id = :person_id
                      AND lifecycle_status = :lifecycle_status
                    ORDER BY {section_records_order_by(section_code, spec['id_col'])}
                    """
                ),
                {
                    "person_id": int(person_id),
                    "lifecycle_status": lifecycle_status,
                },
            )
            .mappings()
            .all()
        )
        return tuple(_row_to_record(section_code, row) for row in rows)
