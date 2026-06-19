"""ADR-039/037 — relax QUALIFICATION_CATEGORY specialty requirement for import promotion.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
"""
from __future__ import annotations

from alembic import op

revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE public.document_types
        SET requires_medical_specialty = FALSE
        WHERE code = 'QUALIFICATION_CATEGORY'
        """
    )
    op.execute(
        """
        UPDATE public.hr_import_normalized_records nr
        SET
            document_type_id = dt.document_type_id,
            document_type_code = dt.code,
            updated_at = NOW()
        FROM public.document_types dt
        WHERE dt.code = 'QUALIFICATION_CATEGORY'
          AND nr.record_kind = 'category'
          AND (
                nr.document_type_id IS NULL
             OR nr.document_type_code IS NULL
             OR nr.document_type_code <> dt.code
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.document_types
        SET requires_medical_specialty = TRUE
        WHERE code = 'QUALIFICATION_CATEGORY'
        """
    )
