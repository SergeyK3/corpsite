"""Separate event-only organisational scope from personnel-card visibility."""
from alembic import op


revision = "per002eventscope"
down_revision = "per001eventsread"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE public.personnel_event_visibility_assignments (
        assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        target_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
        scope_type TEXT NOT NULL CHECK (scope_type IN ('ORGANIZATION', 'DEPARTMENT', 'DEPARTMENT_GROUP')),
        scope_department_id BIGINT NULL REFERENCES public.org_units(unit_id) ON DELETE SET NULL,
        scope_department_group_id BIGINT NULL REFERENCES public.deps_group(group_id) ON DELETE SET NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
        revoked_at TIMESTAMPTZ NULL,
        revoked_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE SET NULL,
        revoke_reason TEXT NULL,
        CONSTRAINT chk_peva_scope_subject CHECK (
          (scope_type = 'ORGANIZATION' AND scope_department_id IS NULL AND scope_department_group_id IS NULL)
          OR (scope_type = 'DEPARTMENT' AND scope_department_id IS NOT NULL AND scope_department_group_id IS NULL)
          OR (scope_type = 'DEPARTMENT_GROUP' AND scope_department_id IS NULL AND scope_department_group_id IS NOT NULL)
        )
      )
    """)
    op.execute("""
      CREATE INDEX ix_peva_active_target_user
      ON public.personnel_event_visibility_assignments(target_user_id)
      WHERE is_active = TRUE
    """)
    op.execute("""
      COMMENT ON TABLE public.personnel_event_visibility_assignments IS
      'Event-only organisational scope for PERSONNEL_EVENTS_READ; never grants personnel/PPR visibility.'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_event_visibility_assignments")
