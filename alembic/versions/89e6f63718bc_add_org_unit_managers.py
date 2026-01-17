"""add org_unit_managers

Revision ID: 89e6f63718bc
Revises: 0004_upsert_task_statuses
Create Date: 2026-01-17 15:34:22.224077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "89e6f63718bc"
down_revision: Union[str, Sequence[str], None] = "0004_upsert_task_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_unit_managers",
        sa.Column(
            "manager_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("unit_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("manager_type", sa.Text(), nullable=False),  # HEAD | DEPUTY (MVP)
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["org_units.unit_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "idx_org_unit_managers_unit_active",
        "org_unit_managers",
        ["unit_id", "is_active"],
        unique=False,
    )

    op.create_index(
        "idx_org_unit_managers_user_active",
        "org_unit_managers",
        ["user_id", "is_active"],
        unique=False,
    )

    # One active HEAD per unit (partial unique index)
    op.execute(
        """
        CREATE UNIQUE INDEX ux_org_unit_managers_one_head
        ON public.org_unit_managers (unit_id)
        WHERE manager_type = 'HEAD' AND is_active = TRUE;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ux_org_unit_managers_one_head")
    op.drop_index("idx_org_unit_managers_user_active", table_name="org_unit_managers")
    op.drop_index("idx_org_unit_managers_unit_active", table_name="org_unit_managers")
    op.drop_table("org_unit_managers")
