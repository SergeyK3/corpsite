"""Store preliminary electronic hire names as separate fields.

Revision ID: eha005
Revises: eha004
"""
from alembic import op

revision = "eha005"
down_revision = "eha004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.electronic_hire_applications
            ADD COLUMN preliminary_last_name TEXT,
            ADD COLUMN preliminary_first_name TEXT,
            ADD COLUMN preliminary_middle_name TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM public.electronic_hire_applications
                       WHERE preliminary_last_name IS NOT NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade: structured candidate names exist';
            END IF;
        END $$;
        ALTER TABLE public.electronic_hire_applications
            DROP COLUMN preliminary_middle_name,
            DROP COLUMN preliminary_first_name,
            DROP COLUMN preliminary_last_name;
    """)
