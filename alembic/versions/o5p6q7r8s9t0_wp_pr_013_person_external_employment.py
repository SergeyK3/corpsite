"""WP-PR-013: person_external_employment table for PPR-EMPLOYMENT-BIOGRAPHY.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
"""
from __future__ import annotations

from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None

_RECORD_KINDS = (
    "episode",
    "narrative_summary",
    "attestation_none",
)

_EMPLOYMENT_TYPES = (
    "primary",
    "part_time",
    "contract",
    "internship",
    "other",
)

_SOURCE_SYSTEMS = (
    "manual",
    "import_row",
    "pmf_migration",
    "integration",
)

_VERIFICATION_STATUSES = (
    "pending",
    "verified",
    "disputed",
)

# ADR-056 §12.1: active | superseded | voided (no draft — PMF wizard draft stays on migration_items).
_LIFECYCLE_STATUSES = (
    "active",
    "superseded",
    "voided",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    record_kinds_sql = _sql_tuple(_RECORD_KINDS)
    employment_types_sql = _sql_tuple(_EMPLOYMENT_TYPES)
    source_systems_sql = _sql_tuple(_SOURCE_SYSTEMS)
    verification_statuses_sql = _sql_tuple(_VERIFICATION_STATUSES)
    lifecycle_statuses_sql = _sql_tuple(_LIFECYCLE_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.person_external_employment (
            employment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            record_kind TEXT NOT NULL,
            employer_name TEXT NULL,
            department_name TEXT NULL,
            position_title TEXT NULL,
            employment_type TEXT NULL,
            started_at DATE NULL,
            ended_at DATE NULL,
            termination_reason TEXT NULL,
            document_reference TEXT NULL,
            source_system TEXT NOT NULL DEFAULT 'manual',
            source_id TEXT NULL,
            provenance JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            verification_status TEXT NOT NULL DEFAULT 'pending',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            notes TEXT NULL,
            employee_context_id BIGINT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_person_external_employment_record_kind
                CHECK (record_kind IN ({record_kinds_sql})),
            CONSTRAINT chk_person_external_employment_employment_type
                CHECK (
                    employment_type IS NULL
                    OR employment_type IN ({employment_types_sql})
                ),
            CONSTRAINT chk_person_external_employment_source_system
                CHECK (source_system IN ({source_systems_sql})),
            CONSTRAINT chk_person_external_employment_verification_status
                CHECK (verification_status IN ({verification_statuses_sql})),
            CONSTRAINT chk_person_external_employment_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_statuses_sql})),
            CONSTRAINT chk_person_external_employment_date_order
                CHECK (
                    started_at IS NULL
                    OR ended_at IS NULL
                    OR ended_at >= started_at
                ),
            CONSTRAINT chk_person_external_employment_episode_fields
                CHECK (
                    record_kind <> 'episode'
                    OR (
                        btrim(coalesce(employer_name, '')) <> ''
                        AND btrim(coalesce(position_title, '')) <> ''
                        AND (
                            started_at IS NOT NULL
                            OR btrim(coalesce(notes, '')) <> ''
                        )
                    )
                ),
            CONSTRAINT chk_person_external_employment_narrative_notes
                CHECK (
                    record_kind <> 'narrative_summary'
                    OR btrim(coalesce(notes, '')) <> ''
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_external_employment_person_id
            ON public.person_external_employment (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_external_employment_person_lifecycle
            ON public.person_external_employment (person_id, lifecycle_status)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_external_employment IS
            'WP-PR-013 / ADR-056: external employment biography (PPR-EMPLOYMENT-BIOGRAPHY, person-owned SoT).'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.person_external_employment CASCADE")
