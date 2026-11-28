"""Immutable explicit test-origin marks for safe org-unit deletion.

Revision ID: td009unitclean
Revises: td007employee01
"""
from alembic import op
from sqlalchemy import text

revision = "td009unitclean"
down_revision = "td007employee01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.test_org_unit_marks (
            marker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            unit_id BIGINT NOT NULL UNIQUE,
            unit_name TEXT NOT NULL,
            unit_snapshot_hash CHAR(64) NOT NULL,
            evidence TEXT NOT NULL,
            marked_by_user_id BIGINT NOT NULL,
            marked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_test_org_unit_mark_evidence CHECK (length(btrim(evidence)) >= 20)
        );
        CREATE FUNCTION public.guard_test_org_unit_marks()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'test org unit marks are append-only';
        END $$;
        CREATE TRIGGER trg_test_org_unit_marks_immutable
            BEFORE UPDATE OR DELETE ON public.test_org_unit_marks
            FOR EACH ROW EXECUTE FUNCTION public.guard_test_org_unit_marks();
    """)


def downgrade() -> None:
    if op.get_bind().execute(text("SELECT EXISTS(SELECT 1 FROM public.test_org_unit_marks)")).scalar_one():
        raise RuntimeError("Refusing to discard test org unit origin evidence")
    op.execute("DROP TRIGGER trg_test_org_unit_marks_immutable ON public.test_org_unit_marks")
    op.execute("DROP FUNCTION public.guard_test_org_unit_marks()")
    op.execute("DROP TABLE public.test_org_unit_marks")
