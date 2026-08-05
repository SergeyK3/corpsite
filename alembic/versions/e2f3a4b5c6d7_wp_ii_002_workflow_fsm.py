"""WP-II-002 — Incoming Information workflow FSM foundation fix and schema."""
from __future__ import annotations

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

_NEW_STATUSES = (
    ("ASSIGNED", "Назначен исполнитель", False, 20),
    ("WAITING_INFORMATION", "Ожидает информации", False, 40),
    ("RESOLVED", "Исполнено", False, 50),
)

_LEGACY_DEACTIVATE = (
    "UNDER_REVIEW",
    "EXECUTOR_ASSIGNED",
    "AWAITING_INFO",
    "DRAFT_PREPARED",
    "ON_APPROVAL",
    "EXECUTED",
)

_LEGACY_TO_NEW = (
    ("EXECUTOR_ASSIGNED", "ASSIGNED"),
    ("AWAITING_INFO", "WAITING_INFORMATION"),
    ("EXECUTED", "RESOLVED"),
)

_AUDIT_ACTIONS = (
    "CREATED",
    "FIELD_CHANGED",
    "STATUS_CHANGED",
    "ASSIGNMENT_CHANGED",
    "LINK_ADDED",
    "LINK_REMOVED",
    "ATTACHMENT_ADDED",
    "ATTACHMENT_REMOVED",
    "OPERATION_ASSIGN",
    "OPERATION_REASSIGN",
    "OPERATION_TRANSFER",
    "OPERATION_START",
    "OPERATION_WAIT",
    "OPERATION_RESUME",
    "OPERATION_CHANGE_DEADLINE",
    "OPERATION_RESOLVE",
    "OPERATION_CLOSE",
    "OPERATION_REOPEN",
    "OPERATION_CANCEL",
)

