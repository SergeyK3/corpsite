"""WP-II-003 — Incoming Information review fixes: control fields and restricted bypass."""
from __future__ import annotations

from alembic import op

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

_NEW_PERMISSION = "INCOMING_INFO_RESTRICTED_BYPASS"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD COLUMN IF NOT EXISTS control_decision TEXT NULL,
            ADD COLUMN IF NOT EXISTS control_comment TEXT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD CONSTRAINT chk_incoming_documents_control_decision
                CHECK (control_decision IS NULL OR btrim(control_decision) <> '')
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            ADD CONSTRAINT chk_incoming_documents_control_comment
                CHECK (control_comment IS NULL OR btrim(control_comment) <> '')
        """
    )

    display_name = _NEW_PERMISSION.replace("_", " ").title()
    op.execute(
        f"""
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        )
        VALUES (
            '{_NEW_PERMISSION}',
            '{display_name}',
            'WP-II-003 Incoming Information ({_NEW_PERMISSION})',
            'MANAGER', 20, TRUE
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
        f"""
        DELETE FROM public.access_grants g
        USING public.access_roles ar
        WHERE g.access_role_id = ar.access_role_id
          AND ar.code = '{_NEW_PERMISSION}'
        """
    )
    op.execute(
        f"""
        DELETE FROM public.access_roles
        WHERE code = '{_NEW_PERMISSION}'
        """
    )
    op.execute(
        """
        ALTER TABLE public.incoming_documents
            DROP CONSTRAINT IF EXISTS chk_incoming_documents_control_comment,
            DROP CONSTRAINT IF EXISTS chk_incoming_documents_control_decision,
            DROP COLUMN IF EXISTS control_comment,
            DROP COLUMN IF EXISTS control_decision
        """
    )
