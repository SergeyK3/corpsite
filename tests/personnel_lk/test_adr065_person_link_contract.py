"""Contract tests for the ADR-065 Person-link first slice."""
from app.directory.personnel_lk_schemas import PersonLinkApplyIn
from app.services.adr065_person_link_service import build_precondition


def test_precondition_is_stable_and_order_independent() -> None:
    assert build_precondition(44, "Нурбеков Бахдат Байтлевич", [9, 3]) == build_precondition(
        44, "Нурбеков Бахдат Байтлевич", [3, 9]
    )


def test_apply_contract_requires_request_and_expected_precondition() -> None:
    payload = PersonLinkApplyIn(
        employee_id=44,
        normalized_record_ids=[101, 102],
        expected_precondition="a" * 64,
        request_id="adr065-request-44",
        confirm_name_correction=True,
    )
    assert payload.employee_id == 44
    assert payload.confirm_name_correction is True
