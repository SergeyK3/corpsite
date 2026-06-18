"""ADR-039 Phase 3B — training normalization schema (staging + requirements + provenance).

Revision ID: n7a8b9c0d1e2
Revises: m6f7a8b9c0d1
Create Date: 2026-06-18

DDL only: training_hour_requirements, hr_import_normalized_records,
employee_documents provenance columns, indexes, FKs, CHECK constraints.
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "n7a8b9c0d1e2"
down_revision = "m6f7a8b9c0d1"
branch_labels = None
depends_on = None


def _add_constraint_if_missing(constraint_sql: str, constraint_name: str) -> None:
    stmt = constraint_sql.strip().rstrip(";") + ";"
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{constraint_name}'
            ) THEN
                EXECUTE $adr039${stmt}$adr039$;
            END IF;
        END $$
        """
    )


def upgrade() -> None:
    # Step 1: training_hour_requirements (+ indexes, seed DEFAULT_144)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.training_hour_requirements (
            requirement_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code                TEXT NOT NULL,
            name                TEXT NOT NULL,
            hours_required      INTEGER NOT NULL,
            window_years        INTEGER NOT NULL DEFAULT 5,
            date_basis          TEXT NOT NULL DEFAULT 'issued_at',
            specialty_group_id  BIGINT NULL,
            include_superseded  BOOLEAN NOT NULL DEFAULT FALSE,
            effective_from      DATE NOT NULL,
            effective_to        DATE NULL,
            is_active           BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order          INTEGER NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_training_hour_requirements_code
                UNIQUE (code),

            CONSTRAINT fk_training_hour_requirements_specialty_group
                FOREIGN KEY (specialty_group_id)
                REFERENCES public.medical_specialty_groups(group_id)
                ON DELETE SET NULL,

            CONSTRAINT chk_training_hour_requirements_hours_positive
                CHECK (hours_required > 0),

            CONSTRAINT chk_training_hour_requirements_window_positive
                CHECK (window_years > 0),

            CONSTRAINT chk_training_hour_requirements_date_basis
                CHECK (date_basis IN ('issued_at', 'end_date')),

            CONSTRAINT chk_training_hour_requirements_effective_range
                CHECK (effective_to IS NULL OR effective_to >= effective_from)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.training_hour_requirements IS
            'ADR-039: configurable training hour norms (e.g. 144h / 5y).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.training_hour_requirements.specialty_group_id IS
            'NULL = applies to all groups; DOCTOR/NURSE via medical_specialty_groups.code.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.training_hour_requirements.date_basis IS
            'Which employee_documents date column drives the rolling window.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.training_hour_requirements.include_superseded IS
            'Reserved; Phase 3C service defaults to FALSE (ACTIVE only).'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_training_hour_requirements_active
            ON public.training_hour_requirements (is_active, sort_order)
            WHERE is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_training_hour_requirements_group
            ON public.training_hour_requirements (specialty_group_id)
            WHERE specialty_group_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO public.training_hour_requirements (
            code, name, hours_required, window_years, date_basis,
            specialty_group_id, effective_from, is_active, sort_order
        )
        VALUES (
            'DEFAULT_144',
            'Норма НМО: 144 часа за 5 лет',
            144,
            5,
            'issued_at',
            NULL,
            DATE '2020-01-01',
            TRUE,
            10
        )
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            hours_required = EXCLUDED.hours_required,
            window_years = EXCLUDED.window_years,
            date_basis = EXCLUDED.date_basis,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order,
            updated_at = NOW()
        """
    )

    # Step 2: hr_import_normalized_records (without fk_hinr_promoted_document)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_normalized_records (
            normalized_record_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            batch_id                    BIGINT NOT NULL,
            row_id                      BIGINT NOT NULL,
            employee_id                 BIGINT NULL,
            fragment_index              INTEGER NOT NULL DEFAULT 0,
            source_field                TEXT NOT NULL,
            source_text                 TEXT NOT NULL,

            source_record_key           TEXT NOT NULL,

            record_kind                 TEXT NOT NULL,
            document_type_id            BIGINT NULL,
            document_type_code          TEXT NULL,

            title                       TEXT NULL,
            provider                    TEXT NULL,
            hours                       INTEGER NULL,
            start_date                  DATE NULL,
            end_date                    DATE NULL,
            issue_date                  DATE NULL,
            expiry_date                 DATE NULL,
            document_number             TEXT NULL,
            specialty_text              TEXT NULL,
            medical_specialty_id        BIGINT NULL,
            file_url                    TEXT NULL,

            parse_method                TEXT NOT NULL DEFAULT 'regex_v1',
            confidence                  NUMERIC(5, 4) NULL,

            review_status               TEXT NOT NULL DEFAULT 'pending',
            reviewed_at                 TIMESTAMPTZ NULL,
            reviewed_by                 BIGINT NULL,
            review_notes                TEXT NULL,
            promoted_document_id        BIGINT NULL,
            promoted_at                 TIMESTAMPTZ NULL,
            promoted_by                 BIGINT NULL,

            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT fk_hinr_batch
                FOREIGN KEY (batch_id)
                REFERENCES public.hr_import_batches(batch_id)
                ON DELETE CASCADE,

            CONSTRAINT fk_hinr_row
                FOREIGN KEY (row_id)
                REFERENCES public.hr_import_rows(row_id)
                ON DELETE CASCADE,

            CONSTRAINT fk_hinr_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id)
                ON DELETE SET NULL,

            CONSTRAINT fk_hinr_document_type
                FOREIGN KEY (document_type_id)
                REFERENCES public.document_types(document_type_id)
                ON DELETE SET NULL,

            CONSTRAINT fk_hinr_medical_specialty
                FOREIGN KEY (medical_specialty_id)
                REFERENCES public.medical_specialties(medical_specialty_id)
                ON DELETE SET NULL,

            CONSTRAINT fk_hinr_reviewed_by
                FOREIGN KEY (reviewed_by)
                REFERENCES public.users(user_id)
                ON DELETE SET NULL,

            CONSTRAINT fk_hinr_promoted_by
                FOREIGN KEY (promoted_by)
                REFERENCES public.users(user_id)
                ON DELETE SET NULL,

            CONSTRAINT uq_hinr_row_source_record_key
                UNIQUE (row_id, source_record_key),

            CONSTRAINT chk_hinr_record_kind
                CHECK (record_kind IN ('training', 'certificate', 'category', 'education')),

            CONSTRAINT chk_hinr_review_status
                CHECK (review_status IN (
                    'pending', 'approved', 'rejected', 'promoted', 'superseded'
                )),

            CONSTRAINT chk_hinr_parse_method
                CHECK (parse_method IN (
                    'regex_v1', 'manual_override', 'manual', 'ai_extraction', 'import_promoted'
                )),

            CONSTRAINT chk_hinr_hours_nonneg
                CHECK (hours IS NULL OR hours >= 0),

            CONSTRAINT chk_hinr_confidence_range
                CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),

            CONSTRAINT chk_hinr_fragment_index_nonneg
                CHECK (fragment_index >= 0),

            CONSTRAINT chk_hinr_source_field_nonempty
                CHECK (length(trim(source_field)) > 0),

            CONSTRAINT chk_hinr_source_record_key_nonempty
                CHECK (length(trim(source_record_key)) > 0),

            CONSTRAINT chk_hinr_date_order_start_end
                CHECK (
                    start_date IS NULL OR end_date IS NULL OR start_date <= end_date
                ),

            CONSTRAINT chk_hinr_date_order_issue_expiry
                CHECK (
                    issue_date IS NULL OR expiry_date IS NULL OR issue_date <= expiry_date
                ),

            CONSTRAINT chk_hinr_promoted_requires_document
                CHECK (
                    review_status <> 'promoted' OR promoted_document_id IS NOT NULL
                ),

            CONSTRAINT chk_hinr_rejected_no_promotion
                CHECK (
                    review_status <> 'rejected' OR promoted_document_id IS NULL
                )
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_import_normalized_records IS
            'ADR-039: parsed training/certificate/education records awaiting HR review and promotion.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.hr_import_normalized_records.source_record_key IS
            'Deterministic dedup key; UNIQUE per row_id; copied to employee_documents on promotion.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.hr_import_normalized_records.document_type_code IS
            'Staging fallback when document_type_id not yet resolved (parser proposed type code).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.hr_import_normalized_records.provider IS
            'Training organization / certificate issuer (maps to employee_documents.issued_by).'
        """
    )

    # Step 3: indexes on hr_import_normalized_records
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_batch_id
            ON public.hr_import_normalized_records (batch_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_row_id
            ON public.hr_import_normalized_records (row_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_employee_id
            ON public.hr_import_normalized_records (employee_id)
            WHERE employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_batch_review_status
            ON public.hr_import_normalized_records (batch_id, review_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_employee_review_open
            ON public.hr_import_normalized_records (employee_id, review_status)
            WHERE employee_id IS NOT NULL
              AND review_status IN ('pending', 'approved')
              AND promoted_document_id IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_promoted_document
            ON public.hr_import_normalized_records (promoted_document_id)
            WHERE promoted_document_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_record_kind
            ON public.hr_import_normalized_records (record_kind)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_expiry_date
            ON public.hr_import_normalized_records (expiry_date)
            WHERE expiry_date IS NOT NULL
              AND review_status IN ('pending', 'approved', 'promoted')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hinr_employee_source_key_open
            ON public.hr_import_normalized_records (employee_id, source_record_key)
            WHERE employee_id IS NOT NULL
              AND review_status IN ('pending', 'approved')
              AND promoted_document_id IS NULL
        """
    )

    # Step 4: employee_documents provenance columns
    op.execute(
        """
        ALTER TABLE public.employee_documents
            ADD COLUMN IF NOT EXISTS source_batch_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS source_row_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS source_normalized_record_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS source_record_key TEXT NULL,
            ADD COLUMN IF NOT EXISTS source_text TEXT NULL,
            ADD COLUMN IF NOT EXISTS parse_method TEXT NULL,
            ADD COLUMN IF NOT EXISTS parse_confidence NUMERIC(5, 4) NULL,
            ADD COLUMN IF NOT EXISTS end_date DATE NULL,
            ADD COLUMN IF NOT EXISTS verification_status TEXT NULL
        """
    )

    # Step 5: FK employee_documents → import tables / staging
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT fk_employee_documents_source_batch
                FOREIGN KEY (source_batch_id)
                REFERENCES public.hr_import_batches(batch_id)
                ON DELETE SET NULL
        """,
        "fk_employee_documents_source_batch",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT fk_employee_documents_source_row
                FOREIGN KEY (source_row_id)
                REFERENCES public.hr_import_rows(row_id)
                ON DELETE SET NULL
        """,
        "fk_employee_documents_source_row",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT fk_employee_documents_source_normalized_record
                FOREIGN KEY (source_normalized_record_id)
                REFERENCES public.hr_import_normalized_records(normalized_record_id)
                ON DELETE SET NULL
        """,
        "fk_employee_documents_source_normalized_record",
    )

    # Step 6: reverse FK hr_import_normalized_records → employee_documents
    _add_constraint_if_missing(
        """
        ALTER TABLE public.hr_import_normalized_records
            ADD CONSTRAINT fk_hinr_promoted_document
                FOREIGN KEY (promoted_document_id)
                REFERENCES public.employee_documents(document_id)
                ON DELETE SET NULL
        """,
        "fk_hinr_promoted_document",
    )

    # Step 7: CHECK constraints on employee_documents
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT chk_employee_documents_parse_confidence_range
                CHECK (parse_confidence IS NULL OR (parse_confidence >= 0 AND parse_confidence <= 1))
        """,
        "chk_employee_documents_parse_confidence_range",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT chk_employee_documents_parse_method
                CHECK (parse_method IS NULL OR parse_method IN (
                    'regex_v1', 'manual_override', 'manual', 'ai_extraction', 'import_promoted'
                ))
        """,
        "chk_employee_documents_parse_method",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT chk_employee_documents_verification_status
                CHECK (verification_status IS NULL OR verification_status IN (
                    'UNVERIFIED', 'VERIFIED', 'REJECTED'
                ))
        """,
        "chk_employee_documents_verification_status",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT chk_employee_documents_end_date_order
                CHECK (
                    issued_at IS NULL OR end_date IS NULL OR issued_at <= end_date
                )
        """,
        "chk_employee_documents_end_date_order",
    )
    _add_constraint_if_missing(
        """
        ALTER TABLE public.employee_documents
            ADD CONSTRAINT chk_employee_documents_source_record_key_nonempty
                CHECK (source_record_key IS NULL OR length(trim(source_record_key)) > 0)
        """,
        "chk_employee_documents_source_record_key_nonempty",
    )

    # Step 8: indexes on employee_documents
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_source_batch
            ON public.employee_documents (source_batch_id)
            WHERE source_batch_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_source_row
            ON public.employee_documents (source_row_id)
            WHERE source_row_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_source_normalized_record
            ON public.employee_documents (source_normalized_record_id)
            WHERE source_normalized_record_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_verification_status
            ON public.employee_documents (verification_status)
            WHERE verification_status IS NOT NULL
              AND lifecycle_status = 'ACTIVE'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_end_date
            ON public.employee_documents (end_date)
            WHERE end_date IS NOT NULL
              AND lifecycle_status = 'ACTIVE'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_documents_employee_source_key_active
            ON public.employee_documents (employee_id, source_record_key)
            WHERE lifecycle_status = 'ACTIVE'
              AND source_record_key IS NOT NULL
        """
    )


def downgrade() -> None:
    conn = op.get_bind()

    promoted_docs = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.employee_documents
            WHERE source_normalized_record_id IS NOT NULL
            """
        )
    ).scalar()
    if promoted_docs and int(promoted_docs) > 0:
        raise RuntimeError(
            "ADR-039 3B downgrade blocked: promoted documents exist "
            f"(source_normalized_record_id count={int(promoted_docs)}). Use forward migration."
        )

    staging_rows = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.hr_import_normalized_records
            """
        )
    ).scalar()
    if staging_rows and int(staging_rows) > 0:
        raise RuntimeError(
            "ADR-039 3B downgrade blocked: hr_import_normalized_records is not empty "
            f"(count={int(staging_rows)}). Export staging data or use forward migration."
        )

    # Step 8↓
    op.execute("DROP INDEX IF EXISTS public.uq_employee_documents_employee_source_key_active")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_end_date")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_verification_status")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_source_normalized_record")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_source_row")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_source_batch")

    # Step 7↓ + Step 5↓ + Step 6↓
    op.execute(
        """
        ALTER TABLE public.hr_import_normalized_records
            DROP CONSTRAINT IF EXISTS fk_hinr_promoted_document
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_documents
            DROP CONSTRAINT IF EXISTS chk_employee_documents_source_record_key_nonempty,
            DROP CONSTRAINT IF EXISTS chk_employee_documents_end_date_order,
            DROP CONSTRAINT IF EXISTS chk_employee_documents_verification_status,
            DROP CONSTRAINT IF EXISTS chk_employee_documents_parse_method,
            DROP CONSTRAINT IF EXISTS chk_employee_documents_parse_confidence_range,
            DROP CONSTRAINT IF EXISTS fk_employee_documents_source_normalized_record,
            DROP CONSTRAINT IF EXISTS fk_employee_documents_source_row,
            DROP CONSTRAINT IF EXISTS fk_employee_documents_source_batch
        """
    )

    # Step 4↓
    op.execute(
        """
        ALTER TABLE public.employee_documents
            DROP COLUMN IF EXISTS verification_status,
            DROP COLUMN IF EXISTS end_date,
            DROP COLUMN IF EXISTS parse_confidence,
            DROP COLUMN IF EXISTS parse_method,
            DROP COLUMN IF EXISTS source_text,
            DROP COLUMN IF EXISTS source_record_key,
            DROP COLUMN IF EXISTS source_normalized_record_id,
            DROP COLUMN IF EXISTS source_row_id,
            DROP COLUMN IF EXISTS source_batch_id
        """
    )

    # Steps 3↓ 2↓
    op.execute("DROP TABLE IF EXISTS public.hr_import_normalized_records CASCADE")

    # Step 1↓
    op.execute("DROP INDEX IF EXISTS public.ix_training_hour_requirements_group")
    op.execute("DROP INDEX IF EXISTS public.ix_training_hour_requirements_active")
    op.execute("DROP TABLE IF EXISTS public.training_hour_requirements CASCADE")
