"""Separate official paper headings; never rewrite existing versions or orders."""
from alembic import op
import sqlalchemy as sa

revision = 'poprint001'
down_revision = 'medspec001'
branch_labels = None
depends_on = None


def upgrade():
    for locale in ('ru', 'kk'):
        op.add_column('personnel_order_template_versions', sa.Column(f'print_title_{locale}', sa.Text(), nullable=True), schema='public')
    op.execute('''CREATE FUNCTION public.personnel_print_title_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status <> 'DRAFT' AND
             (NEW.print_title_ru IS DISTINCT FROM OLD.print_title_ru OR NEW.print_title_kk IS DISTINCT FROM OLD.print_title_kk) THEN
            RAISE EXCEPTION 'Published/archived print titles are immutable; create a new version';
          END IF;
          RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER personnel_print_title_immutable BEFORE UPDATE ON public.personnel_order_template_versions
                  FOR EACH ROW EXECUTE FUNCTION public.personnel_print_title_immutable()''')


def downgrade():
    op.execute('DROP TRIGGER personnel_print_title_immutable ON public.personnel_order_template_versions')
    op.execute('DROP FUNCTION public.personnel_print_title_immutable()')
    for locale in ('kk', 'ru'):
        op.drop_column('personnel_order_template_versions', f'print_title_{locale}', schema='public')
