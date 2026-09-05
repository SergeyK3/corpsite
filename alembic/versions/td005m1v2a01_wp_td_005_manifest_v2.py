"""WP-TD-005 stage 1: PERSON-root applicant manifest v2.

Revision ID: td005m1v2a01
Revises: b1c2d3e4f5a6
"""
from __future__ import annotations

from alembic import op


revision = "td005m1v2a01"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
            ADD COLUMN manifest_version SMALLINT NOT NULL DEFAULT 1,
            ADD COLUMN process_type TEXT NOT NULL DEFAULT 'APPLICANT_ONLY',
            ADD CONSTRAINT ck_tpdr_manifest_version CHECK (manifest_version IN (1, 2)),
            ADD CONSTRAINT ck_tpdr_process_type CHECK (process_type = 'APPLICANT_ONLY')
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td005_application_ids_are_canonical(input_values BIGINT[])
        RETURNS BOOLEAN
        LANGUAGE sql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
            SELECT cardinality(input_values) > 0
               AND array_position(input_values, NULL) IS NULL
               AND NOT EXISTS (
                    SELECT 1
                    FROM generate_subscripts(input_values, 1) AS position
                    WHERE input_values[position] <= 0
                       OR (position > 1 AND input_values[position] <= input_values[position - 1])
               )
        $$
        """
    )
    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_manifest_v2_targets (
            manifest_target_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL
                REFERENCES public.test_personnel_deletion_requests (request_id)
                ON DELETE RESTRICT,
            root_type TEXT NOT NULL DEFAULT 'PERSON',
            person_id BIGINT NOT NULL,
            application_ids BIGINT[] NOT NULL,
            manifest_order INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT ck_tpd_v2_root_type CHECK (root_type = 'PERSON'),
            CONSTRAINT ck_tpd_v2_person_id CHECK (person_id > 0),
            CONSTRAINT ck_tpd_v2_application_ids CHECK (
                public.td005_application_ids_are_canonical(application_ids)
            ),
            CONSTRAINT ck_tpd_v2_manifest_order CHECK (manifest_order >= 0),
            CONSTRAINT uq_tpd_v2_request_person UNIQUE (request_id, person_id),
            CONSTRAINT uq_tpd_v2_request_order UNIQUE (request_id, manifest_order)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tpd_v2_request
        ON public.test_personnel_deletion_manifest_v2_targets (request_id, manifest_order)
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td005_manifest_v2_target_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            request_manifest_version SMALLINT;
            request_process_type TEXT;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'WP_TD_005_MANIFEST_V2_TARGET_RETAINED';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'WP_TD_005_MANIFEST_V2_TARGET_IMMUTABLE';
            END IF;

            SELECT manifest_version, process_type
              INTO request_manifest_version, request_process_type
              FROM public.test_personnel_deletion_requests
             WHERE request_id = NEW.request_id;

            IF request_manifest_version IS DISTINCT FROM 2
               OR request_process_type IS DISTINCT FROM 'APPLICANT_ONLY' THEN
                RAISE EXCEPTION 'WP_TD_005_MANIFEST_V2_REQUEST_REQUIRED';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_manifest_v2_targets_guard
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.test_personnel_deletion_manifest_v2_targets
        FOR EACH ROW EXECUTE FUNCTION public.td005_manifest_v2_target_guard()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td002_request_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'WP_TD_002_REQUEST_RETAINED';
            END IF;
            IF NEW.request_id IS DISTINCT FROM OLD.request_id
               OR NEW.request_number IS DISTINCT FROM OLD.request_number
               OR NEW.basis IS DISTINCT FROM OLD.basis
               OR NEW.reason_code IS DISTINCT FROM OLD.reason_code
               OR NEW.preview_criteria IS DISTINCT FROM OLD.preview_criteria
               OR NEW.original_mask IS DISTINCT FROM OLD.original_mask
               OR NEW.target_set_hash IS DISTINCT FROM OLD.target_set_hash
               OR NEW.manifest_version IS DISTINCT FROM OLD.manifest_version
               OR NEW.process_type IS DISTINCT FROM OLD.process_type
               OR NEW.initiated_by_user_id IS DISTINCT FROM OLD.initiated_by_user_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'WP_TD_002_REQUEST_MANIFEST_IMMUTABLE';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.test_personnel_deletion_requests
                WHERE manifest_version = 2
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_V2_REQUESTS_PREVENT_DOWNGRADE';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td002_request_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'WP_TD_002_REQUEST_RETAINED';
            END IF;
            IF NEW.request_id IS DISTINCT FROM OLD.request_id
               OR NEW.request_number IS DISTINCT FROM OLD.request_number
               OR NEW.basis IS DISTINCT FROM OLD.basis
               OR NEW.reason_code IS DISTINCT FROM OLD.reason_code
               OR NEW.preview_criteria IS DISTINCT FROM OLD.preview_criteria
               OR NEW.original_mask IS DISTINCT FROM OLD.original_mask
               OR NEW.target_set_hash IS DISTINCT FROM OLD.target_set_hash
               OR NEW.initiated_by_user_id IS DISTINCT FROM OLD.initiated_by_user_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'WP_TD_002_REQUEST_MANIFEST_IMMUTABLE';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_test_personnel_deletion_manifest_v2_targets_guard
        ON public.test_personnel_deletion_manifest_v2_targets
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.td005_manifest_v2_target_guard()")
    op.execute("DROP TABLE public.test_personnel_deletion_manifest_v2_targets")
    op.execute("DROP FUNCTION public.td005_application_ids_are_canonical(BIGINT[])")
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
            DROP CONSTRAINT ck_tpdr_process_type,
            DROP CONSTRAINT ck_tpdr_manifest_version,
            DROP COLUMN process_type,
            DROP COLUMN manifest_version
        """
    )
