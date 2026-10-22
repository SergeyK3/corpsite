"""Display rate tokens consistently without rewriting other numeric text."""


def format_template_rate(item_type_code: str, token: str, value: str) -> str:
    if item_type_code in {"TRANSFER", "CONCURRENT_DUTY_START"} and token in {"rate", "concurrent.rate", "total.rate"}:
        return value.replace(".", ",")
    return value
