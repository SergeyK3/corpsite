"""ADR-042 Phase B5 — idempotent access_roles seed (SECURITY_AUDITOR)."""
from __future__ import annotations

from alembic import op

revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        )
        VALUES
            (
                'SECURITY_AUDITOR',
                'Security Auditor',
                'Read security audit and access diagnostics',
                'OBSERVER', 10, TRUE
            )
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            access_level = EXCLUDED.access_level,
            level_rank = EXCLUDED.level_rank,
            is_system = EXCLUDED.is_system,
            is_active = TRUE,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM public.access_roles
        WHERE code = 'SECURITY_AUDITOR'
          AND NOT EXISTS (
              SELECT 1 FROM public.access_grants g
              JOIN public.access_roles r ON r.access_role_id = g.access_role_id
              WHERE r.code = 'SECURITY_AUDITOR'
          )
        """
    )
