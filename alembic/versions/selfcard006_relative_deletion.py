"""Allow reviewed deletion and withdrawal of relative requests."""
from alembic import op

revision = "selfcard006"
down_revision = "selfcard005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.person_relative_change_requests DROP CONSTRAINT person_relative_change_requests_request_kind_check")
    op.execute("""ALTER TABLE public.person_relative_change_requests ADD CONSTRAINT person_relative_change_requests_request_kind_check
        CHECK (request_kind IN ('correction','addition','deletion'))""")
    op.execute("ALTER TABLE public.person_relative_change_requests DROP CONSTRAINT person_relative_change_requests_status_check")
    op.execute("""ALTER TABLE public.person_relative_change_requests ADD CONSTRAINT person_relative_change_requests_status_check
        CHECK (status IN ('pending','returned','approved','withdrawn'))""")
    op.execute("ALTER TABLE public.person_relative_change_requests DROP CONSTRAINT person_relative_request_target_shape")
    op.execute("""ALTER TABLE public.person_relative_change_requests ADD CONSTRAINT person_relative_request_target_shape CHECK (
        (request_kind IN ('correction','deletion') AND relative_id IS NOT NULL AND expected_updated_at IS NOT NULL)
        OR (request_kind='addition' AND relative_id IS NULL AND expected_updated_at IS NULL))""")


def downgrade() -> None:
    raise RuntimeError("Relative deletion requests require a data-preserving rollback plan")
