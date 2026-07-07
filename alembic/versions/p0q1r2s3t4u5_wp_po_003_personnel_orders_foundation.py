"""WP-PO-003 — Personnel orders storage foundation.

Creates personnel_orders, personnel_order_items, personnel_order_localized_texts,
personnel_order_attachments, personnel_order_prints; adds employee_events.order_id
and employee_events.order_item_id FK columns.

MVP order types: HIRE, TRANSFER, TERMINATION, CONCURRENT_DUTY_START, CONCURRENT_DUTY_END.
"""
from __future__ import annotations

from alembic import op

revision = "p0q1r2s3t4u5"
down_revision = "o9p0q1r2s3t4"
branch_labels = None
depends_on = None

_MVP_ITEM_TYPES = (
    "HIRE",
    "TRANSFER",
    "TERMINATION",
    "CONCURRENT_DUTY_START",
    "CONCURRENT_DUTY_END",
)
_MVP_HEADER_TYPES = _MVP_ITEM_TYPES + ("COMPOSITE",)

_ORDER_STATUSES = (
    "DRAFT",
    "READY_FOR_SIGNATURE",
    "SIGNED",
    "REGISTERED",
    "VOIDED",
)

_ITEM_STATUSES = ("ACTIVE", "VOIDED")
_SOURCE_MODES = ("PAPER", "DIGITAL")
_LOCALES = ("kk", "ru")
_ATTACHMENT_KINDS = ("SIGNED_SCAN", "BASIS_DOCUMENT", "UNSIGNED_DRAFT")
_STORAGE_TYPES = ("LOCAL_SHARE", "URL")
_PRINT_FORMATS = ("pdf", "docx")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    header_types_sql = _in_list(_MVP_HEADER_TYPES)
    item_types_sql = _in_list(_MVP_ITEM_TYPES)
    order_statuses_sql = _in_list(_ORDER_STATUSES)
    item_statuses_sql = _in_list(_ITEM_STATUSES)
    source_modes_sql = _in_list(_SOURCE_MODES)
    locales_sql = _in_list(_LOCALES)
    attachment_kinds_sql = _in_list(_ATTACHMENT_KINDS)
    storage_types_sql = _in_list(_STORAGE_TYPES)
    print_formats_sql = _in_list(_PRINT_FORMATS)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_orders (
            order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_number TEXT NOT NULL,
            order_date DATE NOT NULL,
            order_type_code TEXT NOT NULL,
            order_class TEXT NOT NULL DEFAULT 'PERSONNEL',
            status TEXT NOT NULL,
            source_mode TEXT NOT NULL,
            legal_basis_article TEXT NULL,
            signed_by_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            signed_by_name TEXT NULL,
            signed_by_position TEXT NULL,
            executor_name TEXT NULL,
            basis_summary TEXT NULL,
            comment TEXT NULL,
            void_reason TEXT NULL,
            voided_at TIMESTAMPTZ NULL,
            voided_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            created_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_personnel_orders_order_number
                UNIQUE (order_number),
            CONSTRAINT chk_personnel_orders_order_type_code
                CHECK (order_type_code IN ({header_types_sql})),
            CONSTRAINT chk_personnel_orders_order_class
                CHECK (order_class = 'PERSONNEL'),
            CONSTRAINT chk_personnel_orders_status
                CHECK (status IN ({order_statuses_sql})),
            CONSTRAINT chk_personnel_orders_source_mode
                CHECK (source_mode IN ({source_modes_sql})),
            CONSTRAINT chk_personnel_orders_void_reason
                CHECK (
                    status <> 'VOIDED'
                    OR (void_reason IS NOT NULL AND btrim(void_reason) <> '')
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_orders_status
            ON public.personnel_orders (status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_orders_order_date
            ON public.personnel_orders (order_date DESC, order_id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_orders_type_code
            ON public.personnel_orders (order_type_code)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_orders IS
            'WP-PO-003: personnel order header (кадровый приказ). MVP class PERSONNEL only.'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_items (
            item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            item_number INTEGER NOT NULL,
            item_type_code TEXT NOT NULL,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            effective_date DATE NULL,
            period_start DATE NULL,
            period_end DATE NULL,
            payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            item_status TEXT NOT NULL DEFAULT 'ACTIVE',
            void_reason TEXT NULL,
            voided_at TIMESTAMPTZ NULL,
            voided_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_personnel_order_items_order_item_number
                UNIQUE (order_id, item_number),
            CONSTRAINT chk_personnel_order_items_item_type_code
                CHECK (item_type_code IN ({item_types_sql})),
            CONSTRAINT chk_personnel_order_items_item_status
                CHECK (item_status IN ({item_statuses_sql})),
            CONSTRAINT chk_personnel_order_items_item_number_positive
                CHECK (item_number > 0),
            CONSTRAINT chk_personnel_order_items_void_reason
                CHECK (
                    item_status <> 'VOIDED'
                    OR (void_reason IS NOT NULL AND btrim(void_reason) <> '')
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_items_order_id
            ON public.personnel_order_items (order_id, item_number)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_items_employee_id
            ON public.personnel_order_items (employee_id, effective_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_items_type_code
            ON public.personnel_order_items (item_type_code)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_order_items IS
            'WP-PO-003: numbered clause within a personnel order; may produce 0..N employee_events.'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_localized_texts (
            localized_text_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            locale TEXT NOT NULL,
            title TEXT NULL,
            preamble TEXT NULL,
            body_text TEXT NULL,
            render_version INTEGER NOT NULL DEFAULT 1,
            is_authoritative BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_personnel_order_localized_texts_order_locale
                UNIQUE (order_id, locale),
            CONSTRAINT chk_personnel_order_localized_texts_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_personnel_order_localized_texts_render_version
                CHECK (render_version > 0)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_localized_texts_order_id
            ON public.personnel_order_localized_texts (order_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_attachments (
            attachment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            attachment_kind TEXT NOT NULL,
            storage_type TEXT NOT NULL DEFAULT 'LOCAL_SHARE',
            file_path TEXT NULL,
            file_url TEXT NULL,
            file_comment TEXT NULL,
            locale TEXT NULL,
            created_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_order_attachments_kind
                CHECK (attachment_kind IN ({attachment_kinds_sql})),
            CONSTRAINT chk_personnel_order_attachments_storage_type
                CHECK (storage_type IN ({storage_types_sql})),
            CONSTRAINT chk_personnel_order_attachments_locale
                CHECK (locale IS NULL OR locale IN ({locales_sql})),
            CONSTRAINT chk_personnel_order_attachments_file_ref
                CHECK (file_path IS NOT NULL OR file_url IS NOT NULL)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_attachments_order_id
            ON public.personnel_order_attachments (order_id, created_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_prints (
            print_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            locale TEXT NOT NULL,
            format TEXT NOT NULL,
            file_path TEXT NULL,
            file_url TEXT NULL,
            is_signed_copy BOOLEAN NOT NULL DEFAULT FALSE,
            render_version INTEGER NOT NULL DEFAULT 1,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            generated_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            CONSTRAINT chk_personnel_order_prints_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_personnel_order_prints_format
                CHECK (format IN ({print_formats_sql})),
            CONSTRAINT chk_personnel_order_prints_render_version
                CHECK (render_version > 0),
            CONSTRAINT chk_personnel_order_prints_file_ref
                CHECK (file_path IS NOT NULL OR file_url IS NOT NULL)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_prints_order_id
            ON public.personnel_order_prints (order_id, generated_at DESC)
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD COLUMN IF NOT EXISTS order_id BIGINT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD COLUMN IF NOT EXISTS order_item_id BIGINT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_employee_events_order'
            ) THEN
                ALTER TABLE public.employee_events
                    ADD CONSTRAINT fk_employee_events_order
                        FOREIGN KEY (order_id)
                        REFERENCES public.personnel_orders (order_id)
                        ON DELETE RESTRICT;
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_employee_events_order_item'
            ) THEN
                ALTER TABLE public.employee_events
                    ADD CONSTRAINT fk_employee_events_order_item
                        FOREIGN KEY (order_item_id)
                        REFERENCES public.personnel_order_items (item_id)
                        ON DELETE RESTRICT;
            END IF;
        END
        $$
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_events_order_id
            ON public.employee_events (order_id)
            WHERE order_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_events_order_item_id
            ON public.employee_events (order_item_id)
            WHERE order_item_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_employee_events_order_item_id")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_events_order_id")

    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS fk_employee_events_order_item
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS fk_employee_events_order
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP COLUMN IF EXISTS order_item_id
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP COLUMN IF EXISTS order_id
        """
    )

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_prints_order_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_prints")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_attachments_order_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_attachments")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_localized_texts_order_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_localized_texts")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_items_type_code")
    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_items_employee_id")
    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_items_order_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_items")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_orders_type_code")
    op.execute("DROP INDEX IF EXISTS public.ix_personnel_orders_order_date")
    op.execute("DROP INDEX IF EXISTS public.ix_personnel_orders_status")
    op.execute("DROP TABLE IF EXISTS public.personnel_orders")
