"""ADR-040 Phase F — materialized HR change events between canonical snapshots.

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
"""
from __future__ import annotations

from alembic import op

revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None

_EVENT_TYPES = (
    "NEW",
    "REMOVED",
    "POSITION_CHANGED",
    "DEPARTMENT_CHANGED",
    "EDUCATION_CHANGED",
    "CERTIFICATE_CHANGED",
)


def upgrade() -> None:
    types_sql = ", ".join(f"'{t}'" for t in _EVENT_TYPES)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_change_events (
            change_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            prior_snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            new_snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            event_at TIMESTAMPTZ NOT NULL,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            match_key TEXT NOT NULL,
            record_kind TEXT NOT NULL DEFAULT 'roster',
            prior_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            new_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            field_name TEXT NULL,
            old_value TEXT NULL,
            new_value TEXT NULL,
            department TEXT NULL,
            org_unit_id BIGINT NULL,
            full_name TEXT NULL,
            iin TEXT NULL,
            details JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_hr_change_events_event_type
                CHECK (event_type IN ({types_sql})),
            CONSTRAINT chk_hr_change_events_match_key_nonempty
                CHECK (length(trim(match_key)) > 0),
            CONSTRAINT chk_hr_change_events_record_kind
                CHECK (record_kind IN (
                    'roster', 'training', 'certificate', 'category', 'education'
                ))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_change_events_new_snapshot
            ON public.hr_change_events (new_snapshot_id, event_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_change_events_employee
            ON public.hr_change_events (employee_id, event_at DESC)
            WHERE employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_change_events_org_unit
            ON public.hr_change_events (org_unit_id, event_at DESC)
            WHERE org_unit_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_change_events_event_type
            ON public.hr_change_events (event_type, event_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_change_events_snapshot_pair_dedup
            ON public.hr_change_events (
                prior_snapshot_id,
                new_snapshot_id,
                event_type,
                match_key,
                COALESCE(field_name, ''),
                COALESCE(prior_entry_id, 0),
                COALESCE(new_entry_id, 0)
            )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_change_events IS
            'ADR-040 Phase F: materialized changes between canonical HR snapshot versions.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_change_events CASCADE")
