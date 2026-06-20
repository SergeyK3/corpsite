"""ADR-043 Phase B2 — personnel lifecycle DDL, stewardship seed, alters.

Revision ID: x6y7z8a9b0c1
Revises: w5x6y7z8a9b0
"""
from __future__ import annotations

from alembic import op

revision = "x6y7z8a9b0c1"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None

_OVERRIDE_STATUSES = (
    "pending_approval",
    "active",
    "rejected",
    "expired",
    "revoked",
    "superseded",
)
_SCOPE_TYPES = ("PERSON", "ASSIGNMENT", "DOCUMENT", "TRAINING", "CERTIFICATE", "CATEGORY")
_OWNER_DOMAINS = ("HR", "QUALITY", "TRAINING_CENTER", "MEDICAL_ADMIN", "SYSTEM")
_HISTORY_EVENT_TYPES = (
    "CREATED",
    "VALUE_CHANGED",
    "APPROVED",
    "REJECTED",
    "RECONFIRMED",
    "MARKED_STALE",
    "EXPIRED",
    "REVOKED",
    "SUPERSEDED",
    "SCOPE_MIGRATED",
)
_PERSONNEL_EVENT_TYPES = (
    "NEW_PERSON",
    "TERMINATED_PERSON",
    "NEW_ASSIGNMENT",
    "CLOSED_ASSIGNMENT",
    "TRANSFER",
    "POSITION_CHANGED",
    "DEPARTMENT_CHANGED",
    "RATE_CHANGED",
    "FIELD_CHANGED",
    "OVERRIDE_APPLIED",
    "OVERRIDE_EXPIRED",
)
_PERSONNEL_EVENT_STATUSES = ("detected", "acknowledged", "enrolled", "ignored", "superseded")
_CREATION_CHANNELS = (
    "review_ui",
    "promotion_materialize",
    "override_registry",
    "backfill",
    "identity_correction",
)
_PERSISTENCE_POLICIES = ("until_incoming_matches", "manual_only_revoke", "until_snapshot_superseded")


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    statuses_sql = _sql_in(_OVERRIDE_STATUSES)
    scope_types_sql = _sql_in(_SCOPE_TYPES)
    owner_domains_sql = _sql_in(_OWNER_DOMAINS)
    history_events_sql = _sql_in(_HISTORY_EVENT_TYPES)
    personnel_events_sql = _sql_in(_PERSONNEL_EVENT_TYPES)
    personnel_statuses_sql = _sql_in(_PERSONNEL_EVENT_STATUSES)
    channels_sql = _sql_in(_CREATION_CHANNELS)
    policies_sql = _sql_in(_PERSISTENCE_POLICIES)

    # ------------------------------------------------------------------
    # 1. hr_source_files
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_source_files (
            source_file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            content_sha256 TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            report_month DATE NOT NULL,
            source_system TEXT NOT NULL DEFAULT 'HR_CONTROL_LIST',
            byte_size BIGINT NOT NULL,
            storage_ref TEXT NOT NULL,
            uploaded_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_hsf_byte_size_nonneg CHECK (byte_size >= 0),
            CONSTRAINT chk_hsf_sha256_nonempty CHECK (length(trim(content_sha256)) > 0),
            CONSTRAINT chk_hsf_filename_nonempty CHECK (length(trim(original_filename)) > 0),
            CONSTRAINT chk_hsf_storage_ref_nonempty CHECK (length(trim(storage_ref)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hsf_report_month
            ON public.hr_source_files (report_month DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hsf_sha256_report_month
            ON public.hr_source_files (content_sha256, report_month, source_system)
        """
    )

    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            ADD COLUMN IF NOT EXISTS source_file_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_hr_import_batches_source_file'
            ) THEN
                ALTER TABLE public.hr_import_batches
                    ADD CONSTRAINT fk_hr_import_batches_source_file
                        FOREIGN KEY (source_file_id)
                        REFERENCES public.hr_source_files (source_file_id)
                        ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_batches_source_file
            ON public.hr_import_batches (source_file_id)
            WHERE source_file_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 2. hr_override_stewardship_rules (+ seed later)
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_override_stewardship_rules (
            rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            field_path_pattern TEXT NOT NULL,
            scope_type TEXT NULL,
            owner_domain TEXT NOT NULL,
            required_tier SMALLINT NOT NULL DEFAULT 1,
            requires_evidence BOOLEAN NOT NULL DEFAULT FALSE,
            requires_second_approval BOOLEAN NOT NULL DEFAULT FALSE,
            persistence_policy_default TEXT NOT NULL DEFAULT 'until_incoming_matches',
            priority SMALLINT NOT NULL DEFAULT 100,
            active_flag BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_hosr_tier CHECK (required_tier IN (0, 1, 2)),
            CONSTRAINT chk_hosr_owner_domain
                CHECK (owner_domain IN ({owner_domains_sql})),
            CONSTRAINT chk_hosr_scope_type
                CHECK (
                    scope_type IS NULL
                    OR scope_type IN ({scope_types_sql})
                ),
            CONSTRAINT chk_hosr_pattern_nonempty
                CHECK (length(trim(field_path_pattern)) > 0),
            CONSTRAINT chk_hosr_persistence_policy
                CHECK (persistence_policy_default IN ({policies_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hosr_pattern_scope_active
            ON public.hr_override_stewardship_rules (
                field_path_pattern,
                COALESCE(scope_type, '')
            )
            WHERE active_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hosr_lookup
            ON public.hr_override_stewardship_rules (active_flag, priority, scope_type)
            WHERE active_flag = TRUE
        """
    )

    # ------------------------------------------------------------------
    # 3. hr_review_overrides
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_review_overrides (
            override_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id BIGINT NULL,
            scope_key TEXT NOT NULL,
            person_key TEXT NULL,
            assignment_key TEXT NULL,
            person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE SET NULL,
            assignment_id BIGINT NULL
                REFERENCES public.person_assignments (assignment_id) ON DELETE SET NULL,
            normalized_record_id BIGINT NULL
                REFERENCES public.hr_import_normalized_records (normalized_record_id)
                ON DELETE SET NULL,
            record_kind TEXT NULL,
            field_path TEXT NOT NULL,
            canonical_value JSONB NULL,
            override_value JSONB NOT NULL,
            tier SMALLINT NOT NULL,
            owner_domain TEXT NOT NULL,
            status TEXT NOT NULL,
            stale_flag BOOLEAN NOT NULL DEFAULT FALSE,
            stale_reason TEXT NULL,
            stale_since TIMESTAMPTZ NULL,
            last_reconfirmed_at TIMESTAMPTZ NULL,
            last_reconfirmed_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            expired_at TIMESTAMPTZ NULL,
            expire_reason TEXT NULL,
            persistence_policy TEXT NOT NULL,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            creation_channel TEXT NOT NULL,
            justification TEXT NULL,
            evidence_url TEXT NULL,
            source_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            source_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            source_normalized_record_id BIGINT NULL
                REFERENCES public.hr_import_normalized_records (normalized_record_id)
                ON DELETE SET NULL,
            source_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            basis_diff JSONB NULL,
            approved_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ NULL,
            approval_comment TEXT NULL,
            rejected_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            rejected_at TIMESTAMPTZ NULL,
            reject_reason TEXT NULL,
            revoked_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            revoked_at TIMESTAMPTZ NULL,
            revoke_reason TEXT NULL,
            supersedes_override_id BIGINT NULL,
            superseded_by_override_id BIGINT NULL,
            superseded_at TIMESTAMPTZ NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,

            CONSTRAINT fk_hro_supersedes_override
                FOREIGN KEY (supersedes_override_id)
                REFERENCES public.hr_review_overrides (override_id)
                ON DELETE SET NULL,
            CONSTRAINT fk_hro_superseded_by_override
                FOREIGN KEY (superseded_by_override_id)
                REFERENCES public.hr_review_overrides (override_id)
                ON DELETE SET NULL,

            CONSTRAINT chk_hro_scope_type
                CHECK (scope_type IN ({scope_types_sql})),
            CONSTRAINT chk_hro_status
                CHECK (status IN ({statuses_sql})),
            CONSTRAINT chk_hro_tier CHECK (tier IN (0, 1, 2)),
            CONSTRAINT chk_hro_owner_domain
                CHECK (owner_domain IN ({owner_domains_sql})),
            CONSTRAINT chk_hro_persistence_policy
                CHECK (persistence_policy IN ({policies_sql})),
            CONSTRAINT chk_hro_creation_channel
                CHECK (creation_channel IN ({channels_sql})),
            CONSTRAINT chk_hro_scope_key_format
                CHECK (scope_key ~ '^(PERSON|ASSIGNMENT|DOCUMENT|TRAINING|CERTIFICATE|CATEGORY):'),
            CONSTRAINT chk_hro_field_path_nonempty
                CHECK (length(trim(field_path)) > 0),
            CONSTRAINT chk_hro_stale_pair
                CHECK (NOT stale_flag OR stale_reason IS NOT NULL),
            CONSTRAINT chk_hro_revoked_pair
                CHECK (
                    (status = 'revoked' AND revoked_at IS NOT NULL)
                    OR (status <> 'revoked')
                ),
            CONSTRAINT chk_hro_superseded_pair
                CHECK (
                    (status = 'superseded' AND superseded_by_override_id IS NOT NULL)
                    OR (status <> 'superseded')
                ),
            CONSTRAINT chk_hro_pending_no_approval_yet
                CHECK (
                    status <> 'pending_approval'
                    OR approved_at IS NULL
                ),
            CONSTRAINT chk_hro_tier2_active_approval
                CHECK (
                    tier <> 2
                    OR status <> 'active'
                    OR (
                        approved_by_user_id IS NOT NULL
                        AND approved_at IS NOT NULL
                        AND approved_by_user_id <> created_by_user_id
                    )
                ),
            CONSTRAINT chk_hro_tier1_justification
                CHECK (
                    tier = 0
                    OR status IN ('expired', 'revoked', 'superseded', 'rejected')
                    OR (
                        justification IS NOT NULL
                        AND length(trim(justification)) >= 10
                    )
                )
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hro_active_scope_field
            ON public.hr_review_overrides (scope_key, field_path)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hro_pending_scope_field
            ON public.hr_review_overrides (scope_key, field_path)
            WHERE status = 'pending_approval'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_person_key
            ON public.hr_review_overrides (person_key)
            WHERE person_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_assignment_key
            ON public.hr_review_overrides (assignment_key)
            WHERE assignment_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_field_path
            ON public.hr_review_overrides (field_path)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_status_tier
            ON public.hr_review_overrides (status, tier, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_owner_domain
            ON public.hr_review_overrides (owner_domain, status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_person_id_active
            ON public.hr_review_overrides (person_id)
            WHERE status IN ('active', 'pending_approval')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_stale
            ON public.hr_review_overrides (stale_flag, stale_since)
            WHERE stale_flag = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hro_supersedes
            ON public.hr_review_overrides (supersedes_override_id)
            WHERE supersedes_override_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 4. hr_review_override_history (append-only)
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_review_override_history (
            history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            override_id BIGINT NOT NULL
                REFERENCES public.hr_review_overrides (override_id) ON DELETE RESTRICT,
            scope_key TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            happened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            from_status TEXT NULL,
            to_status TEXT NULL,
            field_path TEXT NOT NULL,
            old_value JSONB NULL,
            new_value JSONB NULL,
            reason TEXT NULL,
            evidence_url TEXT NULL,
            basis_diff JSONB NULL,
            source_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            source_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,

            CONSTRAINT chk_hroh_event_type
                CHECK (event_type IN ({history_events_sql})),
            CONSTRAINT chk_hroh_scope_key_format
                CHECK (scope_key ~ '^(PERSON|ASSIGNMENT|DOCUMENT|TRAINING|CERTIFICATE|CATEGORY):'),
            CONSTRAINT chk_hroh_field_path_nonempty
                CHECK (length(trim(field_path)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hroh_override_happened
            ON public.hr_review_override_history (override_id, happened_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hroh_scope_replay
            ON public.hr_review_override_history (scope_key, field_path, happened_at ASC, history_id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hroh_event_type
            ON public.hr_review_override_history (event_type, happened_at DESC)
        """
    )

    # Append-only enforced via trigger (RULE DO INSTEAD NOTHING breaks user FK checks).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.prevent_hr_review_override_history_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'hr_review_override_history is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hroh_append_only
            BEFORE UPDATE OR DELETE ON public.hr_review_override_history
            FOR EACH ROW
            EXECUTE FUNCTION public.prevent_hr_review_override_history_mutation();
        """
    )

    # ------------------------------------------------------------------
    # 5. hr_personnel_change_events
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_personnel_change_events (
            personnel_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_event_id BIGINT NULL
                REFERENCES public.hr_change_events (change_event_id) ON DELETE SET NULL,
            previous_snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE SET NULL,
            assignment_id BIGINT NULL
                REFERENCES public.person_assignments (assignment_id) ON DELETE SET NULL,
            person_key TEXT NOT NULL,
            assignment_key TEXT NULL,
            event_type TEXT NOT NULL,
            field_path TEXT NULL,
            old_value JSONB NULL,
            new_value JSONB NULL,
            effective_old_value JSONB NULL,
            effective_new_value JSONB NULL,
            event_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'detected',
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ NULL,
            resolved_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,

            CONSTRAINT chk_hpe_event_type
                CHECK (event_type IN ({personnel_events_sql})),
            CONSTRAINT chk_hpe_status
                CHECK (status IN ({personnel_statuses_sql})),
            CONSTRAINT chk_hpe_person_key_nonempty
                CHECK (length(trim(person_key)) > 0),
            CONSTRAINT chk_hpe_event_hash_len
                CHECK (length(trim(event_hash)) = 64),
            CONSTRAINT chk_hpe_snapshot_pair
                CHECK (snapshot_id <> previous_snapshot_id)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hpe_event_hash
            ON public.hr_personnel_change_events (event_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_snapshot
            ON public.hr_personnel_change_events (snapshot_id, detected_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_snapshot_person_assignment
            ON public.hr_personnel_change_events (snapshot_id, person_key, assignment_key)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_person
            ON public.hr_personnel_change_events (person_id, detected_at DESC)
            WHERE person_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_person_key
            ON public.hr_personnel_change_events (person_key, detected_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_type_status
            ON public.hr_personnel_change_events (event_type, status, detected_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hpe_source_event
            ON public.hr_personnel_change_events (source_event_id)
            WHERE source_event_id IS NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.enrollment_queue
            ADD COLUMN IF NOT EXISTS personnel_event_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_eq_personnel_event'
            ) THEN
                ALTER TABLE public.enrollment_queue
                    ADD CONSTRAINT fk_eq_personnel_event
                        FOREIGN KEY (personnel_event_id)
                        REFERENCES public.hr_personnel_change_events (personnel_event_id)
                        ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_eq_personnel_event
            ON public.enrollment_queue (personnel_event_id)
            WHERE personnel_event_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 6. hr_snapshot_effective_entries
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_snapshot_effective_entries (
            effective_entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            canonical_entry_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            person_key TEXT NULL,
            assignment_key TEXT NULL,
            match_key TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            effective_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            payload_hash TEXT NOT NULL,
            override_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            override_version_hash TEXT NOT NULL,
            compute_version INTEGER NOT NULL DEFAULT 1,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_hsee_scope_type
                CHECK (scope_type IN ('PERSON', 'ASSIGNMENT', 'DOCUMENT', 'TRAINING', 'CERTIFICATE', 'CATEGORY', 'ROSTER')),
            CONSTRAINT chk_hsee_scope_key_nonempty CHECK (length(trim(scope_key)) > 0),
            CONSTRAINT chk_hsee_match_key_nonempty CHECK (length(trim(match_key)) > 0),
            CONSTRAINT chk_hsee_payload_hash_nonempty CHECK (length(trim(payload_hash)) > 0),
            CONSTRAINT chk_hsee_override_version_hash_nonempty
                CHECK (length(trim(override_version_hash)) > 0),
            CONSTRAINT chk_hsee_record_kind
                CHECK (record_kind IN (
                    'roster', 'training', 'certificate', 'category', 'education'
                ))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hsee_snapshot_match_key
            ON public.hr_snapshot_effective_entries (snapshot_id, match_key)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hsee_snapshot_payload_hash
            ON public.hr_snapshot_effective_entries (snapshot_id, payload_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hsee_person_key
            ON public.hr_snapshot_effective_entries (person_key)
            WHERE person_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hsee_computed_at
            ON public.hr_snapshot_effective_entries (snapshot_id, computed_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.hr_source_files IS
            'ADR-043: immutable HR upload provenance.';
        COMMENT ON TABLE public.hr_override_stewardship_rules IS
            'ADR-043: field-path stewardship and tier defaults.';
        COMMENT ON TABLE public.hr_review_overrides IS
            'ADR-043: persistent review overrides (Effective Canonical layer).';
        COMMENT ON TABLE public.hr_review_override_history IS
            'ADR-043: append-only override audit trail.';
        COMMENT ON TABLE public.hr_personnel_change_events IS
            'ADR-043: assignment-centric personnel change journal.';
        COMMENT ON TABLE public.hr_snapshot_effective_entries IS
            'ADR-043: materialized Effective Canonical for active snapshot.';
        """
    )

    # ------------------------------------------------------------------
    # 7. Stewardship seed (idempotent)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO public.hr_override_stewardship_rules (
            field_path_pattern, scope_type, owner_domain, required_tier,
            requires_evidence, requires_second_approval, persistence_policy_default, priority
        )
        SELECT
            v.field_path_pattern,
            v.scope_type,
            v.owner_domain,
            v.required_tier,
            v.requires_evidence,
            v.requires_second_approval,
            v.persistence_policy_default,
            v.priority
        FROM (
            VALUES
                ('identity.iin', 'PERSON', 'HR', 2, TRUE, TRUE, 'manual_only_revoke', 10),
                ('identity.full_name', 'PERSON', 'HR', 2, FALSE, TRUE, 'manual_only_revoke', 11),
                ('identity.birth_date', 'PERSON', 'HR', 2, FALSE, TRUE, 'manual_only_revoke', 12),
                ('roster.%', 'ASSIGNMENT', 'HR', 1, FALSE, FALSE, 'until_incoming_matches', 20),
                ('specialty.%', NULL, 'MEDICAL_ADMIN', 1, FALSE, FALSE, 'until_incoming_matches', 30),
                ('category.%', 'CATEGORY', 'QUALITY', 1, FALSE, FALSE, 'until_incoming_matches', 40),
                ('education.%', 'DOCUMENT', 'HR', 1, FALSE, FALSE, 'until_incoming_matches', 50),
                ('certificate.%', 'CERTIFICATE', 'TRAINING_CENTER', 1, TRUE, FALSE, 'until_incoming_matches', 60),
                ('training.%', 'TRAINING', 'TRAINING_CENTER', 1, FALSE, FALSE, 'until_incoming_matches', 70),
                ('note.%', NULL, 'HR', 0, FALSE, FALSE, 'until_incoming_matches', 900),
                ('display.%', NULL, 'SYSTEM', 0, FALSE, FALSE, 'until_incoming_matches', 910),
                ('%', NULL, 'HR', 0, FALSE, FALSE, 'until_incoming_matches', 1000)
        ) AS v(
            field_path_pattern, scope_type, owner_domain, required_tier,
            requires_evidence, requires_second_approval, persistence_policy_default, priority
        )
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.hr_override_stewardship_rules r
            WHERE r.field_path_pattern = v.field_path_pattern
              AND COALESCE(r.scope_type, '') = COALESCE(v.scope_type, '')
              AND r.active_flag = TRUE
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.enrollment_queue
            DROP CONSTRAINT IF EXISTS fk_eq_personnel_event
        """
    )
    op.execute(
        """
        ALTER TABLE public.enrollment_queue
            DROP COLUMN IF EXISTS personnel_event_id
        """
    )

    op.execute("DROP TABLE IF EXISTS public.hr_snapshot_effective_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_personnel_change_events CASCADE")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_hroh_append_only ON public.hr_review_override_history"
    )
    op.execute("DROP FUNCTION IF EXISTS public.prevent_hr_review_override_history_mutation()")
    op.execute("DROP TABLE IF EXISTS public.hr_review_override_history CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_review_overrides CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_override_stewardship_rules CASCADE")

    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            DROP CONSTRAINT IF EXISTS fk_hr_import_batches_source_file
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            DROP COLUMN IF EXISTS source_file_id
        """
    )
    op.execute("DROP TABLE IF EXISTS public.hr_source_files CASCADE")
