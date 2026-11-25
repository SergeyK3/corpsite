"""The application print endpoint must not couple Kazakh to Russian inflection."""

from datetime import date
from decimal import Decimal

import pytest

from app.personnel_applications.application import electronic_hire_service as hire


def _application(position_ru: str, position_kk: str) -> dict:
    return {
        "position_resolution": "catalog",
        "position_ru": position_ru,
        "position_kk": position_kk,
        "position_document_ru": position_ru,
        "position_document_kk": None,
        "org_unit_ru": "Отдел кадров",
        "org_unit_kk": "Кадр бөлімі",
        "full_name": "Тестовый кандидат",
        "intended_employment_rate": Decimal("1"),
        "planned_start_date": date(2026, 11, 24),
        "application_received_at": date(2026, 11, 23),
    }


def test_unknown_russian_form_does_not_block_kazakh(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _application("неопределённая роль", "белгісіз лауазым")
    monkeypatch.setattr(hire, "load_electronic_hire", lambda _conn, _id: dict(app))

    kk = hire.render_application(None, 999, locale="kk")
    assert set(kk) == {"kk"}
    assert "белгісіз лауазым" in kk["kk"]

    with pytest.raises(hire.ElectronicHireError) as error:
        hire.render_application(None, 999, locale="ru")
    assert error.value.code == "POSITION_FORM_REQUIRED"
    with pytest.raises(hire.ElectronicHireError):
        hire.render_application(None, 999)


def test_archivist_form_and_default_bilingual_response(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _application("Архивариус", "Мұрағатшы")
    monkeypatch.setattr(hire, "load_electronic_hire", lambda _conn, _id: dict(app))

    document = hire.render_application(None, 231)
    assert set(document) == {"ru", "kk"}
    assert "на должность архивариуса" in document["ru"]
    assert "Мұрағатшы".lower() in document["kk"]
