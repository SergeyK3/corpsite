"""WP-PO-EDIT-002 — Editorial persistence (normalized block-row model).

Creates:
  - personnel_order_editorial_blocks (order-level title/preamble/closing)
  - personnel_order_item_editorial_blocks (item-level body/basis)
  - personnel_order_item_bases (structured basis facts, 1:1 with item)

Extends security_audit_log.chk_sal_event_type with editorial event types.

Does NOT modify personnel_order_localized_texts.
"""
from __future__ import annotations

from alembic import op

revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None

_LOCALES = ("kk", "ru")
_ORDER_BLOCK_TYPES = ("title", "preamble", "closing")
_ITEM_BLOCK_TYPES = ("body", "basis")
_REVIEW_STATUSES = ("CURRENT", "STALE", "REVIEW_REQUIRED", "GENERATION_FAILED")
_BASIS_TYPES = (
    "PERSONAL_APPLICATION",
    "MEMO",
    "MANAGEMENT_SUBMISSION",
    "MEDICAL_CONCLUSION",
    "COMMISSION_PROTOCOL",
    "COURT_ACT",
    "OTHER",
)

_SAL_EVENT_TYPES = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "LOGOUT",
    "PASSWORD_RESET_REQUESTED",
    "PASSWORD_RESET_COMPLETED",
    "PASSWORD_CHANGED",
    "TEMP_PASSWORD_ISSUED",
    "USER_LOCKED",
    "USER_UNLOCKED",
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "ACCESS_CHANGED",
    "ENROLLMENT_APPROVED",
    "ENROLLMENT_REJECTED",
    "ENROLLMENT_COMPLETED",
    "USER_BLOCKED",
    "USER_UNBLOCKED",
    "PERSON_IIN_RECONCILED",
    "VISIBILITY_GRANTED",
    "VISIBILITY_REVOKED",
    "USER_EMPLOYEE_LINKED",
    "USER_EMPLOYEE_UNLINKED",
    "USER_EMPLOYEE_LINK_ROLLED_BACK",
    "EMPLOYEE_ENROLLED_FROM_IMPORT",
    "EDITORIAL_GENERATED",
    "EDITORIAL_REGENERATED",
    "EDITORIAL_OVERRIDE_UPDATED",
    "EDITORIAL_OVERRIDE_CLEARED",
    "EDITORIAL_MARKED_STALE",
    "READY_GATE_REJECTED",
)

_SAL_EVENT_TYPES_DOWN = tuple(
    t
    for t in _SAL_EVENT_TYPES
    if t
    not in {
        "EDITORIAL_GENERATED",
        "EDITORIAL_REGENERATED",
        "EDITORIAL_OVERRIDE_UPDATED",
        "EDITORIAL_OVERRIDE_CLEARED",
        "EDITORIAL_MARKED_STALE",
        "READY_GATE_REJECTED",
    }
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    locales_sql = _in_list(_LOCALES)
    order_block_types_sql = _in_list(_ORDER_BLOCK_TYPES)
    item_block_types_sql = _in_list(_ITEM_BLOCK_TYPES)
    review_statuses_sql = _in_list(_REVIEW_STATUSES)
    basis_types_sql = _in_list(_BASIS_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_editorial_blocks (
            editorial_block_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            locale TEXT NOT NULL,
            block_type TEXT NOT NULL,
            generated_text TEXT NULL,
            override_text TEXT NULL,
            generator_key TEXT NULL,
            generator_version TEXT NULL,
            source_fingerprint TEXT NULL,
            review_status TEXT NOT NULL DEFAULT 'CURRENT',
            generated_at TIMESTAMPTZ NULL,
            edited_at TIMESTAMPTZ NULL,
            edited_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            revision INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_personnel_order_editorial_blocks_order_locale_type
                UNIQUE (order_id, locale, block_type),
            CONSTRAINT chk_personnel_order_editorial_blocks_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_personnel_order_editorial_blocks_block_type
                CHECK (block_type IN ({order_block_types_sql})),
            CONSTRAINT chk_personnel_order_editorial_blocks_review_status
                CHECK (review_status IN ({review_statuses_sql})),
            CONSTRAINT chk_personnel_order_editorial_blocks_revision
                CHECK (revision > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_editorial_blocks_order_id
            ON public.personnel_order_editorial_blocks (order_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_order_editorial_blocks IS
            'WP-PO-EDIT-002: order-level editorial blocks (title/preamble/closing) per locale.'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_item_editorial_blocks (
            item_editorial_block_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_item_id BIGINT NOT NULL
                REFERENCES public.personnel_order_items (item_id) ON DELETE RESTRICT,
            locale TEXT NOT NULL,
            block_type TEXT NOT NULL,
            generated_text TEXT NULL,
            override_text TEXT NULL,
            generator_key TEXT NULL,
            generator_version TEXT NULL,
            source_fingerprint TEXT NULL,
            review_status TEXT NOT NULL DEFAULT 'CURRENT',
            basis_required BOOLEAN NOT NULL DEFAULT FALSE,
            generated_at TIMESTAMPTZ NULL,
            edited_at TIMESTAMPTZ NULL,
            edited_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            revision INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_personnel_order_item_editorial_blocks_item_locale_type
                UNIQUE (order_item_id, locale, block_type),
            CONSTRAINT chk_personnel_order_item_editorial_blocks_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_personnel_order_item_editorial_blocks_block_type
                CHECK (block_type IN ({item_block_types_sql})),
            CONSTRAINT chk_personnel_order_item_editorial_blocks_review_status
                CHECK (review_status IN ({review_statuses_sql})),
            CONSTRAINT chk_personnel_order_item_editorial_blocks_revision
                CHECK (revision > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_item_editorial_blocks_item_id
            ON public.personnel_order_item_editorial_blocks (order_item_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_order_item_editorial_blocks IS
            'WP-PO-EDIT-002: item-level editorial blocks (body/basis) per locale.'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_item_bases (
            item_basis_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_item_id BIGINT NOT NULL
                REFERENCES public.personnel_order_items (item_id) ON DELETE RESTRICT,
            basis_type TEXT NOT NULL,
            subject_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            document_date DATE NULL,
            document_number TEXT NULL,
            free_text TEXT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_personnel_order_item_bases_order_item_id
                UNIQUE (order_item_id),
            CONSTRAINT chk_personnel_order_item_bases_basis_type
                CHECK (basis_type IN ({basis_types_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_order_item_bases_order_item_id
            ON public.personnel_order_item_bases (order_item_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_order_item_bases IS
            'WP-PO-EDIT-002: structured basis facts (1:1 with order item); metadata is optional extras only.'
        """
    )

    sal_types_sql = _in_list(_SAL_EVENT_TYPES)
    op.execute(
        """
        ALTER TABLE public.security_audit_log
            DROP CONSTRAINT IF EXISTS chk_sal_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.security_audit_log
            ADD CONSTRAINT chk_sal_event_type
                CHECK (event_type IN ({sal_types_sql}))
        """
    )


def downgrade() -> None:
    sal_types_sql = _in_list(_SAL_EVENT_TYPES_DOWN)
    op.execute(
        """
        ALTER TABLE public.security_audit_log
            DROP CONSTRAINT IF EXISTS chk_sal_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.security_audit_log
            ADD CONSTRAINT chk_sal_event_type
                CHECK (event_type IN ({sal_types_sql}))
        """
    )

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_item_bases_order_item_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_item_bases")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_item_editorial_blocks_item_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_item_editorial_blocks")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_editorial_blocks_order_id")
    op.execute("DROP TABLE IF EXISTS public.personnel_order_editorial_blocks")
