"""Add draft versions for the first editable personnel-order template.

Revision ID: pojson013
Revises: pojson012
"""
from alembic import op


revision = "pojson013"
down_revision = "pojson012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.personnel_order_template_versions (
            template_version_id BIGSERIAL PRIMARY KEY,
            item_type_code TEXT NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number >= 1),
            status TEXT NOT NULL CHECK (status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            title_ru TEXT NOT NULL CHECK (btrim(title_ru) <> ''),
            title_kk TEXT NOT NULL CHECK (btrim(title_kk) <> ''),
            preamble_ru TEXT NOT NULL CHECK (btrim(preamble_ru) <> ''),
            preamble_kk TEXT NOT NULL CHECK (btrim(preamble_kk) <> ''),
            body_template_ru TEXT NOT NULL CHECK (btrim(body_template_ru) <> ''),
            body_template_kk TEXT NOT NULL CHECK (btrim(body_template_kk) <> ''),
            basis_template_ru TEXT NOT NULL CHECK (btrim(basis_template_ru) <> ''),
            basis_template_kk TEXT NOT NULL CHECK (btrim(basis_template_kk) <> ''),
            based_on_built_in BOOLEAN NOT NULL DEFAULT TRUE,
            created_by_user_id BIGINT REFERENCES public.users(user_id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_by_user_id BIGINT REFERENCES public.users(user_id),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_personnel_order_template_versions_type_number UNIQUE (item_type_code, version_number)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_personnel_order_template_versions_one_draft
        ON public.personnel_order_template_versions (item_type_code)
        WHERE status = 'DRAFT'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE public.personnel_order_template_versions")
