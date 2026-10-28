"""Only synthetic tables and values, for the native template API rehearsal."""
from sqlalchemy import text


def seed_category_fixture(engine):
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE personnel_order_templates(
            template_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,item_type_code text NOT NULL,
            name_ru text NOT NULL,name_kk text NOT NULL,is_default boolean DEFAULT false,
            created_by_user_id bigint,copied_from_template_version_id bigint)'''))
        conn.execute(text('CREATE UNIQUE INDEX category_fixture_default ON personnel_order_templates(item_type_code) WHERE is_default'))
        conn.execute(text('''CREATE TABLE personnel_order_template_versions(
            template_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,template_id bigint REFERENCES personnel_order_templates,
            item_type_code text,version_number int,status text CHECK(status IN ('DRAFT','PUBLISHED','ARCHIVED')),
            revision int DEFAULT 1,title_ru text,title_kk text,print_title_ru text,print_title_kk text,
            preamble_ru text,preamble_kk text,body_template_ru text,body_template_kk text,basis_template_ru text,basis_template_kk text,
            based_on_built_in boolean DEFAULT false,created_at timestamptz DEFAULT now(),updated_at timestamptz DEFAULT now(),
            created_by_user_id bigint,updated_by_user_id bigint,published_at timestamptz,published_by_user_id bigint,
            UNIQUE(template_id,version_number))'''))
        conn.execute(text('CREATE TABLE medical_specialty_groups(group_id bigint PRIMARY KEY,code text,name text,is_active boolean)'))
        conn.execute(text('CREATE TABLE medical_specialties(medical_specialty_id bigint PRIMARY KEY,group_id bigint REFERENCES medical_specialty_groups,code text,name text,name_kk text,is_active boolean)'))
        conn.execute(text("INSERT INTO medical_specialty_groups VALUES(900001,'TEST','TEST',true)"))
        conn.execute(text("INSERT INTO medical_specialties VALUES(900003,900001,'TEST_SPECIALTY_CODE','Терапия','Терапия',true)"))
