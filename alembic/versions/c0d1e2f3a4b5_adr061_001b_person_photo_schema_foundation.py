"""WP-ADR061-001B: canonical person photo schema foundation (ADR-061 rev.3).

Revision ID: c0d1e2f3a4b5
Revises: a9b0c1d2e3f4
"""
from __future__ import annotations

from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

_SOURCE_KINDS = ("intake", "manual_upload")
_CANONICALIZATION_MODES = ("transfer", "hire_apply", "backfill")
_BLOCKER_CODES = ("INTAKE_PHOTO_UNAVAILABLE", "PHOTO_CANONICALIZATION_FAILED")


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    source_kinds_sql = _sql_tuple(_SOURCE_KINDS)
    canonicalization_modes_sql = _sql_tuple(_CANONICALIZATION_MODES)
    blocker_codes_sql = _sql_tuple(_BLOCKER_CODES)

    op.execute(
        """
        CREATE TABLE public.person_photos (
            person_photo_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,

            file_id TEXT NOT NULL,
            storage_rel_path TEXT NOT NULL,

            mime_type TEXT NOT NULL,
            byte_size BIGINT NOT NULL,
            checksum_sha256 CHAR(64) NOT NULL,

            is_active BOOLEAN NOT NULL,
            superseded_at TIMESTAMPTZ NULL,

            uploaded_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_person_photos_id_person
                UNIQUE (person_photo_id, person_id),
            CONSTRAINT uq_person_photos_storage_rel_path
                UNIQUE (storage_rel_path),

            CONSTRAINT chk_person_photos_file_id_hex
                CHECK (file_id ~ '^[a-f0-9]{32}$'),
            CONSTRAINT chk_person_photos_mime_jpeg
                CHECK (mime_type = 'image/jpeg'),
            CONSTRAINT chk_person_photos_byte_size
                CHECK (byte_size > 0 AND byte_size <= 512000),
            CONSTRAINT chk_person_photos_sha256
                CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$'),
            CONSTRAINT chk_person_photos_two_state_lifecycle
                CHECK (
                    (is_active = TRUE AND superseded_at IS NULL)
                    OR (is_active = FALSE AND superseded_at IS NOT NULL)
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_person_photos_one_active
            ON public.person_photos (person_id)
            WHERE is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX ix_person_photos_person_created
            ON public.person_photos (person_id, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.trg_person_photos_guard_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'person_photos rows are not deletable';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF NEW.person_photo_id IS DISTINCT FROM OLD.person_photo_id
                OR NEW.person_id IS DISTINCT FROM OLD.person_id
                OR NEW.file_id IS DISTINCT FROM OLD.file_id
                OR NEW.storage_rel_path IS DISTINCT FROM OLD.storage_rel_path
                OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
                OR NEW.byte_size IS DISTINCT FROM OLD.byte_size
                OR NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.uploaded_by_user_id IS DISTINCT FROM OLD.uploaded_by_user_id THEN
                    RAISE EXCEPTION 'person_photos immutable columns cannot change';
                END IF;

                IF OLD.superseded_at IS NOT NULL AND NEW.superseded_at IS DISTINCT FROM OLD.superseded_at THEN
                    RAISE EXCEPTION 'superseded_at is write-once';
                END IF;
                IF OLD.superseded_at IS NOT NULL AND NEW.superseded_at IS NULL THEN
                    RAISE EXCEPTION 'cannot clear superseded_at';
                END IF;

                IF OLD.superseded_at IS NOT NULL THEN
                    IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
                        RAISE EXCEPTION 'superseded person_photos row is terminal';
                    END IF;
                    RETURN NEW;
                END IF;

                IF OLD.is_active = FALSE AND NEW.is_active = TRUE THEN
                    RAISE EXCEPTION 'cannot reactivate person_photos row';
                END IF;

                IF OLD.is_active = TRUE AND NEW.is_active = FALSE THEN
                    IF NEW.superseded_at IS NULL THEN
                        RAISE EXCEPTION 'deactivating person_photos requires superseded_at';
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_person_photos_guard_mutation
            BEFORE UPDATE OR DELETE ON public.person_photos
            FOR EACH ROW
            EXECUTE FUNCTION public.trg_person_photos_guard_mutation()
        """
    )

    op.execute(
        f"""
        CREATE TABLE public.person_photo_sources (
            person_photo_source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            person_photo_id BIGINT NOT NULL,
            person_id BIGINT NOT NULL,

            source_kind TEXT NOT NULL
                CHECK (source_kind IN ({source_kinds_sql})),
            canonicalization_mode TEXT NOT NULL
                CHECK (canonicalization_mode IN ({canonicalization_modes_sql})),

            source_application_id BIGINT NULL,
            source_intake_photo_file_id TEXT NULL,

            command_id TEXT NOT NULL,
            correlation_id TEXT NULL,

            application_status_snapshot TEXT NULL,
            canonicalized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            canonicalized_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,

            CONSTRAINT fk_person_photo_sources_photo_person
                FOREIGN KEY (person_photo_id, person_id)
                REFERENCES public.person_photos (person_photo_id, person_id)
                ON DELETE RESTRICT,

            CONSTRAINT uq_person_photo_sources_command_id
                UNIQUE (command_id),

            CONSTRAINT chk_pps_intake_file_id_format
                CHECK (
                    source_intake_photo_file_id IS NULL
                    OR source_intake_photo_file_id ~ '^[a-f0-9]{{32}}$'
                ),
            CONSTRAINT chk_pps_command_id_nonempty
                CHECK (length(btrim(command_id)) > 0),
            CONSTRAINT chk_pps_intake_requires_app_and_file
                CHECK (
                    source_kind <> 'intake'
                    OR (
                        source_application_id IS NOT NULL
                        AND source_intake_photo_file_id IS NOT NULL
                    )
                ),
            CONSTRAINT chk_pps_manual_requires_null_intake_refs
                CHECK (
                    source_kind <> 'manual_upload'
                    OR (
                        source_application_id IS NULL
                        AND source_intake_photo_file_id IS NULL
                    )
                ),
            CONSTRAINT chk_pps_manual_mode_not_hire_apply
                CHECK (
                    source_kind <> 'manual_upload'
                    OR canonicalization_mode <> 'hire_apply'
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_person_photo_sources_intake_material
            ON public.person_photo_sources (source_application_id, source_intake_photo_file_id)
            WHERE source_kind = 'intake'
        """
    )
    op.execute(
        """
        CREATE INDEX ix_person_photo_sources_person
            ON public.person_photo_sources (person_id, canonicalized_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_person_photo_sources_photo
            ON public.person_photo_sources (person_photo_id)
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.person_photo_sources_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'person_photo_sources are append-only: UPDATE/DELETE are forbidden';
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_person_photo_sources_append_only
            BEFORE UPDATE OR DELETE ON public.person_photo_sources
            FOR EACH ROW
            EXECUTE FUNCTION public.person_photo_sources_append_only()
        """
    )

    op.execute(
        f"""
        CREATE TABLE public.personnel_application_blockers (
            blocker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL
                REFERENCES public.personnel_applications (application_id) ON DELETE CASCADE,
            blocker_code TEXT NOT NULL,
            detail_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ NULL,
            resolved_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,

            CONSTRAINT chk_pab_blocker_code
                CHECK (blocker_code IN ({blocker_codes_sql})),
            CONSTRAINT chk_pab_resolved_consistency
                CHECK (
                    (
                        resolved_at IS NULL
                        AND resolved_by_user_id IS NULL
                    )
                    OR (
                        resolved_at IS NOT NULL
                        AND resolved_by_user_id IS NOT NULL
                    )
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_personnel_application_blockers_open
            ON public.personnel_application_blockers (application_id, blocker_code)
            WHERE resolved_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_personnel_application_blockers_application
            ON public.personnel_application_blockers (application_id, created_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.person_photos IS
            'ADR-061: canonical person-scoped photo versions (terminal superseded).';
        COMMENT ON TABLE public.person_photo_sources IS
            'ADR-061: append-only provenance ledger; survives application hard-delete.';
        COMMENT ON TABLE public.personnel_application_blockers IS
            'ADR-061: HR-visible apply blockers for intake photo canonicalization.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_person_photo_sources_append_only
            ON public.person_photo_sources
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_person_photos_guard_mutation
            ON public.person_photos
        """
    )

    op.execute("DROP FUNCTION IF EXISTS public.person_photo_sources_append_only()")
    op.execute("DROP FUNCTION IF EXISTS public.trg_person_photos_guard_mutation()")

    op.execute(
        "DROP INDEX IF EXISTS public.uq_personnel_application_blockers_open"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.ix_personnel_application_blockers_application"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.uq_person_photo_sources_intake_material"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.ix_person_photo_sources_person"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.ix_person_photo_sources_photo"
    )
    op.execute("DROP INDEX IF EXISTS public.uq_person_photos_one_active")
    op.execute("DROP INDEX IF EXISTS public.ix_person_photos_person_created")

    op.execute("DROP TABLE IF EXISTS public.personnel_application_blockers CASCADE")
    op.execute("DROP TABLE IF EXISTS public.person_photo_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS public.person_photos CASCADE")
