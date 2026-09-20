"""Person-rooted personnel-card correction permission and contacts."""
from alembic import op

revision = "pce001cardedit"
# Continue the committed PPR branch.  The local Data Exchange migrations are
# a separate uncommitted branch and must not become a prerequisite of this
# independently deployable personnel-card change.
down_revision = "ppr005qnotedetails01"
branch_labels = None
depends_on = None

PERMISSION = "PERSONNEL_CARD_EDIT"


def upgrade() -> None:
    op.execute("""
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES ('PERSONNEL_CARD_EDIT','Personnel Card Edit',
              'Person-rooted HR personal-card corrections','MANAGER',20,TRUE)
      ON CONFLICT (code) DO UPDATE SET is_active=TRUE, updated_at=now()
    """)
    # Match the existing HR_ENROLLMENT_MANAGER access contour rather than all
    # visibility readers.  ROLE grants preserve the existing organizational
    # scope evaluation at request time.
    op.execute("""
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT card.access_role_id,'ROLE',role_target.target_id,admin.user_id,
             'Initial personnel-card editor grant mirrors HR_ENROLLMENT_MANAGER'
      FROM public.access_roles card
      JOIN public.access_roles enrollment ON enrollment.code='HR_ENROLLMENT_MANAGER' AND enrollment.is_active
      JOIN public.access_grants enrollment_grant ON enrollment_grant.access_role_id=enrollment.access_role_id
        AND enrollment_grant.active_flag=TRUE AND enrollment_grant.target_type='ROLE'
      JOIN LATERAL (SELECT enrollment_grant.target_id) role_target ON TRUE
      CROSS JOIN LATERAL (SELECT user_id FROM public.users WHERE is_active=TRUE ORDER BY user_id LIMIT 1) admin
      WHERE card.code='PERSONNEL_CARD_EDIT' AND card.is_active
        AND NOT EXISTS (SELECT 1 FROM public.access_grants x WHERE x.active_flag=TRUE
          AND x.access_role_id=card.access_role_id AND x.target_type='ROLE' AND x.target_id=role_target.target_id)
    """)
    op.execute("""
      CREATE TABLE IF NOT EXISTS public.person_contacts (
        person_id BIGINT PRIMARY KEY REFERENCES public.persons(person_id) ON DELETE RESTRICT,
        mobile_phone TEXT NULL,
        email TEXT NULL,
        registration_address TEXT NULL,
        residence_address TEXT NULL,
        version BIGINT NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
        updated_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
        source_kind TEXT NOT NULL DEFAULT 'HR_MANUAL'
      )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.person_contacts")
    op.execute("DELETE FROM public.access_grants WHERE access_role_id IN (SELECT access_role_id FROM public.access_roles WHERE code='PERSONNEL_CARD_EDIT')")
    op.execute("DELETE FROM public.access_roles WHERE code='PERSONNEL_CARD_EDIT'")
