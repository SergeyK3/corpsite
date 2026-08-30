"""WP-PO-002 Stage 2D: single-row archive review."""
from __future__ import annotations

from alembic import op

revision = "v5w6x7y8z9a"
down_revision = "u4v5w6x7y8z"
branch_labels = None
depends_on = None

_PERMISSION = "OPERATIONAL_ORDER_ARCHIVE_REVIEW"
_ROLE_CODES = ("HR_reg", "ADMIN")
_GRANT_REASON = "WP-PO-002 Stage 2D archive review"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.operational_order_import_rows
            ADD COLUMN confirmed_subject TEXT NULL,
            ADD COLUMN review_comment TEXT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_import_rows
            ADD CONSTRAINT chk_oo_import_rows_review_outcome
                CHECK (
                    review_outcome IS NULL OR review_outcome IN (
                        'CONFIRMED', 'NEEDS_CLARIFICATION', 'DRAFT_ORDER',
                        'ORDER_ANNEX', 'SUPPORTING_DOCUMENT', 'DUPLICATE', 'NOT_AN_ORDER'
                    )
                ),
            ADD CONSTRAINT chk_oo_import_rows_confirmed_fields
                CHECK (
                    review_outcome <> 'CONFIRMED' OR (
                        confirmed_document_type IS NOT NULL
                        AND btrim(confirmed_document_type) <> ''
                        AND confirmed_order_number IS NOT NULL
                        AND btrim(confirmed_order_number) <> ''
                        AND confirmed_order_date IS NOT NULL
                        AND confirmed_subject IS NOT NULL
                        AND btrim(confirmed_subject) <> ''
                    )
                ),
            ADD CONSTRAINT chk_oo_import_rows_review_comment
                CHECK (
                    review_outcome IS NULL OR review_outcome = 'CONFIRMED'
                    OR (review_comment IS NOT NULL AND btrim(review_comment) <> '')
                ),
            ADD CONSTRAINT chk_oo_import_rows_nonconfirmed_fields
                CHECK (
                    review_outcome IS NULL OR review_outcome = 'CONFIRMED' OR (
                        confirmed_document_type IS NULL
                        AND confirmed_order_number IS NULL
                        AND confirmed_order_date IS NULL
                        AND confirmed_subject IS NULL
                    )
                )
        """
    )
    op.execute(
        f"""
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        ) VALUES (
            '{_PERMISSION}',
            'Operational Order Archive Review',
            'Review one operational-order archive staging row',
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
    roles_sql = ", ".join(f"'{code}'" for code in _ROLE_CODES)
    reason = _GRANT_REASON.replace("'", "''")
    op.execute(
        f"""
        INSERT INTO public.access_grants (
            access_role_id, target_type, target_id, granted_by_user_id, reason
        )
        SELECT ar.access_role_id, 'ROLE', r.role_id,
               COALESCE(
                   (SELECT user_id FROM public.users
                    WHERE lower(login) = 'admin' AND is_active = TRUE
                    ORDER BY user_id LIMIT 1),
                   (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1)
               ),
               '{reason}'
        FROM public.access_roles ar
        CROSS JOIN public.roles r
        WHERE ar.code = '{_PERMISSION}'
          AND ar.is_active = TRUE
          AND r.code IN ({roles_sql})
          AND NOT EXISTS (
              SELECT 1 FROM public.access_grants g
              WHERE g.active_flag = TRUE
                AND g.access_role_id = ar.access_role_id
                AND g.target_type = 'ROLE'
                AND g.target_id = r.role_id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.operational_order_import_rows
                WHERE confirmed_subject IS NOT NULL OR review_comment IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'WP-PO-002 Stage 2D downgrade refused: review data exists';
            END IF;
        END
        $$
        """
    )

    roles_sql = ", ".join(f"'{code}'" for code in _ROLE_CODES)
    reason = _GRANT_REASON.replace("'", "''")
    op.execute(
        f"""
        DELETE FROM public.access_grants g
        USING public.access_roles ar, public.roles r
        WHERE g.access_role_id = ar.access_role_id
          AND g.target_type = 'ROLE'
          AND g.target_id = r.role_id
          AND ar.code = '{_PERMISSION}'
          AND r.code IN ({roles_sql})
          AND g.reason = '{reason}'
        """
    )
    op.execute(
        f"""
        DELETE FROM public.access_roles ar
        WHERE ar.code = '{_PERMISSION}'
          AND NOT EXISTS (
              SELECT 1 FROM public.access_grants g
              WHERE g.access_role_id = ar.access_role_id
          )
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_import_rows
            DROP CONSTRAINT IF EXISTS chk_oo_import_rows_nonconfirmed_fields,
            DROP CONSTRAINT chk_oo_import_rows_review_comment,
            DROP CONSTRAINT chk_oo_import_rows_confirmed_fields,
            DROP CONSTRAINT chk_oo_import_rows_review_outcome,
            DROP COLUMN review_comment,
            DROP COLUMN confirmed_subject
        """
    )
