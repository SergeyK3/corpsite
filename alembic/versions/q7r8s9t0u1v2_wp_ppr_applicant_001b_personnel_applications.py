"""WP-PPR-APPLICANT-001B: personnel_applications table foundation.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
"""
from __future__ import annotations

from alembic import op

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None

_APPLICATION_STATUSES = (
    "registered",
    "intake_pending",
    "intake_submitted",
    "under_review",
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

_APPLICATION_SOURCES = ("paper",)

_VACANCY_CHECK_STATUSES = (
    "pending",
    "confirmed_visually",
    "not_confirmed",
)

_DIRECTOR_RESOLUTION_STATUSES = (
    "pending",
    "approved",
    "rejected",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    statuses_sql = _sql_tuple(_APPLICATION_STATUSES)
    terminal_sql = _sql_tuple(_TERMINAL_APPLICATION_STATUSES)
    sources_sql = _sql_tuple(_APPLICATION_SOURCES)
    vacancy_sql = _sql_tuple(_VACANCY_CHECK_STATUSES)
    director_sql = _sql_tuple(_DIRECTOR_RESOLUTION_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_applications (
            application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'registered',
            application_received_at DATE NOT NULL,
            application_source TEXT NOT NULL DEFAULT 'paper',
            vacancy_check_status TEXT NOT NULL DEFAULT 'pending',
            vacancy_checked_at TIMESTAMPTZ NULL,
            vacancy_checked_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            intended_org_group_id BIGINT NULL
                REFERENCES public.deps_group (group_id) ON DELETE RESTRICT,
            intended_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            intended_position_id BIGINT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            intended_employment_rate NUMERIC(4, 2) NULL,
            intended_vacancy_text TEXT NULL,
            contact_mobile_phone TEXT NULL,
            contact_email TEXT NULL,
            director_resolution_status TEXT NULL,
            director_resolution_at TIMESTAMPTZ NULL,
            director_resolution_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            director_resolution_note TEXT NULL,
            personnel_order_id BIGINT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            registered_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            hr_note TEXT NULL,
            idempotency_key TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_applications_status
                CHECK (status IN ({statuses_sql})),
            CONSTRAINT chk_personnel_applications_application_source
                CHECK (application_source IN ({sources_sql})),
            CONSTRAINT chk_personnel_applications_vacancy_check_status
                CHECK (vacancy_check_status IN ({vacancy_sql})),
            CONSTRAINT chk_personnel_applications_director_resolution_status
                CHECK (
                    director_resolution_status IS NULL
                    OR director_resolution_status IN ({director_sql})
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_applications_person_id_created_at
            ON public.personnel_applications (person_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_applications_status
            ON public.personnel_applications (status)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_applications_idempotency_key
            ON public.personnel_applications (idempotency_key)
            WHERE idempotency_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_applications_personnel_order_id
            ON public.personnel_applications (personnel_order_id)
            WHERE personnel_order_id IS NOT NULL
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_applications_one_active_per_person
            ON public.personnel_applications (person_id)
            WHERE status NOT IN ({terminal_sql})
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_applications IS
            'WP-PPR-APPLICANT-001B / ADR-057: personnel application episode aggregate SoT.'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_applications CASCADE")
