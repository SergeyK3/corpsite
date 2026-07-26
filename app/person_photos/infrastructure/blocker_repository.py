"""Repository for personnel_application_blockers (ADR-061 photo apply gates)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.person_photos import (
    BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
    BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
)

_PHOTO_BLOCKER_CODES = (
    BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
    BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
)


class PersonPhotoBlockerRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_open_blocker(
        self,
        *,
        application_id: int,
        blocker_code: str,
        detail_json: dict[str, Any] | None = None,
    ) -> None:
        payload = detail_json or {}
        self._conn.execute(
            text(
                """
                INSERT INTO public.personnel_application_blockers (
                    application_id, blocker_code, detail_json
                ) VALUES (
                    :application_id, :blocker_code, CAST(:detail_json AS jsonb)
                )
                ON CONFLICT (application_id, blocker_code) WHERE resolved_at IS NULL
                DO UPDATE SET detail_json = EXCLUDED.detail_json
                """
            ),
            {
                "application_id": int(application_id),
                "blocker_code": blocker_code,
                "detail_json": _json_payload(payload),
            },
        )

    def resolve_photo_blockers(
        self,
        *,
        application_id: int,
        resolved_by_user_id: int,
    ) -> None:
        now = datetime.now(UTC)
        self._conn.execute(
            text(
                """
                UPDATE public.personnel_application_blockers
                SET resolved_at = :resolved_at,
                    resolved_by_user_id = :resolved_by_user_id
                WHERE application_id = :application_id
                  AND blocker_code = ANY(:blocker_codes)
                  AND resolved_at IS NULL
                """
            ),
            {
                "application_id": int(application_id),
                "blocker_codes": list(_PHOTO_BLOCKER_CODES),
                "resolved_at": now,
                "resolved_by_user_id": int(resolved_by_user_id),
            },
        )


def _json_payload(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
