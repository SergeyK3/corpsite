"""ADR-039 Phase 3F — QUALIFICATION_CATEGORY document type seed.

Revision ID: o7p8q9r0s1t2
Revises: n7a8b9c0d1e2
"""
from __future__ import annotations

from alembic import op

revision = "o7p8q9r0s1t2"
down_revision = "n7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO public.document_types (
            code, name, category,
            has_valid_until, requires_medical_specialty,
            tracks_hours, is_active, sort_order
        )
        VALUES (
            'QUALIFICATION_CATEGORY',
            'Квалификационная категория',
            'CREDENTIAL',
            TRUE, TRUE, FALSE, TRUE, 25
        )
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            has_valid_until = EXCLUDED.has_valid_until,
            requires_medical_specialty = EXCLUDED.requires_medical_specialty,
            tracks_hours = EXCLUDED.tracks_hours,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order
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
          AND nr.document_type_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.hr_import_normalized_records nr
        SET
            document_type_id = NULL,
            document_type_code = 'QUALIFICATION_CATEGORY',
            updated_at = NOW()
        FROM public.document_types dt
        WHERE dt.code = 'QUALIFICATION_CATEGORY'
          AND nr.document_type_id = dt.document_type_id
          AND nr.record_kind = 'category'
        """
    )
    op.execute(
        """
        UPDATE public.document_types
        SET is_active = FALSE
        WHERE code = 'QUALIFICATION_CATEGORY'
        """
    )
