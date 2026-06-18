"""ADR-039 Phase 3E.1 — contract between backend record_kind and Review UI labels."""
from __future__ import annotations

from app.services.hr_import_normalized_record_service import RECORD_KINDS

# Must match corpsite-ui/app/directory/personnel/_lib/normalizedRecordLabels.ts
EXPECTED_REVIEW_UI_KIND_LABELS: dict[str, str] = {
    "training": "Обучение",
    "certificate": "Сертификат",
    "category": "Категория",
    "education": "Образование",
}

EXPECTED_REVIEW_UI_SUMMARY_LABELS: dict[str, str] = {
    "training": "Обучение",
    "certificate": "Сертификаты",
    "category": "Категории",
    "education": "Образование",
}


def test_backend_record_kinds_match_ui_label_contract():
    assert set(EXPECTED_REVIEW_UI_KIND_LABELS.keys()) == set(RECORD_KINDS)
    assert EXPECTED_REVIEW_UI_KIND_LABELS["education"] == "Образование"
    assert EXPECTED_REVIEW_UI_KIND_LABELS["education"] != "Награда"


def test_summary_labels_use_obrazovanie_not_nagrada():
    assert EXPECTED_REVIEW_UI_SUMMARY_LABELS["education"] == "Образование"
