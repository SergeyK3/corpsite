"""ADR-039 Phase 3F.2 — contract between backend promotion blockers and Review UI labels."""
from __future__ import annotations

from app.services.hr_import_promotion_service import (
    BLOCKER_DOCUMENT_TYPE_UNRESOLVED,
    BLOCKER_EMPLOYEE_REQUIRED,
    BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED,
    BLOCKER_NOT_APPROVED,
    BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT,
    BLOCKER_VALIDATION_MISSING_VALID_UNTIL,
    SKIP_ALREADY_PROMOTED,
    SKIP_DUPLICATE_ACTIVE_DOCUMENT,
)

# Must match corpsite-ui/app/directory/personnel/_lib/normalizedRecordPromotionLabels.ts
EXPECTED_PROMOTION_BLOCKER_LABELS: dict[str, str] = {
    BLOCKER_NOT_APPROVED: "Запись не утверждена",
    BLOCKER_EMPLOYEE_REQUIRED: "Сотрудник не привязан",
    BLOCKER_DOCUMENT_TYPE_UNRESOLVED: "Тип документа не определён",
    BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED: "Медицинская специальность не определена",
    BLOCKER_VALIDATION_MISSING_VALID_UNTIL: "Не указан срок действия",
    BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT: "Не указаны часы или дата выдачи",
}

EXPECTED_PROMOTION_SKIP_REASON_LABELS: dict[str, str] = {
    SKIP_ALREADY_PROMOTED: "Уже промотировано",
    SKIP_DUPLICATE_ACTIVE_DOCUMENT: "Дубликат активного документа",
}

EXPECTED_BLOCKER_PANEL_GROUP_CODES: dict[str, list[str]] = {
    "MEDICAL_SPECIALTY_UNRESOLVED": [BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED],
    "DOCUMENT_TYPE_UNRESOLVED": [BLOCKER_DOCUMENT_TYPE_UNRESOLVED],
    "EMPLOYEE_REQUIRED": [BLOCKER_EMPLOYEE_REQUIRED],
    "VALIDATION": [
        BLOCKER_VALIDATION_MISSING_VALID_UNTIL,
        BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT,
    ],
}


def test_backend_blocker_codes_match_ui_label_contract():
    assert set(EXPECTED_PROMOTION_BLOCKER_LABELS.keys()) == {
        BLOCKER_NOT_APPROVED,
        BLOCKER_EMPLOYEE_REQUIRED,
        BLOCKER_DOCUMENT_TYPE_UNRESOLVED,
        BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED,
        BLOCKER_VALIDATION_MISSING_VALID_UNTIL,
        BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT,
    }
    assert EXPECTED_PROMOTION_BLOCKER_LABELS[BLOCKER_EMPLOYEE_REQUIRED] == "Сотрудник не привязан"


def test_validation_blockers_grouped_for_ui_panel():
    validation_codes = EXPECTED_BLOCKER_PANEL_GROUP_CODES["VALIDATION"]
    assert all(code.startswith("VALIDATION_") for code in validation_codes)
    assert BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED in EXPECTED_BLOCKER_PANEL_GROUP_CODES[
        "MEDICAL_SPECIALTY_UNRESOLVED"
    ]


def test_skip_reason_labels_cover_backend_codes():
    assert set(EXPECTED_PROMOTION_SKIP_REASON_LABELS.keys()) == {
        SKIP_ALREADY_PROMOTED,
        SKIP_DUPLICATE_ACTIVE_DOCUMENT,
    }
