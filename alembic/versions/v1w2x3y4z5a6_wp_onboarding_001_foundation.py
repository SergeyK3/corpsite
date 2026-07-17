"""WP-ONBOARDING-001: employee onboarding foundation — onboarding + checklist.

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
"""
from __future__ import annotations

from alembic import op

revision = "v1w2x3y4z5a6"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None

_ONBOARDING_STATUSES = ("planned", "active", "completed", "cancelled")
_CHECKLIST_ITEM_STATUSES = ("pending", "completed", "skipped")
_CHECKLIST_ITEM_CODES = (
    "lna_introduction",
    "pass_issue",
    "equipment_issue",
    "account_creation",
    "safety_briefing",
    "department_introduction",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    statuses_sql = _sql_tuple(_ONBOARDING_STATUSES)
    item_statuses_sql = _sql_tuple(_CHECKLIST_ITEM_STATUSES)
    item_codes_sql = _sql_tuple(_CHECKLIST_ITEM_CODES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.employee_onboardings (
            onboarding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            application_id BIGINT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'active',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            planned_end_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL,
            responsible_hr_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            mentor_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            notes TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_employee_onboardings_status
                CHECK (status IN ({statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_onboardings_application_id
            ON public.employee_onboardings (application_id)
            WHERE application_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboardings_employee_id
            ON public.employee_onboardings (employee_id, started_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboardings_status
            ON public.employee_onboardings (status, started_at DESC)
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_checklist_items (
            item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            onboarding_id BIGINT NOT NULL
                REFERENCES public.employee_onboardings (onboarding_id) ON DELETE CASCADE,
            item_code TEXT NULL,
            title TEXT NOT NULL,
            sort_order INT NOT NULL DEFAULT 0,
            is_custom BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'pending',
            completed_at TIMESTAMPTZ NULL,
            completed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            comment TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_employee_onboarding_checklist_status
                CHECK (status IN ({item_statuses_sql})),
            CONSTRAINT chk_employee_onboarding_checklist_code
                CHECK (
                    is_custom = TRUE
                    OR item_code IN ({item_codes_sql})
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_checklist_onboarding_id
            ON public.employee_onboarding_checklist_items (onboarding_id, sort_order ASC, item_id ASC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.employee_onboardings IS
            'WP-ONBOARDING-001: employee adaptation program after HIRE'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_checklist_items CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_onboardings CASCADE")
