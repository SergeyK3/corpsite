"""Allow document-only personal-data orders, without changing any rows."""
from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    for table,column,name in (
        ('personnel_orders','order_type_code','chk_personnel_orders_order_type_code'),
        ('personnel_order_items','item_type_code','chk_personnel_order_items_item_type_code'),
    ):
        definition=conn.execute(text('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=CAST(:table AS regclass) AND conname=:name'),{'table':'public.'+table,'name':name}).scalar_one()
        if "'PERSONAL_DATA_CHANGE'" in definition:continue
        assert definition.startswith('CHECK (') and definition.endswith(')')
        condition=definition[len('CHECK ('):-1]
        conn.execute(text(f'ALTER TABLE public.{table} DROP CONSTRAINT {name}'))
        conn.execute(text(f"ALTER TABLE public.{table} ADD CONSTRAINT {name} CHECK (({condition}) OR {column}='PERSONAL_DATA_CHANGE')"))


def downgrade(conn):
    raise RuntimeError('Preserve personal-data order snapshots; rollback requires a separate data audit')
