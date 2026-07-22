"""WP-TG-001: Person-level Telegram identity schema (ADR-TG-001).

Revision ID: l3m4n5o6p7q8
Revises: j1k2l3m4n5o6
"""
from __future__ import annotations

from alembic import op

revision = "l3m4n5o6p7q8"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.person_telegram_bindings (
            binding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            telegram_user_id BIGINT NOT NULL,
            telegram_username TEXT NULL,
            revoked_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_person_telegram_bindings_telegram_user_id_positive
                CHECK (telegram_user_id > 0)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_person_telegram_bindings_telegram_user_id_active
            ON public.person_telegram_bindings (telegram_user_id)
            WHERE revoked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_person_telegram_bindings_person_id_active
            ON public.person_telegram_bindings (person_id)
            WHERE revoked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_person_telegram_bindings_person_id_history
            ON public.person_telegram_bindings (person_id, created_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_telegram_bindings IS
            'Persistent Person ↔ Telegram binding (Person-level identity; ADR-TG-001).'
        """
    )
    op.execute(
        """
        CREATE TABLE public.person_telegram_bot_activations (
            activation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            bot_code TEXT NOT NULL,
            first_activated_at TIMESTAMPTZ NOT NULL,
            last_activated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_person_telegram_bot_activations_person_bot
                UNIQUE (person_id, bot_code),
            CONSTRAINT chk_person_telegram_bot_activations_bot_code
                CHECK (bot_code IN ('intake_ppr', 'operational_tasks'))
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.person_telegram_bot_activations IS
            'Per-bot Start activation for Person-level Telegram identity (ADR-TG-001).'
        """
    )


def downgrade() -> None:
    op.drop_table("person_telegram_bot_activations")
    op.drop_table("person_telegram_bindings")
