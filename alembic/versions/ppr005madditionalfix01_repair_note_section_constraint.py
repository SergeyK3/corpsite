"""Repair already-stamped Note-section constraint deployments."""
from alembic import op


revision = "ppr005madditionalfix01"
down_revision = "ppr005ladditional01"
branch_labels = None
depends_on = None


_WITH_NOTE = "'general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles'"
_WITHOUT_NOTE = "'general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','awards','academic_degrees_titles'"


def upgrade() -> None:
    # ppr005l originally addressed a legacy constraint name.  Existing databases
    # may therefore be stamped at that revision while retaining the old CHECK.
    op.execute(f"""
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP CONSTRAINT IF EXISTS ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD CONSTRAINT ck_ppr_migration_status_projection_section_code
        CHECK (section_code IN ({_WITH_NOTE}));
    """)


def downgrade() -> None:
    op.execute(f"""
      DELETE FROM public.ppr_migration_section_status_projection WHERE section_code='additional';
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP CONSTRAINT ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD CONSTRAINT ck_ppr_migration_status_projection_section_code
        CHECK (section_code IN ({_WITHOUT_NOTE}));
    """)
