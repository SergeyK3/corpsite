"""Telegram password recovery request storage.

Revision ID: ua003telegramrecovery
Revises: ua002accessadmin
"""
from alembic import op

revision = "ua003telegramrecovery"
down_revision = "ua002accessadmin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE public.telegram_password_recovery_requests (
        request_id UUID PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
        telegram_user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING'
          CHECK (status IN ('PENDING','CLAIMED','ISSUED','USED','LOCKED','EXPIRED','CANCELLED')),
        code_hash TEXT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 5),
        requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        claim_until TIMESTAMPTZ NULL,
        issued_at TIMESTAMPTZ NULL,
        expires_at TIMESTAMPTZ NULL,
        used_at TIMESTAMPTZ NULL
      )
    """)
    op.execute("CREATE INDEX ix_tg_password_recovery_pending ON public.telegram_password_recovery_requests(status, requested_at)")
    op.execute("CREATE INDEX ix_tg_password_recovery_user_requested ON public.telegram_password_recovery_requests(user_id, requested_at DESC)")


def downgrade() -> None:
    op.drop_table("telegram_password_recovery_requests")
