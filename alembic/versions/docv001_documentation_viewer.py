"""Documentation viewer role and its observer permission; creates no accounts."""
from alembic import op

revision = "docv001"
down_revision = "popdata001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO public.roles(code,name,is_active)
        VALUES ('DOCUMENTATION_VIEWER','Подготовка руководства — просмотр',TRUE)
        ON CONFLICT(code) DO NOTHING;
        INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
        VALUES ('DOCUMENTATION_READ','Documentation viewer',
            'Reviewed read operations and pure previews only; no business mutations.',
            'OBSERVER',10,TRUE) ON CONFLICT(code) DO NOTHING;
        DO $$ BEGIN
            IF EXISTS(SELECT 1 FROM public.access_roles
                WHERE code='DOCUMENTATION_READ' AND (access_level<>'OBSERVER' OR level_rank<>10)) THEN
                RAISE EXCEPTION 'DOCUMENTATION_READ must be an observer permission';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS(SELECT 1 FROM public.users u JOIN public.roles r USING(role_id)
                WHERE r.code='DOCUMENTATION_VIEWER') THEN
                RAISE EXCEPTION 'Documentation accounts must be removed before downgrade';
            END IF;
        END $$;
        DELETE FROM public.access_roles WHERE code='DOCUMENTATION_READ';
        DELETE FROM public.roles WHERE code='DOCUMENTATION_VIEWER';
    """)
