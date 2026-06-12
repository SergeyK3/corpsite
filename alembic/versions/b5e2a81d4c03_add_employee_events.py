"""add employee_events table

Revision ID: b5e2a81d4c03
Revises: c3d8e12a5f01
Create Date: 2026-06-12 10:00:00.000000

ADR-032 Phase 3b-2: append-only personnel event table for transfer/correction history.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b5e2a81d4c03"
down_revision: Union[str, Sequence[str], None] = "c3d8e12a5f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL,
            event_type TEXT NOT NULL,
            effective_date DATE NOT NULL,

            from_org_unit_id BIGINT NULL,
            from_position_id BIGINT NULL,
            from_rate NUMERIC(4,2) NULL,

            to_org_unit_id BIGINT NULL,
            to_position_id BIGINT NULL,
            to_rate NUMERIC(4,2) NULL,

            order_ref TEXT NULL,
            comment TEXT NULL,
            created_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT fk_employee_events_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id),
            CONSTRAINT fk_employee_events_from_org_unit
                FOREIGN KEY (from_org_unit_id)
                REFERENCES public.org_units(unit_id),
            CONSTRAINT fk_employee_events_from_position
                FOREIGN KEY (from_position_id)
                REFERENCES public.positions(position_id),
            CONSTRAINT fk_employee_events_to_org_unit
                FOREIGN KEY (to_org_unit_id)
                REFERENCES public.org_units(unit_id),
            CONSTRAINT fk_employee_events_to_position
                FOREIGN KEY (to_position_id)
                REFERENCES public.positions(position_id),
            CONSTRAINT fk_employee_events_created_by
                FOREIGN KEY (created_by)
                REFERENCES public.users(user_id),
            CONSTRAINT chk_employee_events_event_type CHECK (
                event_type IN ('HIRE', 'TRANSFER', 'CORRECTION', 'TERMINATION')
            )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_events_employee_date
        ON public.employee_events (employee_id, effective_date DESC, event_id DESC)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS public.ix_employee_events_employee_date")
    op.execute("DROP TABLE IF EXISTS public.employee_events")
