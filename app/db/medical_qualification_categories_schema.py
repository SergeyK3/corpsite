"""Fixed bilingual medical qualification classifier; independent of orders."""
from sqlalchemy import text


CATEGORIES = (
    (1, "Без категории", "Санаты жоқ"),
    (2, "Вторая категория", "Екінші санат"),
    (3, "Первая категория", "Бірінші санат"),
    (4, "Высшая категория", "Жоғары санат"),
)


def upgrade(connection):
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.medical_qualification_categories (
            qualification_category_id INTEGER PRIMARY KEY,
            code INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL UNIQUE,
            name_kk TEXT NOT NULL UNIQUE,
            CONSTRAINT medical_qualification_categories_fixed CHECK (
                qualification_category_id = code AND (
                    (code=1 AND name='Без категории' AND name_kk='Санаты жоқ') OR
                    (code=2 AND name='Вторая категория' AND name_kk='Екінші санат') OR
                    (code=3 AND name='Первая категория' AND name_kk='Бірінші санат') OR
                    (code=4 AND name='Высшая категория' AND name_kk='Жоғары санат')
                )
            )
        )
    """))
    for code, name, name_kk in CATEGORIES:
        connection.execute(text("""
            INSERT INTO public.medical_qualification_categories
                (qualification_category_id, code, name, name_kk)
            VALUES (:code, :code, :name, :name_kk)
            ON CONFLICT (qualification_category_id) DO NOTHING
        """), {"code": code, "name": name, "name_kk": name_kk})
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION public.protect_medical_qualification_categories()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Medical qualification categories are a fixed classifier'
                USING ERRCODE = '23514';
        END;
        $$
    """))
    connection.execute(text("DROP TRIGGER IF EXISTS medical_qualification_categories_read_only ON public.medical_qualification_categories"))
    connection.execute(text("""
        CREATE TRIGGER medical_qualification_categories_read_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON public.medical_qualification_categories
        FOR EACH STATEMENT EXECUTE FUNCTION public.protect_medical_qualification_categories()
    """))


def downgrade(connection):
    connection.execute(text("DROP TABLE public.medical_qualification_categories"))
    connection.execute(text("DROP FUNCTION public.protect_medical_qualification_categories()"))
