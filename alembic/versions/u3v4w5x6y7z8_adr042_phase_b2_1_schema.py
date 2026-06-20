"""ADR-042 Phase B2.1 — persons, assignments, enrollment, access, audit DDL.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
"""
from __future__ import annotations

from alembic import op

revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None

_SAL_EVENT_TYPES = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "LOGOUT",
    "PASSWORD_RESET_REQUESTED",
    "PASSWORD_RESET_COMPLETED",
    "PASSWORD_CHANGED",
    "TEMP_PASSWORD_ISSUED",
    "USER_LOCKED",
    "USER_UNLOCKED",
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "ACCESS_CHANGED",
    "ENROLLMENT_APPROVED",
    "ENROLLMENT_REJECTED",
    "ENROLLMENT_COMPLETED",
    "USER_BLOCKED",
    "USER_UNBLOCKED",
)


def upgrade() -> None:
    sal_types_sql = ", ".join(f"'{t}'" for t in _SAL_EVENT_TYPES)

    # ------------------------------------------------------------------
    # 1. persons
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.persons (
            person_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            iin TEXT NULL,
            full_name TEXT NOT NULL,
            last_name TEXT NULL,
            first_name TEXT NULL,
            middle_name TEXT NULL,
            birth_date DATE NULL,
            match_key TEXT NOT NULL,
            person_status TEXT NOT NULL DEFAULT 'active',
            merged_into_person_id BIGINT NULL,
            source TEXT NOT NULL DEFAULT 'canonical',
            canonical_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            canonical_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_persons_merged_into
                FOREIGN KEY (merged_into_person_id)
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            CONSTRAINT chk_persons_status
                CHECK (person_status IN ('active', 'inactive', 'merged')),
            CONSTRAINT chk_persons_source
                CHECK (source IN ('canonical', 'manual', 'migration', 'enrollment')),
            CONSTRAINT chk_persons_match_key_nonempty
                CHECK (length(trim(match_key)) > 0),
            CONSTRAINT chk_persons_full_name_nonempty
                CHECK (length(trim(full_name)) > 0),
            CONSTRAINT chk_persons_iin_format
                CHECK (iin IS NULL OR iin ~ '^[0-9]{12}$'),
            CONSTRAINT chk_persons_merged_target
                CHECK (
                    (person_status = 'merged' AND merged_into_person_id IS NOT NULL)
                    OR (person_status <> 'merged' AND merged_into_person_id IS NULL)
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_persons_match_key_active
            ON public.persons (match_key)
            WHERE person_status IN ('active', 'inactive')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_persons_iin_active
            ON public.persons (iin)
            WHERE iin IS NOT NULL AND person_status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_iin
            ON public.persons (iin)
            WHERE iin IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_full_name
            ON public.persons (lower(full_name))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_birth_date
            ON public.persons (birth_date)
            WHERE birth_date IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_canonical_entry
            ON public.persons (canonical_entry_id)
            WHERE canonical_entry_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_status
            ON public.persons (person_status)
        """
    )

    # ------------------------------------------------------------------
    # 2. person_assignments
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.person_assignments (
            assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            position_id BIGINT NOT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            department_id BIGINT NULL
                REFERENCES public.departments (department_id) ON DELETE SET NULL,
            employment_type TEXT NOT NULL DEFAULT 'primary',
            rate NUMERIC(4,2) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NULL,
            active_flag BOOLEAN NOT NULL DEFAULT FALSE,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            assignment_key TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'canonical',
            canonical_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            canonical_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_pa_employment_type
                CHECK (employment_type IN (
                    'primary', 'part_time', 'internal_combo', 'external', 'locum'
                )),
            CONSTRAINT chk_pa_rate_range
                CHECK (rate > 0 AND rate <= 1.5),
            CONSTRAINT chk_pa_dates
                CHECK (end_date IS NULL OR end_date >= start_date),
            CONSTRAINT chk_pa_source
                CHECK (source IN (
                    'canonical', 'manual', 'migration', 'enrollment',
                    'correction', 'transfer'
                )),
            CONSTRAINT chk_pa_lifecycle
                CHECK (lifecycle_status IN ('active', 'closed', 'voided')),
            CONSTRAINT chk_pa_assignment_key_nonempty
                CHECK (length(trim(assignment_key)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pa_canonical_entry
            ON public.person_assignments (canonical_entry_id)
            WHERE canonical_entry_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_person_id
            ON public.person_assignments (person_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_person_active
            ON public.person_assignments (person_id, active_flag)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_org_unit
            ON public.person_assignments (org_unit_id, active_flag)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_position
            ON public.person_assignments (position_id)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_canonical_entry
            ON public.person_assignments (canonical_entry_id)
            WHERE canonical_entry_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pa_dates
            ON public.person_assignments (person_id, start_date DESC, end_date DESC NULLS FIRST)
        """
    )

    # ------------------------------------------------------------------
    # 3. employees extension (nullable person_id on first step)
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS person_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_employees_person'
            ) THEN
                ALTER TABLE public.employees
                    ADD CONSTRAINT fk_employees_person
                        FOREIGN KEY (person_id)
                        REFERENCES public.persons (person_id)
                        ON DELETE RESTRICT;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS operational_status TEXT NOT NULL DEFAULT 'active'
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS enrolled_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS enrolled_by_user_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_employees_enrolled_by'
            ) THEN
                ALTER TABLE public.employees
                    ADD CONSTRAINT fk_employees_enrolled_by
                        FOREIGN KEY (enrolled_by_user_id)
                        REFERENCES public.users (user_id)
                        ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS enrollment_source TEXT NOT NULL DEFAULT 'migration'
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_employees_operational_status'
            ) THEN
                ALTER TABLE public.employees
                    ADD CONSTRAINT chk_employees_operational_status
                        CHECK (operational_status IN (
                            'draft', 'active', 'suspended', 'terminated'
                        ));
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_employees_enrollment_source'
            ) THEN
                ALTER TABLE public.employees
                    ADD CONSTRAINT chk_employees_enrollment_source
                        CHECK (enrollment_source IN (
                            'enrollment', 'manual_emergency', 'migration'
                        ));
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employees_person_id
            ON public.employees (person_id)
            WHERE person_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_person_active
            ON public.employees (person_id)
            WHERE person_id IS NOT NULL
              AND operational_status IN ('draft', 'active', 'suspended')
        """
    )

    # ------------------------------------------------------------------
    # 4. enrollment_queue (before employee_assignment_links FK)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.enrollment_queue (
            queue_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            assignment_id BIGINT NULL
                REFERENCES public.person_assignments (assignment_id) ON DELETE RESTRICT,
            change_event_id BIGINT NULL
                REFERENCES public.hr_change_events (change_event_id) ON DELETE SET NULL,
            canonical_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            queue_status TEXT NOT NULL DEFAULT 'PENDING',
            reason TEXT NOT NULL,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ NULL,
            resolved_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            decision_comment TEXT NULL,
            superseded_by_queue_id BIGINT NULL,
            idempotency_key TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_eq_superseded_by
                FOREIGN KEY (superseded_by_queue_id)
                REFERENCES public.enrollment_queue (queue_id) ON DELETE SET NULL,
            CONSTRAINT chk_eq_status
                CHECK (queue_status IN (
                    'PENDING', 'APPROVED', 'REJECTED', 'SUPERSEDED', 'ENROLLED'
                )),
            CONSTRAINT chk_eq_reason
                CHECK (reason IN (
                    'NEW_ASSIGNMENT', 'CHANGED_ASSIGNMENT', 'REMOVED_ASSIGNMENT',
                    'RE_ENROLL', 'MANUAL_REQUEST'
                )),
            CONSTRAINT chk_eq_target_present
                CHECK (
                    person_id IS NOT NULL
                    OR assignment_id IS NOT NULL
                    OR canonical_entry_id IS NOT NULL
                ),
            CONSTRAINT chk_eq_resolved_pair
                CHECK (
                    (queue_status IN ('PENDING', 'APPROVED') AND resolved_at IS NULL)
                    OR (queue_status IN ('REJECTED', 'ENROLLED') AND resolved_at IS NOT NULL)
                    OR (queue_status = 'SUPERSEDED')
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_eq_idempotency_active
            ON public.enrollment_queue (idempotency_key)
            WHERE queue_status IN ('PENDING', 'APPROVED')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eq_status_detected
            ON public.enrollment_queue (queue_status, detected_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eq_person
            ON public.enrollment_queue (person_id)
            WHERE person_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eq_assignment
            ON public.enrollment_queue (assignment_id)
            WHERE assignment_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eq_change_event
            ON public.enrollment_queue (change_event_id)
            WHERE change_event_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 5. enrollment_history
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.enrollment_history (
            history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            queue_id BIGINT NOT NULL
                REFERENCES public.enrollment_queue (queue_id) ON DELETE RESTRICT,
            event_type TEXT NOT NULL,
            event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE SET NULL,
            assignment_id BIGINT NULL
                REFERENCES public.person_assignments (assignment_id) ON DELETE SET NULL,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            link_id BIGINT NULL,
            comment TEXT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT chk_eh_event_type
                CHECK (event_type IN (
                    'DETECTED', 'APPROVED', 'REJECTED', 'ENROLLED',
                    'UNENROLLED', 'RE_ENROLLED', 'SUPERSEDED'
                ))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eh_queue_id
            ON public.enrollment_history (queue_id, event_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eh_person
            ON public.enrollment_history (person_id, event_at DESC)
            WHERE person_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eh_employee
            ON public.enrollment_history (employee_id, event_at DESC)
            WHERE employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eh_event_type
            ON public.enrollment_history (event_type, event_at DESC)
        """
    )

    # ------------------------------------------------------------------
    # 6. employee_assignment_links
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_assignment_links (
            link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            assignment_id BIGINT NOT NULL
                REFERENCES public.person_assignments (assignment_id) ON DELETE RESTRICT,
            link_status TEXT NOT NULL DEFAULT 'active',
            enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            enrolled_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            unenrolled_at TIMESTAMPTZ NULL,
            unenrolled_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            enrollment_queue_id BIGINT NULL
                REFERENCES public.enrollment_queue (queue_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_eal_status
                CHECK (link_status IN ('active', 'unenrolled', 'superseded')),
            CONSTRAINT chk_eal_unenroll_pair
                CHECK (
                    (link_status = 'active' AND unenrolled_at IS NULL)
                    OR (
                        link_status IN ('unenrolled', 'superseded')
                        AND unenrolled_at IS NOT NULL
                    )
                ),
            CONSTRAINT uq_eal_employee_assignment
                UNIQUE (employee_id, assignment_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eal_employee_active
            ON public.employee_assignment_links (employee_id)
            WHERE link_status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eal_assignment_active
            ON public.employee_assignment_links (assignment_id)
            WHERE link_status = 'active'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_eal_one_active_per_assignment
            ON public.employee_assignment_links (assignment_id)
            WHERE link_status = 'active'
        """
    )

    # FK enrollment_history.link_id → employee_assignment_links (deferred)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_eh_link'
            ) THEN
                ALTER TABLE public.enrollment_history
                    ADD CONSTRAINT fk_eh_link
                        FOREIGN KEY (link_id)
                        REFERENCES public.employee_assignment_links (link_id)
                        ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # 7. access_roles + B2.2 seed
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.access_roles (
            access_role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NULL,
            access_level TEXT NOT NULL,
            level_rank SMALLINT NOT NULL,
            is_system BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            default_resource_key TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_access_roles_code UNIQUE (code),
            CONSTRAINT chk_access_roles_level
                CHECK (access_level IN ('NONE', 'OBSERVER', 'MANAGER', 'ADMIN')),
            CONSTRAINT chk_access_roles_rank
                CHECK (
                    (access_level = 'NONE'     AND level_rank = 0)
                    OR (access_level = 'OBSERVER' AND level_rank = 10)
                    OR (access_level = 'MANAGER'  AND level_rank = 20)
                    OR (access_level = 'ADMIN'    AND level_rank = 30)
                )
        )
        """
    )

    op.execute(
        """
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        )
        VALUES
            (
                'ACCESS_NONE',
                'No Access',
                'Explicit no-access level for deny overrides',
                'NONE', 0, TRUE
            ),
            (
                'ACCESS_OBSERVER',
                'Observer',
                'Read-only access',
                'OBSERVER', 10, TRUE
            ),
            (
                'ACCESS_MANAGER',
                'Manager',
                'Operational actions within scope',
                'MANAGER', 20, TRUE
            ),
            (
                'ACCESS_ADMIN',
                'Administrator',
                'Full administrative access within scope',
                'ADMIN', 30, TRUE
            ),
            (
                'SYSADMIN_CABINET',
                'System Administrator Cabinet',
                'Full admin cabinet access',
                'ADMIN', 30, TRUE
            ),
            (
                'HR_ENROLLMENT_MANAGER',
                'HR Enrollment Manager',
                'Approve and apply enrollment decisions',
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

    # ------------------------------------------------------------------
    # 8. access_grants
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.access_grants (
            grant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            access_role_id BIGINT NOT NULL
                REFERENCES public.access_roles (access_role_id) ON DELETE RESTRICT,
            target_type TEXT NOT NULL,
            target_id BIGINT NOT NULL,
            resource_key TEXT NOT NULL DEFAULT '*',
            scope_type TEXT NOT NULL DEFAULT 'GLOBAL',
            scope_id BIGINT NULL,
            include_subtree BOOLEAN NOT NULL DEFAULT FALSE,
            starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ends_at TIMESTAMPTZ NULL,
            active_flag BOOLEAN NOT NULL DEFAULT TRUE,
            granted_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            reason TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            revoked_at TIMESTAMPTZ NULL,
            revoked_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            CONSTRAINT chk_ag_target_type
                CHECK (target_type IN (
                    'PERSON', 'ASSIGNMENT', 'POSITION', 'ORG_UNIT', 'EMPLOYEE', 'USER'
                )),
            CONSTRAINT chk_ag_scope_type
                CHECK (scope_type IN ('GLOBAL', 'ORG_UNIT', 'SELF')),
            CONSTRAINT chk_ag_scope_pair
                CHECK (
                    (scope_type = 'ORG_UNIT' AND scope_id IS NOT NULL)
                    OR (scope_type IN ('GLOBAL', 'SELF') AND scope_id IS NULL)
                ),
            CONSTRAINT chk_ag_dates
                CHECK (ends_at IS NULL OR ends_at > starts_at),
            CONSTRAINT chk_ag_revoked_pair
                CHECK (
                    (active_flag = TRUE AND revoked_at IS NULL)
                    OR (active_flag = FALSE AND revoked_at IS NOT NULL)
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ag_target
            ON public.access_grants (target_type, target_id)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ag_role
            ON public.access_grants (access_role_id)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ag_resource
            ON public.access_grants (resource_key)
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ag_scope
            ON public.access_grants (scope_type, scope_id)
            WHERE active_flag = TRUE AND scope_type = 'ORG_UNIT'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ag_validity
            ON public.access_grants (starts_at, ends_at)
            WHERE active_flag = TRUE
        """
    )

    # ------------------------------------------------------------------
    # 9. security_audit_log
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.security_audit_log (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_type TEXT NOT NULL,
            happened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            target_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            target_person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE SET NULL,
            target_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            ip_address INET NULL,
            user_agent TEXT NULL,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            failure_reason TEXT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            request_id TEXT NULL,
            CONSTRAINT chk_sal_event_type
                CHECK (event_type IN ({sal_types_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_happened_at
            ON public.security_audit_log (happened_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_event_type
            ON public.security_audit_log (event_type, happened_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_actor
            ON public.security_audit_log (actor_user_id, happened_at DESC)
            WHERE actor_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_target_user
            ON public.security_audit_log (target_user_id, happened_at DESC)
            WHERE target_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sal_target_person
            ON public.security_audit_log (target_person_id, happened_at DESC)
            WHERE target_person_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 10. users extension
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS temp_password_expires_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS locked_reason TEXT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS last_failed_login_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_failed_login_count'
            ) THEN
                ALTER TABLE public.users
                    ADD CONSTRAINT chk_users_failed_login_count
                        CHECK (failed_login_count >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_locked_reason'
            ) THEN
                ALTER TABLE public.users
                    ADD CONSTRAINT chk_users_locked_reason
                        CHECK (
                            locked_reason IS NULL
                            OR locked_reason IN (
                                'brute_force', 'admin', 'policy', 'security'
                            )
                        );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_lock_pair'
            ) THEN
                ALTER TABLE public.users
                    ADD CONSTRAINT chk_users_lock_pair
                        CHECK (
                            (
                                locked_at IS NULL
                                AND locked_until IS NULL
                                AND locked_reason IS NULL
                            )
                            OR (locked_at IS NOT NULL)
                        );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_users_locked
            ON public.users (locked_at)
            WHERE locked_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_users_must_change
            ON public.users (must_change_password)
            WHERE must_change_password = TRUE
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.persons IS
            'ADR-042: canonical person identity anchor.';
        COMMENT ON TABLE public.person_assignments IS
            'ADR-042: personnel assignment (enrollment unit).';
        COMMENT ON TABLE public.employee_assignment_links IS
            'ADR-042: operational enrollment scope per assignment.';
        COMMENT ON TABLE public.enrollment_queue IS
            'ADR-042: enrollment decision queue.';
        COMMENT ON TABLE public.enrollment_history IS
            'ADR-042: append-only enrollment event history.';
        COMMENT ON TABLE public.access_roles IS
            'ADR-042: access level roles (orthogonal to task roles).';
        COMMENT ON TABLE public.access_grants IS
            'ADR-042: access role grants on targets.';
        COMMENT ON TABLE public.security_audit_log IS
            'ADR-042: security and admin audit log.';
        """
    )


def downgrade() -> None:
    # users extension
    op.execute("DROP INDEX IF EXISTS public.ix_users_must_change")
    op.execute("DROP INDEX IF EXISTS public.ix_users_locked")
    op.execute(
        """
        ALTER TABLE public.users
            DROP CONSTRAINT IF EXISTS chk_users_lock_pair
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            DROP CONSTRAINT IF EXISTS chk_users_locked_reason
        """
    )
    op.execute(
        """
        ALTER TABLE public.users
            DROP CONSTRAINT IF EXISTS chk_users_failed_login_count
        """
    )
    for col in (
        "token_version",
        "last_failed_login_at",
        "last_login_at",
        "locked_reason",
        "locked_until",
        "locked_at",
        "failed_login_count",
        "temp_password_expires_at",
        "password_changed_at",
        "must_change_password",
    ):
        op.execute(f"ALTER TABLE public.users DROP COLUMN IF EXISTS {col}")

    # security_audit_log
    op.execute("DROP TABLE IF EXISTS public.security_audit_log CASCADE")

    # access_grants, access_roles
    op.execute("DROP TABLE IF EXISTS public.access_grants CASCADE")
    op.execute("DROP TABLE IF EXISTS public.access_roles CASCADE")

    # enrollment + links (order matters)
    op.execute(
        """
        ALTER TABLE public.enrollment_history
            DROP CONSTRAINT IF EXISTS fk_eh_link
        """
    )
    op.execute("DROP TABLE IF EXISTS public.employee_assignment_links CASCADE")
    op.execute("DROP TABLE IF EXISTS public.enrollment_history CASCADE")
    op.execute("DROP TABLE IF EXISTS public.enrollment_queue CASCADE")

    # employees extension
    op.execute("DROP INDEX IF EXISTS public.uq_employees_person_active")
    op.execute("DROP INDEX IF EXISTS public.ix_employees_person_id")
    op.execute(
        """
        ALTER TABLE public.employees
            DROP CONSTRAINT IF EXISTS chk_employees_enrollment_source
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            DROP CONSTRAINT IF EXISTS chk_employees_operational_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            DROP CONSTRAINT IF EXISTS fk_employees_enrolled_by
        """
    )
    op.execute(
        """
        ALTER TABLE public.employees
            DROP CONSTRAINT IF EXISTS fk_employees_person
        """
    )
    for col in (
        "updated_at",
        "enrollment_source",
        "enrolled_by_user_id",
        "enrolled_at",
        "operational_status",
        "person_id",
    ):
        op.execute(f"ALTER TABLE public.employees DROP COLUMN IF EXISTS {col}")

    # person_assignments, persons
    op.execute("DROP TABLE IF EXISTS public.person_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS public.persons CASCADE")
