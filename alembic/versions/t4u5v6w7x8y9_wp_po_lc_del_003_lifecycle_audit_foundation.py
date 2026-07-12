"""WP-PO-LC-DEL-003 — Personnel order lifecycle audit and permission foundation.

Adds nullable lifecycle foundation columns on personnel_orders, creates
personnel_order_lifecycle_audit (append-only), backfills void_kind for VOIDED
orders, and seeds PERSONNEL_ORDERS_* access_roles (not wired to enforcement).
"""
from __future__ import annotations

from alembic import op

revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None

_VOID_KINDS = ("CANCEL", "ANNUL")
_LIFECYCLE_AUDIT_ACTIONS = (
    "CANCEL",
    "ANNUL",
    "ARCHIVE",
    "RESTORE",
    "VOID_APPLIED",
    "HARD_DELETE",
    "COMPENSATE_LINK",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    void_kinds_sql = _in_list(_VOID_KINDS)
    actions_sql = _in_list(_LIFECYCLE_AUDIT_ACTIONS)

    op.execute(
        f"""
        ALTER TABLE public.personnel_orders
            ADD COLUMN IF NOT EXISTS void_kind TEXT NULL,
            ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS archived_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS archive_reason_code TEXT NULL,
            ADD COLUMN IF NOT EXISTS archive_reason_text TEXT NULL
        """
    )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_personnel_orders_void_kind'
            ) THEN
                ALTER TABLE public.personnel_orders
                    ADD CONSTRAINT chk_personnel_orders_void_kind
                        CHECK (
                            void_kind IS NULL
                            OR void_kind IN ({void_kinds_sql})
                        );
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_orders_archived_at
            ON public.personnel_orders (archived_at)
            WHERE archived_at IS NOT NULL
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_order_lifecycle_audit (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            previous_status TEXT NULL,
            new_status TEXT NULL,
            previous_void_kind TEXT NULL,
            new_void_kind TEXT NULL,
            actor_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            reason_code TEXT NULL,
            reason_text TEXT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_order_lifecycle_audit_action
                CHECK (action IN ({actions_sql})),
            CONSTRAINT chk_personnel_order_lifecycle_audit_prev_void_kind
                CHECK (
                    previous_void_kind IS NULL
                    OR previous_void_kind IN ({void_kinds_sql})
                ),
            CONSTRAINT chk_personnel_order_lifecycle_audit_new_void_kind
                CHECK (
                    new_void_kind IS NULL
                    OR new_void_kind IN ({void_kinds_sql})
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_po_lifecycle_audit_order_created
            ON public.personnel_order_lifecycle_audit (order_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_po_lifecycle_audit_actor_created
            ON public.personnel_order_lifecycle_audit (actor_user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_po_lifecycle_audit_action
            ON public.personnel_order_lifecycle_audit (action)
        """
    )

    # Idempotent void_kind backfill (PO-LC-DEL-002 heuristic).
    op.execute(
        f"""
        UPDATE public.personnel_orders po
        SET void_kind = 'ANNUL'
        WHERE po.status = 'VOIDED'
          AND po.void_kind IS NULL
          AND EXISTS (
              SELECT 1
              FROM public.employee_events ev
              WHERE ev.order_id = po.order_id
          )
        """
    )
    op.execute(
        """
        UPDATE public.personnel_orders po
        SET void_kind = 'ANNUL'
        WHERE po.status = 'VOIDED'
          AND po.void_kind IS NULL
          AND (
              po.signed_by_employee_id IS NOT NULL
              OR NULLIF(btrim(po.signed_by_name), '') IS NOT NULL
              OR NULLIF(btrim(po.signed_by_position), '') IS NOT NULL
              OR (
                  po.order_number IS NOT NULL
                  AND po.order_date IS NOT NULL
                  AND po.voided_at IS NOT NULL
                  AND po.voided_at > po.created_at + interval '1 minute'
              )
          )
        """
    )
    op.execute(
        """
        UPDATE public.personnel_orders po
        SET void_kind = 'CANCEL'
        WHERE po.status = 'VOIDED'
          AND po.void_kind IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        )
        VALUES
            (
                'PERSONNEL_ORDERS_CANCEL_OWN',
                'Personnel Orders — Cancel Own',
                'Cancel own draft/ready personnel orders (WP-PO-LC-DEL-003 foundation)',
                'MANAGER', 20, TRUE
            ),
            (
                'PERSONNEL_ORDERS_CANCEL_SCOPE',
                'Personnel Orders — Cancel In Scope',
                'Cancel subordinate draft/ready personnel orders (WP-PO-LC-DEL-003 foundation)',
                'MANAGER', 20, TRUE
            ),
            (
                'PERSONNEL_ORDERS_VOID',
                'Personnel Orders — Void',
                'Annul signed/registered personnel orders not yet applied (WP-PO-LC-DEL-003 foundation)',
                'MANAGER', 20, TRUE
            ),
            (
                'PERSONNEL_ORDERS_VOID_APPLIED',
                'Personnel Orders — Void Applied',
                'Governance void with rollback for applied personnel orders (WP-PO-LC-DEL-003 foundation)',
                'ADMIN', 30, TRUE
            ),
            (
                'PERSONNEL_ORDERS_ARCHIVE',
                'Personnel Orders — Archive',
                'Archive completed or voided personnel orders (WP-PO-LC-DEL-003 foundation)',
                'MANAGER', 20, TRUE
            ),
            (
                'PERSONNEL_ORDERS_RESTORE',
                'Personnel Orders — Restore',
                'Restore archived personnel orders (WP-PO-LC-DEL-003 foundation)',
                'MANAGER', 20, TRUE
            ),
            (
                'PERSONNEL_ORDERS_AUDIT_READ',
                'Personnel Orders — Lifecycle Audit Read',
                'Read personnel order lifecycle audit trail (WP-PO-LC-DEL-003 foundation)',
                'OBSERVER', 10, TRUE
            ),
            (
                'PERSONNEL_RECOVERY_ADMIN',
                'Personnel Recovery Administrator',
                'Maintenance hard delete for personnel orders (WP-PO-LC-DEL-003 foundation)',
                'ADMIN', 30, TRUE
            )
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            access_level = EXCLUDED.access_level,
            level_rank = EXCLUDED.level_rank,
            is_system = EXCLUDED.is_system,
            is_active = TRUE,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM public.access_roles
        WHERE code IN (
            'PERSONNEL_ORDERS_CANCEL_OWN',
            'PERSONNEL_ORDERS_CANCEL_SCOPE',
            'PERSONNEL_ORDERS_VOID',
            'PERSONNEL_ORDERS_VOID_APPLIED',
            'PERSONNEL_ORDERS_ARCHIVE',
            'PERSONNEL_ORDERS_RESTORE',
            'PERSONNEL_ORDERS_AUDIT_READ',
            'PERSONNEL_RECOVERY_ADMIN'
        )
          AND NOT EXISTS (
              SELECT 1
              FROM public.access_grants g
              JOIN public.access_roles r ON r.access_role_id = g.access_role_id
              WHERE r.code IN (
                  'PERSONNEL_ORDERS_CANCEL_OWN',
                  'PERSONNEL_ORDERS_CANCEL_SCOPE',
                  'PERSONNEL_ORDERS_VOID',
                  'PERSONNEL_ORDERS_VOID_APPLIED',
                  'PERSONNEL_ORDERS_ARCHIVE',
                  'PERSONNEL_ORDERS_RESTORE',
                  'PERSONNEL_ORDERS_AUDIT_READ',
                  'PERSONNEL_RECOVERY_ADMIN'
              )
          )
        """
    )

    op.execute("DROP TABLE IF EXISTS public.personnel_order_lifecycle_audit CASCADE")

    op.execute("DROP INDEX IF EXISTS public.ix_personnel_orders_archived_at")

    op.execute(
        """
        ALTER TABLE public.personnel_orders
            DROP CONSTRAINT IF EXISTS chk_personnel_orders_void_kind
        """
    )
    op.execute(
        """
        ALTER TABLE public.personnel_orders
            DROP COLUMN IF EXISTS archive_reason_text,
            DROP COLUMN IF EXISTS archive_reason_code,
            DROP COLUMN IF EXISTS archived_by,
            DROP COLUMN IF EXISTS archived_at,
            DROP COLUMN IF EXISTS void_kind
        """
    )
