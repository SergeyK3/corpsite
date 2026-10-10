"""Independent personnel templates, preserving all existing version identities."""
from alembic import op

revision = "hrtpl001"
down_revision = "hrlang001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE public.personnel_order_templates (
        template_id BIGSERIAL PRIMARY KEY,
        item_type_code TEXT NOT NULL,
        name_ru TEXT NOT NULL CHECK (btrim(name_ru) <> ''),
        name_kk TEXT NOT NULL CHECK (btrim(name_kk) <> ''),
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        created_by_user_id BIGINT REFERENCES public.users(user_id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (template_id, item_type_code)
      );
      CREATE UNIQUE INDEX uq_personnel_order_templates_default
        ON public.personnel_order_templates(item_type_code) WHERE is_default;
      LOCK TABLE public.personnel_order_template_versions IN ACCESS EXCLUSIVE MODE;
      INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,is_default)
      SELECT DISTINCT ON (item_type_code) item_type_code,title_ru,title_kk,TRUE
        FROM public.personnel_order_template_versions
        ORDER BY item_type_code, (status='PUBLISHED') DESC, version_number DESC;
      ALTER TABLE public.personnel_order_template_versions ADD COLUMN template_id BIGINT;
      -- The immutable-publication trigger would reject this metadata-only backfill.
      -- Its protection is restored inside this same locked, atomic migration.
      ALTER TABLE public.personnel_order_template_versions DISABLE TRIGGER trg_guard_published_personnel_order_template;
      UPDATE public.personnel_order_template_versions v SET template_id=t.template_id
        FROM public.personnel_order_templates t WHERE t.item_type_code=v.item_type_code AND t.is_default;
      ALTER TABLE public.personnel_order_template_versions ENABLE TRIGGER trg_guard_published_personnel_order_template;
      ALTER TABLE public.personnel_order_template_versions
        ALTER COLUMN template_id SET NOT NULL,
        ADD CONSTRAINT fk_personnel_template_version_template
          FOREIGN KEY(template_id,item_type_code) REFERENCES public.personnel_order_templates(template_id,item_type_code) ON DELETE RESTRICT,
        DROP CONSTRAINT uq_personnel_order_template_versions_type_number,
        ADD CONSTRAINT uq_personnel_order_template_versions_template_number UNIQUE(template_id,version_number);
      DROP INDEX public.uq_personnel_order_template_versions_one_draft;
      DROP INDEX public.uq_personnel_order_template_versions_one_published;
      CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_draft
        ON public.personnel_order_template_versions(template_id) WHERE status='DRAFT';
      CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_published
        ON public.personnel_order_template_versions(template_id) WHERE status='PUBLISHED';
      ALTER TABLE public.personnel_order_templates ADD COLUMN copied_from_template_version_id BIGINT
        REFERENCES public.personnel_order_template_versions(template_version_id) ON DELETE RESTRICT;
      ALTER TABLE public.personnel_orders ADD COLUMN selected_template_version_id BIGINT
        REFERENCES public.personnel_order_template_versions(template_version_id) ON DELETE RESTRICT;
      -- Older import tools omit template_id. Keep their inserts on the default template.
      CREATE FUNCTION public.assign_default_personnel_template() RETURNS trigger AS $$
      BEGIN
        IF NEW.template_id IS NULL THEN
          INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,is_default)
            VALUES(NEW.item_type_code,NEW.title_ru,NEW.title_kk,TRUE)
            ON CONFLICT(item_type_code) WHERE is_default DO UPDATE SET is_default=TRUE
            RETURNING template_id INTO NEW.template_id;
        END IF;
        RETURN NEW;
      END $$ LANGUAGE plpgsql;
      CREATE TRIGGER trg_assign_default_personnel_template BEFORE INSERT
        ON public.personnel_order_template_versions FOR EACH ROW
        EXECUTE FUNCTION public.assign_default_personnel_template();
    """)


def downgrade() -> None:
    op.execute("""
      DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.personnel_order_templates WHERE NOT is_default)
        THEN RAISE EXCEPTION 'Independent templates exist; downgrade would lose their identities'; END IF;
      END $$;
      ALTER TABLE public.personnel_orders DROP COLUMN selected_template_version_id;
      ALTER TABLE public.personnel_order_templates DROP COLUMN copied_from_template_version_id;
      DROP TRIGGER IF EXISTS trg_assign_default_personnel_template ON public.personnel_order_template_versions;
      DROP FUNCTION IF EXISTS public.assign_default_personnel_template();
      DROP INDEX public.uq_personnel_order_template_versions_one_draft;
      DROP INDEX public.uq_personnel_order_template_versions_one_published;
      ALTER TABLE public.personnel_order_template_versions
        DROP CONSTRAINT fk_personnel_template_version_template,
        DROP CONSTRAINT uq_personnel_order_template_versions_template_number,
        DROP COLUMN template_id,
        ADD CONSTRAINT uq_personnel_order_template_versions_type_number UNIQUE(item_type_code,version_number);
      CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_draft
        ON public.personnel_order_template_versions(item_type_code) WHERE status='DRAFT';
      CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_published
        ON public.personnel_order_template_versions(item_type_code) WHERE status='PUBLISHED';
      DROP TABLE public.personnel_order_templates;
    """)
