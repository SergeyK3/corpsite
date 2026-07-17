"""WP-PPR-APPLICANT-004: lifecycle archive — expired status, closed_at, lifecycle audit.

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
"""
from __future__ import annotations

from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None

_LIFECYCLE_ACTIONS = (
    "registered",
    "intake_link_issued",
    "intake_opened",
    "intake_submitted",
    "review_started",
    "review_completed",
    "intake_transferred",
    "resolution_opened",
    "resolution_recorded",
    "resolution_changed",
    "resolution_reopened",
    "hire_order_draft_created",
    "hire_applied",
    "completed",
    "rejected",
    "cancelled",
    "expired",
)

_APPLICATION_STATUSES = (
    "registered",
    "intake_pending",
    "intake_submitted",
    "under_review",
    "review_completed",
    "resolution_pending",
    "approved",
    "rejected",
    "revision_requested",
    "order_draft_created",
    "awaiting_director_resolution",
    "resolution_approved",
    "resolution_rejected",
    "completed",
    "withdrawn",
    "cancelled",
    "expired",
)

_TERMINAL_APPLICATION_STATUSES = (
    "completed",
    "withdrawn",
    "cancelled",
    "resolution_rejected",
    "rejected",
    "expired",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_applications
            ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS cancel_reason TEXT NULL,
            ADD COLUMN IF NOT EXISTS cancelled_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS closed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT
        """
    )

    actions_sql = _sql_tuple(_LIFECYCLE_ACTIONS)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_application_lifecycle_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            previous_status TEXT NULL,
            new_status TEXT NULL,
            comment TEXT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            metadata JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_application_lifecycle_audit_action
                CHECK (action IN ({actions_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_application_lifecycle_audit_application_id
            ON public.personnel_application_lifecycle_audit (application_id, created_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_application_lifecycle_audit IS
            'WP-PPR-APPLICANT-004: audit log for application lifecycle transitions'
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

    terminal_sql = _sql_tuple(_TERMINAL_APPLICATION_STATUSES)
    op.execute(
        "DROP INDEX IF EXISTS public.uq_personnel_applications_one_active_per_person"
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_applications_one_active_per_person
            ON public.personnel_applications (person_id)
            WHERE status NOT IN ({terminal_sql})
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.personnel_applications
        SET status = 'cancelled'
        WHERE status = 'expired'
        """
    )

    op.execute("DROP TABLE IF EXISTS public.personnel_application_lifecycle_audit CASCADE")

    op.execute(
        """
        ALTER TABLE public.personnel_applications
            DROP COLUMN IF EXISTS completed_at,
            DROP COLUMN IF EXISTS closed_at,
            DROP COLUMN IF EXISTS cancel_reason,
            DROP COLUMN IF EXISTS cancelled_by_user_id,
            DROP COLUMN IF EXISTS closed_by_user_id
        """
    )

    statuses_sql = _sql_tuple(
        tuple(s for s in _APPLICATION_STATUSES if s != "expired")
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

    terminal_sql = _sql_tuple(
        tuple(s for s in _TERMINAL_APPLICATION_STATUSES if s != "expired")
    )
    op.execute(
        "DROP INDEX IF EXISTS public.uq_personnel_applications_one_active_per_person"
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_applications_one_active_per_person
            ON public.personnel_applications (person_id)
            WHERE status NOT IN ({terminal_sql})
        """
    )
