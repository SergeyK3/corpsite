"""Canonical job catalog and legacy lookup, without reassignment or data import."""
from alembic import op

revision = "jobcat001"
down_revision = "poskk001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.job_positions_catalog (
        job_code TEXT PRIMARY KEY CHECK (job_code ~ '^[A-Z][A-Z0-9_]*$'),
        job_nameru TEXT NOT NULL CHECK (btrim(job_nameru) <> ''),
        job_namekk TEXT NOT NULL CHECK (btrim(job_namekk) <> ''),
        job_namekk_doc TEXT NOT NULL CHECK (btrim(job_namekk_doc) <> '')
    )""")
    op.execute("""CREATE TABLE public.position_job_catalog (
        position_id INTEGER PRIMARY KEY REFERENCES public.positions(position_id),
        job_code TEXT NOT NULL REFERENCES public.job_positions_catalog(job_code)
    )""")
    op.execute("CREATE INDEX ix_position_job_catalog_code ON public.position_job_catalog(job_code)")


def downgrade():
    op.execute("DROP TABLE public.position_job_catalog")
    op.execute("DROP TABLE public.job_positions_catalog")
