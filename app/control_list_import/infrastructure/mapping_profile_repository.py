"""Mapping profile persistence (WP-CL-003).

Profiles are versioned configuration. This repository persists profile definitions only;
it does not apply profiles to staging or write to canonical PPR / Employment stores.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
    MappingProfileSummary,
)
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    PROFILE_STATUS_DRAFT,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


class SqlAlchemyControlListMappingProfileRepository:
    """Minimal mapping profile repository without profile application logic."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create_profile(
        self,
        *,
        profile_code: str,
        profile_version: int,
        profile_name: str,
        created_by: int,
        description: str | None = None,
        status: str = PROFILE_STATUS_DRAFT,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profiles (
                    profile_code,
                    profile_version,
                    profile_name,
                    description,
                    status,
                    created_by
                )
                VALUES (
                    :profile_code,
                    :profile_version,
                    :profile_name,
                    :description,
                    :status,
                    :created_by
                )
                RETURNING profile_id
                """
            ),
            {
                "profile_code": profile_code,
                "profile_version": int(profile_version),
                "profile_name": profile_name,
                "description": description,
                "status": status,
                "created_by": int(created_by),
            },
        ).one()
        return int(row.profile_id)

    def create_profile_sheet(
        self,
        *,
        profile_id: int,
        sheet_name: str,
        personnel_category: str = PERSONNEL_CATEGORY_DOCTOR,
        employment_mode: str = EMPLOYMENT_MODE_PRIMARY,
        sheet_purpose: str = SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        header_row_override: int | None = None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profile_sheets (
                    profile_id,
                    sheet_name,
                    personnel_category,
                    employment_mode,
                    sheet_purpose,
                    header_row_override
                )
                VALUES (
                    :profile_id,
                    :sheet_name,
                    :personnel_category,
                    :employment_mode,
                    :sheet_purpose,
                    :header_row_override
                )
                RETURNING profile_sheet_id
                """
            ),
            {
                "profile_id": int(profile_id),
                "sheet_name": sheet_name,
                "personnel_category": personnel_category,
                "employment_mode": employment_mode,
                "sheet_purpose": sheet_purpose,
                "header_row_override": header_row_override,
            },
        ).one()
        return int(row.profile_sheet_id)

    def create_profile_column(
        self,
        *,
        profile_sheet_id: int,
        column_index: int,
        semantic_field: str,
        parser_code: str,
        column_letter: str | None = None,
        raw_header: str | None = None,
        is_required: bool = False,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profile_columns (
                    profile_sheet_id,
                    column_index,
                    column_letter,
                    raw_header,
                    semantic_field,
                    parser_code,
                    is_required
                )
                VALUES (
                    :profile_sheet_id,
                    :column_index,
                    :column_letter,
                    :raw_header,
                    :semantic_field,
                    :parser_code,
                    :is_required
                )
                RETURNING profile_column_id
                """
            ),
            {
                "profile_sheet_id": int(profile_sheet_id),
                "column_index": int(column_index),
                "column_letter": column_letter,
                "raw_header": raw_header,
                "semantic_field": semantic_field,
                "parser_code": parser_code,
                "is_required": bool(is_required),
            },
        ).one()
        return int(row.profile_column_id)

    def get_profile(
        self,
        *,
        profile_id: int | None = None,
        profile_code: str | None = None,
        profile_version: int | None = None,
    ) -> Optional[MappingProfileSnapshot]:
        if profile_id is not None:
            where_sql = "p.profile_id = :profile_id"
            params: dict[str, object] = {"profile_id": int(profile_id)}
        elif profile_code is not None and profile_version is not None:
            where_sql = "p.profile_code = :profile_code AND p.profile_version = :profile_version"
            params = {
                "profile_code": profile_code,
                "profile_version": int(profile_version),
            }
        else:
            raise ValueError("Provide profile_id or (profile_code and profile_version)")

        profile_row = self._conn.execute(
            text(
                f"""
                SELECT
                    p.profile_id,
                    p.profile_code,
                    p.profile_version,
                    p.profile_name,
                    p.description,
                    p.status,
                    p.created_at,
                    p.created_by,
                    p.updated_at
                FROM public.control_list_mapping_profiles p
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        if profile_row is None:
            return None

        sheet_rows = self._conn.execute(
            text(
                """
                SELECT
                    s.profile_sheet_id,
                    s.profile_id,
                    s.sheet_name,
                    s.personnel_category,
                    s.employment_mode,
                    s.sheet_purpose,
                    s.header_row_override
                FROM public.control_list_mapping_profile_sheets s
                WHERE s.profile_id = :profile_id
                ORDER BY s.sheet_name
                """
            ),
            {"profile_id": int(profile_row["profile_id"])},
        ).mappings().all()

        sheets: list[MappingProfileSheetSnapshot] = []
        for sheet_row in sheet_rows:
            column_rows = self._conn.execute(
                text(
                    """
                    SELECT
                        c.profile_column_id,
                        c.profile_sheet_id,
                        c.column_index,
                        c.column_letter,
                        c.raw_header,
                        c.semantic_field,
                        c.parser_code,
                        c.is_required
                    FROM public.control_list_mapping_profile_columns c
                    WHERE c.profile_sheet_id = :profile_sheet_id
                    ORDER BY c.column_index
                    """
                ),
                {"profile_sheet_id": int(sheet_row["profile_sheet_id"])},
            ).mappings().all()
            sheets.append(
                MappingProfileSheetSnapshot(
                    profile_sheet_id=int(sheet_row["profile_sheet_id"]),
                    profile_id=int(sheet_row["profile_id"]),
                    sheet_name=str(sheet_row["sheet_name"]),
                    personnel_category=str(sheet_row["personnel_category"]),
                    employment_mode=str(sheet_row["employment_mode"]),
                    sheet_purpose=str(sheet_row["sheet_purpose"]),
                    header_row_override=(
                        int(sheet_row["header_row_override"])
                        if sheet_row["header_row_override"] is not None
                        else None
                    ),
                    columns=[
                        MappingProfileColumnSnapshot(
                            profile_column_id=int(col["profile_column_id"]),
                            profile_sheet_id=int(col["profile_sheet_id"]),
                            column_index=int(col["column_index"]),
                            column_letter=col["column_letter"],
                            raw_header=col["raw_header"],
                            semantic_field=str(col["semantic_field"]),
                            parser_code=str(col["parser_code"]),
                            is_required=bool(col["is_required"]),
                        )
                        for col in column_rows
                    ],
                )
            )

        return MappingProfileSnapshot(
            profile_id=int(profile_row["profile_id"]),
            profile_code=str(profile_row["profile_code"]),
            profile_version=int(profile_row["profile_version"]),
            profile_name=str(profile_row["profile_name"]),
            description=profile_row["description"],
            status=str(profile_row["status"]),
            created_at=profile_row["created_at"],
            created_by=int(profile_row["created_by"]),
            updated_at=profile_row["updated_at"],
            sheets=sheets,
        )

    def list_active_profiles(self) -> list[MappingProfileSummary]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    profile_id,
                    profile_code,
                    profile_version,
                    profile_name,
                    status,
                    created_at
                FROM public.control_list_mapping_profiles
                WHERE status = :status
                ORDER BY profile_code, profile_version DESC
                """
            ),
            {"status": PROFILE_STATUS_ACTIVE},
        ).mappings().all()
        return [
            MappingProfileSummary(
                profile_id=int(row["profile_id"]),
                profile_code=str(row["profile_code"]),
                profile_version=int(row["profile_version"]),
                profile_name=str(row["profile_name"]),
                status=str(row["status"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
