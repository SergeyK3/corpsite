"""Register the audit domain already used by HR personnel contact corrections."""
from alembic import op

revision = "asst003"
down_revision = "asst002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""INSERT INTO public.personnel_migration_domains
        (domain_code,display_name,description,is_enabled,target_table_names,control_list_columns)
        VALUES ('contacts','Personnel contacts','Audit domain for person-owned contact corrections',
                TRUE,'["person_contacts"]'::jsonb,'[]'::jsonb)
        ON CONFLICT(domain_code) DO NOTHING""")


def downgrade():
    # Existing business audit must retain its referenced domain.
    pass
