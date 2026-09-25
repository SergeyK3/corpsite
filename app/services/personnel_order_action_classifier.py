"""Fail-closed action hints for reconstructed personnel-order text."""
from __future__ import annotations

import re


RETURN_FROM_CHILDCARE_LEAVE = "RETURN_FROM_CHILDCARE_LEAVE"
LEAVE_CHILDCARE_GRANT = "LEAVE.CHILDCARE.GRANT"


def classify_personnel_order_action(text: object) -> str | None:
    """Classify only explicit RU/KK return-from-childcare-leave wording."""
    value = " ".join(str(text or "").casefold().split())
    ru_return = re.search(
        r"(?:выход(?:е|а)?\s+из|выйти\s+на\s+работу\s+после|приступить\s+к\s+работе.*после)\s+отпуска\s+по\s+уходу\s+за\s+реб[её]нком",
        value,
    )
    kk_return = re.search(r"бала\s+күтіміне\s+байланысты\s+демалыстан\s+(?:жұмысқа\s+)?шығ", value)
    if ru_return or kk_return:
        return RETURN_FROM_CHILDCARE_LEAVE
    ru_grant = re.search(r"предоставить\s+.*отпуск.*по\s+уходу\s+за\s+реб[её]нком", value)
    kk_grant = re.search(r"бала\s+күтіміне\s+байланысты\s+.*демалыс\s+бер", value)
    return LEAVE_CHILDCARE_GRANT if ru_grant or kk_grant else None
