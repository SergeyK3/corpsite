"""Shared personnel section language; no document data changes."""
from alembic import op

revision = "hrlang001"
down_revision = "orgkk001"
branch_labels = ("personnel_settings",)
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.personnel_section_settings (
            settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
            language VARCHAR(2) NOT NULL DEFAULT 'kk' CHECK (language IN ('kk', 'ru'))
        )
    """)
    op.execute("INSERT INTO public.personnel_section_settings (settings_id, language) VALUES (1, 'kk')")


def downgrade():
    op.execute("DROP TABLE public.personnel_section_settings")
