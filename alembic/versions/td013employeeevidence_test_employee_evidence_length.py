"""Allow a concise explicit reason when marking a test employee.

Revision ID: td013employeeevidence
Revises: td011employeehistory
"""
from alembic import op

revision = "td013employeeevidence"
down_revision = "td011employeehistory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.test_employee_marks DROP CONSTRAINT ck_test_employee_mark_evidence")
    op.execute("ALTER TABLE public.test_employee_marks ADD CONSTRAINT ck_test_employee_mark_evidence CHECK (length(btrim(evidence)) >= 12)")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.test_employee_marks WHERE length(btrim(evidence)) < 20) THEN
            RAISE EXCEPTION 'Cannot restore old evidence length: shorter marks exist';
        END IF;
    END $$""")
    op.execute("ALTER TABLE public.test_employee_marks DROP CONSTRAINT ck_test_employee_mark_evidence")
    op.execute("ALTER TABLE public.test_employee_marks ADD CONSTRAINT ck_test_employee_mark_evidence CHECK (length(btrim(evidence)) >= 20)")
