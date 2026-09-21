"""Add the neutral QM training and attestation expert Platform Role.

Revision ID: qmt001trainingexpert
Revises: emp001employee
"""
from alembic import op


revision = "qmt001trainingexpert"
down_revision = "emp001employee"
branch_labels = None
depends_on = None


ROLE_CODE = "QM_TRAINING_EXPERT"
ROLE_NAME = "Эксперт по внутреннему обучению и аттестации"


def upgrade() -> None:
    # This is a catalog-only, non-privileged functional role.  It deliberately
    # creates neither access_grants nor any implicit permissions.
    op.execute(
        """
        INSERT INTO public.roles (code, name, is_active)
        VALUES ('QM_TRAINING_EXPERT', 'Эксперт по внутреннему обучению и аттестации', TRUE)
        ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name,
                is_active = TRUE
        """
    )
    op.execute(
        """
        DO $$
        DECLARE training_role_id BIGINT;
        BEGIN
            SELECT role_id INTO training_role_id
            FROM public.roles
            WHERE code = 'QM_TRAINING_EXPERT';
            IF EXISTS (
                SELECT 1
                FROM public.access_grants
                WHERE target_type = 'ROLE'
                  AND target_id = training_role_id
                  AND active_flag = TRUE
                  AND revoked_at IS NULL
            ) THEN
                RAISE EXCEPTION 'QM_TRAINING_EXPERT Platform Role must not have active access grants';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE training_role_id BIGINT;
        BEGIN
            SELECT role_id INTO training_role_id
            FROM public.roles
            WHERE code = 'QM_TRAINING_EXPERT';
            IF training_role_id IS NULL THEN
                RETURN;
            END IF;
            IF EXISTS (SELECT 1 FROM public.users WHERE role_id = training_role_id) THEN
                RAISE EXCEPTION 'Cannot remove QM_TRAINING_EXPERT while users reference it';
            END IF;
            IF EXISTS (SELECT 1 FROM public.access_grants WHERE target_type = 'ROLE' AND target_id = training_role_id) THEN
                RAISE EXCEPTION 'Cannot remove QM_TRAINING_EXPERT while grants reference it';
            END IF;
            DELETE FROM public.roles WHERE role_id = training_role_id;
        END $$;
        """
    )
