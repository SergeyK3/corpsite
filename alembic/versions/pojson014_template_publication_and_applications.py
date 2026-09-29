"""Publish personnel templates and retain order-template application history.

Revision ID: pojson014
Revises: pojson013
"""
from alembic import op

revision = "pojson014"
down_revision = "pojson013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_order_template_versions ADD COLUMN published_at TIMESTAMPTZ, ADD COLUMN published_by_user_id BIGINT REFERENCES public.users(user_id)")
    op.execute("CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_published ON public.personnel_order_template_versions(item_type_code) WHERE status='PUBLISHED'")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.guard_published_personnel_order_template() RETURNS trigger AS $$
    BEGIN
      IF OLD.status='PUBLISHED' AND NOT (NEW.status='ARCHIVED' AND (to_jsonb(NEW)-'status'-'updated_at') = (to_jsonb(OLD)-'status'-'updated_at')) THEN RAISE EXCEPTION 'PUBLISHED personnel-order template is immutable'; END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_published_personnel_order_template BEFORE UPDATE ON public.personnel_order_template_versions FOR EACH ROW EXECUTE FUNCTION public.guard_published_personnel_order_template();
    """)
    op.execute("""
    CREATE TABLE public.personnel_order_template_applications (
      template_application_id BIGSERIAL PRIMARY KEY,
      order_id BIGINT NOT NULL REFERENCES public.personnel_orders(order_id) ON DELETE RESTRICT,
      order_item_id BIGINT NOT NULL REFERENCES public.personnel_order_items(item_id) ON DELETE RESTRICT,
      template_version_id BIGINT NOT NULL REFERENCES public.personnel_order_template_versions(template_version_id) ON DELETE RESTRICT,
      template_snapshot JSONB NOT NULL,
      rendered_snapshot JSONB NOT NULL,
      previous_editorial_blocks JSONB NOT NULL,
      applied_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id),
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_personnel_order_template_applications_order_item ON public.personnel_order_template_applications(order_id, order_item_id, template_application_id);
    CREATE OR REPLACE FUNCTION public.guard_personnel_order_template_application_append_only() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'personnel_order_template_applications is append-only'; END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_personnel_order_template_application_append_only BEFORE UPDATE OR DELETE ON public.personnel_order_template_applications FOR EACH ROW EXECUTE FUNCTION public.guard_personnel_order_template_application_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE public.personnel_order_template_applications")
    op.execute("DROP FUNCTION IF EXISTS public.guard_personnel_order_template_application_append_only()")
    op.execute("DROP TRIGGER trg_guard_published_personnel_order_template ON public.personnel_order_template_versions")
    op.execute("DROP FUNCTION public.guard_published_personnel_order_template()")
    op.execute("DROP INDEX public.uq_personnel_order_template_versions_one_published")
    op.execute("ALTER TABLE public.personnel_order_template_versions DROP COLUMN published_by_user_id, DROP COLUMN published_at")
