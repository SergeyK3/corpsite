"""Resolve an assignment once when authoring; never refresh saved order text on reads."""
from datetime import date
from sqlalchemy import text


def employee_catalog_context(conn, employee_id, effective_date=None):
    catalog_ready = conn.execute(text("""SELECT
        to_regclass('public.job_positions_catalog') IS NOT NULL
        AND to_regclass('public.position_job_catalog') IS NOT NULL""")).scalar_one()
    catalog_join = """LEFT JOIN public.position_job_catalog m ON m.position_id=pa.position_id
        LEFT JOIN public.job_positions_catalog j ON j.job_code=m.job_code""" if catalog_ready else ""
    catalog_fields = """j.job_code, j.job_nameru AS position_title_ru,
        j.job_namekk AS position_title_kk,
        COALESCE(j.job_nameru, NULLIF(to_jsonb(p)->>'document_nominative_ru', ''), p.name) AS position_ru,
        COALESCE(j.job_namekk_doc, NULLIF(to_jsonb(p)->>'document_possessive_kk', '')) AS position_kk""" if catalog_ready else """NULL AS job_code,
        NULL AS position_title_ru, NULL AS position_title_kk,
        COALESCE(NULLIF(to_jsonb(p)->>'document_nominative_ru', ''), p.name) AS position_ru,
        NULLIF(to_jsonb(p)->>'document_possessive_kk', '') AS position_kk"""
    position_name = "COALESCE(j.job_nameru, p.name)" if catalog_ready else "p.name"
    row = conn.execute(text(f"""
        SELECT e.full_name, pa.assignment_id,
               {position_name} AS position_name,
               {catalog_fields}, ou.name AS org_unit_name,
               NULLIF(to_jsonb(ou)->>'name_kk', '') AS org_unit_title_kk,
               NULLIF(to_jsonb(ou)->>'name_kk', '') AS org_unit_name_kk,
               NULLIF(to_jsonb(ou)->>'document_genitive_kk', '') AS org_unit_document_genitive_kk
        FROM public.employees e
        LEFT JOIN LATERAL (
            SELECT a.assignment_id, a.position_id, a.org_unit_id
            FROM public.person_assignments a
            WHERE a.person_id=e.person_id AND a.active_flag IS TRUE
              AND a.is_primary IS TRUE AND a.lifecycle_status='active'
              AND a.start_date <= :effective_date
              AND (a.end_date IS NULL OR a.end_date >= :effective_date)
            ORDER BY a.start_date DESC, a.assignment_id DESC LIMIT 1
        ) pa ON TRUE
        LEFT JOIN public.positions p ON p.position_id=pa.position_id
        {catalog_join}
        LEFT JOIN public.org_units ou ON ou.unit_id=pa.org_unit_id
        WHERE e.employee_id=:employee_id
    """), {"employee_id": employee_id, "effective_date": effective_date or date.today()}).mappings().first()
    return dict(row) if row else None


def snapshot_catalog_forms(payload, context):
    """Only fill absent forms. Explicit blanks and saved/manual values are authoritative."""
    result = dict(payload)
    if not context:
        return result
    for locale, defaults in {
        "ru": {"position_document_nominative_ru": context.get("position_ru")},
        "kk": {"position_document_possessive_kk": context.get("position_kk"),
               "org_unit_document_genitive_kk": context.get("org_unit_document_genitive_kk")},
    }.items():
        key = f"document_forms_{locale}"
        forms = dict(result.get(key) or {})
        for field, value in defaults.items():
            if value and field not in forms:
                forms[field] = value
        if forms:
            result[key] = forms
    if context.get("job_code"):
        result.setdefault("job_code", context["job_code"])
        for key in ("position_title_ru", "position_title_kk", "org_unit_title_kk"):
            if context.get(key):
                result.setdefault(key, context[key])
    for key, source in (("source_position_name", "position_name"), ("source_org_unit_name", "org_unit_name")):
        if context.get(source):
            result.setdefault(key, context[source])
    return result
