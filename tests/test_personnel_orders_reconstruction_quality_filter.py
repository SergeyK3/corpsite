from app.services.personnel_orders_query_service import _build_list_filters


def _filters(quality: str, *, q: str | None = None) -> tuple[list[str], dict]:
    return _build_list_filters(
        status=None,
        order_type_code=None,
        date_from=None,
        date_to=None,
        employee_id=None,
        org_unit_id=None,
        q=q,
        reconstruction_quality=quality,
    )


def test_reconstructed_pilot_filter_accepts_every_nonempty_pilot_key_and_search():
    where_parts, params = _filters("RECONSTRUCTED_PILOT", q="891")
    sql = "\n".join(where_parts)

    assert "reconstruction_pilot' IS NOT NULL" in sql
    assert "BTRIM(po.storage_json ->> 'reconstruction_pilot') <> ''" in sql
    assert "personnel-orders-reconstruction-pilot-01" not in sql
    assert params["q_pattern"] == "%891%"


def test_docx_review_filter_remains_independent_of_pilot_key():
    where_parts, _ = _filters("NEEDS_DOCX_REVIEW")
    sql = "\n".join(where_parts)

    assert "reconstruction_status' = 'NEEDS_DOCX_REVIEW'" in sql
    assert "reconstruction_pilot" not in sql


def test_working_scope_is_default_and_excludes_confirmed_and_legacy_technical_orders():
    where_parts, _ = _build_list_filters(
        status=None, order_type_code=None, date_from=None, date_to=None,
        employee_id=77, org_unit_id=None, q=None, reconstruction_quality=None,
    )
    sql = "\n".join(where_parts)
    assert "technical_record" in sql
    assert "record_quality" in sql
    assert "PERSONNEL-IMPORT-%" in sql
    assert "CSV-PILOT-%" in sql
    assert "employee_id = :employee_id" in sql


def test_technical_scope_includes_canonical_and_legacy_classification_only():
    where_parts, _ = _build_list_filters(
        status=None, order_type_code=None, date_from=None, date_to=None,
        employee_id=None, org_unit_id=None, q=None, record_quality="TECHNICAL", reconstruction_quality=None,
    )
    sql = "\n".join(where_parts)
    assert "technical_record" in sql
    assert "PERSONNEL-IMPORT-%" in sql
    assert "NOT (COALESCE(po.storage_json" in sql


def test_all_scope_does_not_add_technical_visibility_clause():
    where_parts, _ = _build_list_filters(
        status=None, order_type_code=None, date_from=None, date_to=None,
        employee_id=None, org_unit_id=None, q=None, record_quality="ALL", reconstruction_quality=None,
    )
    assert "technical_record" not in "\n".join(where_parts)
