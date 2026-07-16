"""WP-PR-P4-001-A: person_relatives table for PPR-FAMILY section.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
"""
from __future__ import annotations

from alembic import op

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None

_RELATIONSHIP_TYPES = (
    # Phase 1 per WP-PR-P4-001 §4.2; extend additively via future migration.
    "father",
    "mother",
    "brother",
    "sister",
    "son",
    "daughter",
    "spouse",
    "other_close",
)

# Align with PMF-1 person_education / person_training (personnel_migration.py).
_VERIFICATION_STATUSES = (
    "pending",
    "verified",
    "needs_attention",
    "rejected",
)

_LIFECYCLE_STATUSES = (
    "draft",
    "active",
    "superseded",
    "voided",
)

_SOURCE_TYPES = (
    "entered",
    "imported",
    "normalized",
    "derived",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    relationship_types_sql = _sql_tuple(_RELATIONSHIP_TYPES)
    verification_statuses_sql = _sql_tuple(_VERIFICATION_STATUSES)
    lifecycle_statuses_sql = _sql_tuple(_LIFECYCLE_STATUSES)
    source_types_sql = _sql_tuple(_SOURCE_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.person_relatives (
            relative_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            relationship_type TEXT NOT NULL,
            full_name TEXT NOT NULL,
            birth_date DATE NULL,
            birth_place TEXT NULL,
            organization_name TEXT NULL,
            residence_address TEXT NULL,
            notes TEXT NULL,
            verification_status TEXT NOT NULL DEFAULT 'pending',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            source_type TEXT NOT NULL DEFAULT 'entered',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_person_relatives_relationship_type
                CHECK (relationship_type IN ({relationship_types_sql})),
            CONSTRAINT chk_person_relatives_full_name
                CHECK (btrim(full_name) <> ''),
            CONSTRAINT chk_person_relatives_verification_status
                CHECK (verification_status IN ({verification_statuses_sql})),
            CONSTRAINT chk_person_relatives_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_statuses_sql})),
            CONSTRAINT chk_person_relatives_source_type
                CHECK (source_type IN ({source_types_sql})),
            CONSTRAINT chk_person_relatives_birth_date
                CHECK (birth_date IS NULL OR birth_date <= CURRENT_DATE)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_relatives_person_id
            ON public.person_relatives (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_relatives_person_lifecycle
            ON public.person_relatives (person_id, lifecycle_status)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_relatives IS
            'WP-PR-P4-001: permanent family/relative records (PPR-FAMILY, person-owned SoT).'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.person_relatives CASCADE")
