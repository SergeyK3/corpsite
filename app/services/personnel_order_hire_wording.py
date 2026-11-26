"""Shared grammatical wording for HIRE applications and orders."""

from app.services.personnel_order_russian_reference_forms import russian_reference_case


_MASCULINE_ROLES = {
    "врач", "терапевт", "хирург", "специалист", "директор", "заведующий",
    "начальник", "бухгалтер", "санитар", "менеджер", "акушер", "фельдшер",
    "лаборант", "фармацевт", "провизор", "психолог", "регистратор",
    "инженер", "техник", "экономист", "юрист", "методист", "инструктор",
    "оператор", "водитель", "повар", "машинист", "уборщик", "архивариус",
}
_FEMININE_POSITION_GENITIVE = {
    "заведующая": "заведующей", "сестра": "сестры", "медсестра": "медсестры",
    "санитарка": "санитарки", "акушерка": "акушерки",
    "уборщица": "уборщицы", "хозяйка": "хозяйки",
}


def hire_position_accusative_ru(title: str, manual_form: str = "") -> str:
    """Return the role form after «на должность»; keep the legacy function name."""
    if str(manual_form or "").strip():
        return str(manual_form).strip()
    words = str(title or "").strip().lower().split()
    heads = [word for word in words if word in _MASCULINE_ROLES | _FEMININE_POSITION_GENITIVE.keys()]
    if len(heads) != 1 or len(words) != 1:
        raise ValueError("Уточните вручную форму должности RU после «на должность»")
    head = heads[0]
    if head in _MASCULINE_ROLES:
        result = russian_reference_case(title, "genitive")
        if result:
            return result
    elif len(words) == 1:
        return _FEMININE_POSITION_GENITIVE[head]
    raise ValueError("Уточните вручную форму должности RU после «на должность»")


def hire_department_destination_kk(title: str) -> str:
    """Use a complete Kazakh unit name once, in the destination case."""
    value = str(title or "").strip()
    for ending, destination in (
        (" бөлімшесі", " бөлімшесіне"),
        (" бөлімі", " бөліміне"),
        (" орталығы", " орталығына"),
    ):
        if value.casefold().endswith(ending):
            return value[:-len(ending)] + destination
    return f"«{value}» бөлімшесіне"


def hire_body_template_with_department(text: str) -> str:
    """Adapt the published HIRE wording in memory without editing its version."""
    return text.replace("«{{org_unit.title_kk}}» бөлімшесіне", "{{org_unit.destination_kk}}")
