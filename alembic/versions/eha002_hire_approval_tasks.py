"""Connect electronic HIRE visas to the shared task inbox.

Revision ID: eha002
Revises: ehapf001
"""
from alembic import op

revision = "eha002"
down_revision = "ehapf001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.electronic_hire_applications
        ADD COLUMN conditions_version BIGINT NOT NULL DEFAULT 1;

        ALTER TABLE public.tasks DROP CONSTRAINT ck_tasks_source_kind;
        ALTER TABLE public.tasks ADD CONSTRAINT ck_tasks_source_kind
        CHECK (source_kind IN ('regular_task', 'manual', 'bot', 'import', 'electronic_hire'));

        CREATE TABLE public.electronic_hire_approval_tasks (
            task_id BIGINT PRIMARY KEY REFERENCES public.tasks(task_id) ON DELETE RESTRICT,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            conditions_hash TEXT NOT NULL CHECK (length(conditions_hash) = 64),
            head_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            decision TEXT CHECK (decision IN ('approved', 'rejected')),
            explanation TEXT,
            decided_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_electronic_hire_approval_task_conditions UNIQUE (application_id, conditions_hash),
            CONSTRAINT ck_electronic_hire_approval_task_decision CHECK
                ((decision IS NULL AND decided_at IS NULL) OR (decision IS NOT NULL AND decided_at IS NOT NULL))
        );
        CREATE INDEX ix_electronic_hire_approval_tasks_head
        ON public.electronic_hire_approval_tasks(head_user_id, task_id DESC);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE public.electronic_hire_approval_tasks;
        ALTER TABLE public.tasks DROP CONSTRAINT ck_tasks_source_kind;
        ALTER TABLE public.tasks ADD CONSTRAINT ck_tasks_source_kind
        CHECK (source_kind IN ('regular_task', 'manual', 'bot', 'import'));
        ALTER TABLE public.electronic_hire_applications DROP COLUMN conditions_version;
    """)
