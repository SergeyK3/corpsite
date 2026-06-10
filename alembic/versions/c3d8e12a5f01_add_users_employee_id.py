"""add users employee_id link

Revision ID: c3d8e12a5f01
Revises: f8c2a91b4e10
Create Date: 2026-06-10 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d8e12a5f01"
down_revision: Union[str, Sequence[str], None] = "f8c2a91b4e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE public.users
        ADD COLUMN IF NOT EXISTS employee_id BIGINT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_users_employee'
            ) THEN
                ALTER TABLE public.users
                ADD CONSTRAINT fk_users_employee
                    FOREIGN KEY (employee_id)
                    REFERENCES public.employees(employee_id);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_employee_id
        ON public.users (employee_id)
        WHERE employee_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS public.uq_users_employee_id")
    op.execute(
        """
        ALTER TABLE public.users
        DROP CONSTRAINT IF EXISTS fk_users_employee
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
        DROP COLUMN IF EXISTS employee_id
        """
    )
