"""ADR-038 Phase A — employee-level import profile overrides (persist across imports).

Revision ID: k4d5e6f7a8b9
Revises: j3c4d5e6f7a8
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op

revision = "k4d5e6f7a8b9"
down_revision = "j3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_import_profile_overrides (
            employee_id BIGINT PRIMARY KEY
                REFERENCES public.employees(employee_id) ON DELETE CASCADE,
            profile_override JSONB NOT NULL,
            profile_status TEXT NOT NULL DEFAULT 'active',
            profile_review_status TEXT NOT NULL DEFAULT 'pending',
            updated_by BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_employee_import_profile_status
                CHECK (profile_status IN ('active', 'archived')),
            CONSTRAINT ck_employee_import_profile_review_status
                CHECK (profile_review_status IN ('pending', 'reviewed', 'needs_attention'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_import_profile_overrides_updated_at
            ON public.employee_import_profile_overrides (updated_at DESC)
        """
    )
    op.execute(
        """
        INSERT INTO public.employee_import_profile_overrides (
            employee_id,
            profile_override,
            profile_status,
            profile_review_status,
            created_at,
            updated_at
        )
        SELECT DISTINCT ON (r.employee_id)
            r.employee_id,
            r.profile_override,
            COALESCE(r.profile_status, 'active'),
            COALESCE(r.profile_review_status, 'pending'),
            NOW(),
            NOW()
        FROM public.hr_import_rows r
        JOIN public.hr_import_batches b ON b.batch_id = r.batch_id
        WHERE r.employee_id IS NOT NULL
          AND r.profile_override IS NOT NULL
        ORDER BY r.employee_id, b.imported_at DESC NULLS LAST, r.row_id DESC
        ON CONFLICT (employee_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.employee_import_profile_overrides CASCADE")
