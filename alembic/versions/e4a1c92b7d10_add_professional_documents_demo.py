"""add professional documents demo tables and seed

Revision ID: e4a1c92b7d10
Revises: b5e2a81d4c03
Create Date: 2026-06-13 12:00:00.000000

ADR-034 demo: certificate_types + employee_certificates with demonstration seed.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e4a1c92b7d10"
down_revision: Union[str, Sequence[str], None] = "b5e2a81d4c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.certificate_types (
            certificate_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_certificates (
            certificate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL,
            certificate_type_id BIGINT NOT NULL,
            certificate_number TEXT NULL,
            issued_at DATE NULL,
            expires_at DATE NULL,
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_employee_certificates_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id),
            CONSTRAINT fk_employee_certificates_type
                FOREIGN KEY (certificate_type_id)
                REFERENCES public.certificate_types(certificate_type_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_certificates_employee_type
        ON public.employee_certificates (employee_id, certificate_type_id)
        WHERE is_current = TRUE
        """
    )

    op.execute(
        """
        INSERT INTO public.certificate_types (code, name, is_active)
        VALUES
            ('MED_SPEC', 'Сертификат специалиста', TRUE),
            ('ACCRED', 'Аккредитация', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active
        """
    )

    # Demo seed: 4 employees with different expiry statuses; 5th+ left without MED_SPEC (MISSING in UI).
    op.execute(
        """
        DELETE FROM public.employee_certificates
        WHERE certificate_number LIKE 'DEMO-%'
        """
    )

    op.execute(
        """
        INSERT INTO public.employee_certificates (
            employee_id,
            certificate_type_id,
            certificate_number,
            issued_at,
            expires_at,
            is_current
        )
        SELECT
            picked.employee_id,
            ct.certificate_type_id,
            picked.cert_number,
            CURRENT_DATE - 365,
            picked.expires_at,
            TRUE
        FROM public.certificate_types ct
        JOIN (
            SELECT *
            FROM (
                SELECT
                    e.employee_id,
                    ROW_NUMBER() OVER (ORDER BY e.employee_id) AS rn,
                    CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                        WHEN 1 THEN CURRENT_DATE + 365
                        WHEN 2 THEN CURRENT_DATE + 45
                        WHEN 3 THEN CURRENT_DATE + 20
                        WHEN 4 THEN CURRENT_DATE - 10
                    END AS expires_at,
                    CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                        WHEN 1 THEN 'DEMO-VALID'
                        WHEN 2 THEN 'DEMO-60'
                        WHEN 3 THEN 'DEMO-30'
                        WHEN 4 THEN 'DEMO-EXP'
                    END AS cert_number,
                    CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                        WHEN 3 THEN 'ACCRED'
                        ELSE 'MED_SPEC'
                    END AS type_code
                FROM public.employees e
                WHERE e.is_active = TRUE
            ) ranked
            WHERE ranked.rn BETWEEN 1 AND 4
        ) picked ON ct.code = picked.type_code
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM public.employee_certificates WHERE certificate_number LIKE 'DEMO-%'")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_certificates_employee_type")
    op.execute("DROP TABLE IF EXISTS public.employee_certificates")
    op.execute("DELETE FROM public.certificate_types WHERE code IN ('MED_SPEC', 'ACCRED')")
    op.execute("DROP TABLE IF EXISTS public.certificate_types")
