"""OO-IMP-005B — Lifecycle and schema foundation (PUBLISHED + header metadata)."""
from __future__ import annotations

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

_DOCUMENT_STATUSES = (
    "CREATED",
    "READY_FOR_SIGNATURE",
    "SIGNED",
    "REGISTERED",
    "PUBLISHED",
    "VOIDED",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    document_statuses_sql = _in_list(_DOCUMENT_STATUSES)

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD COLUMN IF NOT EXISTS signed_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS signed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS registration_number TEXT NULL,
            ADD COLUMN IF NOT EXISTS registration_year SMALLINT NULL,
            ADD COLUMN IF NOT EXISTS registration_date DATE NULL,
            ADD COLUMN IF NOT EXISTS registered_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS registered_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS published_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_status
                CHECK (status IN ({document_statuses_sql}))
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_oo_documents_registration_year_number
            ON public.operational_order_documents (registration_year, registration_number)
            WHERE registration_number IS NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_signed_metadata
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_signed_metadata
                CHECK (status != 'SIGNED' OR signed_at IS NOT NULL)
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_registered_metadata
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_registered_metadata
                CHECK (
                    status != 'REGISTERED'
                    OR (
                        signed_at IS NOT NULL
                        AND registration_number IS NOT NULL
                        AND registration_year IS NOT NULL
                        AND registration_date IS NOT NULL
                        AND registered_at IS NOT NULL
                    )
                )
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_published_metadata
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_published_metadata
                CHECK (
                    status != 'PUBLISHED'
                    OR (
                        published_at IS NOT NULL
                        AND published_by_user_id IS NOT NULL
                    )
                )
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_signed_at_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_signed_at_status
                CHECK (
                    signed_at IS NULL
                    OR status IN ('SIGNED', 'REGISTERED', 'PUBLISHED', 'VOIDED')
                )
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_published_at_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_published_at_status
                CHECK (
                    published_at IS NULL
                    OR status IN ('PUBLISHED', 'VOIDED')
                )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_published_at_status,
            DROP CONSTRAINT IF EXISTS chk_oo_documents_signed_at_status,
            DROP CONSTRAINT IF EXISTS chk_oo_documents_published_metadata,
            DROP CONSTRAINT IF EXISTS chk_oo_documents_registered_metadata,
            DROP CONSTRAINT IF EXISTS chk_oo_documents_signed_metadata
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS public.uq_oo_documents_registration_year_number
        """
    )

    previous_statuses_sql = _in_list(
        (
            "CREATED",
            "READY_FOR_SIGNATURE",
            "SIGNED",
            "REGISTERED",
            "VOIDED",
        )
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP CONSTRAINT IF EXISTS chk_oo_documents_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_documents
            ADD CONSTRAINT chk_oo_documents_status
                CHECK (status IN ({previous_statuses_sql}))
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP COLUMN IF EXISTS published_by_user_id,
            DROP COLUMN IF EXISTS published_at,
            DROP COLUMN IF EXISTS registered_by_user_id,
            DROP COLUMN IF EXISTS registered_at,
            DROP COLUMN IF EXISTS registration_date,
            DROP COLUMN IF EXISTS registration_year,
            DROP COLUMN IF EXISTS registration_number,
            DROP COLUMN IF EXISTS signed_by_user_id,
            DROP COLUMN IF EXISTS signed_at
        """
    )
