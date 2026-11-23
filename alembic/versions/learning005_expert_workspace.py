"""Persist expert catalog, assignment snapshots and review revisions."""
from alembic import op

from app.learning.model import assignment_batches, assignments, courses, lessons, review_events

revision = "learning005"
down_revision = "learning004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (courses, lessons, assignment_batches, assignments, review_events):
        table.create(bind)
    op.execute("ALTER TABLE learning_records DROP CONSTRAINT IF EXISTS learning_records_action_check")
    op.execute("ALTER TABLE learning_records ADD CONSTRAINT learning_records_action_check CHECK (action IN ('opened','approved','rejected','visa_viewed','submitted'))")
    op.execute("ALTER TABLE learning_attempts ADD COLUMN review_source VARCHAR(20)")
    op.execute("ALTER TABLE learning_attempts ADD COLUMN auto_status VARCHAR(20) NOT NULL DEFAULT 'unavailable'")
    op.execute("ALTER TABLE learning_attempts ADD COLUMN auto_note TEXT NOT NULL DEFAULT ''")
    op.execute("""
    INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
    VALUES ('LEARNING_EXPERT','Внутреннее обучение','Каталог, назначения и выполнение','MANAGER',20,true),
           ('LEARNING_MANUAL_REVIEW','Ручная проверка обучения','Итоговая оценка учебной попытки','MANAGER',20,true)
    ON CONFLICT(code) DO NOTHING
    """)
    op.execute("""
    DO $$ DECLARE rid BIGINT; grantor BIGINT; permission_code TEXT; pid BIGINT; BEGIN
      SELECT role_id INTO rid FROM public.roles WHERE roles.code='QM_TRAINING_EXPERT';
      SELECT user_id INTO grantor FROM public.users WHERE is_active=true ORDER BY user_id LIMIT 1;
      IF rid IS NOT NULL AND grantor IS NOT NULL THEN
      FOREACH permission_code IN ARRAY ARRAY['LEARNING_EXPERT'] LOOP
        SELECT access_role_id INTO pid FROM public.access_roles WHERE access_roles.code=permission_code;
        INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
        SELECT pid,'ROLE',rid,grantor,'Learning expert workspace'
        WHERE NOT EXISTS (SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid AND active_flag=true AND revoked_at IS NULL);
      END LOOP;
      END IF;
    END $$
    """)


def downgrade():
    raise RuntimeError("Learning assignments and review history require a data-preserving rollback plan")
