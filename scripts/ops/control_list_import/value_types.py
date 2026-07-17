"""Value typing, issue detection, masking, and composite cell heuristics."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

EXCEL_ERRORS = frozenset(
    {"#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#NUM!", "#GETTING_DATA"}
)

ISSUE_CODES = frozenset(
    {
        "iin_not_12_digits",
        "iin_contains_non_digits",
        "iin_stored_as_number",
        "iin_possible_precision_loss",
        "phone_stored_as_number",
        "phone_invalid_length",
        "date_stored_as_text",
        "number_formatted_as_date",
        "multiple_numbered_records_in_cell",
        "composite_text_without_standard_line_breaks",
        "mixed_value_types_in_column",
        "inflated_excel_used_range",
        "header_not_confident",
        "probable_inherited_section_value",
        "formula_cell_detected",
        "excel_error_cell_detected",
    }
)

_KAZAKH_UPPER = "ӘҒҚҢӨҰҮҺІ"
_FIO_RE = re.compile(
    rf"^[А-ЯЁ{_KAZAKH_UPPER}][а-яё{_KAZAKH_UPPER.lower()}a-z\-']+"
    rf"(?:\s+[А-ЯЁ{_KAZAKH_UPPER}][а-яё{_KAZAKH_UPPER.lower()}a-z\-']+){{1,3}}$"
)
_NUMBERED_START_RE = re.compile(
    r"(?:^|[\n\r\v])\s*(\d+)\s*([.)])\s*",
    re.MULTILINE,
)
_NUMBERED_INLINE_QUOTED_RE = re.compile(r"(?:^|\s)(\d+)\.\s*[\"«]")
_HOURS_RE = re.compile(r"\d+\s*ч\.?", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b\d{4}\s*г\.?", re.IGNORECASE)
_DATE_TEXT_RE = re.compile(r"^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$|^\d{4}[./\-]\d{1,2}[./\-]\d{1,2}$")

IIN_COLUMN_CONFIDENCE_MIN = 0.55


@dataclass(frozen=True)
class CompositeAnalysis:
    is_composite: bool
    record_count: int
    numbered_starts: int
    structural_lines: int
    issues: tuple[str, ...]


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).replace("\u00a0", " ").strip()
    return " ".join(text.split())


def normalize_text(value: Any) -> str:
    return to_text(value).lower().replace("ё", "е")


def sha256_file(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def excel_serial_to_date(serial: float) -> Optional[date]:
    if serial <= 0:
        return None
    try:
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=serial)).date()
    except (OverflowError, ValueError):
        return None


def looks_like_fio(value: Any) -> bool:
    text = to_text(value)
    if not text or len(text) < 5:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    return bool(_FIO_RE.match(text))


def is_iin_column(semantic_field: Optional[str], semantic_confidence: float = 0.0) -> bool:
    return semantic_field == "person.iin" and semantic_confidence >= IIN_COLUMN_CONFIDENCE_MIN


def extract_iin_digits(value: Any, *, apply_issues: bool = True) -> tuple[str, list[str]]:
    issues: list[str] = []
    if isinstance(value, bool):
        return "", (["iin_contains_non_digits"] if apply_issues else [])

    if isinstance(value, int):
        digits = str(abs(value))
        if apply_issues:
            issues.append("iin_stored_as_number")
    elif isinstance(value, float):
        if apply_issues:
            issues.append("iin_stored_as_number")
            if value > 1e11:
                issues.append("iin_possible_precision_loss")
        digits = re.sub(r"\D", "", f"{value:.0f}")
    else:
        raw = to_text(value)
        if apply_issues and re.search(r"\.0+\s*$", raw.replace(" ", "")):
            issues.append("iin_stored_as_number")
        if (
            apply_issues
            and raw
            and not re.sub(r"[\s.\-]", "", raw).isdigit()
            and re.search(r"[A-Za-zА-Яа-я]", raw)
        ):
            issues.append("iin_contains_non_digits")
        digits = re.sub(r"\D", "", raw)
        if (
            apply_issues
            and len(digits) > 12
            and digits.endswith("0")
            and re.search(r"\.0+\s*$", raw.replace(" ", ""))
        ):
            digits = digits[:12]

    if not digits:
        return "", issues

    if len(digits) == 11:
        digits = f"0{digits}"

    if apply_issues and len(digits) != 12:
        issues.append("iin_not_12_digits")

    return digits, issues


def extract_iin_issues(value: Any, *, in_iin_column: bool) -> list[str]:
    if not in_iin_column:
        return []
    _, issues = extract_iin_digits(value, apply_issues=True)
    return list(dict.fromkeys(issues))


def extract_phone_digits(value: Any) -> tuple[str, list[str]]:
    issues: list[str] = []
    if isinstance(value, bool):
        return "", ["phone_invalid_length"]

    if isinstance(value, (int, float)):
        issues.append("phone_stored_as_number")
        digits = re.sub(r"\D", "", str(int(value)))
    else:
        digits = re.sub(r"\D", "", to_text(value))

    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]

    if digits and len(digits) not in (10, 11, 12):
        issues.append("phone_invalid_length")

    return digits, issues


def _count_numbered_starts(raw: str) -> int:
    indices: set[int] = set()
    for match in _NUMBERED_START_RE.finditer(raw):
        indices.add(int(match.group(1)))
    for match in _NUMBERED_INLINE_QUOTED_RE.finditer(raw):
        indices.add(int(match.group(1)))
    return len(indices)


def _is_structural_record_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    has_year = bool(_YEAR_RE.search(line))
    has_hours = bool(_HOURS_RE.search(line))
    has_course_marker = '"' in line or "«" in line or "курс" in line.lower()
    return has_year and (has_hours or has_course_marker)


def analyze_composite_cell(text: str) -> CompositeAnalysis:
    if not text or not str(text).strip():
        return CompositeAnalysis(False, 0, 0, 0, ())

    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    numbered_starts = _count_numbered_starts(raw)
    lines = [ln.strip() for ln in re.split(r"[\n\v]", raw) if ln.strip()]
    structural_lines = sum(1 for ln in lines if _is_structural_record_line(ln))

    record_count = 0
    if numbered_starts >= 2:
        record_count = numbered_starts
    elif structural_lines >= 2:
        record_count = structural_lines
    else:
        record_count = 1

    is_composite = record_count >= 2
    issues: list[str] = []
    if numbered_starts >= 2:
        issues.append("multiple_numbered_records_in_cell")
    if is_composite and "\n" not in raw and "\r" not in raw and "\v" not in raw:
        issues.append("composite_text_without_standard_line_breaks")

    return CompositeAnalysis(
        is_composite=is_composite,
        record_count=record_count,
        numbered_starts=numbered_starts,
        structural_lines=structural_lines,
        issues=tuple(dict.fromkeys(issues)),
    )


def count_composite_records(text: str) -> int:
    analysis = analyze_composite_cell(text)
    return analysis.record_count if analysis.is_composite else (1 if text and str(text).strip() else 0)


def classify_value_type(
    value: Any,
    *,
    number_format: str = "",
    semantic_field: Optional[str] = None,
    semantic_confidence: float = 0.0,
    is_formula: bool = False,
) -> str:
    if is_formula:
        return "formula"

    if value is None:
        return "empty"

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "empty"
        if stripped in EXCEL_ERRORS:
            return "error"
        if stripped.startswith("="):
            return "formula"

    if isinstance(value, bool):
        return "text"

    if isinstance(value, datetime):
        return "excel_date"
    if isinstance(value, date):
        return "excel_date"

    in_iin = is_iin_column(semantic_field, semantic_confidence)
    in_phone = semantic_field == "person.phone" and semantic_confidence >= IIN_COLUMN_CONFIDENCE_MIN

    if isinstance(value, int):
        if in_iin:
            return "iin_candidate"
        if in_phone:
            return "phone_candidate"
        if number_format and _looks_date_format(number_format):
            return "excel_date"
        return "integer"

    if isinstance(value, float):
        if in_iin:
            return "iin_candidate"
        if in_phone:
            return "phone_candidate"
        if number_format and _looks_date_format(number_format):
            return "excel_date"
        if value == int(value):
            return "integer"
        return "decimal"

    text = to_text(value)
    if not text:
        return "empty"

    if in_phone or text.strip().startswith("+") or re.search(r"\(\d{3}\)", text):
        phone_digits, _ = extract_phone_digits(value)
        if phone_digits and len(phone_digits) in (10, 11, 12):
            return "phone_candidate"

    composite = analyze_composite_cell(text)
    if composite.is_composite:
        return "composite_text"

    if in_iin:
        digits, issues = extract_iin_digits(value, apply_issues=True)
        if digits or issues:
            return "iin_candidate"

    if _DATE_TEXT_RE.match(text):
        return "date_text"

    if looks_like_fio(text):
        return "text"

    return "text"


def detect_value_issues(
    value: Any,
    *,
    value_type: str,
    number_format: str = "",
    semantic_field: Optional[str] = None,
    semantic_confidence: float = 0.0,
    is_formula: bool = False,
) -> list[str]:
    issues: list[str] = []
    if is_formula:
        return ["formula_cell_detected"]

    if value_type == "error":
        return ["excel_error_cell_detected"]

    in_iin = is_iin_column(semantic_field, semantic_confidence)
    in_phone = semantic_field == "person.phone" and semantic_confidence >= IIN_COLUMN_CONFIDENCE_MIN

    if in_iin or (value_type == "iin_candidate" and in_iin):
        issues.extend(extract_iin_issues(value, in_iin_column=True))

    if value_type == "phone_candidate" or in_phone:
        _, phone_issues = extract_phone_digits(value)
        issues.extend(phone_issues)

    if value_type == "date_text":
        issues.append("date_stored_as_text")

    if value_type in {"integer", "decimal"} and number_format and _looks_date_format(number_format):
        issues.append("number_formatted_as_date")

    if value_type == "composite_text":
        composite = analyze_composite_cell(to_text(value))
        issues.extend(composite.issues)

    return list(dict.fromkeys(issues))


def mask_iin(value: Any) -> str:
    digits, _ = extract_iin_digits(value, apply_issues=False)
    if len(digits) >= 4:
        return f"******{digits[-4:]}"
    if digits:
        return f"***{digits[-2:]}"
    text = to_text(value)
    return "***" if text else ""


def mask_phone(value: Any) -> str:
    digits, _ = extract_phone_digits(value)
    if len(digits) >= 4:
        prefix = "+7" if digits.startswith("7") else ""
        return f"{prefix}{'*' * max(3, len(digits) - 4)}{digits[-3:]}"
    text = to_text(value)
    if not text:
        return ""
    return re.sub(r"\d", "*", text)


def mask_full_name(value: Any) -> str:
    text = to_text(value)
    if not text:
        return ""
    parts = text.split()
    masked_parts: list[str] = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        else:
            masked_parts.append(f"{part[0]}{'*' * (len(part) - 1)}")
    return " ".join(masked_parts)


def mask_sample_value(value: Any, *, value_type: str, semantic_field: Optional[str] = None) -> str:
    sf = semantic_field or ""
    if value_type == "empty" or value is None:
        return ""

    text = to_text(value)
    if not text:
        return ""

    iin_digits, iin_issues = extract_iin_digits(value, apply_issues=False)
    if len(iin_digits) == 12 and "iin_contains_non_digits" not in iin_issues:
        return mask_iin(value)

    phone_digits, _ = extract_phone_digits(value)
    if phone_digits and len(phone_digits) in (10, 11, 12) and (
        sf.endswith(".phone")
        or value_type == "phone_candidate"
        or text.strip().startswith("+")
        or re.search(r"\(\d{3}\)", text)
    ):
        return mask_phone(value)

    if sf.endswith(".full_name") or (value_type == "text" and looks_like_fio(value)):
        return mask_full_name(value)

    if looks_like_fio(text):
        return mask_full_name(text)

    if value_type == "composite_text":
        return text[:80] + ("…" if len(text) > 80 else "")

    return text[:120] + ("…" if len(text) > 120 else "")


def _looks_date_format(number_format: str) -> bool:
    fmt = (number_format or "").lower()
    return any(token in fmt for token in ("yy", "dd", "mm", "date"))
