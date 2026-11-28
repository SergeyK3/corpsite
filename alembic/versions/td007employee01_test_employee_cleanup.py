"""Explicit employee test marks and durable deletion/file-cleanup audit.

Revision ID: td007employee01
Revises: eha006
"""
from alembic import op
from sqlalchemy import text

revision = "td007employee01"
down_revision = "eha006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.test_employee_marks (
            marker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL UNIQUE,
            person_id BIGINT,
            full_name TEXT NOT NULL,
            snapshot_hash CHAR(64) NOT NULL,
            evidence TEXT NOT NULL,
            marked_by_user_id BIGINT NOT NULL,
            marked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_test_employee_mark_evidence CHECK (length(btrim(evidence)) >= 20)
        );
        CREATE TABLE public.test_employee_deletion_audit (
            deletion_id UUID PRIMARY KEY,
            employee_id BIGINT NOT NULL,
            person_id BIGINT,
            full_name TEXT NOT NULL,
            login TEXT,
            marker_id BIGINT NOT NULL,
            deleted_by_user_id BIGINT NOT NULL,
            deleted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_counts JSONB NOT NULL,
            snapshot_hash CHAR(64) NOT NULL
        );
        CREATE TABLE public.test_employee_file_cleanup (
            cleanup_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            deletion_id UUID NOT NULL REFERENCES public.test_employee_deletion_audit(deletion_id),
            storage_kind TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            completed_at TIMESTAMPTZ,
            last_error TEXT,
            UNIQUE (deletion_id, storage_kind, storage_path)
        );
        CREATE INDEX ix_test_employee_file_cleanup_pending
            ON public.test_employee_file_cleanup(cleanup_id) WHERE completed_at IS NULL;
    """)
    op.execute("""
        CREATE FUNCTION public.guard_test_employee_cleanup_audit()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'test employee cleanup evidence is append-only';
        END $$;
        CREATE TRIGGER trg_test_employee_marks_immutable
            BEFORE UPDATE OR DELETE ON public.test_employee_marks
            FOR EACH ROW EXECUTE FUNCTION public.guard_test_employee_cleanup_audit();
        CREATE TRIGGER trg_test_employee_deletion_audit_immutable
            BEFORE UPDATE OR DELETE ON public.test_employee_deletion_audit
            FOR EACH ROW EXECUTE FUNCTION public.guard_test_employee_cleanup_audit();
    """)
    # Reuse the existing append-only guards with a transaction-local physical
    # cleanup switch.  No FK or other trigger is disabled.
    conn = op.get_bind()
    patches = (
        (
            "public.trg_person_photos_guard_mutation()",
            "IF TG_OP = 'DELETE' THEN\n                RAISE EXCEPTION 'person_photos rows are not deletable';",
            "IF TG_OP = 'DELETE' THEN\n                IF current_setting('corpsite.test_employee_cleanup', true) = 'on' THEN RETURN OLD; END IF;\n                RAISE EXCEPTION 'person_photos rows are not deletable';",
        ),
        (
            "public.person_photo_sources_append_only()",
            "RAISE EXCEPTION 'person_photo_sources are append-only: UPDATE/DELETE are forbidden';",
            "IF TG_OP = 'DELETE' AND current_setting('corpsite.test_employee_cleanup', true) = 'on' THEN RETURN OLD; END IF;\n            RAISE EXCEPTION 'person_photo_sources are append-only: UPDATE/DELETE are forbidden';",
        ),
    )
    for function_name, old, new in patches:
        source = conn.execute(text("SELECT pg_get_functiondef(CAST(:name AS regprocedure))"),
                              {"name": function_name}).scalar_one()
        if source.count(old) != 1:
            raise RuntimeError(f"Unexpected photo guard definition: {function_name}")
        op.execute(source.replace(old, new))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(text("""SELECT EXISTS(SELECT 1 FROM public.test_employee_deletion_audit)
        OR EXISTS(SELECT 1 FROM public.test_employee_marks)""")).scalar_one():
        raise RuntimeError("Refusing to drop recorded test-employee cleanup evidence")
    for function_name, old, new in (
        (
            "public.trg_person_photos_guard_mutation()",
            "IF TG_OP = 'DELETE' THEN\n                RAISE EXCEPTION 'person_photos rows are not deletable';",
            "IF TG_OP = 'DELETE' THEN\n                IF current_setting('corpsite.test_employee_cleanup', true) = 'on' THEN RETURN OLD; END IF;\n                RAISE EXCEPTION 'person_photos rows are not deletable';",
        ),
        (
            "public.person_photo_sources_append_only()",
            "RAISE EXCEPTION 'person_photo_sources are append-only: UPDATE/DELETE are forbidden';",
            "IF TG_OP = 'DELETE' AND current_setting('corpsite.test_employee_cleanup', true) = 'on' THEN RETURN OLD; END IF;\n            RAISE EXCEPTION 'person_photo_sources are append-only: UPDATE/DELETE are forbidden';",
        ),
    ):
        source = conn.execute(text("SELECT pg_get_functiondef(CAST(:name AS regprocedure))"),
                              {"name": function_name}).scalar_one()
        if source.count(new) != 1:
            raise RuntimeError(f"Unexpected photo guard definition: {function_name}")
        op.execute(source.replace(new, old))
    op.execute("DROP TRIGGER trg_test_employee_deletion_audit_immutable ON public.test_employee_deletion_audit")
    op.execute("DROP TRIGGER trg_test_employee_marks_immutable ON public.test_employee_marks")
    op.execute("DROP FUNCTION public.guard_test_employee_cleanup_audit()")
    op.execute("DROP TABLE public.test_employee_file_cleanup")
    op.execute("DROP TABLE public.test_employee_deletion_audit")
    op.execute("DROP TABLE public.test_employee_marks")
