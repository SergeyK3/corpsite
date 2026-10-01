"""Registered import/export package lifecycle and order review staging."""
from __future__ import annotations

from alembic import op


revision = "dxe001framework01"
down_revision = "ppr005qnotedetails01"
branch_labels = None
depends_on = None


_STATUSES = (
    "UPLOADED", "VALIDATING", "PREVIEW_READY", "BLOCKED", "DRY_RUN_PASSED",
    "AWAITING_CONFIRMATION", "APPLYING", "APPLIED", "FAILED", "CANCELLED",
)
_ROW_GROUPS = ("CREATE", "UPDATE", "UNCHANGED", "NOT_FOUND", "AMBIGUOUS", "ERROR", "POSSIBLE_DUPLICATE")
_PERMISSIONS = (
    "DATA_EXCHANGE_VIEW", "DATA_EXCHANGE_UPLOAD_PREVIEW", "DATA_EXCHANGE_DRY_RUN",
    "DATA_EXCHANGE_CONFIRM_APPLY", "DATA_EXCHANGE_EXPORT_REFERENCE",
)


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    statuses = _sql_list(_STATUSES)
    row_groups = _sql_list(_ROW_GROUPS)
    op.execute(
        f"""
        CREATE TABLE public.data_exchange_packages (
            package_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            scenario_code TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'UPLOADED',
            original_filename TEXT NOT NULL,
            media_type TEXT NULL,
            byte_size BIGINT NOT NULL,
            content_sha256 TEXT NOT NULL,
            file_content BYTEA NOT NULL,
            uploaded_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            validated_at TIMESTAMPTZ NULL,
            dry_run_at TIMESTAMPTZ NULL,
            dry_run_target_fingerprint TEXT NULL,
            confirmed_at TIMESTAMPTZ NULL,
            confirmed_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
            applied_at TIMESTAMPTZ NULL,
            applied_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
            counters JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            report JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            version INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT chk_data_exchange_packages_status CHECK (status IN ({statuses})),
            CONSTRAINT chk_data_exchange_packages_filename CHECK (
                btrim(original_filename) <> ''
                AND position('/' in original_filename) = 0
                AND position(chr(92) in original_filename) = 0
            ),
            CONSTRAINT chk_data_exchange_packages_size CHECK (byte_size > 0 AND byte_size <= 26214400),
            CONSTRAINT chk_data_exchange_packages_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{{64}}$'),
            CONSTRAINT chk_data_exchange_packages_version CHECK (version > 0),
            CONSTRAINT uq_data_exchange_packages_scenario_schema_sha UNIQUE (scenario_code, schema_version, content_sha256)
        );
        CREATE INDEX ix_data_exchange_packages_status_created
            ON public.data_exchange_packages(status, uploaded_at DESC);

        CREATE TABLE public.data_exchange_preview_rows (
            preview_row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            package_id BIGINT NOT NULL REFERENCES public.data_exchange_packages(package_id) ON DELETE CASCADE,
            source_row_number INTEGER NOT NULL,
            source_keys JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            target_ref JSONB NULL,
            result_group TEXT NOT NULL,
            proposed_action TEXT NOT NULL,
            reason_code TEXT NULL,
            message TEXT NULL,
            row_payload JSONB NULL,
            row_fingerprint TEXT NOT NULL,
            CONSTRAINT chk_data_exchange_preview_rows_number CHECK (source_row_number > 0),
            CONSTRAINT chk_data_exchange_preview_rows_group CHECK (result_group IN ({row_groups})),
            CONSTRAINT chk_data_exchange_preview_rows_fingerprint CHECK (row_fingerprint ~ '^[0-9a-f]{{64}}$'),
            CONSTRAINT uq_data_exchange_preview_rows_package_row UNIQUE(package_id, source_row_number)
        );
        CREATE INDEX ix_data_exchange_preview_rows_package_group
            ON public.data_exchange_preview_rows(package_id, result_group);

        CREATE TABLE public.data_exchange_audit_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            package_id BIGINT NOT NULL REFERENCES public.data_exchange_packages(package_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
            metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_data_exchange_audit_events_package_created
            ON public.data_exchange_audit_events(package_id, created_at);

        CREATE TABLE public.personnel_order_import_review_records (
            review_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            package_id BIGINT NOT NULL REFERENCES public.data_exchange_packages(package_id) ON DELETE RESTRICT,
            source_row_number INTEGER NOT NULL,
            business_key TEXT NOT NULL,
            employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
            order_kind TEXT NOT NULL,
            order_number TEXT NOT NULL,
            order_date DATE NOT NULL,
            action_type TEXT NOT NULL,
            source_payload JSONB NOT NULL,
            review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
            created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_order_import_review_status CHECK (review_status IN ('PENDING_REVIEW', 'REVIEWED', 'REJECTED', 'PROMOTED')),
            CONSTRAINT uq_personnel_order_import_review_business_key UNIQUE (business_key),
            CONSTRAINT uq_personnel_order_import_review_package_row UNIQUE(package_id, source_row_number)
        );
        CREATE INDEX ix_personnel_order_import_review_employee_status
            ON public.personnel_order_import_review_records(employee_id, review_status);
        """
    )
    for permission in _PERMISSIONS:
        op.execute(
            f"""
            INSERT INTO public.access_roles(code, name, description, access_level, level_rank, is_system)
            VALUES ('{permission}', '{permission.replace('_', ' ').title()}',
                    'Registered data exchange permission ({permission})', 'MANAGER', 20, TRUE)
            ON CONFLICT(code) DO UPDATE SET
                name=EXCLUDED.name, description=EXCLUDED.description,
                access_level=EXCLUDED.access_level, level_rank=EXCLUDED.level_rank,
                is_system=TRUE, is_active=TRUE, updated_at=now()
            """
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_order_import_review_records")
    op.execute("DROP TABLE IF EXISTS public.data_exchange_audit_events")
    op.execute("DROP TABLE IF EXISTS public.data_exchange_preview_rows")
    op.execute("DROP TABLE IF EXISTS public.data_exchange_packages")
    for permission in _PERMISSIONS:
        op.execute(
            f"DELETE FROM public.access_grants WHERE access_role_id IN "
            f"(SELECT access_role_id FROM public.access_roles WHERE code='{permission}')"
        )
        op.execute(f"DELETE FROM public.access_roles WHERE code='{permission}'")
