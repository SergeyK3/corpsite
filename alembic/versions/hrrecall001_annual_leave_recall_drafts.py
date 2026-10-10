"""Allow annual-leave recall drafts and atomic retyping of unused templates."""
from alembic import op
from sqlalchemy import text

revision = "hrrecall001"
down_revision = "hrtpl001"
branch_labels = None
depends_on = None

CONSTRAINTS = (
    ("personnel_orders", "chk_personnel_orders_order_type_code"),
    ("personnel_order_items", "chk_personnel_order_items_item_type_code"),
)


def upgrade() -> None:
    conn = op.get_bind()
    for table, constraint in CONSTRAINTS:
        definition = conn.execute(text("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conname=:name AND conrelid=CAST(:table AS regclass)
        """), {"name": constraint, "table": "public." + table}).scalar_one()
        if "'LEAVE.ANNUAL.RECALL'::text" in definition:
            continue
        marker = "'LEAVE.ANNUAL.GRANT'::text"
        if marker not in definition:
            raise RuntimeError(f"Unexpected definition of {constraint}; stop migration")
        extended = definition.replace(marker, "'LEAVE.ANNUAL.RECALL'::text, " + marker)
        op.execute(f'ALTER TABLE public.{table} DROP CONSTRAINT {constraint}')
        op.execute(f'ALTER TABLE public.{table} ADD CONSTRAINT {constraint} {extended}')
    op.execute("""
        ALTER TABLE public.personnel_order_template_versions
        ALTER CONSTRAINT fk_personnel_template_version_template
        DEFERRABLE INITIALLY IMMEDIATE
    """)


def downgrade() -> None:
    conn = op.get_bind()
    for table, constraint in CONSTRAINTS:
        if conn.execute(text(f"SELECT EXISTS(SELECT 1 FROM public.{table} WHERE "
                             + ("order_type_code" if table == "personnel_orders" else "item_type_code")
                             + "='LEAVE.ANNUAL.RECALL')")).scalar_one():
            raise RuntimeError("Annual recall orders exist; restore a reviewed backup instead of dropping support")
        definition = conn.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=:name AND conrelid=CAST(:table AS regclass)"),
                                  {"name": constraint, "table": "public." + table}).scalar_one()
        reduced = definition.replace("'LEAVE.ANNUAL.RECALL'::text, ", "")
        if reduced != definition:
            op.execute(f'ALTER TABLE public.{table} DROP CONSTRAINT {constraint}')
            op.execute(f'ALTER TABLE public.{table} ADD CONSTRAINT {constraint} {reduced}')
    op.execute("ALTER TABLE public.personnel_order_template_versions ALTER CONSTRAINT fk_personnel_template_version_template NOT DEFERRABLE")
