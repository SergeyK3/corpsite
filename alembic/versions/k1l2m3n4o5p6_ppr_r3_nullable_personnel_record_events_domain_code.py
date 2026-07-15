"""PPR R3 — allow NULL domain_code on personnel_record_events for canonical PPR events.

Canonical envelope/lifecycle/merge/admin events are not PMF migration domains.
Legacy PMF writers continue to supply domain_code; FK to personnel_migration_domains
is preserved for non-null values.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
"""
from __future__ import annotations

from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_record_events
            ALTER COLUMN domain_code DROP NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.personnel_record_events
                WHERE domain_code IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade k1l2m3n4o5p6: personnel_record_events has NULL domain_code rows';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.personnel_record_events
            ALTER COLUMN domain_code SET NOT NULL
        """
    )
