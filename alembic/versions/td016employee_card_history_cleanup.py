"""Permit guarded cleanup of a marked test person's relative request events.

Revision ID: td016employeehistory
Revises: td015ooregmerge
"""
from alembic import op

revision = "td016employeehistory"
down_revision = "td015ooregmerge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original trigger reused personnel_file_events_immutable(), whose
    # cleanup branch reads OLD.person_id. Relative events have no such column.
    # Give this stream its own guard rather than widening the shared guard.
    op.execute("""
        CREATE FUNCTION public.guard_test_relative_change_event_cleanup()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE'
                AND current_setting('corpsite.test_employee_cleanup', true) = 'on'
                AND EXISTS (
                    SELECT 1 FROM public.person_relative_change_requests r
                    JOIN public.test_employee_marks m ON m.person_id = r.person_id
                    WHERE r.request_id = OLD.request_id
                ) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Relative change events are append only';
        END $$;
        DROP TRIGGER person_relative_change_events_immutable
            ON public.person_relative_change_events;
        CREATE TRIGGER person_relative_change_events_immutable
            BEFORE UPDATE OR DELETE ON public.person_relative_change_events
            FOR EACH ROW EXECUTE FUNCTION public.guard_test_relative_change_event_cleanup();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER person_relative_change_events_immutable
            ON public.person_relative_change_events;
        CREATE TRIGGER person_relative_change_events_immutable
            BEFORE UPDATE OR DELETE ON public.person_relative_change_events
            FOR EACH ROW EXECUTE FUNCTION public.personnel_file_events_immutable();
        DROP FUNCTION public.guard_test_relative_change_event_cleanup();
    """)
