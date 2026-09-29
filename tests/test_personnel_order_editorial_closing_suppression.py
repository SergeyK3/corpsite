from app.services.personnel_orders_editorial.mapper import serialize_block


def test_empty_closing_override_is_a_reversible_suppression_marker():
    row = {
        "block_id": 1,
        "locale": "kk",
        "block_type": "closing",
        "generated_text": "Generated closing",
        "override_text": "",
        "review_status": "CURRENT",
        "revision": 1,
    }

    result = serialize_block(row, scope="order", editable=True)

    assert result["suppressed"] is True
    assert result["effective_text"] == ""
    assert result["generated_text"] == "Generated closing"


def test_null_closing_override_restores_generated_text():
    row = {
        "block_id": 1,
        "locale": "kk",
        "block_type": "closing",
        "generated_text": "Generated closing",
        "override_text": None,
        "review_status": "CURRENT",
        "revision": 1,
    }

    result = serialize_block(row, scope="order", editable=True)

    assert result["suppressed"] is False
    assert result["effective_text"] == "Generated closing"
