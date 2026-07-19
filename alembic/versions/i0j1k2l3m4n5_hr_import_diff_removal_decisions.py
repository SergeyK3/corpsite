"""hr_import_diff_removals — operator decisions restore | confirm_removal."""
from __future__ import annotations

from alembic import op

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_diff_removals
            ADD COLUMN IF NOT EXISTS decision TEXT NULL,
            ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS decided_by BIGINT NULL,
            ADD COLUMN IF NOT EXISTS decision_basis TEXT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_hr_import_diff_removals_decision'
            ) THEN
                ALTER TABLE public.hr_import_diff_removals
                    ADD CONSTRAINT chk_hr_import_diff_removals_decision
                    CHECK (
                        decision IS NULL
                        OR decision IN ('restore', 'confirm_removal')
                    );
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_hr_import_diff_removals_decision_audit'
            ) THEN
                ALTER TABLE public.hr_import_diff_removals
                    ADD CONSTRAINT chk_hr_import_diff_removals_decision_audit
                    CHECK (
                        (decision IS NULL AND decided_at IS NULL AND decided_by IS NULL)
                        OR (
                            decision IS NOT NULL
                            AND decided_at IS NOT NULL
                            AND decided_by IS NOT NULL
                        )
                    );
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_diff_removals_batch_pending
            ON public.hr_import_diff_removals (batch_id)
            WHERE decision IS NULL
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.hr_import_diff_removals.decision IS
            'Operator resolution for REMOVED row: restore (carry forward) or confirm_removal.';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_hr_import_diff_removals_batch_pending")
    op.execute(
        """
        ALTER TABLE public.hr_import_diff_removals
            DROP CONSTRAINT IF EXISTS chk_hr_import_diff_removals_decision_audit,
            DROP CONSTRAINT IF EXISTS chk_hr_import_diff_removals_decision,
            DROP COLUMN IF EXISTS decision_basis,
            DROP COLUMN IF EXISTS decided_by,
            DROP COLUMN IF EXISTS decided_at,
            DROP COLUMN IF EXISTS decision
        """
    )
