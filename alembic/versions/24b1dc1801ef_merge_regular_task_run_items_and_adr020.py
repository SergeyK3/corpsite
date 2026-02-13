"""merge regular_task_run_items and adr020

Revision ID: 24b1dc1801ef
Revises: XXXX_regular_task_run_items, 20260127_adr020_regular_tasks_v1
Create Date: 2026-02-08 14:59:07.199928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24b1dc1801ef'
down_revision: Union[str, Sequence[str], None] = ('XXXX_regular_task_run_items', '20260127_adr020_regular_tasks_v1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
