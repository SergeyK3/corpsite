"""add employee documents registry phase 1a

Revision ID: d9e8f71a2b05
Revises: c7f3d92a1e04
Create Date: 2026-06-16 12:00:00.000000

ADR-037 Phase 1A: medical_specialty_groups, medical_specialties,
document_types, document_kinds, employee_documents (production registry).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d9e8f71a2b05"
down_revision: Union[str, Sequence[str], None] = "c7f3d92a1e04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.medical_specialty_groups (
            group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        INSERT INTO public.medical_specialty_groups (code, name, is_active)
        VALUES
            ('DOCTOR', 'Врачи', TRUE),
            ('NURSE', 'Средний медицинский персонал', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.medical_specialties (
            medical_specialty_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            group_id BIGINT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_medical_specialties_group
                FOREIGN KEY (group_id)
                REFERENCES public.medical_specialty_groups(group_id),
            CONSTRAINT uq_medical_specialties_group_code
                UNIQUE (group_id, code)
        )
        """
    )

    op.execute(
        """
        INSERT INTO public.medical_specialties (group_id, code, name, is_active)
        SELECT g.group_id, v.code, v.name, TRUE
        FROM public.medical_specialty_groups g
        JOIN (
            VALUES
                ('DOCTOR', 'ONCOLOGY', 'Врач-онколог'),
                ('DOCTOR', 'SURGERY', 'Врач-хирург'),
                ('DOCTOR', 'THERAPY', 'Врач-терапевт'),
                ('DOCTOR', 'GYNECOLOGY', 'Врач-акушер-гинеколог'),
                ('NURSE', 'GENERAL', 'Медицинская сестра'),
                ('NURSE', 'OR', 'Операционная медсестра')
        ) AS v(group_code, code, name)
          ON g.code = v.group_code
        ON CONFLICT ON CONSTRAINT uq_medical_specialties_group_code DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.document_types (
            document_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            has_valid_until BOOLEAN NOT NULL DEFAULT FALSE,
            requires_medical_specialty BOOLEAN NOT NULL DEFAULT FALSE,
            tracks_hours BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INT NOT NULL DEFAULT 0,
            CONSTRAINT chk_document_types_category CHECK (
                category IN ('CREDENTIAL', 'EDUCATION', 'PARTICIPATION')
            )
        )
        """
    )

    op.execute(
        """
        INSERT INTO public.document_types (
            code, name, category, has_valid_until, requires_medical_specialty,
            tracks_hours, is_active, sort_order
        )
        VALUES
            ('EDUCATION_GRADUATION', 'Окончание учебного заведения', 'EDUCATION', FALSE, FALSE, FALSE, TRUE, 10),
            ('SPECIALIST_CERTIFICATION', 'Сертификация специалиста', 'CREDENTIAL', TRUE, TRUE, FALSE, TRUE, 20),
            ('CONTINUING_EDUCATION', 'Повышение квалификации', 'EDUCATION', FALSE, TRUE, FALSE, TRUE, 30),
            ('PROFESSIONAL_RETRAINING', 'Переподготовка', 'EDUCATION', FALSE, TRUE, FALSE, TRUE, 40),
            ('CONFERENCE_PARTICIPATION', 'Участие в конференции', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 50),
            ('MASTERCLASS_PARTICIPATION', 'Участие в мастер-классе', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 60),
            ('SEMINAR_PARTICIPATION', 'Участие в семинаре', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 70)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            has_valid_until = EXCLUDED.has_valid_until,
            requires_medical_specialty = EXCLUDED.requires_medical_specialty,
            tracks_hours = EXCLUDED.tracks_hours,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order
        """
    )

    op.execute(
        """
        UPDATE public.document_types
        SET is_active = FALSE
        WHERE code IN (
            'SPECIALIST_CERT',
            'ACCREDITATION',
            'QUAL_UPGRADE',
            'RETRAINING_DIPLOMA',
            'CONFERENCE_CERT',
            'SEMINAR_CERT',
            'MASTERCLASS_CERT'
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.document_kinds (
            document_kind_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INT NOT NULL DEFAULT 0
        )
        """
    )

    op.execute(
        """
        INSERT INTO public.document_kinds (code, name, is_active, sort_order)
        VALUES
            ('DIPLOMA', 'Диплом', TRUE, 10),
            ('CERTIFICATE', 'Сертификат', TRUE, 20),
            ('ATTESTATION', 'Свидетельство', TRUE, 30),
            ('COMPLETION_CERT', 'Удостоверение', TRUE, 40),
            ('REFERENCE', 'Справка', TRUE, 50),
            ('OTHER', 'Прочее', TRUE, 60)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_documents (
            document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL,
            document_type_id BIGINT NOT NULL,
            document_kind_id BIGINT NULL,
            medical_specialty_id BIGINT NULL,
            title TEXT NULL,
            training_title TEXT NULL,
            document_number TEXT NULL,
            issued_by TEXT NULL,
            issued_at DATE NULL,
            valid_until DATE NULL,
            file_url TEXT NULL,
            comment TEXT NULL,
            lifecycle_status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_employee_documents_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id),
            CONSTRAINT fk_employee_documents_type
                FOREIGN KEY (document_type_id)
                REFERENCES public.document_types(document_type_id),
            CONSTRAINT fk_employee_documents_kind
                FOREIGN KEY (document_kind_id)
                REFERENCES public.document_kinds(document_kind_id),
            CONSTRAINT fk_employee_documents_specialty
                FOREIGN KEY (medical_specialty_id)
                REFERENCES public.medical_specialties(medical_specialty_id),
            CONSTRAINT fk_employee_documents_created_by
                FOREIGN KEY (created_by)
                REFERENCES public.users(user_id),
            CONSTRAINT chk_employee_documents_lifecycle_status CHECK (
                lifecycle_status IN ('ACTIVE', 'SUPERSEDED', 'DRAFT')
            )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_employee_active
        ON public.employee_documents (employee_id, lifecycle_status)
        WHERE lifecycle_status = 'ACTIVE'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_type
        ON public.employee_documents (document_type_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_specialty
        ON public.employee_documents (medical_specialty_id)
        WHERE medical_specialty_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_valid_until
        ON public.employee_documents (valid_until)
        WHERE lifecycle_status = 'ACTIVE' AND valid_until IS NOT NULL
        """
    )

    # Idempotent for dev DBs that applied an earlier draft of this revision.
    op.execute(
        """
        ALTER TABLE public.employee_documents
            ADD COLUMN IF NOT EXISTS document_kind_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS training_title TEXT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_employee_documents_kind'
            ) THEN
                ALTER TABLE public.employee_documents
                    ADD CONSTRAINT fk_employee_documents_kind
                    FOREIGN KEY (document_kind_id)
                    REFERENCES public.document_kinds(document_kind_id);
            END IF;
        END $$
        """
    )

    # Idempotent refresh for dev DBs that applied an earlier document_types seed draft.
    op.execute(
        """
        INSERT INTO public.document_types (
            code, name, category, has_valid_until, requires_medical_specialty,
            tracks_hours, is_active, sort_order
        )
        VALUES
            ('EDUCATION_GRADUATION', 'Окончание учебного заведения', 'EDUCATION', FALSE, FALSE, FALSE, TRUE, 10),
            ('SPECIALIST_CERTIFICATION', 'Сертификация специалиста', 'CREDENTIAL', TRUE, TRUE, FALSE, TRUE, 20),
            ('CONTINUING_EDUCATION', 'Повышение квалификации', 'EDUCATION', FALSE, TRUE, FALSE, TRUE, 30),
            ('PROFESSIONAL_RETRAINING', 'Переподготовка', 'EDUCATION', FALSE, TRUE, FALSE, TRUE, 40),
            ('CONFERENCE_PARTICIPATION', 'Участие в конференции', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 50),
            ('MASTERCLASS_PARTICIPATION', 'Участие в мастер-классе', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 60),
            ('SEMINAR_PARTICIPATION', 'Участие в семинаре', 'PARTICIPATION', FALSE, FALSE, FALSE, TRUE, 70)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            has_valid_until = EXCLUDED.has_valid_until,
            requires_medical_specialty = EXCLUDED.requires_medical_specialty,
            tracks_hours = EXCLUDED.tracks_hours,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order
        """
    )
    op.execute(
        """
        UPDATE public.document_types
        SET is_active = FALSE
        WHERE code IN (
            'SPECIALIST_CERT',
            'ACCREDITATION',
            'QUAL_UPGRADE',
            'RETRAINING_DIPLOMA',
            'CONFERENCE_CERT',
            'SEMINAR_CERT',
            'MASTERCLASS_CERT'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_valid_until")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_specialty")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_type")
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_employee_active")
    op.execute("DROP TABLE IF EXISTS public.employee_documents")
    op.execute("DROP TABLE IF EXISTS public.document_kinds")
    op.execute("DROP TABLE IF EXISTS public.document_types")
    op.execute("DROP TABLE IF EXISTS public.medical_specialties")
    op.execute("DROP TABLE IF EXISTS public.medical_specialty_groups")
