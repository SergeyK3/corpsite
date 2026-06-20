"""ADR-044 B2 — identity reconciliation run journal (R1a execute).

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
"""
from __future__ import annotations

from alembic import op

revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None

_RUN_STATUSES = ("running", "completed", "failed", "cancelled")
_ITEM_STATUSES = ("planned", "applied", "skipped", "failed")
_ITEM_ACTIONS = (
    "UPDATE_PERSON_IIN",
    "INSERT_EMPLOYEE_IDENTITY",
    "NOOP",
    "SKIP",
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
)


def upgrade() -> None:
    run_statuses = ", ".join(f"'{s}'" for s in _RUN_STATUSES)
    item_statuses = ", ".join(f"'{s}'" for s in _ITEM_STATUSES)
    item_actions = ", ".join(f"'{a}'" for a in _ITEM_ACTIONS)
    sal_types_sql = ", ".join(f"'{t}'" for t in _SAL_EVENT_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.identity_reconciliation_runs (
            run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            phase TEXT NOT NULL DEFAULT 'R1a',
            dry_run BOOLEAN NOT NULL DEFAULT TRUE,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ NULL,
            status TEXT NOT NULL DEFAULT 'running',
            summary JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_irr_phase CHECK (phase = 'R1a'),
            CONSTRAINT chk_irr_status CHECK (status IN ({run_statuses}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_started
            ON public.identity_reconciliation_runs (started_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_snapshot_started
            ON public.identity_reconciliation_runs (snapshot_id, started_at DESC)
            WHERE snapshot_id IS NOT NULL
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_runs IS
            'ADR-044 B2: R1a identity reconciliation run journal.';
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.identity_reconciliation_items (
            item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id BIGINT NOT NULL
                REFERENCES public.identity_reconciliation_runs (run_id) ON DELETE CASCADE,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            previous_iin TEXT NULL,
            resolved_iin TEXT NULL,
            source TEXT NULL,
            outcome TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'NOOP',
            status TEXT NOT NULL DEFAULT 'planned',
            error TEXT NULL,
            rollback_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_iri_status CHECK (status IN ({item_statuses})),
            CONSTRAINT chk_iri_action CHECK (action IN ({item_actions}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_iri_run
            ON public.identity_reconciliation_items (run_id, item_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_iri_person
            ON public.identity_reconciliation_items (person_id, created_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_items IS
            'ADR-044 B2: per-person R1a reconciliation line items with rollback payload.';
        """
    )

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
    sal_types_sql = ", ".join(
        f"'{t}'"
        for t in _SAL_EVENT_TYPES
        if t != "PERSON_IIN_RECONCILED"
    )
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
    op.execute("DROP TABLE IF EXISTS public.identity_reconciliation_items CASCADE")
    op.execute("DROP TABLE IF EXISTS public.identity_reconciliation_runs CASCADE")
