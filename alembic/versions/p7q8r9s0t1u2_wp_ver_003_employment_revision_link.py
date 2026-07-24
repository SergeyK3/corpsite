"""WP-VER-003 — employment_episode pending revision link + task identity.

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
"""
from __future__ import annotations

from alembic import op

revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.person_external_employment
            ADD COLUMN IF NOT EXISTS supersedes_employment_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_pee_supersedes_employment_id'
            ) THEN
                ALTER TABLE public.person_external_employment
                    ADD CONSTRAINT fk_pee_supersedes_employment_id
                    FOREIGN KEY (supersedes_employment_id)
                    REFERENCES public.person_external_employment (employment_id)
                    ON DELETE RESTRICT;
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_pee_supersedes_not_self'
            ) THEN
                ALTER TABLE public.person_external_employment
                    ADD CONSTRAINT chk_pee_supersedes_not_self
                    CHECK (
                        supersedes_employment_id IS NULL
                        OR supersedes_employment_id IS DISTINCT FROM employment_id
                    );
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pee_supersedes_employment_id
            ON public.person_external_employment (supersedes_employment_id)
            WHERE supersedes_employment_id IS NOT NULL
        """
    )

    # Same-person revision link (employment-specific; not a universal lineage model).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_pee_supersedes_same_person()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            prior_person_id BIGINT;
        BEGIN
            IF NEW.supersedes_employment_id IS NULL THEN
                RETURN NEW;
            END IF;

            IF NEW.supersedes_employment_id IS NOT DISTINCT FROM NEW.employment_id THEN
                RAISE EXCEPTION
                    'person_external_employment: supersedes_employment_id cannot reference self';
            END IF;

            SELECT person_id
            INTO prior_person_id
            FROM public.person_external_employment
            WHERE employment_id = NEW.supersedes_employment_id;

            IF prior_person_id IS NULL THEN
                RAISE EXCEPTION
                    'person_external_employment: supersedes_employment_id=% not found',
                    NEW.supersedes_employment_id;
            END IF;

            IF prior_person_id IS DISTINCT FROM NEW.person_id THEN
                RAISE EXCEPTION
                    'person_external_employment: supersedes_employment_id=% belongs to person_id=%, not %',
                    NEW.supersedes_employment_id, prior_person_id, NEW.person_id;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_pee_supersedes_same_person
            ON public.person_external_employment
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_pee_supersedes_same_person
            BEFORE INSERT OR UPDATE OF person_id, supersedes_employment_id
            ON public.person_external_employment
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_pee_supersedes_same_person()
        """
    )

    # WP-VER-003 task identity:
    #   root row: object_id = object_version_id = employment_id
    #   revision: object_version_id = new employment_id,
    #             object_id = supersedes_employment_id
    #             prior must be active and same person
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_verification_task_ppr_ref()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            version_person_id BIGINT;
            version_lifecycle TEXT;
            version_supersedes BIGINT;
            prior_person_id BIGINT;
            prior_lifecycle TEXT;
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

                SELECT person_id, lifecycle_status, supersedes_employment_id
                INTO version_person_id, version_lifecycle, version_supersedes
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

                IF version_supersedes IS NULL THEN
                    IF NEW.object_id IS DISTINCT FROM NEW.object_version_id THEN
                        RAISE EXCEPTION
                            'verification_tasks: root employment requires object_id = object_version_id '
                            '(got object_id=%, object_version_id=%)',
                            NEW.object_id, NEW.object_version_id;
                    END IF;
                ELSE
                    IF NEW.object_id IS DISTINCT FROM version_supersedes THEN
                        RAISE EXCEPTION
                            'verification_tasks: revision object_id=% must equal supersedes_employment_id=%',
                            NEW.object_id, version_supersedes;
                    END IF;

                    SELECT person_id, lifecycle_status
                    INTO prior_person_id, prior_lifecycle
                    FROM public.person_external_employment
                    WHERE employment_id = NEW.object_id;

                    IF prior_person_id IS NULL THEN
                        RAISE EXCEPTION
                            'verification_tasks: orphan object_id=% (prior employment missing)',
                            NEW.object_id;
                    END IF;

                    IF prior_person_id IS DISTINCT FROM NEW.person_id THEN
                        RAISE EXCEPTION
                            'verification_tasks: prior object_id=% person_id=% does not match task person_id=%',
                            NEW.object_id, prior_person_id, NEW.person_id;
                    END IF;

                    IF prior_lifecycle IS DISTINCT FROM 'active' THEN
                        RAISE EXCEPTION
                            'verification_tasks: prior employment object_id=% must be lifecycle_status=active (got %)',
                            NEW.object_id, prior_lifecycle;
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    # Restore WP-VER-002 foundation identity (object_id = object_version_id only).
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
        DROP TRIGGER IF EXISTS trg_pee_supersedes_same_person
            ON public.person_external_employment
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.enforce_pee_supersedes_same_person()")
    op.execute("DROP INDEX IF EXISTS public.ix_pee_supersedes_employment_id")
    op.execute(
        """
        ALTER TABLE public.person_external_employment
            DROP CONSTRAINT IF EXISTS chk_pee_supersedes_not_self
        """
    )
    op.execute(
        """
        ALTER TABLE public.person_external_employment
            DROP CONSTRAINT IF EXISTS fk_pee_supersedes_employment_id
        """
    )
    op.execute(
        """
        ALTER TABLE public.person_external_employment
            DROP COLUMN IF EXISTS supersedes_employment_id
        """
    )
