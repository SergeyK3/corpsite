"""Linked training logins without copying password verifiers.

Revision ID: trn001
Revises: eha001
"""

from alembic import op

revision = "trn001"
down_revision = "eha001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.training_identity_links (
            training_user_id BIGINT PRIMARY KEY REFERENCES public.users(user_id) ON DELETE RESTRICT,
            source_user_id BIGINT NOT NULL,
            source_kind TEXT NOT NULL CHECK (source_kind IN ('local', 'external')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (source_kind, source_user_id)
        );
        COMMENT ON TABLE public.training_identity_links IS
          'Only identity references; no source password or verifier is copied here.';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE public.training_identity_links")
