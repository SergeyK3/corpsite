"""WP-VER-002 — personnel verification foundation (ADR-060).

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
"""
from __future__ import annotations

from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None

_CONTROL_POINTS = ("employment_episode", "medical_category")
_POLICY_STATUSES = ("draft", "active", "inactive")
_TASK_STATUSES = ("pending", "completed", "rejected", "cancelled")
_ATTESTATION_DECISIONS = ("verified", "rejected")


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    control_points_sql = _sql_tuple(_CONTROL_POINTS)
    policy_statuses_sql = _sql_tuple(_POLICY_STATUSES)
    task_statuses_sql = _sql_tuple(_TASK_STATUSES)
    attestation_decisions_sql = _sql_tuple(_ATTESTATION_DECISIONS)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.verification_policies (
            policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            control_point TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            effective_from DATE NOT NULL,
            effective_to DATE NULL,
            decision_basis TEXT NOT NULL,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            published_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            published_at TIMESTAMPTZ NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_vp_control_point
                CHECK (control_point IN ({control_points_sql})),
            CONSTRAINT chk_vp_policy_version_positive
                CHECK (policy_version > 0),
            CONSTRAINT chk_vp_status
                CHECK (status IN ({policy_statuses_sql})),
            CONSTRAINT chk_vp_decision_basis_nonempty
                CHECK (length(btrim(decision_basis)) > 0),
            CONSTRAINT chk_vp_effective_dates
                CHECK (effective_to IS NULL OR effective_to >= effective_from),
            CONSTRAINT chk_vp_publish_consistency
                CHECK (
                    (
                        status = 'draft'
                        AND published_at IS NULL
                        AND published_by_user_id IS NULL
                    )
                    OR (
                        status IN ('active', 'inactive')
                        AND published_at IS NOT NULL
                        AND published_by_user_id IS NOT NULL
                    )
                ),
            CONSTRAINT uq_vp_control_point_version
                UNIQUE (control_point, policy_version)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_vp_one_active_per_control_point
            ON public.verification_policies (control_point)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vp_status_effective
            ON public.verification_policies (status, effective_from, effective_to)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.verification_tasks (
            task_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            control_point TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id BIGINT NOT NULL,
            object_version_id BIGINT NOT NULL,
            policy_id BIGINT NOT NULL
                REFERENCES public.verification_policies (policy_id) ON DELETE RESTRICT,
            policy_version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ NULL,

            CONSTRAINT chk_vt_control_point
                CHECK (control_point IN ({control_points_sql})),
            CONSTRAINT chk_vt_object_type_nonempty
                CHECK (length(btrim(object_type)) > 0),
            CONSTRAINT chk_vt_policy_version_positive
                CHECK (policy_version > 0),
            CONSTRAINT chk_vt_status
                CHECK (status IN ({task_statuses_sql})),
            CONSTRAINT chk_vt_closed_consistency
                CHECK (
                    (
                        status = 'pending'
                        AND closed_at IS NULL
                    )
                    OR (
                        status IN ('completed', 'rejected', 'cancelled')
                        AND closed_at IS NOT NULL
                    )
                )
        )
        """
    )
    # Soft polymorphic ref: unique pending work item per typed revision + policy.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_vt_one_pending_per_version_policy
            ON public.verification_tasks (object_type, object_version_id, policy_id)
            WHERE status = 'pending'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vt_person_status
            ON public.verification_tasks (person_id, status, control_point)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vt_object_version
            ON public.verification_tasks (object_type, object_id, object_version_id)
        """
    )

    # Polymorphic task→PPR integrity (no hard FK: future control points share columns).
    # WP-VER-002 foundation identity for employment_episode (until WP-VER-003):
    #   object_type = person_external_employment
    #   object_version_id = person_external_employment.employment_id
    #   object_id = object_version_id
    # Physical lineage and related verified/pending revision coexistence are WP-VER-003.
    # Same-person existence of a different employment_id is NOT treated as lineage proof.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_verification_task_ppr_ref()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            version_person_id BIGINT;
            version_lifecycle TEXT;
        BEGIN
            IF NEW.control_point = 'medical_category' THEN
                RAISE EXCEPTION
                    'verification_tasks: control_point medical_category has no typed canonical home yet';
            END IF;

            IF NEW.control_point = 'employment_episode'
               OR NEW.object_type = 'person_external_employment' THEN
                IF NEW.control_point IS DISTINCT FROM 'employment_episode'
                   OR NEW.object_type IS DISTINCT FROM 'person_external_employment' THEN
                    RAISE EXCEPTION
                        'verification_tasks: employment_episode requires object_type=person_external_employment';
                END IF;

                IF NEW.object_id IS DISTINCT FROM NEW.object_version_id THEN
                    RAISE EXCEPTION
                        'verification_tasks: foundation requires object_id = object_version_id '
                        '(got object_id=%, object_version_id=%); physical lineage arrives in WP-VER-003',
                        NEW.object_id, NEW.object_version_id;
                END IF;

                SELECT person_id, lifecycle_status
                INTO version_person_id, version_lifecycle
                FROM public.person_external_employment
                WHERE employment_id = NEW.object_version_id;

                IF version_person_id IS NULL THEN
                    RAISE EXCEPTION
                        'verification_tasks: orphan object_version_id=% for person_external_employment',
                        NEW.object_version_id;
                END IF;

                IF version_person_id IS DISTINCT FROM NEW.person_id THEN
                    RAISE EXCEPTION
                        'verification_tasks: person_id=% does not match employment person_id=% for object_version_id=%',
                        NEW.person_id, version_person_id, NEW.object_version_id;
                END IF;

                IF version_lifecycle IS DISTINCT FROM 'active' THEN
                    RAISE EXCEPTION
                        'verification_tasks: employment object_version_id=% must be lifecycle_status=active (got %)',
                        NEW.object_version_id, version_lifecycle;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_verification_task_ppr_ref
            ON public.verification_tasks
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_verification_task_ppr_ref
            BEFORE INSERT OR UPDATE OF
                person_id, control_point, object_type, object_id, object_version_id
            ON public.verification_tasks
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_verification_task_ppr_ref()
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.verification_attestations (
            attestation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            task_id BIGINT NOT NULL
                REFERENCES public.verification_tasks (task_id) ON DELETE RESTRICT,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            control_point TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id BIGINT NOT NULL,
            object_version_id BIGINT NOT NULL,
            policy_id BIGINT NOT NULL
                REFERENCES public.verification_policies (policy_id) ON DELETE RESTRICT,
            policy_version INTEGER NOT NULL,
            decision TEXT NOT NULL,
            verifier_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            verifier_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            decided_at TIMESTAMPTZ NOT NULL,
            comment TEXT NULL,
            evidence_ref TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_va_control_point
                CHECK (control_point IN ({control_points_sql})),
            CONSTRAINT chk_va_object_type_nonempty
                CHECK (length(btrim(object_type)) > 0),
            CONSTRAINT chk_va_policy_version_positive
                CHECK (policy_version > 0),
            CONSTRAINT chk_va_decision
                CHECK (decision IN ({attestation_decisions_sql})),
            CONSTRAINT uq_va_task_id
                UNIQUE (task_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_va_person_decided
            ON public.verification_attestations (person_id, decided_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_va_object_version
            ON public.verification_attestations (object_type, object_id, object_version_id)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.verification_attestations_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'verification_attestations are immutable: UPDATE/DELETE are forbidden';
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_verification_attestations_immutable
            ON public.verification_attestations
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_verification_attestations_immutable
            BEFORE UPDATE OR DELETE ON public.verification_attestations
            FOR EACH ROW
            EXECUTE FUNCTION public.verification_attestations_immutable()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_verification_attestations_immutable
            ON public.verification_attestations
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.verification_attestations_immutable()")
    op.execute("DROP TABLE IF EXISTS public.verification_attestations")
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_verification_task_ppr_ref
            ON public.verification_tasks
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.enforce_verification_task_ppr_ref()")
    op.execute("DROP TABLE IF EXISTS public.verification_tasks")
    op.execute("DROP INDEX IF EXISTS public.uq_vp_one_active_per_control_point")
    op.execute("DROP TABLE IF EXISTS public.verification_policies")
