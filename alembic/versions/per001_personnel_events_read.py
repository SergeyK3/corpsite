"""Add the narrow read-only personnel event journal permission."""
from alembic import op


revision = "per001eventsread"
down_revision = "pce001cardedit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO public.access_roles(code, name, description, access_level, level_rank, is_system)
      VALUES (
        'PERSONNEL_EVENTS_READ',
        'Personnel Events Read',
        'Read-only personnel event journal; requires personnel visibility scope',
        'OBSERVER',
        10,
        TRUE
      )
      ON CONFLICT (code) DO UPDATE
        SET is_active = TRUE, updated_at = now()
    """)


def downgrade() -> None:
    op.execute("""
      DELETE FROM public.access_grants
      WHERE access_role_id IN (
        SELECT access_role_id FROM public.access_roles WHERE code = 'PERSONNEL_EVENTS_READ'
      )
    """)
    op.execute("DELETE FROM public.access_roles WHERE code = 'PERSONNEL_EVENTS_READ'")
