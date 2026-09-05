"""WP-TD-005 stage 3: provenance state and versioned relationship fingerprint.

Revision ID: td005fp3v101
Revises: td005tomb201
"""
from __future__ import annotations

from alembic import op


revision = "td005fp3v101"
down_revision = "td005tomb201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.test_personnel_provenance
            ADD COLUMN provenance_state TEXT NOT NULL DEFAULT 'ACTIVE',
            ADD CONSTRAINT ck_tpp_state
                CHECK (provenance_state IN ('ACTIVE', 'REVOKED'))
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td002_provenance_stamp() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            latest_version INTEGER;
        BEGIN
            SELECT max(provenance_version)
              INTO latest_version
             FROM public.test_personnel_provenance
             WHERE target_type = NEW.target_type
               AND target_id = NEW.target_id;
            IF latest_version IS NOT NULL AND NEW.provenance_version <= latest_version THEN
                RAISE EXCEPTION 'WP_TD_005_PROVENANCE_VERSION_NOT_MONOTONIC';
            END IF;
            NEW.created_at := statement_timestamp();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_provenance_truncate_guard
        BEFORE TRUNCATE ON public.test_personnel_provenance
        FOR EACH STATEMENT EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )

    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
            ADD COLUMN fingerprint_version TEXT NOT NULL DEFAULT 'WP-TD-RELATIONSHIP/v1',
            ADD COLUMN relationship_policy_version TEXT NULL,
            ADD COLUMN catalog_version TEXT NULL,
            ADD COLUMN catalog_fingerprint TEXT NULL,
            ADD CONSTRAINT ck_tpdr_fingerprint_version
                CHECK (length(btrim(fingerprint_version)) BETWEEN 1 AND 128),
            ADD CONSTRAINT ck_tpdr_policy_version
                CHECK (relationship_policy_version IS NULL OR length(btrim(relationship_policy_version)) BETWEEN 1 AND 128),
            ADD CONSTRAINT ck_tpdr_catalog_version
                CHECK (catalog_version IS NULL OR length(btrim(catalog_version)) BETWEEN 1 AND 128),
            ADD CONSTRAINT ck_tpdr_catalog_fingerprint
                CHECK (catalog_fingerprint IS NULL OR catalog_fingerprint ~ '^[0-9a-f]{64}$')
        """
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_decisions
            ADD COLUMN relationship_fingerprint TEXT NULL,
            ADD COLUMN fingerprint_version TEXT NULL,
            ADD COLUMN catalog_fingerprint TEXT NULL,
            ADD CONSTRAINT ck_tpdd_relationship_fingerprint
                CHECK (relationship_fingerprint IS NULL OR relationship_fingerprint ~ '^[0-9a-f]{64}$'),
            ADD CONSTRAINT ck_tpdd_fingerprint_version
                CHECK (fingerprint_version IS NULL OR length(btrim(fingerprint_version)) BETWEEN 1 AND 128),
            ADD CONSTRAINT ck_tpdd_catalog_fingerprint
                CHECK (catalog_fingerprint IS NULL OR catalog_fingerprint ~ '^[0-9a-f]{64}$')
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td005_fingerprint_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.relationship_fingerprint IS DISTINCT FROM OLD.relationship_fingerprint
               OR NEW.fingerprint_version IS DISTINCT FROM OLD.fingerprint_version
               OR NEW.relationship_policy_version IS DISTINCT FROM OLD.relationship_policy_version
               OR NEW.catalog_version IS DISTINCT FROM OLD.catalog_version
               OR NEW.catalog_fingerprint IS DISTINCT FROM OLD.catalog_fingerprint THEN
                IF OLD.status <> 'REAPPROVAL_REQUIRED'
                   OR NEW.status <> 'PENDING_HR_APPROVAL' THEN
                    RAISE EXCEPTION 'WP_TD_005_FINGERPRINT_REFRESH_FORBIDDEN';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_requests_fingerprint_guard
        BEFORE UPDATE ON public.test_personnel_deletion_requests
        FOR EACH ROW EXECUTE FUNCTION public.td005_fingerprint_guard()
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.test_personnel_deletion_requests.catalog_fingerprint IS
            'WP-TD-005 F-CATALOG hash frozen with the request; never authorizes execution by itself.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.test_personnel_provenance.provenance_state IS
            'Append-only state: revoke by inserting the next monotonically increasing version.'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.test_personnel_deletion_requests
                WHERE fingerprint_version <> 'WP-TD-RELATIONSHIP/v1'
                   OR relationship_policy_version IS NOT NULL
                   OR catalog_version IS NOT NULL
                   OR catalog_fingerprint IS NOT NULL
            ) OR EXISTS (
                SELECT 1 FROM public.test_personnel_deletion_decisions
                WHERE relationship_fingerprint IS NOT NULL
                   OR fingerprint_version IS NOT NULL
                   OR catalog_fingerprint IS NOT NULL
            ) OR EXISTS (
                SELECT 1 FROM public.test_personnel_provenance
                WHERE provenance_state <> 'ACTIVE'
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_FINGERPRINT_V2_DATA_PREVENT_DOWNGRADE';
            END IF;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER trg_test_personnel_deletion_requests_fingerprint_guard ON public.test_personnel_deletion_requests"
    )
    op.execute("DROP FUNCTION public.td005_fingerprint_guard()")
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_decisions
            DROP CONSTRAINT ck_tpdd_catalog_fingerprint,
            DROP CONSTRAINT ck_tpdd_fingerprint_version,
            DROP CONSTRAINT ck_tpdd_relationship_fingerprint,
            DROP COLUMN catalog_fingerprint,
            DROP COLUMN fingerprint_version,
            DROP COLUMN relationship_fingerprint
        """
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
            DROP CONSTRAINT ck_tpdr_catalog_fingerprint,
            DROP CONSTRAINT ck_tpdr_catalog_version,
            DROP CONSTRAINT ck_tpdr_policy_version,
            DROP CONSTRAINT ck_tpdr_fingerprint_version,
            DROP COLUMN catalog_fingerprint,
            DROP COLUMN catalog_version,
            DROP COLUMN relationship_policy_version,
            DROP COLUMN fingerprint_version
        """
    )
    op.execute(
        "DROP TRIGGER trg_test_personnel_provenance_truncate_guard ON public.test_personnel_provenance"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td002_provenance_stamp() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.created_at := statement_timestamp();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_provenance
            DROP CONSTRAINT ck_tpp_state,
            DROP COLUMN provenance_state
        """
    )
