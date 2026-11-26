"""Reversible archive state for electronic hire applications.

Revision ID: eha006
Revises: eha005
"""
from alembic import op

revision = "eha006"
down_revision = "eha005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.personnel_applications
            ADD COLUMN archived_at TIMESTAMPTZ,
            ADD COLUMN archived_by_user_id BIGINT REFERENCES public.users(user_id);
        CREATE INDEX ix_personnel_applications_archived_at
            ON public.personnel_applications (archived_at) WHERE archived_at IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX public.ix_personnel_applications_archived_at;
        ALTER TABLE public.personnel_applications
            DROP COLUMN archived_by_user_id,
            DROP COLUMN archived_at;
    """)
