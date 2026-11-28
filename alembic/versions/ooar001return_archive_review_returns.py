"""Keep an audit snapshot whenever a completed archive review is returned."""
from __future__ import annotations

from alembic import op

revision = "ooar001return"
down_revision = "td007employee01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.operational_order_archive_review_returns (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            row_id BIGINT NOT NULL REFERENCES public.operational_order_import_rows (id) ON DELETE CASCADE,
            previous_version INTEGER NOT NULL,
            previous_review_outcome TEXT NOT NULL,
            previous_confirmed_document_type TEXT NULL,
            previous_confirmed_order_number TEXT NULL,
            previous_confirmed_order_date DATE NULL,
            previous_confirmed_subject TEXT NULL,
            previous_review_comment TEXT NULL,
            previous_reviewer_user_id BIGINT NULL,
            previous_reviewer_display_name TEXT NULL,
            previous_reviewed_at TIMESTAMPTZ NULL,
            returned_by_user_id BIGINT NOT NULL,
            returned_by_display_name TEXT NOT NULL,
            returned_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            reason TEXT NOT NULL,
            CONSTRAINT chk_oo_archive_return_previous_outcome CHECK (
                previous_review_outcome IN (
                    'CONFIRMED', 'DRAFT_ORDER', 'ORDER_ANNEX',
                    'SUPPORTING_DOCUMENT', 'DUPLICATE', 'NOT_AN_ORDER'
                )
            ),
            CONSTRAINT chk_oo_archive_return_reason CHECK (btrim(reason) <> '')
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_oo_archive_return_row_time "
        "ON public.operational_order_archive_review_returns (row_id, returned_at DESC, id DESC)"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.operational_order_archive_review_returns) THEN
                RAISE EXCEPTION 'Archive review return history exists; downgrade refused';
            END IF;
        END
        $$
        """
    )
    op.execute("DROP TABLE public.operational_order_archive_review_returns")
