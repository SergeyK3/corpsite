"""Fail-closed action hints for reconstructed personnel-order text."""
from __future__ import annotations

import re


RETURN_FROM_CHILDCARE_LEAVE = "RETURN_FROM_CHILDCARE_LEAVE"


def classify_personnel_order_action(text: object) -> str | None:
    """Classify only explicit RU/KK return-from-childcare-leave wording."""
    value = " ".join(str(text or "").casefold().split())
    ru = re.search(r"выход(?:е|а)?\s+из\s+отпуска\s+по\s+уходу\s+за\s+реб[её]нком", value)
    kk = re.search(r"бала\s+күтіміне\s+байланысты\s+демалыстан\s+шығ", value)
    return RETURN_FROM_CHILDCARE_LEAVE if ru or kk else None
