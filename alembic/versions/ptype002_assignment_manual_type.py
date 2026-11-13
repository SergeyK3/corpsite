"""Nullable manual type override on a person assignment."""
from alembic import op

revision = "ptype002"
down_revision = "ptype001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE public.person_assignments ADD COLUMN manual_type_code SMALLINT")
    op.execute("""
        ALTER TABLE public.person_assignments
        ADD CONSTRAINT fk_person_assignments_manual_type_code
        FOREIGN KEY (manual_type_code) REFERENCES public.position_types(code)
    """)


def downgrade():
    raise RuntimeError("Manual assignment type rollback requires a data-preserving plan")
