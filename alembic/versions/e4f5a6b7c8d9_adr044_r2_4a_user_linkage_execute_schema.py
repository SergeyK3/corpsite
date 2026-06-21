"""ADR-044 R2.4a — user linkage execute journal schema (no linkage writes).

Revision ID: e4f5a6b7c8d9
Revises: c2d3e4f5a6b7
"""
from __future__ import annotations

from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

_RUN_PHASES = ("R1a", "R2")
_RUN_OPERATIONS = ("USER_LINKAGE_EXECUTE_PREVIEW", "USER_LINKAGE_EXECUTE")
_ITEM_ACTIONS = (
    "LINK",
    "NOOP_ALREADY_LINKED",
    "SKIP_NOT_APPROVED",
    "SKIP_PREVIEW_DRIFT",
    "SKIP_CLASSIFICATION_REGRESSION",
    "SKIP_EXCLUDED",
    "FAIL_ALREADY_LINKED_DIFFERENT",
    "FAIL_EMPLOYEE_CONFLICT",
)
_ITEM_STATUSES = ("PLANNED", "APPLIED", "SKIPPED", "FAILED")
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
)


def upgrade() -> None:
    phases_sql = ", ".join(f"'{p}'" for p in _RUN_PHASES)
    operations_sql = ", ".join(f"'{o}'" for o in _RUN_OPERATIONS)
    item_actions_sql = ", ".join(f"'{a}'" for a in _ITEM_ACTIONS)
    item_statuses_sql = ", ".join(f"'{s}'" for s in _ITEM_STATUSES)
    sal_types_sql = ", ".join(f"'{t}'" for t in _SAL_EVENT_TYPES)

    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_phase
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.identity_reconciliation_runs
            ADD CONSTRAINT chk_irr_phase
                CHECK (phase IN ({phases_sql}))
        """
    )

    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            ADD COLUMN IF NOT EXISTS operation TEXT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_operation
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.identity_reconciliation_runs
            ADD CONSTRAINT chk_irr_operation
                CHECK (
                    operation IS NULL
                    OR operation IN ({operations_sql})
                )
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_phase_operation
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.identity_reconciliation_runs
            ADD CONSTRAINT chk_irr_phase_operation
                CHECK (
                    (phase = 'R1a' AND operation IS NULL)
                    OR (
                        phase = 'R2'
                        AND operation IS NOT NULL
                        AND operation IN ({operations_sql})
                    )
                )
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.identity_reconciliation_runs.actor_user_id IS
            'Execute/reconcile operator (R1a + R2). R2.4: serves as created_by_user_id.';
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.identity_reconciliation_runs.operation IS
            'R2 user linkage execute operation; NULL for legacy R1a runs.';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_phase_operation_started
            ON public.identity_reconciliation_runs (phase, operation, started_at DESC)
            WHERE phase = 'R2'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_runs IS
            'ADR-044 B2/R2.4a: identity reconciliation and user linkage execute run journal.';
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.user_linkage_execute_items (
            item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id BIGINT NOT NULL
                REFERENCES public.identity_reconciliation_runs (run_id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            proposed_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            source_decision_id BIGINT NULL
                REFERENCES public.user_linkage_review_decisions (decision_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PLANNED',
            reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
            preview_snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            decision_snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            before_user_snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            after_user_snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            rollback_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_ulei_action CHECK (action IN ({item_actions_sql})),
            CONSTRAINT chk_ulei_status CHECK (status IN ({item_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_run
            ON public.user_linkage_execute_items (run_id, item_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_user
            ON public.user_linkage_execute_items (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_proposed_employee
            ON public.user_linkage_execute_items (proposed_employee_id, created_at DESC)
            WHERE proposed_employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_source_decision
            ON public.user_linkage_execute_items (source_decision_id, created_at DESC)
            WHERE source_decision_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_action_status
            ON public.user_linkage_execute_items (action, status, created_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.user_linkage_execute_items IS
            'ADR-044 R2.4a: per-user user linkage execute line items (journal only; no users.employee_id writes in migration).';
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
        if t != "USER_EMPLOYEE_LINKED"
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

    op.execute("DROP TABLE IF EXISTS public.user_linkage_execute_items CASCADE")

    op.execute("DROP INDEX IF EXISTS public.ix_irr_phase_operation_started")
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_phase_operation
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_operation
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP COLUMN IF EXISTS operation
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            DROP CONSTRAINT IF EXISTS chk_irr_phase
        """
    )
    op.execute(
        """
        ALTER TABLE public.identity_reconciliation_runs
            ADD CONSTRAINT chk_irr_phase
                CHECK (phase = 'R1a')
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_runs IS
            'ADR-044 B2: R1a identity reconciliation run journal.';
        """
    )
