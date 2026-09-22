"""Persist one-time Telegram bind codes across backend processes.

Revision ID: ua004telegrambindcodes
Revises: ua003telegramrecovery
"""
from alembic import op


revision = "ua004telegrambindcodes"
down_revision = "ua003telegramrecovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.telegram_bind_codes (
            bind_code_id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
            code_hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ NULL,
            invalidated_at TIMESTAMPTZ NULL,
            CONSTRAINT chk_telegram_bind_codes_expiry
                CHECK (expires_at > created_at)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_telegram_bind_codes_user_created
            ON public.telegram_bind_codes (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_telegram_bind_codes_one_active_per_user
            ON public.telegram_bind_codes (user_id)
            WHERE used_at IS NULL AND invalidated_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_table("telegram_bind_codes")
