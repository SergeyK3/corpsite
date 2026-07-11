"""Pure text generators for personnel order editorial blocks (WP-PO-EDIT-002).

No React, HTML, or PDF — plain bilingual templates ported from the print spike.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from app.db.models.personnel_orders import (
    BASIS_TYPE_COMMISSION_PROTOCOL,
    BASIS_TYPE_COURT_ACT,
    BASIS_TYPE_MANAGEMENT_SUBMISSION,
    BASIS_TYPE_MEDICAL_CONCLUSION,
    BASIS_TYPE_MEMO,
    BASIS_TYPE_OTHER,
    BASIS_TYPE_PERSONAL_APPLICATION,
    ITEM_BLOCK_TYPE_BASIS,
    ITEM_BLOCK_TYPE_BODY,
    ORDER_BLOCK_TYPE_CLOSING,
    ORDER_BLOCK_TYPE_PREAMBLE,
    ORDER_BLOCK_TYPE_TITLE,
    ORDER_TYPE_COMPOSITE,
    ORDER_TYPE_CONCURRENT_DUTY_END,
    ORDER_TYPE_CONCURRENT_DUTY_START,
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_TRANSFER,
)
from app.services.personnel_orders_editorial.constants import (
    GENERATOR_KEY_ITEM_BASIS,
    GENERATOR_KEY_ITEM_BODY,
    GENERATOR_KEY_ORDER_CLOSING,
    GENERATOR_KEY_ORDER_PREAMBLE,
    GENERATOR_KEY_ORDER_TITLE,
    GENERATOR_VERSION,
)
from app.services.personnel_orders_editorial.fingerprint import compute_fingerprint

DOCUMENT_TITLES: Dict[str, Dict[str, str]] = {
    ORDER_TYPE_HIRE: {
        "kk": "Жұмысқа қабылдау туралы",
        "ru": "О приёме на работу",
    },
    ORDER_TYPE_TRANSFER: {
        "kk": "Ауыстыру туралы",
        "ru": "О переводе",
    },
    ORDER_TYPE_TERMINATION: {
        "kk": "Жұмыстан босату туралы",
        "ru": "Об увольнении",
    },
    ORDER_TYPE_CONCURRENT_DUTY_START: {
        "kk": "Қоса атқаруды белгілеу туралы",
        "ru": "Об установлении совмещения",
    },
    ORDER_TYPE_CONCURRENT_DUTY_END: {
        "kk": "Қоса атқаруды тоқтату туралы",
        "ru": "О прекращении совмещения",
    },
    ORDER_TYPE_COMPOSITE: {
        "kk": "Кадрлық өзгерістер туралы",
        "ru": "О кадровых изменениях",
    },
}

_RU_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
_KK_MONTHS = (
    "қаңтар",
    "ақпан",
    "наурыз",
    "сәуір",
    "мамыр",
    "маусым",
    "шілде",
    "тамыз",
    "қыркүйек",
    "қазан",
    "қараша",
    "желтоқсан",
)


def _dash(value: Any) -> str:
    text = str(value or "").strip()
    return text or "—"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _locale(locale: str) -> str:
    normalized = str(locale or "").strip().lower()
    if normalized not in {"kk", "ru"}:
        raise ValueError(f"Unsupported locale: {locale}")
    return normalized


def _format_date(value: Any, locale: str) -> str:
    raw = _clean(value)
    if not raw:
        return "—"
    # Accept YYYY-MM-DD or date/datetime iso strings.
    match = None
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        try:
            year = int(raw[0:4])
            month = int(raw[5:7])
            day = int(raw[8:10])
            if 1 <= month <= 12 and 1 <= day <= 31:
                match = (year, month, day)
        except ValueError:
            match = None
    if match is None:
        return raw
    year, month, day = match
    if locale == "kk":
        return f"{year} жылғы {day} {_KK_MONTHS[month - 1]}"
    return f"{day} {_RU_MONTHS[month - 1]} {year} года"


def _format_rate_value(rate: Any) -> str:
    if rate is None or rate == "":
        return "—"
    try:
        if isinstance(rate, bool):
            raise ValueError
        numeric = float(str(rate).replace(",", "."))
    except (TypeError, ValueError):
        raw = _clean(rate)
        return raw or "—"
    if numeric == int(numeric):
        return f"{int(numeric)},0"
    text = f"{numeric:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _format_rate(rate: Any, locale: str) -> str:
    formatted = _format_rate_value(rate)
    if formatted == "—":
        return formatted
    unit = "мөлшерлеме" if locale == "kk" else "ставки"
    return f"{formatted} {unit}"


def _localized_name(value: Any, locale: str) -> str:
    if isinstance(value, Mapping):
        preferred = _clean(value.get(locale))
        if preferred:
            return preferred
        for key in ("kk", "ru", "name"):
            fallback = _clean(value.get(key))
            if fallback:
                return fallback
        return "—"
    return _dash(value)


def _result(
    *,
    generated_text: str,
    generator_key: str,
    fingerprint_payload: Dict[str, Any],
) -> Dict[str, str]:
    payload = dict(fingerprint_payload)
    payload["generator_key"] = generator_key
    payload["generator_version"] = GENERATOR_VERSION
    return {
        "generated_text": generated_text,
        "generator_key": generator_key,
        "generator_version": GENERATOR_VERSION,
        "source_fingerprint": compute_fingerprint(payload),
    }


def generate_order_block(
    block_type: str,
    locale: str,
    order_ctx: Mapping[str, Any],
) -> Dict[str, str]:
    """Generate an order-level block (title / preamble / closing)."""
    lang = _locale(locale)
    normalized_type = str(block_type or "").strip().lower()
    order_type = str(order_ctx.get("order_type_code") or "").strip().upper()
    legal_basis = _clean(order_ctx.get("legal_basis_article"))

    if normalized_type == ORDER_BLOCK_TYPE_TITLE:
        titles = DOCUMENT_TITLES.get(order_type) or DOCUMENT_TITLES[ORDER_TYPE_COMPOSITE]
        text = titles.get(lang) or titles["ru"]
        return _result(
            generated_text=text,
            generator_key=GENERATOR_KEY_ORDER_TITLE,
            fingerprint_payload={
                "block_type": ORDER_BLOCK_TYPE_TITLE,
                "locale": lang,
                "order_type_code": order_type or None,
            },
        )

    if normalized_type == ORDER_BLOCK_TYPE_PREAMBLE:
        if lang == "kk":
            if legal_basis:
                text = (
                    f"Қазақстан Республикасының Еңбек кодексінің {legal_basis} "
                    f"бабына сәйкес БҰЙЫРАМЫН:"
                )
            else:
                text = "Қазақстан Республикасының Еңбек кодексіне сәйкес БҰЙЫРАМЫН:"
        else:
            if legal_basis:
                text = (
                    f"В соответствии со статьёй {legal_basis} Трудового кодекса "
                    f"Республики Казахстан ПРИКАЗЫВАЮ:"
                )
            else:
                text = (
                    "В соответствии с Трудовым кодексом Республики Казахстан ПРИКАЗЫВАЮ:"
                )
        return _result(
            generated_text=text,
            generator_key=GENERATOR_KEY_ORDER_PREAMBLE,
            fingerprint_payload={
                "block_type": ORDER_BLOCK_TYPE_PREAMBLE,
                "locale": lang,
                "legal_basis_article": legal_basis or None,
            },
        )

    if normalized_type == ORDER_BLOCK_TYPE_CLOSING:
        # Minimal closing is acceptable for MVP.
        text = ""
        return _result(
            generated_text=text,
            generator_key=GENERATOR_KEY_ORDER_CLOSING,
            fingerprint_payload={
                "block_type": ORDER_BLOCK_TYPE_CLOSING,
                "locale": lang,
            },
        )

    raise ValueError(f"Unsupported order block_type: {block_type}")


def generate_item_body(locale: str, item_ctx: Mapping[str, Any]) -> Dict[str, str]:
    """Generate item body text (ported from personnelOrderPrintItemText.ts)."""
    lang = _locale(locale)
    item_type = str(item_ctx.get("item_type_code") or "").strip().upper()
    employee_name = item_ctx.get("employee_name")
    effective_date = item_ctx.get("effective_date")
    org_unit_name = item_ctx.get("org_unit_name")
    position_name = item_ctx.get("position_name")
    to_org_unit_name = item_ctx.get("to_org_unit_name")
    to_position_name = item_ctx.get("to_position_name")
    rate = item_ctx.get("rate")
    to_rate = item_ctx.get("to_rate")
    concurrent_rate = item_ctx.get("concurrent_rate")
    remaining_rate = item_ctx.get("remaining_rate")
    total_rate = item_ctx.get("total_rate")
    termination_reason = item_ctx.get("termination_reason")

    fio = _dash(employee_name)
    date = _format_date(effective_date, lang)

    if item_type == ORDER_TYPE_HIRE:
        org = _localized_name(org_unit_name, lang)
        position = _localized_name(position_name, lang)
        rate_value = _format_rate_value(rate)
        if lang == "kk":
            text = (
                f"{fio} «{org}» бөлімшесіне «{position}» лауазымына "
                f"{rate_value} мөлшерлемесінде {date} бастап жұмысқа қабылдансын."
            )
        else:
            text = (
                f"Принять на работу {fio} в подразделение «{org}» на должность "
                f"«{position}» со ставкой {rate_value} с {date}."
            )
    elif item_type == ORDER_TYPE_TRANSFER:
        org = _localized_name(to_org_unit_name or org_unit_name, lang)
        position = _localized_name(to_position_name or position_name, lang)
        rate_value = (
            _format_rate_value(to_rate)
            if to_rate is not None and to_rate != ""
            else None
        )
        if lang == "kk":
            rate_part = f", {rate_value} мөлшерлемесінде" if rate_value else ""
            text = (
                f"{fio} «{org}» бөлімшесіне «{position}» лауазымына"
                f"{rate_part} {date} бастап ауыстырылсын."
            )
        else:
            rate_part = f" со ставкой {rate_value}" if rate_value else ""
            text = (
                f"Перевести {fio} в подразделение «{org}» на должность "
                f"«{position}»{rate_part} с {date}."
            )
    elif item_type == ORDER_TYPE_TERMINATION:
        reason = _clean(termination_reason) or None
        if lang == "kk":
            reason_part = f" Негіздеме: {reason}." if reason else ""
            text = f"{fio} {date} бастап жұмыстан босатылсын.{reason_part}"
        else:
            reason_part = f" Основание: {reason}." if reason else ""
            text = f"Уволить {fio} с {date}.{reason_part}"
    elif item_type == ORDER_TYPE_CONCURRENT_DUTY_START:
        concurrent_value = _format_rate_value(concurrent_rate)
        total = (
            _format_rate(total_rate, lang)
            if total_rate is not None and total_rate != ""
            else None
        )
        if lang == "kk":
            total_part = f" Жалпы мөлшерлеме: {total}." if total else ""
            text = (
                f"{fio} үшін қоса атқару {concurrent_value} мөлшерлемесінде "
                f"{date} бастап белгіленсін.{total_part}"
            )
        else:
            total_part = f" Итоговая ставка: {total}." if total else ""
            text = (
                f"Установить {fio} совмещение в размере {concurrent_value} ставки "
                f"с {date}.{total_part}"
            )
    elif item_type == ORDER_TYPE_CONCURRENT_DUTY_END:
        remaining = (
            _format_rate(remaining_rate, lang)
            if remaining_rate is not None and remaining_rate != ""
            else None
        )
        concurrent = (
            _format_rate(concurrent_rate, lang)
            if concurrent_rate is not None and concurrent_rate != ""
            else None
        )
        if lang == "kk":
            rem = f" Қалған мөлшерлеме: {remaining}." if remaining else ""
            rem_concurrent = f" Алынатын мөлшерлеме: {concurrent}." if concurrent else ""
            text = (
                f"{fio} үшін қоса атқару {date} бастап тоқтатылсын."
                f"{rem}{rem_concurrent}"
            )
        else:
            rem = f" Остающаяся ставка: {remaining}." if remaining else ""
            rem_concurrent = f" Снимаемая ставка: {concurrent}." if concurrent else ""
            text = f"Прекратить совмещение для {fio} с {date}.{rem}{rem_concurrent}"
    else:
        if lang == "kk":
            text = f"{fio}, күні {date}."
        else:
            text = f"{fio}, дата {date}."

    return _result(
        generated_text=text,
        generator_key=GENERATOR_KEY_ITEM_BODY,
        fingerprint_payload={
            "block_type": ITEM_BLOCK_TYPE_BODY,
            "locale": lang,
            "item_type_code": item_type or None,
            "employee_name": _clean(employee_name) or None,
            "effective_date": _clean(effective_date) or None,
            "org_unit_name": org_unit_name if org_unit_name not in (None, "") else None,
            "position_name": position_name if position_name not in (None, "") else None,
            "to_org_unit_name": to_org_unit_name if to_org_unit_name not in (None, "") else None,
            "to_position_name": to_position_name if to_position_name not in (None, "") else None,
            "rate": rate if rate not in (None, "") else None,
            "to_rate": to_rate if to_rate not in (None, "") else None,
            "concurrent_rate": concurrent_rate if concurrent_rate not in (None, "") else None,
            "remaining_rate": remaining_rate if remaining_rate not in (None, "") else None,
            "total_rate": total_rate if total_rate not in (None, "") else None,
            "termination_reason": _clean(termination_reason) or None,
        },
    )


def generate_basis_text(locale: str, basis_fact: Mapping[str, Any]) -> Dict[str, str]:
    """Generate basis wording (ported from personnelOrderBasisGenerate.ts)."""
    lang = _locale(locale)
    basis_type = str(basis_fact.get("basis_type") or "").strip().upper()
    name = _clean(basis_fact.get("subject_employee_name"))
    genitive_ru = _clean(basis_fact.get("subject_employee_name_genitive_ru")) or name
    possessive_kk = _clean(basis_fact.get("subject_employee_name_possessive_kk")) or (
        f"{name}тың" if name else ""
    )
    document_number = _clean(basis_fact.get("document_number"))
    document_date = _clean(basis_fact.get("document_date"))
    free_text = _clean(basis_fact.get("free_text"))

    if basis_type == BASIS_TYPE_PERSONAL_APPLICATION:
        if lang == "ru":
            text = (
                "Основание: личное заявление."
                if not genitive_ru
                else f"Основание: личное заявление {genitive_ru}."
            )
        else:
            text = (
                "Негіз: жеке өтініш."
                if not possessive_kk
                else f"Негіз: {possessive_kk} жеке өтініші."
            )
    elif basis_type == BASIS_TYPE_MEMO:
        if lang == "ru":
            text = (
                f"Основание: служебная записка ({name})."
                if name
                else "Основание: служебная записка."
            )
        else:
            text = (
                f"Негіз: қызметтік жазба ({name})."
                if name
                else "Негіз: қызметтік жазба."
            )
    elif basis_type == BASIS_TYPE_MANAGEMENT_SUBMISSION:
        if lang == "ru":
            text = (
                f"Основание: представление ({name})."
                if name
                else "Основание: представление."
            )
        else:
            text = f"Негіз: ұсыным ({name})." if name else "Негіз: ұсыным."
    elif basis_type == BASIS_TYPE_MEDICAL_CONCLUSION:
        text = (
            "Основание: медицинское заключение."
            if lang == "ru"
            else "Негіз: медициналық қорытынды."
        )
    elif basis_type == BASIS_TYPE_COMMISSION_PROTOCOL:
        parts = []
        if document_number:
            parts.append(f"№{document_number}")
        if document_date:
            parts.append(document_date)
        tail = " от ".join(parts) if parts else ""
        if lang == "ru":
            text = (
                f"Основание: протокол комиссии {tail}."
                if tail
                else "Основание: протокол комиссии."
            )
        else:
            text = (
                f"Негіз: комиссия хаттамасы {tail}."
                if tail
                else "Негіз: комиссия хаттамасы."
            )
    elif basis_type == BASIS_TYPE_COURT_ACT:
        text = "Основание: судебный акт." if lang == "ru" else "Негіз: сот актісі."
    else:
        # OTHER / default
        if free_text:
            text = free_text
        else:
            text = "Основание: —" if lang == "ru" else "Негіз: —"
        basis_type = basis_type or BASIS_TYPE_OTHER

    return _result(
        generated_text=text,
        generator_key=GENERATOR_KEY_ITEM_BASIS,
        fingerprint_payload={
            "block_type": ITEM_BLOCK_TYPE_BASIS,
            "locale": lang,
            "basis_type": basis_type or None,
            "subject_employee_id": basis_fact.get("subject_employee_id"),
            "subject_employee_name": name or None,
            "document_date": document_date or None,
            "document_number": document_number or None,
            "free_text": free_text or None,
        },
    )
