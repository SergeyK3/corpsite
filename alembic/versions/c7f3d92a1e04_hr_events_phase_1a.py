"""hr events phase 1a schema

Revision ID: c7f3d92a1e04
Revises: b5e2a81d4c03
Create Date: 2026-06-15 12:00:00.000000

ADR-036 Phase 1A Step 1: employee_events event_class, lifecycle_status, metadata;
extend event_type for POSITION_CHANGE and RATE_CHANGE.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7f3d92a1e04"
down_revision: Union[str, Sequence[str], None] = "b5e2a81d4c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD COLUMN IF NOT EXISTS event_class TEXT NULL,
            ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'APPROVED',
            ADD COLUMN IF NOT EXISTS metadata JSONB NULL
        """
    )

    op.execute(
        """
        UPDATE public.employee_events
        SET event_class = CASE
            WHEN event_type = 'CORRECTION' THEN 'CORRECTION'
            ELSE 'EMPLOYMENT'
        END
        WHERE event_class IS NULL
        """
    )

    op.execute(
        """
        UPDATE public.employee_events
        SET lifecycle_status = 'APPROVED'
        WHERE lifecycle_status IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            ALTER COLUMN event_class SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS chk_employee_events_event_type
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD CONSTRAINT chk_employee_events_event_type CHECK (
                event_type IN (
                    'HIRE',
                    'TRANSFER',
                    'CORRECTION',
                    'TERMINATION',
                    'POSITION_CHANGE',
                    'RATE_CHANGE'
                )
            )
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD CONSTRAINT chk_employee_events_lifecycle_status CHECK (
                lifecycle_status IN ('APPROVED', 'VOIDED')
            )
        """
    )

    # Backward compatibility until Step 2 updates application INSERT (event_class NOT NULL).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trg_employee_events_set_event_class()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.event_class IS NULL THEN
                NEW.event_class := CASE
                    WHEN NEW.event_type = 'CORRECTION' THEN 'CORRECTION'
                    ELSE 'EMPLOYMENT'
                END;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_employee_events_set_event_class
        ON public.employee_events
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_employee_events_set_event_class
        BEFORE INSERT ON public.employee_events
        FOR EACH ROW
        EXECUTE FUNCTION public.trg_employee_events_set_event_class()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_employee_events_set_event_class
        ON public.employee_events
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.trg_employee_events_set_event_class()
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS chk_employee_events_lifecycle_status
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS chk_employee_events_event_type
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            ADD CONSTRAINT chk_employee_events_event_type CHECK (
                event_type IN ('HIRE', 'TRANSFER', 'CORRECTION', 'TERMINATION')
            )
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP COLUMN IF EXISTS metadata,
            DROP COLUMN IF EXISTS lifecycle_status,
            DROP COLUMN IF EXISTS event_class
        """
    )
