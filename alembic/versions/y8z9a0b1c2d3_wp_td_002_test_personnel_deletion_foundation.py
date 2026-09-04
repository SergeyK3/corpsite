"""WP-TD-002: test personnel deletion approval foundation (no deletion).

Revision ID: y8z9a0b1c2d3
Revises: x7y8z9a0b1c2
"""
from __future__ import annotations

from alembic import op

revision = "y8z9a0b1c2d3"
down_revision = "x7y8z9a0b1c2"
branch_labels = None
depends_on = None

_PERMISSION_ROLES = {
    "TEST_PERSONNEL_DELETION_REQUEST": ("Request test personnel deletion", ("ADMIN",)),
    "TEST_PERSONNEL_DELETION_APPROVE": ("Approve test personnel deletion", ("HR_HEAD",)),
    "TEST_PERSONNEL_DELETION_EXECUTE": ("Execute approved test personnel deletion", ("ADMIN",)),
    "TEST_PERSONNEL_DELETION_AUDIT_READ": ("Read test personnel deletion audit", ("ADMIN", "HR_HEAD")),
}
_OWNER_MARKER = "WP-TD-002A:y8z9a0b1c2d3"


def _owned_grant_reasons() -> tuple[str, ...]:
    return tuple(
        f"{_OWNER_MARKER}:{code}:{role}"
        for code, (_name, roles) in _PERMISSION_ROLES.items()
        for role in roles
    )


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.roles WHERE code='ADMIN') <> 1
               OR (SELECT COUNT(*) FROM public.roles WHERE code='HR_HEAD') <> 1 THEN
                RAISE EXCEPTION 'WP_TD_002_CANONICAL_ROLE_CONFLICT';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM public.users WHERE is_active=TRUE) THEN
                RAISE EXCEPTION 'WP_TD_002_ACTIVE_GRANTOR_REQUIRED';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE public.test_personnel_provenance (
            provenance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id BIGINT NOT NULL,
            environment TEXT NOT NULL,
            test_run_id TEXT NOT NULL,
            creation_source TEXT NOT NULL,
            purpose TEXT NOT NULL,
            created_by_user_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source_artifact_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NULL,
            provenance_version INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT ck_tpp_target_type CHECK (target_type IN ('PERSON', 'APPLICATION')),
            CONSTRAINT ck_tpp_target_id CHECK (target_id > 0),
            CONSTRAINT ck_tpp_environment CHECK (btrim(environment) <> ''),
            CONSTRAINT ck_tpp_test_run_id CHECK (length(btrim(test_run_id)) BETWEEN 1 AND 128),
            CONSTRAINT ck_tpp_creation_source CHECK (length(btrim(creation_source)) BETWEEN 1 AND 128),
            CONSTRAINT ck_tpp_purpose CHECK (length(btrim(purpose)) BETWEEN 1 AND 1000),
            CONSTRAINT ck_tpp_source_hash CHECK (source_artifact_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpp_version CHECK (provenance_version >= 1),
            CONSTRAINT ck_tpp_expiry CHECK (expires_at IS NULL OR expires_at > created_at),
            CONSTRAINT uq_tpp_target_version UNIQUE (target_type, target_id, provenance_version)
        )
        """
    )
    op.execute("CREATE INDEX ix_tpp_target ON public.test_personnel_provenance (target_type, target_id)")
    op.execute("CREATE INDEX ix_tpp_test_run ON public.test_personnel_provenance (test_run_id)")

    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_requests (
            request_id UUID PRIMARY KEY,
            request_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            basis TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            preview_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
            original_mask TEXT NULL,
            target_set_hash TEXT NOT NULL,
            relationship_fingerprint TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            initiated_by_user_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            submitted_at TIMESTAMPTZ NULL,
            expires_at TIMESTAMPTZ NULL,
            last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_at TIMESTAMPTZ NULL,
            approval_expires_at TIMESTAMPTZ NULL,
            CONSTRAINT ck_tpdr_status CHECK (status IN (
                'DRAFT', 'PENDING_HR_APPROVAL', 'APPROVED', 'REJECTED',
                'REAPPROVAL_REQUIRED', 'CANCELLED', 'EXPIRED'
            )),
            CONSTRAINT ck_tpdr_basis CHECK (basis IN ('PROVENANCE', 'LEGACY_MANIFEST')),
            CONSTRAINT ck_tpdr_reason_code CHECK (reason_code IN (
                'LEGACY_SYNTHETIC_TEST_DATA', 'PROVENANCE_TEST_RUN_CLEANUP',
                'DUPLICATE_SYNTHETIC_FIXTURE', 'OTHER_APPROVED_TEST_DATA'
            )),
            CONSTRAINT ck_tpdr_target_hash CHECK (target_set_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdr_relationship_hash CHECK (relationship_fingerprint ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdr_version CHECK (version >= 1),
            CONSTRAINT ck_tpdr_expiry CHECK (expires_at IS NULL OR expires_at > created_at),
            CONSTRAINT ck_tpdr_approval_expiry CHECK (
                (approved_at IS NULL AND approval_expires_at IS NULL)
                OR (approved_at IS NOT NULL AND approval_expires_at > approved_at)
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_tpdr_status_created ON public.test_personnel_deletion_requests (status, created_at DESC)")
    op.execute("CREATE INDEX ix_tpdr_initiator ON public.test_personnel_deletion_requests (initiated_by_user_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_targets (
            target_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests (request_id) ON DELETE RESTRICT,
            target_type TEXT NOT NULL,
            person_id BIGINT NOT NULL,
            application_id BIGINT NULL,
            eligibility_status TEXT NOT NULL,
            blocking_codes TEXT[] NOT NULL DEFAULT '{}'::text[],
            tombstone_required_codes TEXT[] NOT NULL DEFAULT '{}'::text[],
            hr_attestation_codes TEXT[] NOT NULL DEFAULT '{}'::text[],
            informational_codes TEXT[] NOT NULL DEFAULT '{}'::text[],
            relationship_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
            relationship_fingerprint TEXT NOT NULL,
            manifest_order INTEGER NOT NULL,
            requires_hr_synthetic_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_tpdt_target_type CHECK (target_type = 'APPLICANT'),
            CONSTRAINT ck_tpdt_person_id CHECK (person_id > 0),
            CONSTRAINT ck_tpdt_application_id CHECK (application_id IS NULL OR application_id > 0),
            CONSTRAINT ck_tpdt_eligibility CHECK (eligibility_status IN (
                'ELIGIBLE', 'TOMBSTONE_REQUIRED', 'HR_ATTESTATION_REQUIRED', 'BLOCKED'
            )),
            CONSTRAINT ck_tpdt_fingerprint CHECK (relationship_fingerprint ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdt_manifest_order CHECK (manifest_order >= 0),
            CONSTRAINT uq_tpdt_request_order UNIQUE (request_id, manifest_order),
            CONSTRAINT uq_tpdt_request_target UNIQUE (request_id, target_type, person_id, application_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tpdt_request ON public.test_personnel_deletion_targets (request_id, manifest_order)")

    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_decisions (
            decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests (request_id) ON DELETE RESTRICT,
            decision TEXT NOT NULL,
            actor_user_id BIGINT NOT NULL,
            actor_role_code TEXT NOT NULL,
            permission_code TEXT NOT NULL,
            request_version INTEGER NOT NULL,
            target_set_hash TEXT NOT NULL,
            comment TEXT NULL,
            submitted_synthetic_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_tpdd_decision CHECK (decision IN ('APPROVE', 'REJECT')),
            CONSTRAINT ck_tpdd_version CHECK (request_version >= 1),
            CONSTRAINT ck_tpdd_hash CHECK (target_set_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdd_comment CHECK (comment IS NULL OR length(btrim(comment)) BETWEEN 1 AND 500)
        )
        """
    )
    op.execute("CREATE INDEX ix_tpdd_request ON public.test_personnel_deletion_decisions (request_id, decided_at DESC)")

    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_history (
            history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests (request_id) ON DELETE RESTRICT,
            actor_user_id BIGINT NOT NULL,
            actor_role_code TEXT NOT NULL,
            permission_code TEXT NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT NULL,
            new_status TEXT NOT NULL,
            old_version INTEGER NULL,
            new_version INTEGER NOT NULL,
            target_set_hash TEXT NOT NULL,
            comment TEXT NULL,
            idempotency_key TEXT NOT NULL,
            command_payload_hash TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            result_code TEXT NOT NULL,
            CONSTRAINT ck_tpdh_action CHECK (action IN ('CREATE', 'SUBMIT', 'APPROVE', 'REJECT', 'CANCEL', 'EXPIRE', 'RECHECK_FAILED')),
            CONSTRAINT ck_tpdh_hash CHECK (target_set_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdh_version CHECK (new_version >= 1 AND (old_version IS NULL OR old_version >= 1)),
            CONSTRAINT ck_tpdh_idempotency CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 128),
            CONSTRAINT ck_tpdh_command_hash CHECK (command_payload_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpdh_result CHECK (length(btrim(result_code)) BETWEEN 1 AND 128),
            CONSTRAINT uq_tpdh_idempotency UNIQUE (actor_user_id, action, idempotency_key)
        )
        """
    )
    op.execute("CREATE INDEX ix_tpdh_request ON public.test_personnel_deletion_history (request_id, occurred_at, history_id)")

    op.execute(
        """
        CREATE FUNCTION public.td002_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'WP_TD_002_APPEND_ONLY';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td002_provenance_stamp() RETURNS trigger
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
        CREATE FUNCTION public.td002_request_guard() RETURNS trigger
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
        CREATE TRIGGER trg_test_personnel_deletion_requests_guard
        BEFORE UPDATE OR DELETE ON public.test_personnel_deletion_requests
        FOR EACH ROW EXECUTE FUNCTION public.td002_request_guard()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td002_target_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'WP_TD_002_TARGET_RETAINED';
            END IF;
            IF NEW.target_id IS DISTINCT FROM OLD.target_id
               OR NEW.request_id IS DISTINCT FROM OLD.request_id
               OR NEW.target_type IS DISTINCT FROM OLD.target_type
               OR NEW.person_id IS DISTINCT FROM OLD.person_id
               OR NEW.application_id IS DISTINCT FROM OLD.application_id
               OR NEW.manifest_order IS DISTINCT FROM OLD.manifest_order
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'WP_TD_002_TARGET_MANIFEST_IMMUTABLE';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_targets_guard
        BEFORE UPDATE OR DELETE ON public.test_personnel_deletion_targets
        FOR EACH ROW EXECUTE FUNCTION public.td002_target_guard()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_provenance_stamp
        BEFORE INSERT ON public.test_personnel_provenance
        FOR EACH ROW EXECUTE FUNCTION public.td002_provenance_stamp()
        """
    )
    for table in (
        "test_personnel_provenance",
        "test_personnel_deletion_decisions",
        "test_personnel_deletion_history",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.td002_reject_mutation()
            """
        )

    for code, (name, _roles) in _PERMISSION_ROLES.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM public.access_roles WHERE code = '{code}') THEN
                    RAISE EXCEPTION 'WP_TD_002_PERMISSION_CODE_CONFLICT:{code}';
                END IF;
                INSERT INTO public.access_roles (code, name, description, access_level, level_rank, is_system)
                VALUES ('{code}', '{name}', '{_OWNER_MARKER}', 'MANAGER', 20, TRUE);
            END $$
            """
        )

    for code, (_name, roles) in _PERMISSION_ROLES.items():
        for role in roles:
            op.execute(
                f"""
            INSERT INTO public.access_grants (
                access_role_id, target_type, target_id, granted_by_user_id, reason
            )
            SELECT ar.access_role_id, 'ROLE', r.role_id, grantor.user_id,
                   '{_OWNER_MARKER}:{code}:{role}'
            FROM public.access_roles ar
            CROSS JOIN public.roles r
            CROSS JOIN LATERAL (
                SELECT user_id FROM public.users ORDER BY
                    CASE WHEN lower(login) = 'admin' THEN 0 ELSE 1 END, user_id LIMIT 1
            ) grantor
            WHERE ar.code = '{code}' AND r.code = '{role}'
              AND NOT EXISTS (
                  SELECT 1 FROM public.access_grants g
                  WHERE g.active_flag = TRUE AND g.access_role_id = ar.access_role_id
                    AND g.target_type = 'ROLE' AND g.target_id = r.role_id
              )
                """
            )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code in sorted(_PERMISSION_ROLES))
    expected_rows = ", ".join(
        f"('{code}', '{role}', '{_OWNER_MARKER}:{code}:{role}')"
        for code, (_name, roles) in _PERMISSION_ROLES.items()
        for role in roles
    )
    op.execute(
        f"""
        DO $$
        DECLARE
            expected_count INTEGER := {len(_owned_grant_reasons())};
        BEGIN
            IF (SELECT COUNT(*) FROM public.access_roles
                WHERE code IN ({codes}) AND description = '{_OWNER_MARKER}')
                <> {len(_PERMISSION_ROLES)} THEN
                RAISE EXCEPTION 'WP_TD_002_RBAC_OWNERSHIP_MISMATCH';
            END IF;
            IF EXISTS (
                WITH expected(permission_code, role_code, reason) AS (
                    VALUES {expected_rows}
                )
                SELECT 1
                FROM public.access_grants g
                JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
                LEFT JOIN public.roles r ON r.role_id = g.target_id AND g.target_type = 'ROLE'
                LEFT JOIN expected e ON e.permission_code = ar.code
                    AND e.role_code = r.code AND e.reason = g.reason
                WHERE ar.code IN ({codes})
                  AND ar.description = '{_OWNER_MARKER}'
                  AND (e.permission_code IS NULL OR g.active_flag IS DISTINCT FROM TRUE)
            ) THEN
                RAISE EXCEPTION 'WP_TD_002_EXTERNAL_GRANTS_PRESENT';
            END IF;
            IF EXISTS (
                WITH expected(permission_code, role_code, reason) AS (
                    VALUES {expected_rows}
                )
                SELECT 1 FROM public.access_grants g
                LEFT JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
                LEFT JOIN public.roles r ON r.role_id = g.target_id AND g.target_type = 'ROLE'
                JOIN expected e ON e.reason = g.reason
                WHERE ar.code IS DISTINCT FROM e.permission_code
                   OR ar.description IS DISTINCT FROM '{_OWNER_MARKER}'
                   OR r.code IS DISTINCT FROM e.role_code
                   OR g.target_type IS DISTINCT FROM 'ROLE'
                   OR g.active_flag IS DISTINCT FROM TRUE
            ) THEN
                RAISE EXCEPTION 'WP_TD_002_EXTERNAL_GRANTS_PRESENT';
            END IF;
            IF (SELECT COUNT(*) FROM public.access_grants g
                JOIN public.access_roles ar ON ar.access_role_id=g.access_role_id
                WHERE ar.code IN ({codes}) AND ar.description='{_OWNER_MARKER}')
                <> expected_count THEN
                RAISE EXCEPTION 'WP_TD_002_RBAC_GRANT_COUNT_MISMATCH';
            END IF;
        END $$
        """
    )
    op.execute(
        f"""
        WITH expected(permission_code, role_code, reason) AS (VALUES {expected_rows})
        DELETE FROM public.access_grants g
        USING public.access_roles ar, public.roles r, expected e
        WHERE g.access_role_id=ar.access_role_id
          AND g.target_type='ROLE' AND g.target_id=r.role_id
          AND ar.code=e.permission_code AND ar.description='{_OWNER_MARKER}'
          AND r.code=e.role_code AND g.reason=e.reason AND g.active_flag=TRUE
        """
    )
    op.execute(
        f"DELETE FROM public.access_roles WHERE code IN ({codes}) AND description = '{_OWNER_MARKER}'"
    )
    for trigger, table in (
        ("trg_test_personnel_deletion_history_append_only", "test_personnel_deletion_history"),
        ("trg_test_personnel_deletion_decisions_append_only", "test_personnel_deletion_decisions"),
        ("trg_test_personnel_provenance_append_only", "test_personnel_provenance"),
        ("trg_test_personnel_provenance_stamp", "test_personnel_provenance"),
        ("trg_test_personnel_deletion_targets_guard", "test_personnel_deletion_targets"),
        ("trg_test_personnel_deletion_requests_guard", "test_personnel_deletion_requests"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON public.{table}")
    for table in (
        "test_personnel_deletion_history",
        "test_personnel_deletion_decisions",
        "test_personnel_deletion_targets",
        "test_personnel_deletion_requests",
        "test_personnel_provenance",
    ):
        op.execute(f"DROP TABLE public.{table}")
    op.execute("DROP FUNCTION IF EXISTS public.td002_reject_mutation()")
    op.execute("DROP FUNCTION IF EXISTS public.td002_provenance_stamp()")
    op.execute("DROP FUNCTION IF EXISTS public.td002_request_guard()")
    op.execute("DROP FUNCTION IF EXISTS public.td002_target_guard()")
