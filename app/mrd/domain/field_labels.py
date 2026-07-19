"""Human-readable field labels for MRD comparison attributes."""
from __future__ import annotations

ROSTER_FIELD_LABELS: dict[str, str] = {
    "full_name": "ФИО",
    "iin": "ИИН",
    "birth_date": "Дата рождения",
    "department": "Отделение",
    "org_unit_id": "Подразделение",
    "position_raw": "Должность",
    "training_raw": "Обучение",
    "certification_raw": "Медицинская категория",
    "education_raw": "Образование",
    "degree_raw": "Учёная степень",
    "experience_raw": "Стаж",
    "note_raw": "Примечание",
    "__record__": "Запись в эталоне",
    "__conflict__": "Конфликт данных",
}

NORMALIZED_FIELD_LABELS: dict[str, str] = {
    "title": "Название",
    "provider": "Организация",
    "hours": "Часы",
    "start_date": "Дата начала",
    "end_date": "Дата окончания",
    "issue_date": "Дата выдачи",
    "expiry_date": "Дата окончания действия",
    "document_number": "Номер документа",
    "specialty_text": "Специальность",
    "medical_specialty_id": "Специальность",
    "file_url": "Ссылка на файл",
    "record_kind": "Тип записи",
}


def get_field_label(attribute: str, *, record_kind: str | None = None) -> str:
    if attribute in ROSTER_FIELD_LABELS:
        return ROSTER_FIELD_LABELS[attribute]
    if record_kind and record_kind != "roster" and attribute in NORMALIZED_FIELD_LABELS:
        return NORMALIZED_FIELD_LABELS[attribute]
    return NORMALIZED_FIELD_LABELS.get(attribute, attribute)
