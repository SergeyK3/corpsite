"""Bring the verified local schema up to the template editor's print titles."""
import importlib.util
from pathlib import Path

from alembic import op

revision = "hrlocal304"
down_revision = "hrlocal303"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout='5s'")
    source = Path(__file__).resolve().parents[3] / "alembic/versions/poprint001_version_print_titles.py"
    spec = importlib.util.spec_from_file_location("local_version_print_titles", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()


def downgrade():
    raise RuntimeError("Print title removal requires a separately reviewed rollback")
