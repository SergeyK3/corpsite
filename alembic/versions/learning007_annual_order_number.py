"""Reserve a personnel order number in the common journal for one calendar year."""
from alembic import op
from sqlalchemy import text

from app.db.personnel_order_header_uniqueness import (
    ACTIVE_HEADER_SQL,
    INDEX_NAME,
    NUMBER_KEY_SQL,
    ORDER_YEAR_SQL,
)

revision = "learning007"
down_revision = "learning006"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    duplicates = conn.execute(text(f"""
        SELECT {NUMBER_KEY_SQL} AS number, {ORDER_YEAR_SQL} AS year,
               array_agg(order_id ORDER BY order_id) AS ids
        FROM public.personnel_orders
        WHERE {ACTIVE_HEADER_SQL}
        GROUP BY 1, 2 HAVING count(*) > 1 LIMIT 10
    """)).mappings().all()
    if duplicates:
        raise RuntimeError(f"Personnel order numbers repeated within a calendar year: {list(duplicates)}")
    op.execute(f"DROP INDEX public.{INDEX_NAME}")
    op.execute(f"CREATE UNIQUE INDEX {INDEX_NAME} ON public.personnel_orders "
               f"(({NUMBER_KEY_SQL}), ({ORDER_YEAR_SQL})) WHERE {ACTIVE_HEADER_SQL}")


def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    op.execute(f"DROP INDEX public.{INDEX_NAME}")
    op.execute(f"CREATE UNIQUE INDEX {INDEX_NAME} ON public.personnel_orders "
               f"(({NUMBER_KEY_SQL}), order_date) WHERE {ACTIVE_HEADER_SQL}")
