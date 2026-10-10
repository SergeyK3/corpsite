"""Add only the profession catalog to the separately verified local stage-3 graph."""
import importlib.util
from pathlib import Path
from alembic import op
from sqlalchemy import text

revision = "hrlocal302"
down_revision = "hrlocal301"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    conn.execute(text("SET LOCAL statement_timeout='120s'"))
    existing = conn.execute(text("SELECT to_regclass('public.job_positions_catalog'), to_regclass('public.position_job_catalog')")).one()
    if any(existing):
        raise RuntimeError("STOP: catalog tables already exist; inspect schema before proceeding")
    source = Path(__file__).resolve().parents[3] / "alembic/versions/jobcat001_job_positions_catalog.py"
    spec = importlib.util.spec_from_file_location("local_job_catalog_schema", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()


def downgrade():
    raise RuntimeError("Catalog downgrade requires a separately reviewed rollback; do not delete reference data automatically")
