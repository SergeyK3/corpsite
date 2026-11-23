"""Versioned training assignments, attempts, evidence, and reviews.

Revision ID: trn002
Revises: trn001
"""
from alembic import op

revision = "trn002"
down_revision = "trn001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.training_course_versions (
            course_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            course_code TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version > 0),
            title TEXT NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (course_code, version)
        );
        CREATE TABLE public.training_lesson_versions (
            lesson_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            course_version_id BIGINT NOT NULL REFERENCES public.training_course_versions(course_version_id) ON DELETE RESTRICT,
            lesson_code TEXT NOT NULL,
            title TEXT NOT NULL,
            position_label TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 1 AND 240),
            steps JSONB NOT NULL,
            rules JSONB NOT NULL,
            UNIQUE (course_version_id, lesson_code)
        );
        CREATE TABLE public.training_assignments (
            assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            participant_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            lesson_version_id BIGINT NOT NULL REFERENCES public.training_lesson_versions(lesson_version_id) ON DELETE RESTRICT,
            required BOOLEAN NOT NULL DEFAULT TRUE,
            instruction_url TEXT,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (participant_user_id, lesson_version_id)
        );
        CREATE TABLE public.training_attempts (
            attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            assignment_id BIGINT NOT NULL REFERENCES public.training_assignments(assignment_id) ON DELETE RESTRICT,
            attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
            status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'under_review', 'technical_pause', 'completed')),
            outcome TEXT CHECK (outcome IN ('passed', 'failed')),
            score SMALLINT CHECK (score BETWEEN 1 AND 5),
            fixture JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_checked_at TIMESTAMPTZ,
            CHECK ((status='completed') = (outcome IS NOT NULL AND score IS NOT NULL)),
            UNIQUE (assignment_id, attempt_number)
        );
        CREATE TABLE public.training_attempt_objects (
            attempt_id BIGINT NOT NULL REFERENCES public.training_attempts(attempt_id) ON DELETE RESTRICT,
            application_id BIGINT REFERENCES public.personnel_applications(application_id) ON DELETE RESTRICT,
            order_id BIGINT REFERENCES public.personnel_orders(order_id) ON DELETE RESTRICT,
            object_role TEXT NOT NULL,
            UNIQUE (attempt_id, object_role)
        );
        CREATE TABLE public.training_evidence (
            evidence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            attempt_id BIGINT NOT NULL REFERENCES public.training_attempts(attempt_id) ON DELETE RESTRICT,
            step_key TEXT NOT NULL,
            uploaded_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png', 'image/jpeg', 'image/webp')),
            width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 10000),
            height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 10000),
            sha256 TEXT NOT NULL,
            perceptual_hash TEXT NOT NULL,
            image_bytes BYTEA NOT NULL,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            superseded_at TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX uq_training_evidence_current
            ON public.training_evidence(attempt_id, step_key) WHERE superseded_at IS NULL;
        CREATE TABLE public.training_attempt_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            attempt_id BIGINT NOT NULL REFERENCES public.training_attempts(attempt_id) ON DELETE RESTRICT,
            step_key TEXT,
            actor_kind TEXT NOT NULL CHECK (actor_kind IN ('participant', 'system', 'organizer')),
            actor_user_id BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            event_type TEXT NOT NULL,
            detail JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE public.training_reviews (
            review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            attempt_id BIGINT NOT NULL REFERENCES public.training_attempts(attempt_id) ON DELETE RESTRICT,
            rules JSONB NOT NULL,
            evidence_ids BIGINT[] NOT NULL,
            outcome TEXT,
            score SMALLINT CHECK (score BETWEEN 1 AND 5),
            explanation TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((outcome IS NULL AND score IS NULL) OR (outcome IN ('passed','failed') AND score IS NOT NULL))
        );
        CREATE INDEX ix_training_attempts_assignment ON public.training_attempts(assignment_id, attempt_id DESC);
        CREATE INDEX ix_training_events_attempt ON public.training_attempt_events(attempt_id, event_id);
        CREATE INDEX ix_training_reviews_attempt ON public.training_reviews(attempt_id, review_id);
    """)


def downgrade() -> None:
    for table in ("training_reviews", "training_attempt_events", "training_evidence",
                  "training_attempt_objects", "training_attempts", "training_assignments",
                  "training_lesson_versions", "training_course_versions"):
        op.execute(f"DROP TABLE public.{table}")
