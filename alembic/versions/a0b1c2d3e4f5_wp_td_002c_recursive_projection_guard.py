"""WP-TD-002C: recursive PII-key guard for immutable result projections.

Revision ID: a0b1c2d3e4f5
Revises: z9a0b1c2d3e4
"""
from __future__ import annotations

from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "z9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION public.td002_jsonb_has_forbidden_key(document JSONB)
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        AS $function$
        DECLARE
            item RECORD;
            element JSONB;
        BEGIN
            IF jsonb_typeof(document) = 'object' THEN
                FOR item IN SELECT key, value FROM jsonb_each(document)
                LOOP
                    IF lower(item.key) = ANY (ARRAY[
                        'iin', 'iin_masked', 'masked_iin',
                        'phone', 'phone_number', 'mobile_phone',
                        'email', 'email_address',
                        'display_name', 'full_name', 'first_name', 'last_name',
                        'middle_name', 'patronymic',
                        'birth_date', 'date_of_birth', 'address', 'comment'
                    ]) OR public.td002_jsonb_has_forbidden_key(item.value) THEN
                        RETURN TRUE;
                    END IF;
                END LOOP;
            ELSIF jsonb_typeof(document) = 'array' THEN
                FOR element IN SELECT value FROM jsonb_array_elements(document)
                LOOP
                    IF public.td002_jsonb_has_forbidden_key(element) THEN
                        RETURN TRUE;
                    END IF;
                END LOOP;
            END IF;
            RETURN FALSE;
        END
        $function$
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_result_projection"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_result_projection CHECK (
            jsonb_typeof(result_projection) = 'object'
            AND NOT public.td002_jsonb_has_forbidden_key(result_projection)
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_result_projection"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_result_projection CHECK (
            jsonb_typeof(result_projection) = 'object'
            AND NOT (result_projection ?| ARRAY[
                'iin', 'phone', 'email', 'display_name', 'full_name', 'comment'
            ])
        )
        """
    )
    op.execute("DROP FUNCTION public.td002_jsonb_has_forbidden_key(JSONB)")
