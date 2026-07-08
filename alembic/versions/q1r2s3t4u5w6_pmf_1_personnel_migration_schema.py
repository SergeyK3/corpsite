"""PMF-1 — Personnel Migration Framework schema foundation.

Creates personnel_migration_domains, personnel_migration_runs,
personnel_migration_items, personnel_record_events, person_education,
person_training; seeds disabled education domain plugin.

See docs/adr/ADR-PMF-001-personnel-migration-framework.md and
docs/adr/ADR-EDU-001-employee-education-migration-architecture.md.
"""
from __future__ import annotations

from alembic import op

revision = "q1r2s3t4u5w6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None

_RUN_STATUSES = ("draft", "committed", "voided", "failed")
_ITEM_STATUSES = ("draft", "committed", "voided", "superseded", "failed")
_EDUCATION_KINDS = ("basic", "internship", "residency", "masters", "phd", "other")
_INSTITUTION_TYPES = ("university", "college", "other", "unknown")
_TRAINING_KINDS = (
    "continuing_education",
    "course",
    "seminar",
    "master_class",
    "certificate",
    "other",
)
_VERIFICATION_STATUSES = ("pending", "verified", "needs_attention", "rejected")
_LIFECYCLE_STATUSES = ("draft", "active", "superseded", "voided")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    run_statuses_sql = _in_list(_RUN_STATUSES)
    item_statuses_sql = _in_list(_ITEM_STATUSES)
    education_kinds_sql = _in_list(_EDUCATION_KINDS)
    institution_types_sql = _in_list(_INSTITUTION_TYPES)
    training_kinds_sql = _in_list(_TRAINING_KINDS)
    verification_statuses_sql = _in_list(_VERIFICATION_STATUSES)
    lifecycle_statuses_sql = _in_list(_LIFECYCLE_STATUSES)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.personnel_migration_domains (
            domain_code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT NULL,
            is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            target_table_names JSONB NOT NULL DEFAULT '[]'::jsonb,
            control_list_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_migration_domains IS
            'PMF-1: registry of personnel migration domain plugins (ADR-PMF-001 §5.1).'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_migration_runs (
            run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            domain_code TEXT NOT NULL
                REFERENCES public.personnel_migration_domains (domain_code)
                ON DELETE RESTRICT,
            employee_context_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            run_status TEXT NOT NULL DEFAULT 'draft',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            committed_at TIMESTAMPTZ NULL,
            voided_at TIMESTAMPTZ NULL,
            started_by TEXT NULL,
            committed_by TEXT NULL,
            voided_by TEXT NULL,
            void_reason TEXT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_pmf_runs_status
                CHECK (run_status IN ({run_statuses_sql})),
            CONSTRAINT chk_pmf_runs_void_reason
                CHECK (
                    run_status <> 'voided'
                    OR (void_reason IS NOT NULL AND btrim(void_reason) <> '')
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pmf_runs_domain_person
            ON public.personnel_migration_runs (domain_code, person_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_migration_runs IS
            'PMF-1: technical audit trail for migration wizard sessions (ADR-PMF-001 §4.5).'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_migration_items (
            item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id BIGINT NOT NULL
                REFERENCES public.personnel_migration_runs (run_id) ON DELETE CASCADE,
            domain_code TEXT NOT NULL
                REFERENCES public.personnel_migration_domains (domain_code)
                ON DELETE RESTRICT,
            source_kind TEXT NOT NULL,
            source_record_id TEXT NULL,
            import_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            import_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            record_kind TEXT NULL,
            target_table_name TEXT NULL,
            target_record_id BIGINT NULL,
            item_status TEXT NOT NULL DEFAULT 'draft',
            draft_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            source_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            committed_at TIMESTAMPTZ NULL,
            voided_at TIMESTAMPTZ NULL,
            void_reason TEXT NULL,
            CONSTRAINT chk_pmf_items_status
                CHECK (item_status IN ({item_statuses_sql})),
            CONSTRAINT chk_pmf_items_void_reason
                CHECK (
                    item_status <> 'voided'
                    OR (void_reason IS NOT NULL AND btrim(void_reason) <> '')
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pmf_items_run_id
            ON public.personnel_migration_items (run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pmf_items_domain_import
            ON public.personnel_migration_items (domain_code, import_batch_id, import_row_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_migration_items IS
            'PMF-1: per-candidate mapping between staging source and committed personnel record.'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.person_education (
            education_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            employee_context_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            education_kind TEXT NOT NULL,
            institution_type TEXT NULL,
            institution_name TEXT NULL,
            specialty TEXT NULL,
            qualification TEXT NULL,
            started_at DATE NULL,
            completed_at DATE NULL,
            diploma_number TEXT NULL,
            document_date DATE NULL,
            verification_status TEXT NOT NULL DEFAULT 'pending',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            import_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            import_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            source_field TEXT NULL,
            source_text TEXT NULL,
            parse_method TEXT NULL,
            confidence NUMERIC NULL,
            migrated_at TIMESTAMPTZ NULL,
            migrated_by TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_person_education_kind
                CHECK (education_kind IN ({education_kinds_sql})),
            CONSTRAINT chk_person_education_institution_type
                CHECK (
                    institution_type IS NULL
                    OR institution_type IN ({institution_types_sql})
                ),
            CONSTRAINT chk_person_education_verification_status
                CHECK (verification_status IN ({verification_statuses_sql})),
            CONSTRAINT chk_person_education_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_education_person_id
            ON public.person_education (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_education_person_lifecycle
            ON public.person_education (person_id, lifecycle_status)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_education IS
            'PMF-1 / ADR-EDU-001: permanent structured education records (person-owned SoT).'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.person_training (
            training_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            employee_context_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            training_kind TEXT NOT NULL,
            title TEXT NULL,
            organization_name TEXT NULL,
            hours NUMERIC NULL,
            started_at DATE NULL,
            completed_at DATE NULL,
            certificate_number TEXT NULL,
            document_date DATE NULL,
            verification_status TEXT NOT NULL DEFAULT 'pending',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            import_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            import_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            source_field TEXT NULL,
            source_text TEXT NULL,
            parse_method TEXT NULL,
            confidence NUMERIC NULL,
            migrated_at TIMESTAMPTZ NULL,
            migrated_by TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_person_training_kind
                CHECK (training_kind IN ({training_kinds_sql})),
            CONSTRAINT chk_person_training_verification_status
                CHECK (verification_status IN ({verification_statuses_sql})),
            CONSTRAINT chk_person_training_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_training_person_id
            ON public.person_training (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_person_training_person_lifecycle
            ON public.person_training (person_id, lifecycle_status)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_training IS
            'PMF-1 / ADR-EDU-001: permanent continuing education / course records (person-owned SoT).'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.personnel_record_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            employee_context_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            domain_code TEXT NOT NULL
                REFERENCES public.personnel_migration_domains (domain_code)
                ON DELETE RESTRICT,
            record_table_name TEXT NOT NULL,
            record_id BIGINT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor_id TEXT NULL,
            event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            migration_run_id BIGINT NULL
                REFERENCES public.personnel_migration_runs (run_id) ON DELETE SET NULL,
            migration_item_id BIGINT NULL
                REFERENCES public.personnel_migration_items (item_id) ON DELETE SET NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_record_events_person_domain
            ON public.personnel_record_events (person_id, domain_code)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_record_events IS
            'PMF-1: business history journal for person-owned personnel records (ADR-PMF-001 §4.8).'
        """
    )

    op.execute(
        """
        INSERT INTO public.personnel_migration_domains (
            domain_code,
            display_name,
            description,
            is_enabled,
            target_table_names,
            control_list_columns
        )
        VALUES (
            'education',
            'Образование',
            'Education domain plugin — person_education and person_training (ADR-EDU-001)',
            FALSE,
            '["person_education", "person_training"]'::jsonb,
            '["H", "I", "K", "M"]'::jsonb
        )
        ON CONFLICT (domain_code) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            is_enabled = EXCLUDED.is_enabled,
            target_table_names = EXCLUDED.target_table_names,
            control_list_columns = EXCLUDED.control_list_columns,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_record_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.person_training CASCADE")
    op.execute("DROP TABLE IF EXISTS public.person_education CASCADE")
    op.execute("DROP TABLE IF EXISTS public.personnel_migration_items CASCADE")
    op.execute("DROP TABLE IF EXISTS public.personnel_migration_runs CASCADE")
    op.execute(
        """
        DELETE FROM public.personnel_migration_domains
        WHERE domain_code = 'education'
        """
    )
    op.execute("DROP TABLE IF EXISTS public.personnel_migration_domains CASCADE")
