"""Files attached to reviewed education and training changes.

Revision ID: selfcard003
Revises: selfcard002
"""
from alembic import op

revision = "selfcard003"
down_revision = "selfcard002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.person_card_change_documents (
        document_id uuid PRIMARY KEY,
        request_id uuid NOT NULL REFERENCES public.person_card_change_requests(request_id),
        person_id bigint NOT NULL REFERENCES public.persons(person_id),
        section text NOT NULL CHECK (section IN ('education','training')),
        document_type text NOT NULL,
        record_id bigint,
        approved_record_id bigint,
        original_name text NOT NULL,
        mime_type text NOT NULL CHECK (mime_type IN ('application/pdf','image/jpeg','image/png')),
        byte_size integer NOT NULL,
        storage_key uuid NOT NULL UNIQUE,
        checksum_sha256 text NOT NULL,
        page_count integer NOT NULL,
        preview_checksums jsonb NOT NULL,
        uploaded_by bigint NOT NULL REFERENCES public.users(user_id),
        uploaded_at timestamptz NOT NULL DEFAULT now(),
        is_current boolean NOT NULL DEFAULT true
    )""")
    op.execute("""CREATE UNIQUE INDEX uq_person_card_change_current_document
        ON public.person_card_change_documents(request_id) WHERE is_current""")
    op.execute("""CREATE TABLE public.person_card_record_documents (
        person_id bigint NOT NULL REFERENCES public.persons(person_id),
        section text NOT NULL CHECK (section IN ('education','training')),
        record_id bigint NOT NULL,
        document_id uuid NOT NULL REFERENCES public.person_card_change_documents(document_id),
        request_id uuid NOT NULL REFERENCES public.person_card_change_requests(request_id),
        PRIMARY KEY (person_id,section,record_id)
    )""")
    op.execute("CREATE INDEX ix_person_card_record_documents_file ON public.person_card_record_documents(document_id)")


def downgrade() -> None:
    op.execute("DROP TABLE public.person_card_record_documents")
    op.execute("DROP TABLE public.person_card_change_documents")
