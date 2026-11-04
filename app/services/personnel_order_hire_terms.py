"""Use the existing HIRE employment rate and basis selection in published templates."""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Mapping


def normalize_hire_position_manual_forms(value: Any) -> dict:
    if not isinstance(value, Mapping) or any(type(value.get(locale)) is not bool for locale in ('ru', 'kk')):
        raise ValueError('Некорректные признаки ручных форм должности RU/KK')
    return {locale: value[locale] for locale in ('ru', 'kk')}


def default_hire_basis(locale: str) -> str:
    """Initial form/preview text only; never replace a saved or edited basis."""
    return "жеке өтініші, еңбек шарты" if locale == "kk" else "личное заявление, трудовой договор"


def normalize_hire_basis(value: Any) -> dict:
    if not isinstance(value, Mapping) or any(not isinstance(value.get(locale, ''), str) for locale in ('ru','kk')):
        raise ValueError('Некорректное основание RU/KK')
    result={locale:value.get(locale,'') for locale in ('ru','kk')}
    if 'kk_intentionally_empty' in value and type(value['kk_intentionally_empty']) is not bool:
        raise ValueError('Некорректное основание RU/KK')
    if value.get('kk_intentionally_empty') is True and not result['kk'].strip():result['kk_intentionally_empty']=True
    return result


def normalize_hire_details(value: Any) -> dict:
    """Optional order-only snapshots; no employee or classifier changes."""
    if not isinstance(value, Mapping):
        raise ValueError("Некорректные данные образования и трудового стажа")
    result = {}
    for group, keys in (("education", ("code", "ru", "kk")), ("service_length", ("ru", "kk"))):
        source = value.get(group, {})
        if not isinstance(source, Mapping) or any(not isinstance(source.get(key, ""), str) for key in keys):
            raise ValueError("Некорректные данные образования и трудового стажа")
        result[group] = {key: source.get(key, "") for key in keys}
    if 'service_length_years' in value:
        raw = value['service_length_years']
        if isinstance(raw, bool) or raw is not None and not isinstance(raw, (str, int, float)):
            raise ValueError("Введите неотрицательное количество лет, например 17,3")
        years = '' if raw is None else str(raw).strip().replace(',', '.')
        if years and not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', years):
            raise ValueError("Введите неотрицательное количество лет, например 17,3")
        result['service_length_years'] = re.sub(r'^0+(?=[0-9])', '', years)
    if 'certificate' in value:
        certificate=value['certificate']
        if not isinstance(certificate, Mapping): raise ValueError('Некорректные данные сертификата')
        specialty=certificate.get('specialty')
        if specialty is not None:
            if (not isinstance(specialty,Mapping) or type(specialty.get('medical_specialty_id')) is not int
                or specialty['medical_specialty_id']<=0 or any(not isinstance(specialty.get(key,''),str) for key in ('name_ru','name_kk'))):
                raise ValueError('Выберите медицинскую специальность из справочника')
            specialty={key:specialty.get(key,'') for key in ('medical_specialty_id','name_ru','name_kk')}
        issued=certificate.get('issued_on') or ''
        if not isinstance(issued,str): raise ValueError('Укажите корректную дату выдачи сертификата')
        if issued:
            try:
                if len(issued)!=10: raise ValueError()
                date.fromisoformat(issued)
            except ValueError: raise ValueError('Укажите корректную дату выдачи сертификата') from None
        result['certificate']={'specialty':specialty,'issued_on':issued}
        for key in ('name_ru','name_kk'):
            if key in certificate:
                if not isinstance(certificate[key],str):raise ValueError('Некорректное название специальности сертификата')
                result['certificate'][key]=certificate[key]
    return result


def hire_rate(value: Any) -> float:
    if value is None or isinstance(value, str) and not value.strip():
        raise ValueError("Укажите ставку")
    try:
        result = float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        raise ValueError("Ставка должна быть больше 0 и не больше 2") from None
    if not math.isfinite(result) or not 0 < result <= 2:
        raise ValueError("Ставка должна быть больше 0 и не больше 2")
    return result


def has_hire_basis(payload: Mapping[str, Any]) -> bool:
    if 'hire_basis' in payload:
        basis=payload['hire_basis']
        return (isinstance(basis,Mapping) and isinstance(basis.get('ru'),str) and bool(basis['ru'].strip())
            and (isinstance(basis.get('kk'),str) and bool(basis['kk'].strip()) or basis.get('kk_intentionally_empty') is True))
    entries = payload.get("basis_entries") or []
    if entries:
        return any(isinstance(entry, Mapping) and (
            str(entry.get("other_text") or "").strip() if entry.get("document_type") == "OTHER"
            else entry.get("document_type") and entry.get("basis_id")) for entry in entries)
    if "basis_other_text" in payload:
        return bool(str(payload["basis_other_text"] or "").strip() or payload.get("basis_ids"))
    return bool(payload.get("basis_ids") or isinstance(payload.get("basis"), str) and payload["basis"].strip())


def validate_hire_terms(payload: Mapping[str, Any]) -> float:
    rate = hire_rate(payload.get("employment_rate"))
    if not has_hire_basis(payload):
        raise ValueError("Заполните основание")
    return rate


def hire_basis_text(payload: Mapping[str, Any], locale: str, documents=(), source_locale: str = 'ru') -> str:
    if 'hire_basis' in payload:
        basis=payload['hire_basis']
        return str(basis.get(locale) or '').strip() if isinstance(basis,Mapping) else ''
    legacy_locale='kk' if source_locale=='kk' else 'ru'
    def manual(value):
        return str(value or '').strip() if locale==legacy_locale else ''
    def linked(identifier):
        document = next((row for row in documents if str(row.get("basis_id")) == str(identifier)), {})
        description = document.get("description") or ""
        if isinstance(description, Mapping):
            return str(description.get(locale) or "").strip()
        return manual(description)

    entries = payload.get("basis_entries") or []
    if entries:
        texts = [manual(entry.get("other_text")) if entry.get("document_type") == "OTHER"
                 else linked(entry.get("basis_id")) for entry in entries if isinstance(entry, Mapping)]
    else:
        texts = [linked(identifier) for identifier in payload.get("basis_ids") or []]
        if "basis_other_text" in payload:
            texts.append(manual(payload.get("basis_other_text")))
        elif isinstance(payload.get("basis"), str):
            texts.append(manual(payload["basis"]))
    return "\n".join(value for value in texts if value)