_RECIPIENT_KINDS = ("USER", "ORG_UNIT", "TEXT")
_TRANSFER_SCOPES = ("INTERNAL", "EXTERNAL")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.incoming_document_attachments
            DROP CONSTRAINT IF EXISTS chk_incoming_document_attachments_file_id
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_document_attachments
            ADD CONSTRAINT chk_incoming_document_attachments_file_id
                CHECK (file_id ~ '^[a-f0-9]{32}$')
        """
    )

    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD COLUMN IF NOT EXISTS row_version INTEGER NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS closed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS cancelled_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS transferred_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS transferred_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS resolve_recorded_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS reopened_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS reopen_reason TEXT NULL,
            ADD COLUMN IF NOT EXISTS reopen_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS external_recipient_kind TEXT NULL,
            ADD COLUMN IF NOT EXISTS external_recipient_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS external_recipient_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS external_recipient_text TEXT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD CONSTRAINT chk_incoming_documents_row_version
                CHECK (row_version >= 1)
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD CONSTRAINT chk_incoming_documents_reopen_count
                CHECK (reopen_count >= 0)
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.incoming_documents
            ADD CONSTRAINT chk_incoming_documents_external_recipient_kind
                CHECK (
                    external_recipient_kind IS NULL
                    OR external_recipient_kind IN ({", ".join(repr(v) for v in _RECIPIENT_KINDS)})
                )
        """
    )

    op.execute(
        """
        ALTER TABLE public.incoming_document_assignments
            ADD COLUMN IF NOT EXISTS cancel_reason TEXT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_deadline_changes (
            deadline_change_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            previous_due_date DATE NULL,
            new_due_date DATE NOT NULL,
            reason TEXT NOT NULL,
            changed_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_incoming_document_deadline_changes_reason
                CHECK (btrim(reason) <> '')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_document_deadline_changes_document
            ON public.incoming_document_deadline_changes (incoming_document_id, changed_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.incoming_document_transfers (
            transfer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            transfer_scope TEXT NOT NULL,
            from_responsible_org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            to_responsible_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            recipient_kind TEXT NULL,
            recipient_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            recipient_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            recipient_text TEXT NULL,
            comment TEXT NOT NULL,
            previous_status_code TEXT NOT NULL,
            new_status_code TEXT NOT NULL,
            actor_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_incoming_document_transfers_scope
                CHECK (transfer_scope IN ({", ".join(repr(v) for v in _TRANSFER_SCOPES)})),
            CONSTRAINT chk_incoming_document_transfers_recipient_kind
                CHECK (
                    recipient_kind IS NULL
                    OR recipient_kind IN ({", ".join(repr(v) for v in _RECIPIENT_KINDS)})
                ),
            CONSTRAINT chk_incoming_document_transfers_comment
                CHECK (btrim(comment) <> '')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_document_transfers_document
            ON public.incoming_document_transfers (incoming_document_id, created_at DESC)
        """
    )

    for code, label, is_terminal, sort_order in _NEW_STATUSES:
        terminal_sql = "TRUE" if is_terminal else "FALSE"
        op.execute(
            f"""
            INSERT INTO public.incoming_document_statuses (code, label, is_terminal, sort_order)
            VALUES ('{code}', '{label}', {terminal_sql}, {sort_order})
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                is_terminal = EXCLUDED.is_terminal,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for code in _LEGACY_DEACTIVATE:
        op.execute(
            f"""
            UPDATE public.incoming_document_statuses
            SET is_active = FALSE, updated_at = now()
            WHERE code = '{code}'
            """
        )

    for old_code, new_code in _LEGACY_TO_NEW:
        op.execute(
            f"""
            UPDATE public.incoming_documents d
            SET status_id = ns.status_id
            FROM public.incoming_document_statuses os
            JOIN public.incoming_document_statuses ns ON ns.code = '{new_code}'
            WHERE d.status_id = os.status_id
              AND os.code = '{old_code}'
            """
        )

    op.execute(
        """
        ALTER TABLE public.incoming_document_audit
            DROP CONSTRAINT IF EXISTS chk_incoming_document_audit_action
        """
    )
    audit_actions_sql = ", ".join(f"'{value}'" for value in _AUDIT_ACTIONS)
    op.execute(
        f"""
        ALTER TABLE public.incoming_document_audit
            ADD CONSTRAINT chk_incoming_document_audit_action
                CHECK (action IN ({audit_actions_sql}))
        """
    )


_LEGACY_AUDIT_ACTIONS = (
    "CREATED",
    "FIELD_CHANGED",
    "STATUS_CHANGED",
    "ASSIGNMENT_CHANGED",
    "LINK_ADDED",
    "LINK_REMOVED",
    "ATTACHMENT_ADDED",
    "ATTACHMENT_REMOVED",
)


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.incoming_document_audit
            DROP CONSTRAINT IF EXISTS chk_incoming_document_audit_action
        """
    )
    op.execute(
        """
        DELETE FROM public.incoming_document_audit
        WHERE action LIKE 'OPERATION_%'
        """
    )
    legacy_actions_sql = ", ".join(f"'{value}'" for value in _LEGACY_AUDIT_ACTIONS)
    op.execute(
        f"""
        ALTER TABLE public.incoming_document_audit
            ADD CONSTRAINT chk_incoming_document_audit_action
                CHECK (action IN ({legacy_actions_sql}))
        """
    )
    op.execute("DROP TABLE IF EXISTS public.incoming_document_transfers CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_deadline_changes CASCADE")
    op.execute(
        """
        ALTER TABLE public.incoming_document_assignments
            DROP COLUMN IF EXISTS cancel_reason
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            DROP CONSTRAINT IF EXISTS chk_incoming_documents_external_recipient_kind,
            DROP CONSTRAINT IF EXISTS chk_incoming_documents_reopen_count,
            DROP CONSTRAINT IF EXISTS chk_incoming_documents_row_version,
            DROP COLUMN IF EXISTS external_recipient_text,
            DROP COLUMN IF EXISTS external_recipient_org_unit_id,
            DROP COLUMN IF EXISTS external_recipient_user_id,
            DROP COLUMN IF EXISTS external_recipient_kind,
            DROP COLUMN IF EXISTS reopen_count,
            DROP COLUMN IF EXISTS reopen_reason,
            DROP COLUMN IF EXISTS reopened_at,
            DROP COLUMN IF EXISTS resolve_recorded_at,
            DROP COLUMN IF EXISTS transferred_by_user_id,
            DROP COLUMN IF EXISTS transferred_at,
            DROP COLUMN IF EXISTS cancelled_by_user_id,
            DROP COLUMN IF EXISTS cancelled_at,
            DROP COLUMN IF EXISTS closed_by_user_id,
            DROP COLUMN IF EXISTS row_version
        """
    )
    for code, _, _, _ in reversed(_NEW_STATUSES):
        op.execute(
            f"""
            UPDATE public.incoming_documents d
            SET status_id = os.status_id
            FROM public.incoming_document_statuses ns
            JOIN public.incoming_document_statuses os ON os.code = 'REGISTERED'
            WHERE d.status_id = ns.status_id
              AND ns.code = '{code}'
            """
        )
        op.execute(
            f"""
            DELETE FROM public.incoming_document_statuses
            WHERE code = '{code}'
            """
        )
    for code in _LEGACY_DEACTIVATE:
        op.execute(
            f"""
            UPDATE public.incoming_document_statuses
            SET is_active = TRUE, updated_at = now()
            WHERE code = '{code}'
            """
        )
