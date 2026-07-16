"""WP-PR-027: person_military_service table for PPR-MILITARY section.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
"""
from __future__ import annotations

from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None

_RECORD_KINDS = (
    "registration",
    "not_applicable",
)

# WP-PR-026 §10.1: no draft — wizard draft stays on migration_items.
_LIFECYCLE_STATUSES = (
    "active",
    "superseded",
    "voided",
)

# Common PPR verification set (person_education / person_relatives pattern).
_VERIFICATION_STATUSES = (
    "pending",
    "verified",
    "needs_attention",
    "rejected",
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
    record_kinds_sql = _sql_tuple(_RECORD_KINDS)
    lifecycle_statuses_sql = _sql_tuple(_LIFECYCLE_STATUSES)
    verification_statuses_sql = _sql_tuple(_VERIFICATION_STATUSES)
    source_types_sql = _sql_tuple(_SOURCE_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.person_military_service (
            military_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            record_kind TEXT NOT NULL,
            obligation_status TEXT NULL,
            registration_category TEXT NULL,
            military_rank TEXT NULL,
            military_specialty_code TEXT NULL,
            personnel_composition TEXT NULL,
            fitness_category TEXT NULL,
            registration_status TEXT NULL,
            commissariat_name TEXT NULL,
            registered_at DATE NULL,
            deregistered_at DATE NULL,
            military_id_book_series TEXT NULL,
            military_id_book_number TEXT NULL,
            registration_certificate_series TEXT NULL,
            registration_certificate_number TEXT NULL,
            notes TEXT NULL,
            verification_status TEXT NOT NULL DEFAULT 'pending',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            source_type TEXT NOT NULL DEFAULT 'entered',
            provenance JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            employee_context_id BIGINT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_person_military_service_record_kind
                CHECK (record_kind IN ({record_kinds_sql})),
            CONSTRAINT chk_person_military_service_verification_status
                CHECK (verification_status IN ({verification_statuses_sql})),
            CONSTRAINT chk_person_military_service_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_statuses_sql})),
            CONSTRAINT chk_person_military_service_source_type
                CHECK (source_type IN ({source_types_sql})),
            CONSTRAINT chk_person_military_service_date_order
                CHECK (
                    registered_at IS NULL
                    OR deregistered_at IS NULL
                    OR deregistered_at >= registered_at
                ),
            CONSTRAINT chk_person_military_service_registration_structured
                CHECK (
                    record_kind <> 'registration'
                    OR (
                        btrim(coalesce(obligation_status, '')) <> ''
                        OR btrim(coalesce(registration_category, '')) <> ''
                        OR btrim(coalesce(military_rank, '')) <> ''
                        OR btrim(coalesce(registration_status, '')) <> ''
                    )
                ),
            CONSTRAINT chk_person_military_service_not_applicable_fields
                CHECK (
                    record_kind <> 'not_applicable'
                    OR (
                        obligation_status IS NULL
                        AND registration_category IS NULL
                        AND military_rank IS NULL
                        AND military_specialty_code IS NULL
                        AND personnel_composition IS NULL
                        AND fitness_category IS NULL
                        AND registration_status IS NULL
                        AND commissariat_name IS NULL
                        AND registered_at IS NULL
                        AND deregistered_at IS NULL
                        AND military_id_book_series IS NULL
                        AND military_id_book_number IS NULL
                        AND registration_certificate_series IS NULL
                        AND registration_certificate_number IS NULL
                    )
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_military_service_person_id
            ON public.person_military_service (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_military_service_person_lifecycle
            ON public.person_military_service (person_id, lifecycle_status)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_person_military_service_one_active_per_person
            ON public.person_military_service (person_id)
            WHERE lifecycle_status = 'active'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_military_service IS
            'WP-PR-027 / WP-PR-026: military registration (PPR-MILITARY, person-owned SoT).'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.person_military_service CASCADE")
