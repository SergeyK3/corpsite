"""Reviewable employee changes for the remaining personal card sections."""
from alembic import op

revision = "selfcard002"
down_revision = "selfeha001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""CREATE TABLE public.person_card_change_requests (
        request_id uuid PRIMARY KEY, person_id bigint NOT NULL REFERENCES public.persons(person_id),
        employee_context_id bigint REFERENCES public.employees(employee_id),
        section text NOT NULL CHECK (section IN ('contacts','education','training','category','employment_biography','languages','awards')),
        request_kind text NOT NULL CHECK (request_kind IN ('addition','correction')),
        record_id bigint, expected_updated_at timestamptz, expected_version integer,
        current jsonb NOT NULL DEFAULT '{}'::jsonb, proposed jsonb NOT NULL,
        status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','returned')),
        revision integer NOT NULL DEFAULT 1, submitted_by bigint NOT NULL REFERENCES public.users(user_id),
        submitted_at timestamptz NOT NULL DEFAULT now(), decided_by bigint REFERENCES public.users(user_id),
        decided_at timestamptz, reason text NOT NULL DEFAULT '', approved_record_id bigint
    )""")
    op.execute("""CREATE UNIQUE INDEX uq_person_card_change_pending ON public.person_card_change_requests
        (person_id,section,request_kind,COALESCE(record_id,0)) WHERE status='pending'""")
    op.execute("""CREATE INDEX ix_person_card_change_mine ON public.person_card_change_requests
        (person_id,submitted_by,submitted_at DESC)""")
    op.execute("""CREATE TABLE public.person_card_change_events (
        event_id bigserial PRIMARY KEY, request_id uuid NOT NULL REFERENCES public.person_card_change_requests(request_id),
        actor_id bigint NOT NULL REFERENCES public.users(user_id), action text NOT NULL,
        detail jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
    )""")

def downgrade() -> None:
    op.execute("DROP TABLE public.person_card_change_events")
    op.execute("DROP TABLE public.person_card_change_requests")
