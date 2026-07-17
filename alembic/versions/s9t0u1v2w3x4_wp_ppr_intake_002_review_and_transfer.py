"""WP-PPR-INTAKE-002: intake review, transfer audit, review_completed status.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
"""
from __future__ import annotations

from alembic import op

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None

_SECTION_REVIEW_STATUSES = (
    "pending",
    "accepted",
    "rework_requested",
    "skipped",
)

_TRANSFER_STATUSES = (
    "pending",
    "completed",
    "failed",
)

_APPLICATION_STATUSES = (
    "registered",
    "intake_pending",
    "intake_submitted",
    "under_review",
    "review_completed",
    "awaiting_director_resolution",
    "resolution_approved",
    "resolution_rejected",
    "completed",
    "withdrawn",
    "cancelled",
)

_TERMINAL_APPLICATION_STATUSES = (
    "completed",
    "withdrawn",
    "cancelled",
    "resolution_rejected",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    review_statuses_sql = _sql_tuple(_SECTION_REVIEW_STATUSES)
    transfer_statuses_sql = _sql_tuple(_TRANSFER_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_intake_section_reviews (
            review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            section_code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            rework_comment TEXT NULL,
            reviewed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            reviewed_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_intake_section_reviews_status
                CHECK (status IN ({review_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_intake_section_reviews_app_section
            ON public.personnel_intake_section_reviews (application_id, section_code)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_intake_section_reviews_application_id
            ON public.personnel_intake_section_reviews (application_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_intake_transfers (
            transfer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT NULL,
            transferred_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            transferred_at TIMESTAMPTZ NULL,
            sections_transferred JSONB NOT NULL DEFAULT '[]'::jsonb,
            command_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_message TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_intake_transfers_status
                CHECK (status IN ({transfer_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_intake_transfers_application_id
            ON public.personnel_intake_transfers (application_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_intake_section_reviews IS
            'WP-PPR-INTAKE-002: HR per-section review of submitted intake draft'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_intake_transfers IS
            'WP-PPR-INTAKE-002: audit log for intake → PPR transfer'
        """
    )

    statuses_sql = _sql_tuple(_APPLICATION_STATUSES)
    op.execute(
        "ALTER TABLE public.personnel_applications DROP CONSTRAINT IF EXISTS chk_personnel_applications_status"
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_applications
            ADD CONSTRAINT chk_personnel_applications_status
                CHECK (status IN ({statuses_sql}))
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_intake_transfers CASCADE")
    op.execute("DROP TABLE IF EXISTS public.personnel_intake_section_reviews CASCADE")

    statuses_sql = _sql_tuple(
        tuple(s for s in _APPLICATION_STATUSES if s != "review_completed")
    )
    op.execute(
        "ALTER TABLE public.personnel_applications DROP CONSTRAINT IF EXISTS chk_personnel_applications_status"
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_applications
            ADD CONSTRAINT chk_personnel_applications_status
                CHECK (status IN ({statuses_sql}))
        """
    )
