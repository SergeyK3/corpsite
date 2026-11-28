"""Preserve historical attribution while removing reviewed test personnel files.

Revision ID: td011employeehistory
Revises: td009unitclean
"""
from alembic import op
from sqlalchemy import text

revision = "td011employeehistory"
down_revision = "td009unitclean"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_file_events ALTER COLUMN actor_id DROP NOT NULL")
    op.execute("ALTER TABLE public.personnel_file_versions ALTER COLUMN uploaded_by DROP NOT NULL")
    op.execute("""
        CREATE TABLE public.test_employee_retained_history_refs (
            deletion_id UUID NOT NULL REFERENCES public.test_employee_deletion_audit(deletion_id)
                DEFERRABLE INITIALLY DEFERRED,
            source_table TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_column TEXT NOT NULL,
            deleted_entity_kind TEXT NOT NULL,
            deleted_entity_id BIGINT NOT NULL,
            deleted_full_name TEXT NOT NULL,
            deleted_login TEXT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (deletion_id, source_table, source_key, source_column)
        );
        CREATE FUNCTION public.guard_test_employee_retained_history_refs()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'retained history attribution is append-only';
        END $$;
        CREATE TRIGGER trg_test_employee_retained_history_refs_immutable
            BEFORE UPDATE OR DELETE ON public.test_employee_retained_history_refs
            FOR EACH ROW EXECUTE FUNCTION public.guard_test_employee_retained_history_refs();
    """)
    # Ordinary personnel-file events remain append-only. The physical cleanup
    # may remove only events for an explicitly marked test person or clear only
    # the actor of an event belonging to another person. The attribution is
    # copied into the append-only sidecar in the same transaction.
    op.execute("""
        CREATE OR REPLACE FUNCTION public.personnel_file_events_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('corpsite.test_employee_cleanup', true) = 'on' THEN
                IF TG_OP = 'DELETE' AND EXISTS (
                    SELECT 1 FROM public.test_employee_marks m
                    WHERE m.person_id = OLD.person_id
                ) THEN
                    RETURN OLD;
                END IF;
                IF TG_OP = 'UPDATE' AND NEW.actor_id IS NULL
                    AND OLD.actor_id IS NOT NULL
                    AND (to_jsonb(NEW) - 'actor_id') = (to_jsonb(OLD) - 'actor_id')
                    AND EXISTS (
                        SELECT 1 FROM public.test_employee_marks m
                        JOIN public.employees e ON e.employee_id = m.employee_id
                        JOIN public.users u ON u.employee_id = e.employee_id
                        WHERE u.user_id = OLD.actor_id
                    ) THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'Personnel file events are append only';
        END $$;
    """)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM public.test_employee_retained_history_refs)")).scalar_one():
        raise RuntimeError("Refusing to discard retained history attribution")
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM public.personnel_file_events WHERE actor_id IS NULL) OR EXISTS(SELECT 1 FROM public.personnel_file_versions WHERE uploaded_by IS NULL)")).scalar_one():
        raise RuntimeError("Cannot restore NOT NULL historical actor columns")
    op.execute("""
        CREATE OR REPLACE FUNCTION public.personnel_file_events_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Personnel file events are append only'; END $$;
    """)
    op.execute("DROP TRIGGER trg_test_employee_retained_history_refs_immutable ON public.test_employee_retained_history_refs")
    op.execute("DROP FUNCTION public.guard_test_employee_retained_history_refs()")
    op.execute("DROP TABLE public.test_employee_retained_history_refs")
    op.execute("ALTER TABLE public.personnel_file_versions ALTER COLUMN uploaded_by SET NOT NULL")
    op.execute("ALTER TABLE public.personnel_file_events ALTER COLUMN actor_id SET NOT NULL")
