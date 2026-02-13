from alembic import op
import sqlalchemy as sa

revision = "XXXX_regular_task_run_items"
down_revision = "89e6f63718bc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "regular_task_run_items",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("regular_task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "regular_task_id",
            sa.BigInteger(),
            sa.ForeignKey("regular_tasks.regular_task_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="ok"),
        sa.Column("stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "finished_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_regular_task_run_items_run_id",
        "regular_task_run_items",
        ["run_id"],
    )
    op.create_index(
        "ix_regular_task_run_items_regular_task_id",
        "regular_task_run_items",
        ["regular_task_id"],
    )


def downgrade():
    op.drop_index(
        "ix_regular_task_run_items_regular_task_id",
        table_name="regular_task_run_items",
    )
    op.drop_index(
        "ix_regular_task_run_items_run_id",
        table_name="regular_task_run_items",
    )
    op.drop_table("regular_task_run_items")
