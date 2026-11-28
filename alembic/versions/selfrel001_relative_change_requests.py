"""Reviewable employee corrections for existing relative records."""
from alembic import op

revision = "selfrel001"
down_revision = "ehapf001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.person_relative_change_requests (
            request_id UUID PRIMARY KEY,
            person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
            relative_id BIGINT NOT NULL REFERENCES public.person_relatives(relative_id) ON DELETE RESTRICT,
            expected_updated_at TIMESTAMPTZ NOT NULL,
            proposed JSONB NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','returned','approved')),
            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
            submitted_by BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_by BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            decided_at TIMESTAMPTZ,
            reason TEXT NOT NULL DEFAULT '',
            approved_relative_id BIGINT REFERENCES public.person_relatives(relative_id) ON DELETE RESTRICT
        );
        CREATE UNIQUE INDEX person_relative_requests_one_pending
            ON public.person_relative_change_requests(person_id, relative_id) WHERE status='pending';
        CREATE INDEX person_relative_requests_person_status
            ON public.person_relative_change_requests(person_id, status, submitted_at DESC);
        CREATE TABLE public.person_relative_change_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.person_relative_change_requests(request_id) ON DELETE RESTRICT,
            actor_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            detail JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TRIGGER person_relative_change_events_immutable
            BEFORE UPDATE OR DELETE ON public.person_relative_change_events
            FOR EACH ROW EXECUTE FUNCTION public.personnel_file_events_immutable();
    """)


def downgrade() -> None:
    raise RuntimeError("Relative change requests require a data-preserving rollback plan")
