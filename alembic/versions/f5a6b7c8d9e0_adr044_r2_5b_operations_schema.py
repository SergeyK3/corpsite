"""ADR-044 R2.5b — user linkage operations journal schema extensions (DDL only).

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""
from __future__ import annotations

from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None

# R2.4 operations (unchanged)
_RUN_OPERATIONS_R2_4 = (
    "USER_LINKAGE_EXECUTE_PREVIEW",
    "USER_LINKAGE_EXECUTE",
)
# R2.5 operations (added)
_RUN_OPERATIONS_R2_5 = (
    "USER_LINKAGE_MANUAL_LINK",
    "USER_LINKAGE_MANUAL_UNLINK",
    "USER_LINKAGE_ROLLBACK_ITEM",
    "USER_LINKAGE_REPAIR_PREVIEW",
    "USER_LINKAGE_RERUN_EXECUTE",
)
_RUN_OPERATIONS = _RUN_OPERATIONS_R2_4 + _RUN_OPERATIONS_R2_5

# R2.4 item actions (unchanged)
_ITEM_ACTIONS_R2_4 = (
    "LINK",
    "NOOP_ALREADY_LINKED",
    "SKIP_NOT_APPROVED",
    "SKIP_PREVIEW_DRIFT",
    "SKIP_CLASSIFICATION_REGRESSION",
    "SKIP_EXCLUDED",
    "FAIL_ALREADY_LINKED_DIFFERENT",
    "FAIL_EMPLOYEE_CONFLICT",
)
# R2.5 item actions (added)
_ITEM_ACTIONS_R2_5 = (
    "MANUAL_LINK",
    "MANUAL_UNLINK",
    "ROLLBACK_LINK",
    "REPAIR_PREVIEW",
    "RERUN_EXECUTE",
)
_ITEM_ACTIONS = _ITEM_ACTIONS_R2_4 + _ITEM_ACTIONS_R2_5

# R2.4 statuses (unchanged)
_ITEM_STATUSES_R2_4 = ("PLANNED", "APPLIED", "SKIPPED", "FAILED")
# R2.5 idempotent noop statuses (added)
_ITEM_STATUSES_R2_5 = (
    "NOOP_ALREADY_LINKED",
    "NOOP_ALREADY_UNLINKED",
    "NOOP_ALREADY_ROLLED_BACK",
)
_ITEM_STATUSES = _ITEM_STATUSES_R2_4 + _ITEM_STATUSES_R2_5

_SAL_EVENT_TYPES_R2_4 = (
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
_SAL_EVENT_TYPES = _SAL_EVENT_TYPES_R2_4 + ("USER_EMPLOYEE_UNLINKED",)

_REASON_CODES_DOCUMENTATION = (
    "MANUAL_OPERATOR_DECISION, ROLLBACK_PAYLOAD_APPLIED, ROLLBACK_TARGET_CHANGED, "
    "ROLLBACK_ALREADY_APPLIED, LINK_TARGET_CONFLICT, UNLINK_TARGET_EMPTY, "
    "CONCURRENT_RUN_BLOCKED, plus legacy R2.4 execute preview/apply codes"
)


def _operations_sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    operations_sql = _operations_sql(_RUN_OPERATIONS)
    item_actions_sql = _operations_sql(_ITEM_ACTIONS)
    item_statuses_sql = _operations_sql(_ITEM_STATUSES)
    sal_types_sql = _operations_sql(_SAL_EVENT_TYPES)

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
        COMMENT ON COLUMN public.identity_reconciliation_runs.operation IS
            'R2 user linkage operation; NULL for legacy R1a runs. '
            'R2.4: execute preview/apply. R2.5: manual link/unlink, rollback, repair, re-execute.';
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_runs IS
            'ADR-044 B2/R2.4a/R2.5b: identity reconciliation and user linkage run journal.';
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_r2_operation_status_started
            ON public.identity_reconciliation_runs (operation, status, started_at DESC)
            WHERE phase = 'R2'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_r2_actor_started
            ON public.identity_reconciliation_runs (actor_user_id, started_at DESC)
            WHERE phase = 'R2' AND actor_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_irr_r2_summary_source_item
            ON public.identity_reconciliation_runs ((summary->>'source_item_id'))
            WHERE phase = 'R2'
              AND operation = 'USER_LINKAGE_ROLLBACK_ITEM'
              AND summary ? 'source_item_id'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_irr_r2_execute_running_per_preview
            ON public.identity_reconciliation_runs ((summary->>'source_preview_run_id'))
            WHERE phase = 'R2'
              AND operation = 'USER_LINKAGE_EXECUTE'
              AND status = 'running'
              AND summary ? 'source_preview_run_id'
        """
    )

    op.execute(
        """
        ALTER TABLE public.user_linkage_execute_items
            DROP CONSTRAINT IF EXISTS chk_ulei_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.user_linkage_execute_items
            ADD CONSTRAINT chk_ulei_action
                CHECK (action IN ({item_actions_sql}))
        """
    )
    op.execute(
        """
        ALTER TABLE public.user_linkage_execute_items
            DROP CONSTRAINT IF EXISTS chk_ulei_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.user_linkage_execute_items
            ADD CONSTRAINT chk_ulei_status
                CHECK (status IN ({item_statuses_sql}))
        """
    )
    op.execute(
        f"""
        COMMENT ON COLUMN public.user_linkage_execute_items.reason_codes IS
            'JSONB string array of machine reason codes. R2.5 documented values include: {_REASON_CODES_DOCUMENTATION}.';
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.user_linkage_execute_items IS
            'ADR-044 R2.4a/R2.5b: per-user user linkage journal line items (execute + operations).';
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_run_status_action
            ON public.user_linkage_execute_items (run_id, status, action, item_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_link_applied_user
            ON public.user_linkage_execute_items (user_id, item_id DESC)
            WHERE action = 'LINK' AND status = 'APPLIED'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ulei_rollback_applied_source
            ON public.user_linkage_execute_items (user_id, created_at DESC)
            WHERE action = 'ROLLBACK_LINK' AND status = 'APPLIED'
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
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_target_employee
            ON public.security_audit_log (target_employee_id, happened_at DESC)
            WHERE target_employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_user_employee_linked
            ON public.security_audit_log (target_user_id, happened_at DESC)
            WHERE event_type IN ('USER_EMPLOYEE_LINKED', 'USER_EMPLOYEE_UNLINKED')
              AND target_user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    operations_sql = _operations_sql(_RUN_OPERATIONS_R2_4)
    item_actions_sql = _operations_sql(_ITEM_ACTIONS_R2_4)
    item_statuses_sql = _operations_sql(_ITEM_STATUSES_R2_4)
    sal_types_sql = _operations_sql(_SAL_EVENT_TYPES_R2_4)

    op.execute("DROP INDEX IF EXISTS public.ix_sal_user_employee_linked")
    op.execute("DROP INDEX IF EXISTS public.ix_sal_target_employee")

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

    op.execute("DROP INDEX IF EXISTS public.ix_ulei_rollback_applied_source")
    op.execute("DROP INDEX IF EXISTS public.ix_ulei_link_applied_user")
    op.execute("DROP INDEX IF EXISTS public.ix_ulei_run_status_action")

    op.execute(
        """
        ALTER TABLE public.user_linkage_execute_items
            DROP CONSTRAINT IF EXISTS chk_ulei_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.user_linkage_execute_items
            ADD CONSTRAINT chk_ulei_action
                CHECK (action IN ({item_actions_sql}))
        """
    )
    op.execute(
        """
        ALTER TABLE public.user_linkage_execute_items
            DROP CONSTRAINT IF EXISTS chk_ulei_status
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.user_linkage_execute_items
            ADD CONSTRAINT chk_ulei_status
                CHECK (status IN ({item_statuses_sql}))
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
        COMMENT ON COLUMN public.user_linkage_execute_items.reason_codes IS NULL
        """
    )

    op.execute("DROP INDEX IF EXISTS public.uq_irr_r2_execute_running_per_preview")
    op.execute("DROP INDEX IF EXISTS public.ix_irr_r2_summary_source_item")
    op.execute("DROP INDEX IF EXISTS public.ix_irr_r2_actor_started")
    op.execute("DROP INDEX IF EXISTS public.ix_irr_r2_operation_status_started")

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
        COMMENT ON COLUMN public.identity_reconciliation_runs.operation IS
            'R2 user linkage execute operation; NULL for legacy R1a runs.';
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.identity_reconciliation_runs IS
            'ADR-044 B2/R2.4a: identity reconciliation and user linkage execute run journal.';
        """
    )
