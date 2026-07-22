"""Additional ADR-059 review polish tests."""
from __future__ import annotations

from app.services.hr_import_review_exception_detail_service import _build_row_import_review_override
from app.services.hr_import_training_date_quality_service import (
    _effective_roster_training_fields,
    assess_normalized_record_date_quality,
)


def test_build_row_import_review_override_is_sparse() -> None:
    import app.services.hr_import_review_exception_detail_service as module

    original_load = module.load_row_payload

    def fake_load(_conn, batch_id, row_id):
        return {
            "payload": {
                "position_raw": "химиоьерапевт",
                "department": "Химиотерапия",
            },
            "metadata": {},
        }

    module.load_row_payload = fake_load
    try:
        sparse = _build_row_import_review_override(
            object(),
            1,
            10,
            {"position_raw": "химиотерапевт", "department": "Химиотерапия"},
        )
    finally:
        module.load_row_payload = original_load

    assert sparse == {"position_raw": "химиотерапевт"}


def test_effective_roster_training_fields_use_override() -> None:
    row = {
        "normalized_payload": {
            "training_raw": "2022",
            "education_raw": "",
            "metadata": {
                "import_review_override": {
                    "training_raw": "15.03.2020 — курс повышения квалификации",
                }
            },
        }
    }
    training_raw, _education_raw = _effective_roster_training_fields(row)
    assert "15.03.2020" in training_raw
    assert (
        assess_normalized_record_date_quality(
            {
                "record_kind": "training",
                "title": "Курс",
                "start_date": "2020-03-15",
                "end_date": "2020-03-20",
            }
        )
        == []
    )


def test_quality_report_dedupes_normalized_record_id() -> None:
    rows = [
        {
            "normalized_record_id": 5,
            "record_kind": "training",
            "title": "A",
            "issue_date": "2022-01-01",
        },
        {
            "normalized_record_id": 5,
            "record_kind": "training",
            "title": "A",
            "issue_date": "2022-01-01",
        },
    ]
    seen: set[int] = set()
    count = 0
    for row in rows:
        normalized_record_id = int(row["normalized_record_id"])
        if normalized_record_id in seen:
            continue
        if assess_normalized_record_date_quality(row):
            seen.add(normalized_record_id)
            count += 1
    assert count == 1
