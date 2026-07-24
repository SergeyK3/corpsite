"""WP-PPR-CARD-COORDINATION-003: reconciliation decision foundation.

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
"""
from __future__ import annotations

from alembic import op

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None

_ACTIONS = (
    "add",
    "keep_existing",
    "update_version",
    "supersede",
    "manual_review",
)

_APPLY_STATUSES = (
    "pending",
    "applied",
    "skipped_manual",
    "blocked",
    "failed",
)

_SECTION_CODES = (
    "education",
    "training",
    "employment_biography",
    "military",
)

_DECISION_SOURCES = (
    "system",
    "hr",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    actions_sql = _sql_tuple(_ACTIONS)
    statuses_sql = _sql_tuple(_APPLY_STATUSES)
    sections_sql = _sql_tuple(_SECTION_CODES)
    sources_sql = _sql_tuple(_DECISION_SOURCES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_intake_reconciliation_decisions (
            decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            section_code TEXT NOT NULL,
            proposal_index INTEGER NOT NULL,
            proposal_fingerprint TEXT NOT NULL,
            proposal_payload_digest TEXT NOT NULL,
            action TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            evidence JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            target_canonical_record_id BIGINT NULL,
            expected_row_version TEXT NULL,
            expected_canonical_precondition TEXT NOT NULL,
            decision_source TEXT NOT NULL DEFAULT 'system',
            override_token TEXT NULL,
            matcher_rule_id TEXT NOT NULL,
            matcher_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            digest_algorithm_version TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            intent_fingerprint TEXT NOT NULL,
            apply_status TEXT NOT NULL DEFAULT 'pending',
            failure_evidence JSONB NULL,
            row_version BIGINT NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_pird_section_code
                CHECK (section_code IN ({sections_sql})),
            CONSTRAINT chk_pird_action
                CHECK (action IN ({actions_sql})),
            CONSTRAINT chk_pird_apply_status
                CHECK (apply_status IN ({statuses_sql})),
            CONSTRAINT chk_pird_decision_source
                CHECK (decision_source IN ({sources_sql})),
            CONSTRAINT chk_pird_proposal_index_nonneg
                CHECK (proposal_index >= 0),
            CONSTRAINT chk_pird_row_version_positive
                CHECK (row_version >= 1),
            CONSTRAINT chk_pird_nonempty_idempotency_key
                CHECK (length(btrim(idempotency_key)) > 0),
            CONSTRAINT chk_pird_nonempty_intent_fingerprint
                CHECK (length(btrim(intent_fingerprint)) > 0),
            CONSTRAINT chk_pird_nonempty_precondition
                CHECK (length(btrim(expected_canonical_precondition)) > 0),
            CONSTRAINT chk_pird_override_token_consistency
                CHECK (
                    (
                        decision_source = 'system'
                        AND override_token IS NULL
                    )
                    OR (
                        decision_source = 'hr'
                        AND override_token IS NOT NULL
                        AND length(btrim(override_token)) > 0
                    )
                ),
            CONSTRAINT chk_pird_failure_evidence_consistency
                CHECK (
                    (
                        apply_status IN ('blocked', 'failed')
                        AND failure_evidence IS NOT NULL
                    )
                    OR (
                        apply_status NOT IN ('blocked', 'failed')
                        AND failure_evidence IS NULL
                    )
                ),
            CONSTRAINT uq_pird_idempotency_key
                UNIQUE (idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pird_application_section
            ON public.personnel_intake_reconciliation_decisions
            (application_id, section_code, proposal_index)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pird_person_status
            ON public.personnel_intake_reconciliation_decisions
            (person_id, apply_status)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_intake_reconciliation_decisions IS
            'WP-PPR-CARD-COORDINATION-003: durable reconciliation decisions (no PPR mutation in this WP)'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_intake_reconciliation_decisions CASCADE")
