"""WP-PO-002 Stage 2A — operational order archive import staging.

Revision ID: u4v5w6x7y8z
Revises: t3u4v5w6x7y
"""
from __future__ import annotations

from alembic import op


revision = "u4v5w6x7y8z"
down_revision = "t3u4v5w6x7y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.operational_order_import_batches (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_manifest_name TEXT NOT NULL,
            source_manifest_sha256 TEXT NOT NULL,
            batch_fingerprint TEXT NOT NULL,
            format_version TEXT NOT NULL,
            source_root_name TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'IMPORTED',
            total_rows INTEGER NOT NULL,
            valid_rows INTEGER NOT NULL,
            error_rows INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            archive_section_count INTEGER NOT NULL,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ NULL,
            CONSTRAINT uq_oo_import_batches_fingerprint
                UNIQUE (batch_fingerprint),
            CONSTRAINT chk_oo_import_batches_status
                CHECK (status IN ('IMPORTED', 'IN_REVIEW', 'COMPLETED', 'CANCELLED')),
            CONSTRAINT chk_oo_import_batches_counts
                CHECK (
                    total_rows >= 0
                    AND valid_rows >= 0
                    AND error_rows >= 0
                    AND total_rows = valid_rows + error_rows
                    AND file_count >= 0
                    AND file_count <= total_rows
                    AND archive_section_count >= 0
                ),
            CONSTRAINT chk_oo_import_batches_manifest_name
                CHECK (
                    btrim(source_manifest_name) <> ''
                    AND position('/' in source_manifest_name) = 0
                    AND position(chr(92) in source_manifest_name) = 0
                ),
            CONSTRAINT chk_oo_import_batches_manifest_sha256
                CHECK (source_manifest_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT chk_oo_import_batches_fingerprint
                CHECK (batch_fingerprint ~ '^[0-9a-f]{64}$'),
            CONSTRAINT chk_oo_import_batches_format_version
                CHECK (btrim(format_version) <> ''),
            CONSTRAINT chk_oo_import_batches_root_name
                CHECK (
                    btrim(source_root_name) <> ''
                    AND position('/' in source_root_name) = 0
                    AND position(chr(92) in source_root_name) = 0
                ),
            CONSTRAINT chk_oo_import_batches_sheet_name
                CHECK (btrim(sheet_name) <> '')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_oo_import_batches_status
            ON public.operational_order_import_batches (status)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_oo_import_batches_created_at
            ON public.operational_order_import_batches (created_at)
        """
    )

    op.execute(
        """
        CREATE TABLE public.operational_order_import_rows (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id BIGINT NOT NULL
                REFERENCES public.operational_order_import_batches (id) ON DELETE CASCADE,
            source_row_number TEXT NOT NULL,
            source_filename TEXT NOT NULL,
            source_document_type TEXT NOT NULL,
            source_status TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            source_order_number TEXT NULL,
            source_order_date DATE NULL,
            source_note TEXT NULL,
            source_folder TEXT NOT NULL,
            archive_section TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_extension TEXT NOT NULL,
            file_size BIGINT NOT NULL,
            file_sha256 TEXT NOT NULL,
            initial_review_state TEXT NOT NULL,
            confirmed_document_type TEXT NULL,
            confirmed_order_number TEXT NULL,
            confirmed_order_date DATE NULL,
            review_outcome TEXT NULL,
            reviewed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ NULL,
            official_document_id BIGINT NULL
                REFERENCES public.operational_order_documents (id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            version INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_oo_import_rows_batch_source_row
                UNIQUE (batch_id, source_row_number),
            CONSTRAINT uq_oo_import_rows_batch_relative_path
                UNIQUE (batch_id, relative_path),
            CONSTRAINT chk_oo_import_rows_source_row_number
                CHECK (btrim(source_row_number) <> ''),
            CONSTRAINT chk_oo_import_rows_source_filename
                CHECK (btrim(source_filename) <> ''),
            CONSTRAINT chk_oo_import_rows_source_status
                CHECK (
                    source_status IN (
                        'Найден',
                        'Не найден',
                        'Требует проверки',
                        'Не является приказом'
                    )
                ),
            CONSTRAINT chk_oo_import_rows_relative_path
                CHECK (btrim(relative_path) <> ''),
            CONSTRAINT chk_oo_import_rows_file_extension
                CHECK (file_extension IN ('.doc', '.docx', '.pdf')),
            CONSTRAINT chk_oo_import_rows_file_size
                CHECK (file_size >= 0),
            CONSTRAINT chk_oo_import_rows_file_sha256
                CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT chk_oo_import_rows_initial_review_state
                CHECK (
                    initial_review_state IN (
                        'REQUISITES_PRECONFIRMED',
                        'NEEDS_REQUISITES',
                        'NEEDS_DOCUMENT_TYPE',
                        'POSSIBLE_NON_ORDER'
                    )
                ),
            CONSTRAINT chk_oo_import_rows_version
                CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_oo_import_rows_batch
            ON public.operational_order_import_rows (batch_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_oo_import_rows_file_sha256
            ON public.operational_order_import_rows (file_sha256)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_oo_import_rows_initial_review
            ON public.operational_order_import_rows (initial_review_state)
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.guard_oo_import_row_source_fields()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF ROW(
                NEW.batch_id,
                NEW.source_row_number,
                NEW.source_filename,
                NEW.source_document_type,
                NEW.source_status,
                NEW.source_event_type,
                NEW.source_order_number,
                NEW.source_order_date,
                NEW.source_note,
                NEW.source_folder,
                NEW.archive_section,
                NEW.relative_path,
                NEW.file_extension,
                NEW.file_size,
                NEW.file_sha256,
                NEW.initial_review_state
            ) IS DISTINCT FROM ROW(
                OLD.batch_id,
                OLD.source_row_number,
                OLD.source_filename,
                OLD.source_document_type,
                OLD.source_status,
                OLD.source_event_type,
                OLD.source_order_number,
                OLD.source_order_date,
                OLD.source_note,
                OLD.source_folder,
                OLD.archive_section,
                OLD.relative_path,
                OLD.file_extension,
                OLD.file_size,
                OLD.file_sha256,
                OLD.initial_review_state
            ) THEN
                RAISE EXCEPTION 'operational order import source fields are immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_oo_import_row_source_fields_immutable
            BEFORE UPDATE ON public.operational_order_import_rows
            FOR EACH ROW
            EXECUTE FUNCTION public.guard_oo_import_row_source_fields()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_oo_import_row_source_fields_immutable
            ON public.operational_order_import_rows
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.guard_oo_import_row_source_fields()")
    op.execute("DROP INDEX IF EXISTS public.ix_oo_import_rows_initial_review")
    op.execute("DROP INDEX IF EXISTS public.ix_oo_import_rows_file_sha256")
    op.execute("DROP INDEX IF EXISTS public.ix_oo_import_rows_batch")
    op.execute("DROP TABLE IF EXISTS public.operational_order_import_rows")
    op.execute("DROP INDEX IF EXISTS public.ix_oo_import_batches_created_at")
    op.execute("DROP INDEX IF EXISTS public.ix_oo_import_batches_status")
    op.execute("DROP TABLE IF EXISTS public.operational_order_import_batches")
