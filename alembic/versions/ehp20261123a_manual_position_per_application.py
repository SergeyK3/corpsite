"""Keep the manual HIRE position document form on the application.

Revision ID: ehp20261123a
Revises: eha001
"""
from alembic import op

revision = "ehp20261123a"
down_revision = "eha001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.electronic_hire_applications
        ADD COLUMN manual_position_document_ru TEXT NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE public.electronic_hire_applications
        DROP COLUMN manual_position_document_ru
    """)
