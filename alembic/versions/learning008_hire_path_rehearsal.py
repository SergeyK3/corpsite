"""Bind hire-path attempts and keep training delivery separate from external channels."""
from alembic import op

from app.learning.model import (
    hire_acknowledgements, hire_messages, hire_recipients, hire_signatures, hire_step_links,
)

revision = "learning008"
down_revision = "learning007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    hire_step_links.create(bind)
    hire_recipients.create(bind)
    hire_messages.create(bind)
    hire_acknowledgements.create(bind)
    hire_signatures.create(bind)
    op.create_index("ix_learning_hire_step_root", "learning_hire_step_links", ["root_attempt_id", "step"])
    op.create_index("ix_learning_hire_message_recipient", "learning_hire_messages", ["recipient_user_id", "created_at"])
    op.execute("CREATE UNIQUE INDEX uq_learning_hire_order_notice ON public.learning_hire_messages(root_attempt_id) WHERE kind='order_notice'")


def downgrade():
    raise RuntimeError("Hire rehearsal links and events need a data-preserving rollback plan")
