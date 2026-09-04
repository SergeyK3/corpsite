"""WP-TD-002B: immutable command result projection.

Revision ID: z9a0b1c2d3e4
Revises: y8z9a0b1c2d3
"""
from __future__ import annotations

from alembic import op

revision = "z9a0b1c2d3e4"
down_revision = "y8z9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing history is append-only.  Remove only our exact trigger while a
    # safe, PII-free projection is backfilled, then restore protection before
    # returning control to Alembic.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_test_personnel_deletion_history_append_only "
        "ON public.test_personnel_deletion_history"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "ADD COLUMN result_projection JSONB"
    )
    op.execute(
        """
        UPDATE public.test_personnel_deletion_history
        SET result_projection = jsonb_build_object(
            'request_id', request_id::text,
            'status', new_status,
            'version', new_version,
            'result_code', result_code,
            'target_set_hash', target_set_hash
        )
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "ALTER COLUMN result_projection SET NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_result_projection CHECK (
            jsonb_typeof(result_projection) = 'object'
            AND NOT (result_projection ?| ARRAY[
                'iin', 'phone', 'email', 'display_name', 'full_name', 'comment'
            ])
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_history_append_only
        BEFORE UPDATE OR DELETE ON public.test_personnel_deletion_history
        FOR EACH ROW EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_test_personnel_deletion_history_append_only "
        "ON public.test_personnel_deletion_history"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_result_projection"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP COLUMN result_projection"
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_history_append_only
        BEFORE UPDATE OR DELETE ON public.test_personnel_deletion_history
        FOR EACH ROW EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )
