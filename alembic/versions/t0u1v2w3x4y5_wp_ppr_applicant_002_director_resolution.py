"""WP-PPR-APPLICANT-002: director resolution audit + applicant workflow statuses.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
"""
from __future__ import annotations

from alembic import op

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None

_RESOLUTION_ACTIONS = (
    "opened",
    "recorded",
    "changed",
    "reopened",
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
)

_TERMINAL_APPLICATION_STATUSES = (
    "completed",
    "withdrawn",
    "cancelled",
    "resolution_rejected",
    "rejected",
)

_DIRECTOR_RESOLUTION_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "revision_requested",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    actions_sql = _sql_tuple(_RESOLUTION_ACTIONS)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_application_resolution_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            previous_application_status TEXT NULL,
            new_application_status TEXT NOT NULL,
            previous_resolution_status TEXT NULL,
            new_resolution_status TEXT NULL,
            comment TEXT NULL,
            actor_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_application_resolution_audit_action
                CHECK (action IN ({actions_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_application_resolution_audit_application_id
            ON public.personnel_application_resolution_audit (application_id, created_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_application_resolution_audit IS
            'WP-PPR-APPLICANT-002: audit log for director resolution workflow'
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

    resolution_sql = _sql_tuple(_DIRECTOR_RESOLUTION_STATUSES)
    op.execute(
        """
        ALTER TABLE public.personnel_applications
            DROP CONSTRAINT IF EXISTS chk_personnel_applications_director_resolution_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_applications
            ADD CONSTRAINT chk_personnel_applications_director_resolution_status
                CHECK (
                    director_resolution_status IS NULL
                    OR director_resolution_status IN ({resolution_sql})
                )
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
    op.execute("DROP TABLE IF EXISTS public.personnel_application_resolution_audit CASCADE")

    op.execute(
        """
        UPDATE public.personnel_applications
        SET status = 'awaiting_director_resolution'
        WHERE status = 'resolution_pending'
        """
    )
    op.execute(
        """
        UPDATE public.personnel_applications
        SET status = 'resolution_approved'
        WHERE status IN ('approved', 'order_draft_created')
        """
    )
    op.execute(
        """
        UPDATE public.personnel_applications
        SET status = 'resolution_rejected'
        WHERE status = 'rejected'
        """
    )
    op.execute(
        """
        UPDATE public.personnel_applications
        SET status = 'awaiting_director_resolution'
        WHERE status = 'revision_requested'
        """
    )
    op.execute(
        """
        UPDATE public.personnel_applications
        SET director_resolution_status = 'rejected'
        WHERE director_resolution_status = 'revision_requested'
        """
    )

    statuses_sql = _sql_tuple(
        tuple(
            s
            for s in _APPLICATION_STATUSES
            if s
            not in {
                "resolution_pending",
                "approved",
                "rejected",
                "revision_requested",
                "order_draft_created",
            }
        )
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

    resolution_sql = _sql_tuple(("pending", "approved", "rejected"))
    op.execute(
        """
        ALTER TABLE public.personnel_applications
            DROP CONSTRAINT IF EXISTS chk_personnel_applications_director_resolution_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_applications
            ADD CONSTRAINT chk_personnel_applications_director_resolution_status
                CHECK (
                    director_resolution_status IS NULL
                    OR director_resolution_status IN ({resolution_sql})
                )
        """
    )

    terminal_sql = _sql_tuple(("completed", "withdrawn", "cancelled", "resolution_rejected"))
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
