"""Electronic HIRE application, signed copy, independent visas and delivery state.

Revision ID: eha001
Revises: ptype002
"""
from alembic import op

revision = "eha001"
down_revision = "ptype002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.personnel_applications
        DROP CONSTRAINT chk_personnel_applications_application_source;
        ALTER TABLE public.personnel_applications
        ADD CONSTRAINT chk_personnel_applications_application_source
        CHECK (application_source IN ('paper', 'electronic'));
        CREATE TABLE public.electronic_hire_applications (
            application_id BIGINT PRIMARY KEY REFERENCES public.personnel_applications(application_id) ON DELETE RESTRICT,
            planned_start_date DATE NOT NULL,
            candidate_checked_at TIMESTAMPTZ,
            candidate_checked_by_user_id BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE public.electronic_hire_visas (
            visa_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            explanation TEXT,
            conditions_hash TEXT NOT NULL,
            conditions JSONB NOT NULL,
            decided_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (decision <> 'rejected' OR NULLIF(BTRIM(explanation), '') IS NOT NULL)
        );
        CREATE INDEX ix_electronic_hire_visas_application ON public.electronic_hire_visas(application_id, visa_id DESC);
        CREATE TABLE public.electronic_hire_notifications (
            notification_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            conditions_hash TEXT NOT NULL,
            recipient_user_id BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            status TEXT NOT NULL CHECK (status IN ('no_manager', 'pending', 'sent', 'failed')),
            last_error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(application_id, conditions_hash)
        );
        CREATE TABLE public.electronic_hire_attachments (
            attachment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            file_name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            uploaded_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE public.electronic_hire_link_deliveries (
            link_id BIGINT PRIMARY KEY REFERENCES public.personnel_intake_links(link_id) ON DELETE RESTRICT,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            status TEXT NOT NULL CHECK (status IN ('sent', 'failed')),
            last_error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE public.electronic_hire_link_deliveries")
    op.execute("DROP TABLE public.electronic_hire_attachments")
    op.execute("DROP TABLE public.electronic_hire_notifications")
    op.execute("DROP TABLE public.electronic_hire_visas")
    op.execute("DROP TABLE public.electronic_hire_applications")
    op.execute("ALTER TABLE public.personnel_applications DROP CONSTRAINT chk_personnel_applications_application_source")
    op.execute("ALTER TABLE public.personnel_applications ADD CONSTRAINT chk_personnel_applications_application_source CHECK (application_source = 'paper')")
