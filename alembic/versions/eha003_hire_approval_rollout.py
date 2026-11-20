"""Snapshot HIRE approval mode and store paper confirmations and rollout audit.

Revision ID: eha003
Revises: eha002
"""
from alembic import op

revision = "eha003"
down_revision = "eha002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.hire_approval_unit_modes (
            unit_id BIGINT PRIMARY KEY REFERENCES public.org_units(unit_id) ON DELETE RESTRICT,
            mode TEXT NOT NULL CHECK (mode IN ('paper', 'electronic')),
            updated_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE public.hire_approval_mode_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            unit_id BIGINT NOT NULL REFERENCES public.org_units(unit_id) ON DELETE RESTRICT,
            application_id BIGINT REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            old_mode TEXT NOT NULL CHECK (old_mode IN ('paper', 'electronic')),
            new_mode TEXT NOT NULL CHECK (new_mode IN ('paper', 'electronic')),
            changed_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason TEXT NOT NULL CHECK (btrim(reason) <> '')
        );
        ALTER TABLE public.electronic_hire_applications
          ADD COLUMN approval_mode TEXT NOT NULL DEFAULT 'electronic'
          CHECK (approval_mode IN ('paper', 'electronic'));
        -- Every pre-existing application began with mandatory electronic approval.
        -- Explicit creation of new applications chooses the configured unit mode.
        CREATE TABLE public.electronic_hire_paper_confirmations (
            confirmation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            conditions_hash TEXT NOT NULL CHECK (length(conditions_hash) = 64),
            conditions JSONB NOT NULL,
            approver_name TEXT NOT NULL CHECK (btrim(approver_name) <> ''),
            approved_on DATE NOT NULL,
            note TEXT,
            attachment_id BIGINT REFERENCES public.electronic_hire_attachments(attachment_id) ON DELETE RESTRICT,
            recorded_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (application_id, conditions_hash)
        );
        CREATE INDEX ix_hire_paper_application
          ON public.electronic_hire_paper_confirmations(application_id, confirmation_id DESC);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE public.electronic_hire_paper_confirmations;
        ALTER TABLE public.electronic_hire_applications DROP COLUMN approval_mode;
        DROP TABLE public.hire_approval_mode_audit;
        DROP TABLE public.hire_approval_unit_modes;
    """)
