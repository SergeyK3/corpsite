from datetime import date

from app.services.hr_import_training_review_service import (
    calculate_year_only_training_dates,
    training_review_hours_summary,
)
from app.services.hr_import_document_parser import split_numbered_training_fragments


def test_split_preview_endpoint_resolves_selected_staging_record_without_name_error(monkeypatch):
    """Regression for the route's SQL ``text`` import, before calling preview."""
    from app.directory import hr_import_routes as routes

    class ScalarResult:
        def scalar_one_or_none(self):
            return 456

    class Conn:
        def execute(self, statement, params):
            assert "normalized_record_id" in str(statement)
            assert params == {"record_id": 41246}
            return ScalarResult()

    expected = {"record_id": 41246, "suggested_boundary": 10, "fragments": []}
    monkeypatch.setattr(routes, "_training_review_scope", lambda _user: {"privileged": True})
    monkeypatch.setattr(routes, "_require_training_review_employee_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, "_with_conn", lambda fn, **kwargs: fn(Conn(), **kwargs))
    monkeypatch.setattr(routes, "training_split_preview", lambda _conn, *, record_id: expected if record_id == 41246 else None)

    assert routes.get_import_training_review_split_preview(41246, {"user_id": 361}) == expected


def _record(*, status: str, end_date: str | None, hours: int | None):
    return {
        "hours": hours,
        "training_review": {
            "status": status,
            "dates": {"end_date": end_date},
        },
    }


def test_year_only_training_dates_use_january_monday_and_working_days():
    start, end = calculate_year_only_training_dates(2024, 8)
    assert (start, end) == (date(2024, 1, 1), date(2024, 1, 1))

    start, end = calculate_year_only_training_dates(2024, 16)
    assert (start, end) == (date(2024, 1, 1), date(2024, 1, 2))

    start, end = calculate_year_only_training_dates(2024, 54)
    assert (start, end) == (date(2024, 1, 1), date(2024, 1, 9))

    start, end = calculate_year_only_training_dates(2024, 120)
    assert (start, end) == (date(2024, 1, 1), date(2024, 1, 19))


def test_training_review_summary_separates_confirmed_pending_rejected_and_proposed():
    summary = training_review_hours_summary(
        [
            _record(status="CHECKED", end_date="2024-01-01", hours=120),
            _record(status="CHECKED", end_date="2024-02-01", hours=24),
            _record(status="REQUIRES_REVIEW", end_date="2024-03-01", hours=16),
            _record(status="REJECTED", end_date="2024-04-01", hours=100),
            _record(status="EMPLOYEE_PROPOSED", end_date="2024-05-01", hours=100),
        ],
        as_of=date(2026, 9, 12),
    )

    assert summary["confirmed_hours_last_5y"] == 144
    assert summary["preliminary_hours_last_5y"] == 160
    assert summary["hours_missing"] == 0
    assert summary["nearest_exclusion_date"] == "2029-01-02"
    assert summary["hours_after_nearest_exclusion"] == 24
    assert summary["norm_valid_through"] == "2029-01-01"


def test_training_splitter_uses_only_reliable_consecutive_ordinals():
    source = "1. Course A, 16 h., 2024г.2. Course B, 8 h., 2025г.3. Course C, 54 h."
    fragments = split_numbered_training_fragments(source)
    assert [item.ordinal for item in fragments] == [1, 2, 3]
    assert "".join(item.raw_text for item in fragments) == source


def test_training_splitter_accepts_year_adjacent_ordinal_but_not_numbers_in_data():
    source = "8. Course A, 8 h., 2024г.9. Course B, 120/4, 2025г."
    fragments = split_numbered_training_fragments(source)
    assert [item.ordinal for item in fragments] == [8, 9]
    assert fragments[1].start_offset == source.index("9.")
    for unsafe in ("120/4; 16 h.; 2024 г.; 12.09.2024; certificate 42.", "1. Course A 3. Course B"):
        assert len(split_numbered_training_fragments(unsafe)) == 1
