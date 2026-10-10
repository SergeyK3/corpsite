"""Document-only vacation substitution, with explicit rate or allowance inputs."""
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from app.services.personnel_order_concurrent_contract import LABELS
from app.services.personnel_orders_editorial.generators import _format_date_from, format_personnel_order_date_numeric

VARIABLES = ("replacement.employee_genitive_ru", "replacement.employee_genitive_kk", "replacement.position_genitive_ru", "replacement.org_unit_genitive_ru", "replacement.position_kk", "replacement.org_unit_kk", "replacement.term", "replacement.work", "allowance.percent", "allowance.basis")
COMMON_RU = "Разрешить {{employee.full_name_dative_ru}} с {{effective_date}} совмещение должности {{concurrent.position_genitive_ru}} {{concurrent.org_unit_genitive_ru}}"
LEAVE_RU = "на время отпуска {{replacement.employee_genitive_ru}}, {{replacement.position_genitive_ru}} {{replacement.org_unit_genitive_ru}}, {{replacement.term}}"
RATE_RU = COMMON_RU + " на {{concurrent.rate}} ставки " + LEAVE_RU + ". (Всего: {{total.rate}} ставки)."
PAY_RU = COMMON_RU + " " + LEAVE_RU + " с доплатой в размере {{allowance.percent}}% от {{allowance.basis}}."
LEAVE_KK = "{{replacement.org_unit_kk}} {{replacement.position_kk}} {{replacement.employee_genitive_kk}} еңбек демалысы кезеңінде {{replacement.term}}"
WORK_KK = "{{employee.full_name_dative_kk}} {{effective_date}} бастап"
RATE_KK = WORK_KK + " " + LEAVE_KK + " {{concurrent.rate}} ставкада {{concurrent.org_unit_kk}} {{concurrent.position_kk}} қызметін қоса атқаруға рұқсат берілсін. (Барлығы: {{total.rate}} ставка)."
PAY_KK = WORK_KK + " " + LEAVE_KK + " {{concurrent.org_unit_kk}} {{concurrent.position_kk}} қызметін қоса атқаруға рұқсат берілсін және {{allowance.basis}} {{allowance.percent}}% мөлшерінде қосымша ақы белгіленсін."
OPTIONAL_PAY_RU = "Разрешить {{employee.full_name_dative_ru}} с {{effective_date}} {{replacement.work}} " + LEAVE_RU + " с доплатой в размере {{allowance.percent}}% от {{allowance.basis}}."
OPTIONAL_PAY_KK = WORK_KK + " " + LEAVE_KK + " {{replacement.work}} рұқсат берілсін және {{allowance.basis}} {{allowance.percent}}% мөлшерінде қосымша ақы белгіленсін."


def optional_placement(texts):
    from app.services.personnel_order_service_area_contract import enabled
    if enabled(texts):return True
    return variant(texts) == "PAY" and all(re.search(r"\{\{\s*replacement\.work\s*\}\}", str(texts.get("body_template_" + locale) or "")) for locale in ("ru", "kk"))


def variant(texts):
    body = " ".join(str(texts.get(k) or "") for k in ("body_template_ru", "body_template_kk"))
    return ("PAY" if re.search(r"\{\{\s*allowance\.percent\s*\}\}", body) else "RATE") if re.search(r"\{\{\s*replacement\.", body) else None


def validate_bodies(texts):
    from app.services.personnel_order_service_area_contract import enabled,validate_bodies as validate_area
    if enabled(texts):return validate_area(texts)
    mode = variant(texts)
    if not mode:
        return
    for locale in ("ru", "kk"):
        key = "body_template_" + locale
        tokens = set(re.findall(r"\{\{\s*([\w.]+)\s*\}\}", texts[key]))
        required = {"employee.full_name_dative_" + locale, "effective_date", "replacement.employee_genitive_" + locale, "replacement.term"}
        required.update({"replacement.position_genitive_ru", "replacement.org_unit_genitive_ru"} if locale == "ru" else {"replacement.position_kk", "replacement.org_unit_kk"})
        required.update({"replacement.work"} if optional_placement(texts) else {"concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru"} if locale == "ru" else {"concurrent.position_kk", "concurrent.org_unit_kk"})
        required.update({"concurrent.rate", "total.rate"} if mode == "RATE" else {"allowance.percent", "allowance.basis"})
        if required - tokens:
            raise ValueError(f"{key}: отсутствуют подстановки замещения: " + ", ".join(sorted(required - tokens)))
        if mode == "PAY" and tokens & {"concurrent.rate", "total.rate"}:
            raise ValueError("Вариант с доплатой не должен содержать ставки.")


