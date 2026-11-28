"""Reviewable record deletion and employee withdrawal on the self card."""
from alembic import op

revision = "selfcard005"
down_revision = "selfcard004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE public.person_card_change_requests
        DROP CONSTRAINT person_card_change_requests_request_kind_check""")
    op.execute("""ALTER TABLE public.person_card_change_requests
        ADD CONSTRAINT person_card_change_requests_request_kind_check
        CHECK (request_kind IN ('addition','correction','deletion'))""")
    op.execute("""ALTER TABLE public.person_card_change_requests
        DROP CONSTRAINT person_card_change_requests_status_check""")
    op.execute("""ALTER TABLE public.person_card_change_requests
        ADD CONSTRAINT person_card_change_requests_status_check
        CHECK (status IN ('pending','approved','returned','withdrawn'))""")
    op.execute("DROP INDEX public.uq_person_card_change_pending")
    op.execute("""CREATE UNIQUE INDEX uq_person_card_change_pending
        ON public.person_card_change_requests (person_id,section,COALESCE(record_id,0))
        WHERE status='pending'""")


def downgrade() -> None:
    op.execute("DROP INDEX public.uq_person_card_change_pending")
    op.execute("""CREATE UNIQUE INDEX uq_person_card_change_pending
        ON public.person_card_change_requests (person_id,section,request_kind,COALESCE(record_id,0))
        WHERE status='pending'""")
    op.execute("ALTER TABLE public.person_card_change_requests DROP CONSTRAINT person_card_change_requests_status_check")
    op.execute("""ALTER TABLE public.person_card_change_requests
        ADD CONSTRAINT person_card_change_requests_status_check
        CHECK (status IN ('pending','approved','returned'))""")
    op.execute("ALTER TABLE public.person_card_change_requests DROP CONSTRAINT person_card_change_requests_request_kind_check")
    op.execute("""ALTER TABLE public.person_card_change_requests
        ADD CONSTRAINT person_card_change_requests_request_kind_check
        CHECK (request_kind IN ('addition','correction'))""")
