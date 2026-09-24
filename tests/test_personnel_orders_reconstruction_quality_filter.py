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
