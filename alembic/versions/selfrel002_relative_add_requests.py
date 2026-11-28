"""Allow employee proposals for a new relative in the existing review queue."""
from alembic import op

revision = "selfrel002"
down_revision = "selfrel001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.person_relative_change_requests
            ADD COLUMN request_kind TEXT NOT NULL DEFAULT 'correction'
                CHECK (request_kind IN ('correction', 'addition'));
        ALTER TABLE public.person_relative_change_requests
            ALTER COLUMN relative_id DROP NOT NULL,
            ALTER COLUMN expected_updated_at DROP NOT NULL;
        ALTER TABLE public.person_relative_change_requests
            ADD CONSTRAINT person_relative_request_target_shape CHECK (
                (request_kind = 'correction' AND relative_id IS NOT NULL AND expected_updated_at IS NOT NULL)
                OR (request_kind = 'addition' AND relative_id IS NULL AND expected_updated_at IS NULL)
            );
        CREATE UNIQUE INDEX person_relative_requests_one_pending_addition
            ON public.person_relative_change_requests(person_id)
            WHERE request_kind = 'addition' AND status = 'pending';
    """)


def downgrade() -> None:
    raise RuntimeError("Relative addition requests require a data-preserving rollback plan")
