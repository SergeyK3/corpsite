"""Add verification-aware employee termination records.

Revision ID: k8l9m0n1o2p3
Revises: l9m0n1o2p3q4
"""
from __future__ import annotations

from alembic import op


revision = "k8l9m0n1o2p3"
down_revision = "l9m0n1o2p3q4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.employee_termination_records (
            termination_record_id BIGSERIAL PRIMARY KEY,
            employee_id BIGINT NOT NULL UNIQUE,
            verification_status TEXT NOT NULL,
            termination_date DATE NULL,
            order_number TEXT NULL,
            order_date DATE NULL,
            termination_event_id BIGINT NULL UNIQUE,
            source_batch_id BIGINT NULL,
            source_row_id BIGINT NULL,
            source_normalized_record_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
            created_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by BIGINT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            verified_by BIGINT NULL,
            verified_at TIMESTAMPTZ NULL,
            CONSTRAINT fk_etr_employee
                FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_event
                FOREIGN KEY (termination_event_id) REFERENCES public.employee_events(event_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_batch
                FOREIGN KEY (source_batch_id) REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_row
                FOREIGN KEY (source_row_id) REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_created_by
                FOREIGN KEY (created_by) REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_updated_by
                FOREIGN KEY (updated_by) REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT fk_etr_verified_by
                FOREIGN KEY (verified_by) REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT chk_etr_status
                CHECK (verification_status IN ('UNVERIFIED', 'VERIFIED')),
            CONSTRAINT chk_etr_order_number
                CHECK (order_number IS NULL OR BTRIM(order_number) <> ''),
            CONSTRAINT chk_etr_provenance
                CHECK ((source_batch_id IS NULL) = (source_row_id IS NULL)),
            CONSTRAINT chk_etr_verification_shape CHECK (
                (
                    verification_status = 'UNVERIFIED'
                    AND termination_event_id IS NULL
                    AND verified_by IS NULL
                    AND verified_at IS NULL
                )
                OR
                (
                    verification_status = 'VERIFIED'
                    AND termination_date IS NOT NULL
                    AND order_number IS NOT NULL
                    AND order_date IS NOT NULL
                    AND termination_event_id IS NOT NULL
                    AND verified_by IS NOT NULL
                    AND verified_at IS NOT NULL
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_etr_status
        ON public.employee_termination_records (verification_status, employee_id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_etr_source_row
        ON public.employee_termination_records (source_batch_id, source_row_id)
        WHERE source_batch_id IS NOT NULL AND source_row_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE public.employee_termination_record_audit (
            audit_id BIGSERIAL PRIMARY KEY,
            termination_record_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            before_status TEXT NULL,
            after_status TEXT NOT NULL,
            actor_user_id BIGINT NOT NULL,
            details JSONB NOT NULL DEFAULT '{}'::JSONB,
            happened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_etra_record
                FOREIGN KEY (termination_record_id)
                REFERENCES public.employee_termination_records(termination_record_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_etra_actor
                FOREIGN KEY (actor_user_id) REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT chk_etra_action
                CHECK (action IN ('CREATED_UNVERIFIED', 'VERIFIED')),
            CONSTRAINT chk_etra_statuses CHECK (
                (action = 'CREATED_UNVERIFIED' AND before_status IS NULL AND after_status = 'UNVERIFIED')
                OR
                (action = 'VERIFIED' AND before_status = 'UNVERIFIED' AND after_status = 'VERIFIED')
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.employee_termination_record_audit")
    op.execute("DROP INDEX IF EXISTS public.uq_etr_source_row")
    op.execute("DROP INDEX IF EXISTS public.ix_etr_status")
    op.execute("DROP TABLE IF EXISTS public.employee_termination_records")
