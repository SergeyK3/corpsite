"""Confirmed RU accusative only: there is no established RU accusative rule."""
from collections.abc import Mapping


def confirmed_transfer_accusative(payload):
    if not isinstance(payload, Mapping):
        return ''
    employee = payload.get('employee')
    employee = employee if isinstance(employee, Mapping) else {}
    for source, key in (
        (payload.get('document_forms_ru'), 'employee_full_name_accusative_ru'),
        (payload, 'employee_full_name_accusative_ru'),
        (employee.get('document_forms_ru'), 'employee_full_name_accusative_ru'),
        (employee.get('name'), 'full_name_accusative_ru'),
        (employee, 'employee_full_name_accusative_ru'),
    ):
        value = source.get(key) if isinstance(source, Mapping) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''