def number(value, label, *, positive=True, maximum=None):
    try:
        result = Decimal(str(value).replace(",", "."))
    except (ValueError, InvalidOperation):
        raise ValueError(f"{label}: укажите число.") from None
    if not result.is_finite() or (positive and result <= 0) or (maximum is not None and result > maximum):
        raise ValueError(f"{label}: недопустимое значение.")
    return result


def decimal_text(value, *, fractional=False):
    text = format(value.normalize(), "f")
    if fractional and "." not in text:
        text += ".0"
    return text.replace(".", ",")


def replacement_values(concurrent, replacement, effective_date, mode=None, *, optional_placement=False):
    concurrent = concurrent if isinstance(concurrent, Mapping) else {}
    replacement = replacement if isinstance(replacement, Mapping) else {}
    mode = mode or replacement.get("mode")
    if mode not in {"RATE", "PAY"}:
        raise ValueError("Выберите вариант замещения: дополнительная ставка или доплата.")
    labels = {k: v for k, v in LABELS.items() if k not in {"rate", "total_rate"}}
    if mode == "PAY" and optional_placement:
        for key in ("position_ru", "position_kk", "org_unit_ru", "org_unit_kk", "position_genitive_ru", "org_unit_genitive_ru"):
            labels.pop(key, None)
        for nominal, form in (("position_ru", "position_genitive_ru"), ("org_unit_ru", "org_unit_genitive_ru")):
            if str(concurrent.get(nominal) or "").strip(): labels[form] = LABELS[form]
    missing = [label for key, label in labels.items() if not str(concurrent.get(key) or "").strip()]
    replaced_labels = {"employee_name_ru": "замещаемый сотрудник (RU)", "employee_name_kk": "замещаемый сотрудник (KK)", "employee_genitive_ru": "ФИО замещаемого в родительном падеже (RU)", "employee_genitive_kk": "ФИО замещаемого в родительном падеже (KK)", "position_ru": "должность замещаемого (RU)", "org_unit_ru": "подразделение замещаемого (RU)", "position_genitive_ru": "должность замещаемого в родительном падеже (RU)", "org_unit_genitive_ru": "подразделение замещаемого в родительном падеже (RU)", "position_kk": "должность замещаемого для текста (KK)", "org_unit_kk": "подразделение замещаемого для текста (KK)"}
    missing += [label for key, label in replaced_labels.items() if not str(replacement.get(key) or "").strip()]
    if missing:
        raise ValueError("Заполните данные замещения: " + ", ".join(missing) + ".")
    try:
        start = date.fromisoformat(str(effective_date))
    except ValueError:
        raise ValueError("Укажите дату начала замещения.") from None
    term = replacement.get("term_type")
    if term == "DATE":
        try:
            end = date.fromisoformat(str(replacement.get("end_date")))
        except ValueError:
            raise ValueError("Укажите дату окончания замещения.") from None
        if end < start:
            raise ValueError("Дата окончания замещения раньше даты начала.")
        months_to = ("қаңтарға", "ақпанға", "наурызға", "сәуірге", "мамырға", "маусымға", "шілдеге", "тамызға", "қыркүйекке", "қазанға", "қарашаға", "желтоқсанға")
        term_ru = "по " + end.strftime("%d.%m.%Y") + " включительно"
        term_kk = f"{end.year} жылғы {end.day} {months_to[end.month-1]} дейін"
    elif term == "UNTIL_RETURN":
        term_ru = "до выхода замещаемого работника из отпуска"
        term_kk = "орны алмастырылатын қызметкердің еңбек демалысынан жұмысқа шығуына дейін"
    else:
        raise ValueError("Укажите срок замещения: дата окончания или до выхода работника из отпуска.")
    result = {"employee.full_name_dative_ru": str(concurrent["employee_dative_ru"]).strip(), "employee.full_name_dative_kk": str(concurrent["employee_dative_kk"]).strip(), "effective_date.ru": format_personnel_order_date_numeric(start), "effective_date.kk": _format_date_from(start, "kk"), "replacement.term.ru": term_ru, "replacement.term.kk": term_kk, "basis.ru": str(concurrent["basis_ru"]).strip(), "basis.kk": str(concurrent["basis_kk"]).strip()}
    result.update({"concurrent." + key: str(concurrent.get(key) or "").strip() for key in ("position_genitive_ru", "org_unit_genitive_ru", "position_kk", "org_unit_kk")})
    result.update({"replacement." + key: str(replacement[key]).strip() for key in ("employee_genitive_ru", "employee_genitive_kk", "position_genitive_ru", "org_unit_genitive_ru", "position_kk", "org_unit_kk")})
    if mode == "RATE":
        rate, total = (number(concurrent.get(key), label) for key, label in (("rate", "Дополнительная ставка"), ("total_rate", "Суммарная ставка")))
        if total <= rate:
            raise ValueError("Подтверждённая суммарная ставка должна быть больше дополнительной.")
        result.update({"concurrent.rate": decimal_text(rate, fractional=True), "total.rate": decimal_text(total, fractional=True)})
    else:
        percent = number(replacement.get("allowance_percent"), "Процент доплаты")
        if optional_placement and percent not in (Decimal(25), Decimal(50)):
            raise ValueError("Выберите доплату +25% или +50%.")
        for locale in ("ru", "kk"):
            base = str(replacement.get("allowance_basis_" + locale) or "").strip()
            if not base:
                raise ValueError("Укажите базу расчёта доплаты (" + locale.upper() + ").")
            result["allowance.basis." + locale] = base
        result["allowance.percent"] = decimal_text(percent)
        if optional_placement:
            position_ru = result["concurrent.position_genitive_ru"] if str(concurrent.get("position_ru") or "").strip() else ""
            unit_ru = result["concurrent.org_unit_genitive_ru"] if str(concurrent.get("org_unit_ru") or "").strip() else ""
            result["replacement.work.ru"] = " ".join(filter(None, ("совмещение должности" if position_ru else "исполнение обязанностей замещаемого работника", position_ru, unit_ru)))
            position_kk = result["concurrent.position_kk"]
            unit_kk = result["concurrent.org_unit_kk"]
            result["replacement.work.kk"] = " ".join(filter(None, (unit_kk, position_kk, "қызметін қоса атқаруға" if position_kk else "орны алмастырылатын қызметкердің міндеттерін атқаруға")))
    return result


