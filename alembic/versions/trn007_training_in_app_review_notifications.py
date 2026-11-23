"""Store in-app notices for graded training reviews.

Revision ID: trn007
Revises: trn006
"""
from __future__ import annotations

from alembic import op

revision = "trn007"
down_revision = "trn006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_training_review_in_app_notice
        ON public.notifications ((payload->>'training_review_id'))
        WHERE channel='IN_APP_TRAINING'
    """)
    op.execute("""
        INSERT INTO public.notifications(channel,recipient_user_id,payload,status)
        SELECT 'IN_APP_TRAINING', a.participant_user_id,
               jsonb_build_object('training_review_id',r.review_id,
                                  'attempt_id',t.attempt_id,
                                  'assignment_id',a.assignment_id),
               'PENDING'
        FROM public.training_reviews r
        JOIN public.training_attempts t ON t.attempt_id=r.attempt_id
        JOIN public.training_assignments a ON a.assignment_id=t.assignment_id
        JOIN public.training_lesson_versions l ON l.lesson_version_id=a.lesson_version_id
        WHERE r.score IS NOT NULL AND l.lesson_code='skill_2'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Keep delivered in-app notices and all training history.
    op.execute("DROP INDEX IF EXISTS public.uq_training_review_in_app_notice")
