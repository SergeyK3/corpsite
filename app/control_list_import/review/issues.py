"""Issue aggregation helpers for review assembly (WP-CL-011)."""
from __future__ import annotations

from app.control_list_import.domain.review_models import BlockingIssueSummary


def dedupe_issues(
    issues: tuple[BlockingIssueSummary, ...] | list[BlockingIssueSummary],
) -> tuple[BlockingIssueSummary, ...]:
    """Stable deduplication by (code, source, blocking)."""
    seen: set[tuple[str, str, bool]] = set()
    deduped: list[BlockingIssueSummary] = []
    for issue in issues:
        key = (issue.code, issue.source, issue.blocking)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return tuple(deduped)
