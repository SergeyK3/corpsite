"""Separate assistant role and personnel lifecycle permissions; no accounts/grants."""
from alembic import op

revision = "asst001"
down_revision = "docv001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO public.roles(code,name,is_active)
        VALUES ('SYSADMIN_ASSISTANT','Помощник системного администратора',TRUE)
        ON CONFLICT(code) DO NOTHING;
        INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
        VALUES
          ('ASSISTANT_PERSONNEL_ORDERS_EDIT','Assistant: edit personnel orders',
           'Existing personnel-order draft, preparation and document-review operations only','MANAGER',20,TRUE),
          ('ASSISTANT_PERSONNEL_ORDERS_REGISTER','Assistant: register personnel orders',
           'Standard personnel-order registration checks','MANAGER',20,TRUE),
          ('ASSISTANT_PERSONNEL_ORDERS_APPLY','Assistant: apply personnel orders',
           'Standard lifecycle, including effects on real employees','MANAGER',20,TRUE),
          ('ASSISTANT_PERSONNEL_ORDERS_DELETE_OWN','Assistant: delete own drafts',
           'Own records only; all existing status, dependency and audit rules remain','MANAGER',20,TRUE)
        ON CONFLICT(code) DO NOTHING;
        DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM public.access_roles WHERE code IN (
            'ASSISTANT_PERSONNEL_ORDERS_EDIT','ASSISTANT_PERSONNEL_ORDERS_REGISTER',
            'ASSISTANT_PERSONNEL_ORDERS_APPLY','ASSISTANT_PERSONNEL_ORDERS_DELETE_OWN')
            AND (access_level<>'MANAGER' OR level_rank<>20)) THEN
            RAISE EXCEPTION 'Assistant permissions must use MANAGER level, never ADMIN';
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM public.users u JOIN public.roles r USING(role_id)
            WHERE r.code='SYSADMIN_ASSISTANT') OR EXISTS(
            SELECT 1 FROM public.access_grants g JOIN public.access_roles a USING(access_role_id)
            WHERE a.code IN ('ASSISTANT_PERSONNEL_ORDERS_EDIT','ASSISTANT_PERSONNEL_ORDERS_REGISTER',
              'ASSISTANT_PERSONNEL_ORDERS_APPLY','ASSISTANT_PERSONNEL_ORDERS_DELETE_OWN')) THEN
            RAISE EXCEPTION 'Remove assistant accounts/grants explicitly before downgrade';
          END IF;
        END $$;
        DELETE FROM public.access_roles WHERE code IN (
          'ASSISTANT_PERSONNEL_ORDERS_EDIT','ASSISTANT_PERSONNEL_ORDERS_REGISTER',
          'ASSISTANT_PERSONNEL_ORDERS_APPLY','ASSISTANT_PERSONNEL_ORDERS_DELETE_OWN');
        DELETE FROM public.roles WHERE code='SYSADMIN_ASSISTANT';
    """)
