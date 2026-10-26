"""Document-only specialty snapshot; never mutates a position or employee."""
import re
from collections.abc import Mapping


def specialty_values(item_type, payload, template):
    snapshot = payload.get("medical_specialty")
    if snapshot is None or item_type not in {"TRANSFER", "CONCURRENT_DUTY_START"}:
        return {}
    if item_type == "CONCURRENT_DUTY_START" and (payload.get("replacement") or "{{concurrent.rate}}" not in str(template.get("body_template_ru", ""))):
        return {}
    if (not isinstance(snapshot, Mapping) or type(snapshot.get("medical_specialty_id")) is not int
            or snapshot["medical_specialty_id"] < 1
            or not all(isinstance(snapshot.get(key), str) and snapshot[key].strip() for key in ("name_ru", "name_kk"))):
        raise ValueError("Для выбранной специальности нужны сохранённые названия RU и KK. Выберите специальность заново или очистите поле.")
    return {"__medical_specialty.ru": snapshot["name_ru"], "__medical_specialty.kk": snapshot["name_kk"]}


def specialty_texts(texts, item_type, values):
    result = dict(texts)
    for locale in ("ru", "kk"):
        key = f"__medical_specialty.{locale}"
        if not values.get(key):
            continue
        field = f"body_template_{locale}"
        source = result[field]
        tokens = ([f"position.title_{locale}"] if item_type == "TRANSFER" else
                  ["concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru"] if locale == "ru" else
                  ["concurrent.org_unit_kk", "concurrent.position_kk"])
        matches = [re.search(r"\{\{\s*" + re.escape(token) + r"\s*\}\}[»“”\"]?", source) for token in tokens]
        if not all(matches):
            raise ValueError("Шаблон не содержит полного названия должности для выбранной специальности.")
        end = max(match.end() for match in matches)
        # A render-local token only. Published template contents stay untouched.
        source = source[:end] + f" ({{{{{key}}}}})" + source[end:]
        if item_type == "CONCURRENT_DUTY_START" and locale == "kk":
            # The current KK rate template puts the rate before the placement.
            # For the optional specialty, keep placement + specialty before rate.
            rate = re.search(r"\{\{\s*concurrent\.rate\s*\}\}\s+ставкада\s+", source)
            marker = source.index(f" ({{{{{key}}}}})") + len(f" ({{{{{key}}}}})")
            if rate and rate.start() < marker:
                phrase = rate.group().rstrip()
                source = source[:marker] + " " + phrase + source[marker:]
                source = source[:rate.start()] + source[rate.end():]
        result[field] = source
    return result
