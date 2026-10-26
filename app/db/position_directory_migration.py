"""One position directory: stable variants own text; job tables classify them.

Shared by the canonical migration and the verified local recovery branch.
Never rewrites assignments, identities, cabinets, or order snapshots.
"""
from sqlalchemy import text


def upgrade(connection):
    connection.execute(text("""ALTER TABLE public.positions
        ADD COLUMN document_nominative_ru TEXT,
        ADD COLUMN document_possessive_kk TEXT,
        ADD COLUMN translation_status TEXT NOT NULL DEFAULT 'needs_review'
            CHECK (translation_status IN ('confirmed','needs_review')),
        ADD COLUMN document_form_status TEXT NOT NULL DEFAULT 'needs_review'
            CHECK (document_form_status IN ('confirmed','needs_review')),
        ADD COLUMN record_kind TEXT NOT NULL DEFAULT 'standalone'
            CHECK (record_kind IN ('standalone','variant','search_synonym')),
        ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)"""))
    # Specific clinical titles and disputed professional/function mappings must
    # not inherit the generic family's translation or grammatical form.
    connection.execute(text("""UPDATE public.positions p SET
        name_kk=COALESCE(NULLIF(btrim(p.name_kk),''),j.job_namekk),
        document_possessive_kk=j.job_namekk_doc,
        document_form_status='confirmed'
        FROM public.position_job_catalog m
        JOIN public.job_positions_catalog j USING(job_code)
        WHERE m.position_id=p.position_id
          AND j.job_code <> 'CLINICAL_DEPARTMENT_HEAD'
          AND NOT (j.job_code='PHYSICIAN_STATISTICIAN' AND p.name <> j.job_nameru)
          AND NOT (j.job_code='EXPERT_PHYSICIAN' AND p.name <> j.job_nameru)"""))
    connection.execute(text("""UPDATE public.positions SET
        document_nominative_ru=name,
        translation_status=CASE WHEN NULLIF(btrim(name_kk),'') IS NOT NULL
            THEN 'confirmed' ELSE 'needs_review' END"""))
    connection.execute(text("""UPDATE public.positions p SET record_kind='variant'
        FROM public.position_job_catalog m JOIN public.job_positions_catalog j USING(job_code)
        WHERE m.position_id=p.position_id AND (p.name<>j.job_nameru OR
            (SELECT count(*) FROM public.position_job_catalog x WHERE x.job_code=m.job_code)>1)"""))
    # These names remain addressable records, even when also searchable as aliases.
    connection.execute(text("""UPDATE public.positions p SET record_kind='search_synonym'
        FROM public.position_job_catalog m WHERE m.position_id=p.position_id
        AND ((m.job_code='MEDICAL_STATISTICIAN' AND p.name='Медстатистик')
          OR (m.job_code='ECONOMIST' AND p.name ~ '^экономист[123]$'))"""))
    connection.execute(text("ALTER TABLE public.position_job_catalog ALTER COLUMN position_id TYPE BIGINT"))
    for name, alias in (
        ('сестра-хозяйка', 'сестра хозяйка'),
        ('Процедурная медсестра', 'Медицинская сестра процедурная'),
        ('Процедурная медсестра', 'Процедурная медицинская сестра'),
    ):
        from app.services.position_directory_service import normalize_alias
        connection.execute(text('INSERT INTO public.position_aliases(position_id,alias_text,normalized_alias) '
            'SELECT position_id,:alias,:normalized FROM public.positions WHERE name=:name '
            'ON CONFLICT(normalized_alias) DO NOTHING'),
            {'name': name, 'alias': alias, 'normalized': normalize_alias(alias)})
    connection.execute(text("""CREATE VIEW public.position_directory AS SELECT p.*,m.job_code,
        j.job_nameru AS family_name_ru,j.job_namekk AS family_name_kk,
        j.job_namekk_doc AS family_document_kk,
        p.name AS job_nameru,
        CASE WHEN p.translation_status='confirmed' THEN p.name_kk END AS job_namekk,
        CASE WHEN p.document_form_status='confirmed' THEN p.document_possessive_kk END AS job_namekk_doc
        FROM public.positions p LEFT JOIN public.position_job_catalog m USING(position_id)
        LEFT JOIN public.job_positions_catalog j USING(job_code)"""))


def downgrade(connection):
    # Forms edited after migration are user data. Never drop them automatically.
    raise RuntimeError('Position directory rollback requires an explicit data-preserving plan')
