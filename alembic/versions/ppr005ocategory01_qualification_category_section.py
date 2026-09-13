"""Add persisted qualification-category migration-status section."""
from alembic import op


revision = "ppr005ocategory01"
down_revision = "ppr005nimportiinidx01"
branch_labels = None
depends_on = None


_WITH_CATEGORY = "'general','education','training','category','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles'"
_WITHOUT_CATEGORY = "'general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles'"


def upgrade() -> None:
    op.execute(f"""
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP CONSTRAINT IF EXISTS ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD CONSTRAINT ck_ppr_migration_status_projection_section_code
        CHECK (section_code IN ({_WITH_CATEGORY}));
    """)


def downgrade() -> None:
    op.execute(f"""
      DELETE FROM public.ppr_migration_section_status_projection WHERE section_code='category';
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP CONSTRAINT ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD CONSTRAINT ck_ppr_migration_status_projection_section_code
        CHECK (section_code IN ({_WITHOUT_CATEGORY}));
    """)
