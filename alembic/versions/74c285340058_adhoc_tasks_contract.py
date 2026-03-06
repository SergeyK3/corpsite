"""adhoc tasks contract

Revision ID: 74c285340058
Revises: b17f7f69c7d5
Create Date: 2026-03-06 23:24:54.579245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74c285340058'
down_revision: Union[str, Sequence[str], None] = 'b17f7f69c7d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
