"""Read/validate the versioned JSON contract for unpaid leave items."""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping


class UnpaidLeaveContractError(ValueError):
    pass


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise UnpaidLeaveContractError(f"{field} must be an ISO date.") from exc


def _days(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise UnpaidLeaveContractError("Leave item requires integer leave.days.") from exc
    if result < 1:
        raise UnpaidLeaveContractError("leave.days must be positive.")
    return result


def unpaid_leave_period(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical period without changing the stored legacy payload.

    New records use ``payload.leave``.  The legacy triplet remains readable so
    historical reconstruction records keep their original JSON unchanged.
    """
    modern = payload.get("leave")
    legacy_present = any(key in payload for key in ("leave_start", "leave_end", "leave_days"))
    if modern is not None and not isinstance(modern, Mapping):
        raise UnpaidLeaveContractError("leave must be an object.")
    if modern is None:
        if not legacy_present:
            raise UnpaidLeaveContractError("Leave item requires leave period data.")
        start = _date(payload.get("leave_start"), "payload.leave_start")
        end = _date(payload.get("leave_end"), "payload.leave_end")
        days = _days(payload.get("leave_days"))
        if end < start or days != (end - start).days + 1:
            raise UnpaidLeaveContractError("Unpaid leave payload.leave_days must equal inclusive leave period days.")
        return {
            "period_type": "SINGLE_DAY" if start == end else "CONTINUOUS_RANGE",
            "start": start,
            "end": end,
            "days": days,
            "legacy": True,
        }

    kind = str(modern.get("period_type") or "").strip().upper()
    if kind not in {"SINGLE_DAY", "CONTINUOUS_RANGE"}:
        raise UnpaidLeaveContractError("leave.period_type must be SINGLE_DAY or CONTINUOUS_RANGE.")
    days = _days(modern.get("days"))
    if "dates" in modern:
        raise UnpaidLeaveContractError("leave.dates is not supported; use leave.start and leave.end.")
    start = _date(modern.get("start"), "leave.start")
    end = _date(modern.get("end"), "leave.end")
    if end < start:
        raise UnpaidLeaveContractError("leave.end must not be earlier than leave.start.")
    expected_kind = "SINGLE_DAY" if start == end else "CONTINUOUS_RANGE"
    if kind != expected_kind:
        raise UnpaidLeaveContractError(f"{kind} must match leave.start and leave.end.")
    expected_days = (end - start).days + 1
    if days != expected_days:
        raise UnpaidLeaveContractError(f"{kind} leave.days must equal inclusive range days.")
    result = {"period_type": kind, "start": start, "end": end, "days": days, "legacy": False}
    if legacy_present:
        legacy = unpaid_leave_period({key: payload.get(key) for key in ("leave_start", "leave_end", "leave_days")})
        if (legacy["start"], legacy["end"], legacy["days"]) != (result["start"], result["end"], result["days"]):
            raise UnpaidLeaveContractError("Legacy leave_start/leave_end/leave_days conflicts with leave.")
    return result


_RU_MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
_KK_MONTHS = ("қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан")


def format_leave_date(value: date, locale: str) -> str:
    return f"{value.day} {_RU_MONTHS[value.month - 1]} {value.year} года" if locale == "ru" else f"{value.year} жылғы {value.day} {_KK_MONTHS[value.month - 1]}"


def period_text(period: Mapping[str, Any], locale: str) -> str:
    kind = str(period["period_type"])
    if kind == "SINGLE_DAY":
        return format_leave_date(period["start"], locale)
    if kind == "CONTINUOUS_RANGE":
        return f"с {format_leave_date(period['start'], locale)} по {format_leave_date(period['end'], locale)} включительно" if locale == "ru" else f"{format_leave_date(period['start'], locale)} мен {format_leave_date(period['end'], locale)} аралығы"
    raise UnpaidLeaveContractError("Unknown leave.period_type.")


def period_clause_ru(period: Mapping[str, Any]) -> str:
    """Return the approved Russian clause for a supported unpaid-leave period."""
    start, end = period["start"], period["end"]
    if str(period["period_type"]) == "SINGLE_DAY":
        return format_leave_date(start, "ru")
    if start.year == end.year and start.month == end.month:
        return f"с {start.day} по {end.day} {_RU_MONTHS[start.month - 1]} {start.year} года включительно"
    if start.year == end.year:
        return f"с {start.day} {_RU_MONTHS[start.month - 1]} по {end.day} {_RU_MONTHS[end.month - 1]} {start.year} года включительно"
    return f"с {format_leave_date(start, 'ru')} по {format_leave_date(end, 'ru')} включительно"


def period_clause_kk(period: Mapping[str, Any]) -> str:
    """Return the grammatical KK period clause used by unpaid-leave orders.

    This is intentionally separate from the neutral display ``period_text``:
    the approved document wording has a different case ending for each period
    kind.  It only formats dates; names and organisational forms never pass
    through this helper and are never inflected programmatically.
    """
    kind = str(period["period_type"])
    def day_month(value: date) -> str:
        return f"{value.day} {_KK_MONTHS[value.month - 1]}"

    if kind == "SINGLE_DAY":
        value = period["start"]
        return f"{value.year} жылғы {day_month(value)} күніне"
    if kind == "CONTINUOUS_RANGE":
        start, end = period["start"], period["end"]
        if start.year == end.year and start.month == end.month:
            return f"{start.year} жылғы {start.day} мен {end.day} {_KK_MONTHS[start.month - 1]} аралығында"
        if start.year == end.year:
            return f"{start.year} жылғы {day_month(start)} мен {day_month(end)} аралығында"
        return f"{start.year} жылғы {day_month(start)} мен {end.year} жылғы {day_month(end)} аралығында"
    raise UnpaidLeaveContractError("Unknown leave.period_type.")
