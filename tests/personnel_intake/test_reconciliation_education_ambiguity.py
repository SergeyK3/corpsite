"""EDU-04 / EDU-04a / EDU-16 — HR Q3 ambiguity (WP-006 §8 / §11)."""
from __future__ import annotations

import pytest

from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
    QUALITY_KEY,
)
from app.personnel_intake.domain.reconciliation.actions import (
    MATCH_CONFIDENCE_HIGH,
    MATCH_KIND_AMBIGUOUS,
)
from tests.personnel_intake.edu_plugin_helpers import build_proposal, canonical_ref


@pytest.fixture
def plugin() -> EducationReconciliationPlugin:
    return EducationReconciliationPlugin()


def test_edu_04_ambiguous_q3(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin)
    c1 = canonical_ref(10)
    c2 = canonical_ref(11)
    match = plugin.match(proposal, (c1, c2))
    assert match.match_kind == MATCH_KIND_AMBIGUOUS
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert match.matched_canonical_record_id is None
    assert match.candidate_canonical_record_ids == (10, 11)
    assert match.detail["reason"] == "HR_Q3_AMBIGUOUS_IDENTITY"
    assert match.detail["identity_key"] == ["basic", "мгу"]
    assert QUALITY_KEY in match.detail


def test_edu_04a_ambiguity_plus_year_only(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="2019")
    match = plugin.match(proposal, (canonical_ref(20), canonical_ref(21)))
    assert match.match_kind == MATCH_KIND_AMBIGUOUS
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert match.candidate_canonical_record_ids == (20, 21)
    assert match.detail["reason"] == "HR_Q3_AMBIGUOUS_IDENTITY"
    assert match.detail[QUALITY_KEY]["started_at"]["raw"] == "2019"
    assert match.detail[QUALITY_KEY]["started_at"]["precision"] == "incomplete"


def test_edu_16_e17_q3_marker(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, institution="МГУ")
    match = plugin.match(
        proposal,
        (
            canonical_ref(1, institution_name="мгу"),
            canonical_ref(2, institution_name="МГУ"),
        ),
    )
    assert match.match_kind == MATCH_KIND_AMBIGUOUS
    assert match.detail["reason"] == "HR_Q3_AMBIGUOUS_IDENTITY"
    assert set(match.candidate_canonical_record_ids) == {1, 2}
