import pytest
from app.services.personnel_order_hire_from_person_service import validate_hire_item_identity
from app.services.personnel_orders_command_service import PersonnelOrderValidationError


@pytest.mark.parametrize("code", ["SERVICE_LENGTH_CHANGE", "EDUCATION_INFORMATION_CHANGE", "PERSONAL_DATA_CHANGE"])
def test_document_orders_accept_explicit_manual_subject_identity(code):
    validate_hire_item_identity(None, item_type_code=code, employee_id=None,
        payload={"subject_mode": "MANUAL", "unresolved_subject": {"full_name": "TEST employee"}})


@pytest.mark.parametrize("code", ["SERVICE_LENGTH_CHANGE", "EDUCATION_INFORMATION_CHANGE", "PERSONAL_DATA_CHANGE", "TRANSFER"])
def test_missing_manual_subject_does_not_bypass_employee_identity(code):
    with pytest.raises(PersonnelOrderValidationError):
        validate_hire_item_identity(None, item_type_code=code, employee_id=None, payload={"subject_mode": "MANUAL"})


def test_other_order_types_still_require_employee_id_even_with_manual_payload():
    with pytest.raises(PersonnelOrderValidationError):
        validate_hire_item_identity(None, item_type_code="TRANSFER", employee_id=None,
            payload={"subject_mode": "MANUAL", "unresolved_subject": {"full_name": "TEST employee"}})
