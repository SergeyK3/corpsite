"""WP-ONBOARDING-002: onboarding tasks, notifications, audit, attachments.

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
"""
from __future__ import annotations

from alembic import op

revision = "w2x3y4z5a6b7"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None

_ASSIGNEE_KINDS = ("hr", "mentor", "employee")
_PRIORITIES = ("low", "normal", "high", "urgent")
_NOTIFICATION_TYPES = (
    "TASK_ASSIGNED",
    "TASK_DUE_SOON",
    "TASK_OVERDUE",
    "TASK_COMPLETED",
)
_DELIVERY_CHANNELS = ("system", "telegram")
_DELIVERY_STATUSES = ("PENDING", "SENT", "FAILED")


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    assignee_kinds_sql = _sql_tuple(_ASSIGNEE_KINDS)
    priorities_sql = _sql_tuple(_PRIORITIES)
    notification_types_sql = _sql_tuple(_NOTIFICATION_TYPES)
    delivery_channels_sql = _sql_tuple(_DELIVERY_CHANNELS)
    delivery_statuses_sql = _sql_tuple(_DELIVERY_STATUSES)

    op.execute(
        f"""
        ALTER TABLE public.employee_onboarding_checklist_items
            ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS assignee_kind TEXT NULL,
            ADD COLUMN IF NOT EXISTS assignee_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS assignee_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'normal'
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.employee_onboarding_checklist_items
            DROP CONSTRAINT IF EXISTS chk_employee_onboarding_checklist_assignee_kind,
            ADD CONSTRAINT chk_employee_onboarding_checklist_assignee_kind
                CHECK (
                    assignee_kind IS NULL
                    OR assignee_kind IN ({assignee_kinds_sql})
                ),
            DROP CONSTRAINT IF EXISTS chk_employee_onboarding_checklist_priority,
            ADD CONSTRAINT chk_employee_onboarding_checklist_priority
                CHECK (priority IN ({priorities_sql}))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_checklist_due_date
            ON public.employee_onboarding_checklist_items (due_date ASC, status)
            WHERE status = 'pending'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_checklist_assignee_user
            ON public.employee_onboarding_checklist_items (assignee_user_id, status)
            WHERE assignee_user_id IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_checklist_attachments (
            attachment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            item_id BIGINT NOT NULL
                REFERENCES public.employee_onboarding_checklist_items (item_id) ON DELETE CASCADE,
            file_url TEXT NOT NULL,
            file_comment TEXT NULL,
            created_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_checklist_attachments_item_id
            ON public.employee_onboarding_checklist_attachments (item_id, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_task_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            item_id BIGINT NOT NULL
                REFERENCES public.employee_onboarding_checklist_items (item_id) ON DELETE CASCADE,
            onboarding_id BIGINT NOT NULL
                REFERENCES public.employee_onboardings (onboarding_id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_task_audit_item_id
            ON public.employee_onboarding_task_audit (item_id, created_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_notifications (
            notification_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            item_id BIGINT NULL
                REFERENCES public.employee_onboarding_checklist_items (item_id) ON DELETE SET NULL,
            onboarding_id BIGINT NOT NULL
                REFERENCES public.employee_onboardings (onboarding_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            dedup_key TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_employee_onboarding_notifications_event_type
                CHECK (event_type IN ({notification_types_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_onboarding_notifications_dedup
            ON public.employee_onboarding_notifications (item_id, event_type, dedup_key)
            WHERE dedup_key IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_notification_recipients (
            notification_id BIGINT NOT NULL
                REFERENCES public.employee_onboarding_notifications (notification_id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE CASCADE,
            PRIMARY KEY (notification_id, user_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.employee_onboarding_notification_deliveries (
            notification_id BIGINT NOT NULL
                REFERENCES public.employee_onboarding_notifications (notification_id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error_code TEXT NULL,
            sent_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (notification_id, user_id, channel),
            CONSTRAINT chk_employee_onboarding_notification_deliveries_channel
                CHECK (channel IN ({delivery_channels_sql})),
            CONSTRAINT chk_employee_onboarding_notification_deliveries_status
                CHECK (status IN ({delivery_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_onboarding_notification_deliveries_pending
            ON public.employee_onboarding_notification_deliveries (status, channel)
            WHERE status = 'PENDING'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.employee_onboarding_notifications IS
            'WP-ONBOARDING-002: onboarding task notification events (mirrors task_events pattern)'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_notification_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_notification_recipients CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_task_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_onboarding_checklist_attachments CASCADE")
    op.execute(
        """
        ALTER TABLE public.employee_onboarding_checklist_items
            DROP COLUMN IF EXISTS due_date,
            DROP COLUMN IF EXISTS assignee_kind,
            DROP COLUMN IF EXISTS assignee_user_id,
            DROP COLUMN IF EXISTS assignee_employee_id,
            DROP COLUMN IF EXISTS priority
        """
    )
