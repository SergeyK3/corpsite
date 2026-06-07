"""add group_id to org_units

Revision ID: d668fb72f5f7
Revises: 74c285340058
Create Date: 2026-06-07 09:22:28.245816

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd668fb72f5f7'
down_revision: Union[str, Sequence[str], None] = '74c285340058'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    ALTER TABLE public.org_units
    ADD COLUMN IF NOT EXISTS group_id bigint
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    ALTER TABLE public.org_units
    DROP COLUMN IF EXISTS group_id
    """)
