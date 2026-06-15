"""add professional documents demo (bridge stub)

Revision ID: e4a1c92b7d10
Revises: b5e2a81d4c03
Create Date: 2026-06-13

Bridge revision for environments where the ADR-034 demo migration was already
applied before it was removed from the Alembic chain (commit 6e0f320).

The original migration created certificate_types / employee_certificates and
DEMO seed data. That demo schema is now local-only and managed by
scripts/local_demo/adr034_* — not by Alembic.

This no-op stub restores Alembic continuity so later revisions can run.
"""

from typing import Sequence, Union

revision: str = "e4a1c92b7d10"
down_revision: Union[str, Sequence[str], None] = "b5e2a81d4c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
