"""create users and hierarchy tables; add FK constraints to tasks

Revision ID: 0002_create_users_hierarchy
Revises: 0001_create_periods_tasks_statuses
Create Date: 2026-01-02 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_create_users_hierarchy"
down_revision = "0001_create_periods_tasks_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)

    # --- user_profiles ---
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_user_profiles_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_user_profiles_phone", "user_profiles", ["phone"], unique=False)
    op.create_index(
        "ix_user_profiles_telegram_chat_id", "user_profiles", ["telegram_chat_id"], unique=False
    )

    # --- user_reporting_lines (direct manager -> subordinate) ---
    op.create_table(
        "user_reporting_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("manager_user_id", sa.BigInteger(), nullable=False),
        sa.Column("subordinate_user_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["manager_user_id"],
            ["users.user_id"],
            name="fk_reporting_lines_manager_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subordinate_user_id"],
            ["users.user_id"],
            name="fk_reporting_lines_subordinate_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "manager_user_id <> subordinate_user_id", name="ck_reporting_lines_not_self"
        ),
    )
    op.create_index(
        "ix_reporting_lines_manager",
        "user_reporting_lines",
        ["manager_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_reporting_lines_subordinate",
        "user_reporting_lines",
        ["subordinate_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_reporting_lines_active",
        "user_reporting_lines",
        ["manager_user_id", "subordinate_user_id", "valid_to"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_reporting_lines_unique_pair",
        "user_reporting_lines",
        ["manager_user_id", "subordinate_user_id", "valid_from"],
    )

    # --- add FK constraints to tasks -> users (now that users exists) ---
    op.create_foreign_key(
        "fk_tasks_initiator_user_id",
        "tasks",
        "users",
        ["initiator_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_tasks_executor_user_id",
        "tasks",
        "users",
        ["executor_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # drop FKs from tasks first
    op.drop_constraint("fk_tasks_executor_user_id", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_initiator_user_id", "tasks", type_="foreignkey")

    # reporting lines
    op.drop_constraint("uq_reporting_lines_unique_pair", "user_reporting_lines", type_="unique")
    op.drop_index("ix_reporting_lines_active", table_name="user_reporting_lines")
    op.drop_index("ix_reporting_lines_subordinate", table_name="user_reporting_lines")
    op.drop_index("ix_reporting_lines_manager", table_name="user_reporting_lines")
    op.drop_table("user_reporting_lines")

    # profiles
    op.drop_index("ix_user_profiles_telegram_chat_id", table_name="user_profiles")
    op.drop_index("ix_user_profiles_phone", table_name="user_profiles")
    op.drop_table("user_profiles")

    # users
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
