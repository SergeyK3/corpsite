"""Align header uniqueness with dated, non-deleted personnel orders."""
from alembic import op
from sqlalchemy import text
from app.db.personnel_order_header_uniqueness import NUMBER_KEY_SQL,ACTIVE_HEADER_SQL,INDEX_NAME

revision='podup001'
down_revision='hrjobmerge001'
branch_labels=None
depends_on=None


def upgrade():
    conn=op.get_bind()
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    duplicates=conn.execute(text(f"SELECT {NUMBER_KEY_SQL} AS number,order_date,array_agg(order_id ORDER BY order_id) AS ids FROM public.personnel_orders WHERE {ACTIVE_HEADER_SQL} GROUP BY 1,2 HAVING count(*)>1 LIMIT 10")).mappings().all()
    if duplicates:raise RuntimeError(f'Active personnel header duplicates require review: {list(duplicates)}')
    op.execute('ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS uq_personnel_orders_order_number')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME} ON public.personnel_orders (({NUMBER_KEY_SQL}),order_date) WHERE {ACTIVE_HEADER_SQL}')


def downgrade():
    conn=op.get_bind()
    duplicates=conn.execute(text('SELECT order_number FROM public.personnel_orders WHERE order_number IS NOT NULL GROUP BY order_number HAVING count(*)>1 LIMIT 1')).first()
    if duplicates:raise RuntimeError('Cannot restore number-only uniqueness without changing retained orders.')
    op.execute(f'DROP INDEX IF EXISTS public.{INDEX_NAME}')
    op.execute('ALTER TABLE public.personnel_orders ADD CONSTRAINT uq_personnel_orders_order_number UNIQUE (order_number)')
