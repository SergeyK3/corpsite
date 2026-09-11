"""WP-PPR-MIG-005C report-read permission; HR_HEAD default only."""
from alembic import op

revision = "ppr005cread01"
down_revision = "ppr005bproj01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""DO $$ DECLARE rid bigint; grantor bigint; pid bigint; BEGIN
      SELECT role_id INTO rid FROM public.roles WHERE code='HR_HEAD';
      SELECT user_id INTO grantor FROM public.users WHERE is_active ORDER BY user_id LIMIT 1;
      IF rid IS NULL OR grantor IS NULL THEN RAISE EXCEPTION 'PPR status read requires HR_HEAD and active grantor'; END IF;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES('PPR_MIGRATION_STATUS_READ','PPR migration status read','Read scoped PPR migration status matrix','OBSERVER',10,true) ON CONFLICT(code) DO NOTHING;
      SELECT access_role_id INTO pid FROM public.access_roles WHERE code='PPR_MIGRATION_STATUS_READ';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT pid,'ROLE',rid,grantor,'WP-PPR-MIG-005C default HR_HEAD read grant'
      WHERE NOT EXISTS(SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid);
    END $$;""")


def downgrade() -> None:
    op.execute("DELETE FROM public.access_grants USING public.access_roles WHERE access_grants.access_role_id=access_roles.access_role_id AND access_roles.code='PPR_MIGRATION_STATUS_READ'")
    op.execute("DELETE FROM public.access_roles WHERE code='PPR_MIGRATION_STATUS_READ'")
