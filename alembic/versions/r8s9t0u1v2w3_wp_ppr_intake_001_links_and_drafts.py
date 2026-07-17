"""WP-PPR-INTAKE-001: personnel intake links and drafts.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
"""
from __future__ import annotations

from alembic import op

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None

_LINK_STATUSES = (
    "issued",
    "opened",
    "submitted",
    "expired",
    "revoked",
)

_DRAFT_STATUSES = (
    "editable",
    "submitted",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    link_statuses_sql = _sql_tuple(_LINK_STATUSES)
    draft_statuses_sql = _sql_tuple(_DRAFT_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_intake_links (
            link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            token_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'issued',
            issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            issued_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            expires_at TIMESTAMPTZ NOT NULL,
            opened_at TIMESTAMPTZ NULL,
            submitted_at TIMESTAMPTZ NULL,
            revoked_at TIMESTAMPTZ NULL,
            revoked_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            superseded_by_link_id BIGINT NULL
                REFERENCES public.personnel_intake_links (link_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_intake_links_status
                CHECK (status IN ({link_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_intake_links_token_hash
            ON public.personnel_intake_links (token_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personnel_intake_links_application_id
            ON public.personnel_intake_links (application_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_intake_links_one_active_per_application
            ON public.personnel_intake_links (application_id)
            WHERE status IN ('issued', 'opened')
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_intake_drafts (
            draft_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE RESTRICT,
            link_id BIGINT NOT NULL
                REFERENCES public.personnel_intake_links (link_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'editable',
            payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            submitted_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_personnel_intake_drafts_status
                CHECK (status IN ({draft_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_intake_drafts_application_id
            ON public.personnel_intake_drafts (application_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_intake_links IS
            'WP-PPR-INTAKE-001: protected one-time intake links for applicant self-service'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.personnel_intake_drafts IS
            'WP-PPR-INTAKE-001: applicant intake draft payload (separate from PPR)'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_intake_drafts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.personnel_intake_links CASCADE")
