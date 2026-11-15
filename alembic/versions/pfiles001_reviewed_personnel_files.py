"""Reviewed person-owned files, versions and append-only audit; no legacy backfill."""
from alembic import op

revision = 'pfiles001'
down_revision = 'ptype002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE TABLE public.personnel_file_sets (
            set_id UUID PRIMARY KEY,
            person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
            kind TEXT NOT NULL CHECK(kind IN ('photo','certificate','diploma','identity','name_change')),
            title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 300),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(set_id, person_id)
        );
        CREATE UNIQUE INDEX personnel_files_single_photo ON public.personnel_file_sets(person_id) WHERE kind='photo';
        CREATE TABLE public.personnel_file_versions (
            version_id UUID PRIMARY KEY,
            set_id UUID NOT NULL REFERENCES public.personnel_file_sets(set_id) ON DELETE RESTRICT,
            version_no INTEGER NOT NULL CHECK(version_no>0),
            state TEXT NOT NULL CHECK(state IN ('pending','returned','approved','superseded','revoked','archived')),
            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
            storage_key TEXT NOT NULL UNIQUE,
            original_name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            byte_size BIGINT NOT NULL CHECK(byte_size>0),
            checksum_sha256 CHAR(64) NOT NULL,
            page_count INTEGER NOT NULL CHECK(page_count BETWEEN 1 AND 20),
            uploaded_by BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_by BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            decided_at TIMESTAMPTZ,
            reason TEXT NOT NULL DEFAULT '',
            proposed_name JSONB,
            preview_checksums JSONB NOT NULL,
            name_applied_at TIMESTAMPTZ,
            UNIQUE(set_id, version_no)
        );
        CREATE UNIQUE INDEX personnel_files_one_approved ON public.personnel_file_versions(set_id) WHERE state='approved';
        CREATE INDEX personnel_files_pending ON public.personnel_file_versions(created_at) WHERE state='pending';
        CREATE INDEX personnel_files_person ON public.personnel_file_sets(person_id);
        CREATE TABLE public.personnel_file_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
            version_id UUID REFERENCES public.personnel_file_versions(version_id) ON DELETE RESTRICT,
            actor_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            request_id UUID NOT NULL,
            detail JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE public.personnel_file_inbox (
            user_id BIGINT PRIMARY KEY REFERENCES public.users(user_id) ON DELETE RESTRICT,
            last_event_id BIGINT NOT NULL DEFAULT 0
        );
        CREATE INDEX personnel_files_events_person ON public.personnel_file_events(person_id,event_id);
        INSERT INTO public.access_roles(code,name,access_level,level_rank,is_active)
        VALUES ('PERSONNEL_FILES_READ','Просмотр одобренных файлов сотрудников','MANAGER',20,true),
               ('PERSONNEL_FILES_REVIEW','Проверка файлов сотрудников','MANAGER',20,true)
        ON CONFLICT(code) DO NOTHING;
        CREATE FUNCTION public.personnel_file_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Personnel file events are append only'; END $$;
        CREATE TRIGGER personnel_file_events_immutable BEFORE UPDATE OR DELETE ON public.personnel_file_events
        FOR EACH ROW EXECUTE FUNCTION public.personnel_file_events_immutable();
    ''')


def downgrade():
    raise RuntimeError('Personnel files require a data-preserving rollback plan; do not drop stored files or audit.')
