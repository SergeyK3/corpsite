"""Link immutable certificate facts to the registry; no legacy inference/backfill."""
from alembic import op

revision = 'pfiles002'
down_revision = 'pfiles001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE TABLE certificate_classifier_editions (
            edition_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE CHECK(length(trim(code)) BETWEEN 1 AND 100),
            title text NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 500),
            source_reference text NOT NULL CHECK(length(trim(source_reference)) BETWEEN 1 AND 2000),
            effective_from date NOT NULL,
            accepts_new boolean NOT NULL DEFAULT true,
            created_by bigint NOT NULL REFERENCES users(user_id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE certificate_classifier_entries (
            entry_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            edition_id bigint NOT NULL REFERENCES certificate_classifier_editions(edition_id),
            medical_specialty_id bigint NOT NULL REFERENCES medical_specialties(medical_specialty_id),
            specialty_code text NOT NULL CHECK(length(trim(specialty_code)) BETWEEN 1 AND 100),
            specialty_name text NOT NULL CHECK(length(trim(specialty_name)) BETWEEN 1 AND 500),
            UNIQUE(edition_id,specialty_code), UNIQUE(edition_id,medical_specialty_id)
        );
        CREATE TABLE certificate_specialty_mappings (
            mapping_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            from_entry_id bigint NOT NULL REFERENCES certificate_classifier_entries(entry_id),
            to_entry_id bigint NOT NULL REFERENCES certificate_classifier_entries(entry_id),
            source_reference text NOT NULL CHECK(length(trim(source_reference)) BETWEEN 1 AND 2000),
            reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
            effective_from date NOT NULL,
            confirmed_by bigint NOT NULL REFERENCES users(user_id),
            confirmed_at timestamptz NOT NULL DEFAULT now(),
            active boolean NOT NULL DEFAULT true,
            CHECK(from_entry_id<>to_entry_id), UNIQUE(from_entry_id,to_entry_id)
        );
        CREATE TABLE certificate_classifier_events (
            event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            actor_id bigint NOT NULL REFERENCES users(user_id),
            action text NOT NULL, detail jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TRIGGER certificate_classifier_events_immutable BEFORE UPDATE OR DELETE ON certificate_classifier_events
            FOR EACH ROW EXECUTE FUNCTION personnel_file_events_immutable();
        ALTER TABLE employee_documents ADD COLUMN certificate_entry_id bigint REFERENCES certificate_classifier_entries(entry_id),
            ADD COLUMN specialty_name_at_issue text,
            ADD COLUMN specialty_code_at_issue text,
            ADD COLUMN classifier_edition_at_issue text;
        ALTER TABLE personnel_file_versions
            ADD COLUMN employee_document_id bigint UNIQUE REFERENCES employee_documents(document_id) ON DELETE RESTRICT,
            ADD COLUMN registry_created_by_upload boolean NOT NULL DEFAULT false,
            ADD COLUMN replaces_version_id uuid REFERENCES personnel_file_versions(version_id);
        CREATE FUNCTION certificate_facts_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Classifier identities are immutable'; END IF;
            IF TG_TABLE_NAME='certificate_classifier_entries' OR
               (to_jsonb(NEW)-'accepts_new') IS DISTINCT FROM (to_jsonb(OLD)-'accepts_new') THEN
                RAISE EXCEPTION 'Classifier identities are immutable';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER certificate_entries_immutable BEFORE UPDATE OR DELETE ON certificate_classifier_entries
            FOR EACH ROW EXECUTE FUNCTION certificate_facts_immutable();
        CREATE TRIGGER certificate_editions_immutable BEFORE UPDATE OR DELETE ON certificate_classifier_editions
            FOR EACH ROW EXECUTE FUNCTION certificate_facts_immutable();
        CREATE FUNCTION certificate_document_facts_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE entry record;
        BEGIN
            IF TG_OP='UPDATE' THEN
                IF ROW(NEW.certificate_entry_id,NEW.specialty_name_at_issue,NEW.specialty_code_at_issue,NEW.classifier_edition_at_issue)
                   IS DISTINCT FROM ROW(OLD.certificate_entry_id,OLD.specialty_name_at_issue,OLD.specialty_code_at_issue,OLD.classifier_edition_at_issue) THEN
                    RAISE EXCEPTION 'Issued certificate specialty facts are immutable';
                END IF;
                IF (OLD.certificate_entry_id IS NOT NULL OR EXISTS(SELECT 1 FROM personnel_file_versions WHERE employee_document_id=OLD.document_id)) AND
                   ROW(NEW.employee_id,NEW.document_type_id,NEW.medical_specialty_id,NEW.issued_at,NEW.valid_until,NEW.document_number,NEW.issued_by)
                   IS DISTINCT FROM ROW(OLD.employee_id,OLD.document_type_id,OLD.medical_specialty_id,OLD.issued_at,OLD.valid_until,OLD.document_number,OLD.issued_by) THEN
                    RAISE EXCEPTION 'Linked certificate requisites are immutable; submit a new document';
                END IF;
            ELSIF NEW.certificate_entry_id IS NOT NULL THEN
                SELECT e.*,d.code AS edition_code INTO STRICT entry FROM certificate_classifier_entries e
                    JOIN certificate_classifier_editions d USING(edition_id) WHERE entry_id=NEW.certificate_entry_id;
                IF NEW.medical_specialty_id IS DISTINCT FROM entry.medical_specialty_id OR
                   NEW.specialty_name_at_issue IS NULL OR length(trim(NEW.specialty_name_at_issue))=0 THEN
                    RAISE EXCEPTION 'Certificate specialty and original issued name are required';
                END IF;
                NEW.specialty_code_at_issue=entry.specialty_code;
                NEW.classifier_edition_at_issue=entry.edition_code;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER certificate_document_facts_guard BEFORE INSERT OR UPDATE ON employee_documents
            FOR EACH ROW EXECUTE FUNCTION certificate_document_facts_guard();
        INSERT INTO access_roles(code,name,access_level,level_rank,is_active)
        VALUES('CERTIFICATE_CLASSIFIERS_MANAGE','Централизованные редакции и соответствия сертификатов','MANAGER',20,true)
        ON CONFLICT(code) DO NOTHING;
    ''')


def downgrade():
    raise RuntimeError('Preserve certificate facts, registry links and audit on rollback.')
