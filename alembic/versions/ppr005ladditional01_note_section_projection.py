"""Add persisted Note section to the migration-status projection."""
from alembic import op

revision = "ppr005ladditional01"
down_revision = "ppr005kimport01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP CONSTRAINT IF EXISTS ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD CONSTRAINT ck_ppr_migration_status_projection_section_code CHECK
        (section_code IN ('general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles'));
    """)


def downgrade() -> None:
    op.execute("""
      DELETE FROM public.ppr_migration_section_status_projection WHERE section_code='additional';
      ALTER TABLE public.ppr_migration_section_status_projection DROP CONSTRAINT ck_ppr_migration_status_projection_section_code;
      ALTER TABLE public.ppr_migration_section_status_projection ADD CONSTRAINT ck_ppr_migration_status_projection_section_code CHECK
        (section_code IN ('general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','awards','academic_degrees_titles'));
    """)
