"""ADR-044 R2.3 — user linkage review decision audit (no linkage writes).

Revision ID: c2d3e4f5a6b7
Revises: b0c1d2e3f4a5
"""
from __future__ import annotations

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None

_DECISIONS = ("APPROVE", "REJECT", "DEFER")


def upgrade() -> None:
    decisions_sql = ", ".join(f"'{d}'" for d in _DECISIONS)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.user_linkage_review_decisions (
            decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            reviewer_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            proposed_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            classification TEXT NOT NULL,
            match_strategy TEXT NULL,
            decision TEXT NOT NULL,
            reason TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_ulrd_decision CHECK (decision IN ({decisions_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulrd_user_created
            ON public.user_linkage_review_decisions (user_id, created_at DESC, decision_id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulrd_created
            ON public.user_linkage_review_decisions (created_at DESC, decision_id DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.user_linkage_review_decisions IS
            'ADR-044 R2.3: append-only user linkage review decisions (no users.employee_id writes).';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.user_linkage_review_decisions CASCADE")