SAMPLE_CONCURRENT = dict(position_ru="Врач", position_kk="дәрігері", org_unit_ru="Отделение терапии", org_unit_kk="терапия бөлімшесінің", position_genitive_ru="врача", org_unit_genitive_ru="отделения терапии", employee_dative_ru="Турымову Алибеку Рапхатовичу", employee_dative_kk="Алибек Рапхатович Турымовқа", rate="0,25", total_rate="1,25", basis_ru="личное заявление", basis_kk="жеке өтініш")
SAMPLE_REPLACEMENT = dict(employee_name_ru="Иванов Иван Иванович", employee_name_kk="Иван Иванович Иванов", employee_genitive_ru="Иванова Ивана Ивановича", employee_genitive_kk="Иван Иванович Ивановтың", position_ru="Врач", org_unit_ru="Отделение терапии", position_genitive_ru="врача", org_unit_genitive_ru="отделения терапии", position_kk="дәрігері", org_unit_kk="терапия бөлімшесінің", term_type="DATE", end_date="2026-07-31", allowance_percent="25", allowance_basis_ru="должностного оклада замещаемого работника", allowance_basis_kk="орны алмастырылатын қызметкердің лауазымдық жалақысының")


def preview_context(mode, *, optional_placement=False):
    data = replacement_values(SAMPLE_CONCURRENT, SAMPLE_REPLACEMENT, "2026-07-03", mode, optional_placement=optional_placement)
    return {locale: {key: data.get(key + "." + locale, data.get(key, "")) for key in (*VARIABLES, "employee.full_name_dative_ru", "employee.full_name_dative_kk", "effective_date", "concurrent.rate", "total.rate", "basis", "concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru", "concurrent.position_kk", "concurrent.org_unit_kk")} for locale in ("ru", "kk")}
