"""Allow reviewed certificates for qualification category records.

Revision ID: selfcard004
Revises: selfcard003
"""
from alembic import op

revision = "selfcard004"
down_revision = "selfcard003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("person_card_change_documents", "person_card_record_documents"):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_section_check")
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {table}_section_check "
                   "CHECK (section IN ('education','training','category'))")


def downgrade() -> None:
    for table in ("person_card_change_documents", "person_card_record_documents"):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_section_check")
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {table}_section_check "
                   "CHECK (section IN ('education','training'))")
