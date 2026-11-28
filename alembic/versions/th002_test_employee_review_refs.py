"""Allow historical card-review actors to be archived before test-user deletion.

Revision ID: th002cardreview
Revises: th001history
"""
from alembic import op
from sqlalchemy import text

revision = "th002cardreview"
down_revision = "th001history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(text("SELECT to_regclass('public.person_card_change_events') IS NOT NULL")).scalar_one():
        op.execute("ALTER TABLE public.person_card_change_events ALTER COLUMN actor_id DROP NOT NULL")
    # These review tables belong to the separate self-card migration line and
    # do not yet exist on the production base. The TEST merge applies this
    # change after that line; a future production merge must recheck it.
    if conn.execute(text("SELECT to_regclass('public.person_relative_change_events') IS NOT NULL")).scalar_one():
        if not conn.execute(text("SELECT to_regprocedure('public.guard_test_relative_change_event_cleanup()') IS NOT NULL")).scalar_one():
            raise RuntimeError("Relative review history guard is missing")
        op.execute("ALTER TABLE public.person_relative_change_events ALTER COLUMN actor_id DROP NOT NULL")
        op.execute("""
            CREATE OR REPLACE FUNCTION public.guard_test_relative_change_event_cleanup()
            RETURNS trigger LANGUAGE plpgsql AS $function$
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
                IF TG_OP = 'UPDATE'
                    AND current_setting('corpsite.test_employee_cleanup', true) = 'on'
                    AND NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL
                    AND to_jsonb(NEW) - 'actor_id' = to_jsonb(OLD) - 'actor_id'
                    AND EXISTS (
                        SELECT 1 FROM public.test_employee_history_snapshots s
                        JOIN public.users u ON u.user_id = OLD.actor_id
                        JOIN public.test_employee_marks m ON m.employee_id = u.employee_id
                        WHERE s.deletion_id::text = current_setting(
                            'corpsite.test_employee_cleanup_deletion_id', true)
                          AND s.source_table = 'person_relative_change_events'
                          AND s.source_key = OLD.event_id::text
                          AND s.disposition = 'RETAINED'
                          AND s.row_snapshot->>'actor_id' = OLD.actor_id::text
                    ) THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Relative change events are append only';
            END $function$;
        """)


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("person_card_change_events", "person_relative_change_events"):
        if not conn.execute(text(f"SELECT to_regclass('public.{table}') IS NOT NULL")).scalar_one():
            continue
        if conn.execute(text(f"SELECT EXISTS(SELECT 1 FROM public.{table} WHERE actor_id IS NULL)")).scalar_one():
            raise RuntimeError(f"Refusing to discard archived reviewer attribution in {table}")
    if conn.execute(text("SELECT to_regclass('public.person_relative_change_events') IS NOT NULL")).scalar_one():
        op.execute("ALTER TABLE public.person_relative_change_events ALTER COLUMN actor_id SET NOT NULL")
        op.execute("""
            CREATE OR REPLACE FUNCTION public.guard_test_relative_change_event_cleanup()
            RETURNS trigger LANGUAGE plpgsql AS $function$
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
            END $function$;
        """)
    if conn.execute(text("SELECT to_regclass('public.person_card_change_events') IS NOT NULL")).scalar_one():
        op.execute("ALTER TABLE public.person_card_change_events ALTER COLUMN actor_id SET NOT NULL")
