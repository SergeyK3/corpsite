"""PPR R1 — personnel_record_metadata envelope table (minimal lifecycle/version).

See docs/architecture/WP-PR-010-persistence-model-and-repository-contracts.md and
docs/architecture/WP-PR-004-ppr-lifecycle-and-state-machine.md.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
"""
from __future__ import annotations

from alembic import op

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None

_PPR_LIFECYCLE_STATES = (
    "CREATED",
    "COLLECTING",
    "READY",
    "ACTIVE",
    "ARCHIVED",
    "MERGED",
)
_HR_RELATIONSHIP_CONTEXTS = (
    "CANDIDATE",
    "EMPLOYED",
    "FORMER_EMPLOYEE",
    "UNKNOWN",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    lifecycle_sql = _in_list(_PPR_LIFECYCLE_STATES)
    hr_context_sql = _in_list(_HR_RELATIONSHIP_CONTEXTS)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_record_metadata (
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            ppr_lifecycle_state TEXT NOT NULL DEFAULT 'CREATED',
            hr_relationship_context TEXT NOT NULL DEFAULT 'UNKNOWN',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_personnel_record_metadata PRIMARY KEY (person_id),
            CONSTRAINT ck_prm_ppr_lifecycle_state
                CHECK (ppr_lifecycle_state IN ({lifecycle_sql})),
            CONSTRAINT ck_prm_hr_relationship_context
                CHECK (hr_relationship_context IN ({hr_context_sql})),
            CONSTRAINT ck_prm_version_positive
                CHECK (version >= 1)
        )
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.personnel_record_metadata IS
            'PPR R1: minimal aggregate envelope keyed by person_id (ADR-054, WP-PR-010).'
        """
    )


def downgrade() -> None:
    op.drop_table("personnel_record_metadata")
