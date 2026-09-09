"""EDU-KIND-ALLOWLIST-v1 — deterministic, fail-closed classifier."""
from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = "EDU-KIND-ALLOWLIST-v1"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class EducationKindClassification:
    kind: str | None
    outcome: str
    reason_code: str
    policy_version: str = POLICY_VERSION
    specific_markers: tuple[str, ...] = ()


def classify_education_kind(*values: object) -> EducationKindClassification:
    # Unicode escapes make marker matching stable even when the shell's code
    # page cannot faithfully display Cyrillic source text.
    clean_text = " ".join(str(value or "") for value in values).casefold()
    try:
        # Some historic local test/import artifacts were decoded as cp1251.
        # Treat the reversible form as an input-normalisation candidate, never
        # as a fallback classification.
        candidate_texts = (clean_text, clean_text.encode("cp1251").decode("utf-8"))
    except UnicodeError:
        candidate_texts = (clean_text,)
    allowlist = {
        "internship": ("\u0438\u043d\u0442\u0435\u0440\u043d\u0430\u0442\u0443\u0440", "\u0432\u0440\u0430\u0447-\u0438\u043d\u0442\u0435\u0440\u043d"),
        "residency": ("\u0440\u0435\u0437\u0438\u0434\u0435\u043d\u0442\u0443\u0440", "\u043e\u0440\u0434\u0438\u043d\u0430\u0442\u0443\u0440"),
        "masters": ("\u043c\u0430\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u0443\u0440", "\u043c\u0430\u0433\u0438\u0441\u0442\u0440"),
        "phd": ("phd", "\u0434\u043e\u043a\u0442\u043e\u0440\u0430\u043d\u0442\u0443\u0440", "\u0434\u043e\u043a\u0442\u043e\u0440 \u0444\u0438\u043b\u043e\u0441\u043e\u0444\u0438\u0438"),
    }
    hits = tuple(kind for kind, markers in allowlist.items() if any(marker in candidate for candidate in candidate_texts for marker in markers))
    if len(hits) > 1:
        return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_CONFLICTING_SPECIFIC_MARKERS", specific_markers=hits)
    if hits:
        return EducationKindClassification(hits[0], "READY_TO_ADD", "STAGE2_KIND_SPECIFIC_MARKER", specific_markers=hits)
    if any("\u043f\u043e\u0441\u043b\u0435\u0432\u0443\u0437\u043e\u0432" in candidate for candidate in candidate_texts):
        return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_POSTGRADUATE_UNSPECIFIED")
    basic = ("\u0432\u044b\u0441\u0448", "\u0441\u0440\u0435\u0434\u043d", "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a", "\u043f\u0440\u043e\u0444\u0435\u0441\u0441\u0438\u043e\u043d\u0430\u043b\u044c\u043d", "\u0431\u0430\u0437\u043e\u0432", "\u0434\u0438\u043f\u043b\u043e\u043c")
    if any(marker in candidate for candidate in candidate_texts for marker in basic):
        return EducationKindClassification("basic", "READY_TO_ADD", "STAGE2_KIND_BASIC")
    return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_KIND_UNKNOWN")

    # Kept below temporarily only to minimise a mechanical rewrite of the
    # previously prepared file; all paths return from the approved policy above.
    text = " ".join(str(value or "") for value in values).casefold()
    groups = {
        "internship": ("интернатур", "врач-интерн"),
        "residency": ("резидентур", "ординатур"),
        "masters": ("магистратур", "магистр"),
        "phd": ("phd", "докторантур", "доктор философии"),
    }
    hits = tuple(kind for kind, markers in groups.items() if any(marker in text for marker in markers))
    if len(hits) > 1:
        return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_CONFLICTING_SPECIFIC_MARKERS", specific_markers=hits)
    if hits:
        return EducationKindClassification(hits[0], "READY_TO_ADD", "STAGE2_KIND_SPECIFIC_MARKER", specific_markers=hits)
    if "послевузов" in text:
        return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_POSTGRADUATE_UNSPECIFIED")
    basic_markers = ("высш", "средн", "техническ", "профессиональн", "базов", "диплом")
    # A non-empty fragment alone is not evidence of a basic education.  Stage
    # 2 v1 must not silently classify an unknown/other value as ``basic``.
    if any(marker in text for marker in basic_markers):
        return EducationKindClassification("basic", "READY_TO_ADD", "STAGE2_KIND_BASIC")
    return EducationKindClassification(None, REVIEW_REQUIRED, "STAGE2_KIND_UNKNOWN")
