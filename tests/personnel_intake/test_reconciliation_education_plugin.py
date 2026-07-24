"""EDU unit matrix — match / equality / choose / anti-degradation (WP-006 §11)."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, TRAINING_KIND_COURSE
from app.personnel_intake.application.reconciliation.plugins import education as education_mod
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
    QUALITY_KEY,
)
from app.personnel_intake.domain.reconciliation.actions import (
    MATCH_CONFIDENCE_HIGH,
    MATCH_CONFIDENCE_LOW,
    MATCH_KIND_EXACT_ONE,
    MATCH_KIND_NONE,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.digest import CanonJsonV1DigestBuilder
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.ppr.domain.section_models import EducationRecord, TrainingRecord
from tests.personnel_intake.edu_plugin_helpers import build_proposal, canonical_ref, intake_row


@pytest.fixture
def plugin() -> EducationReconciliationPlugin:
    return EducationReconciliationPlugin()


def test_plugin_identity_and_versions(plugin: EducationReconciliationPlugin) -> None:
    assert plugin.section_code == "education"
    assert plugin.section_apply_mode == "per_record"
    assert plugin.matcher_rule_id == "EDU-MATCH-v1"
    assert plugin.matcher_version == "1.0.0"
    assert plugin.policy_version == "1.0.0"


def test_edu_01_confident_new_add(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin)
    match = plugin.match(proposal, ())
    assert match.match_kind == MATCH_KIND_NONE
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert match.semantically_equal is None


def test_edu_02_reapp_identical_keep(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin)
    target = canonical_ref(42)
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert match.semantically_equal is True
    assert match.matched_canonical_record_id == 42
    assert match.candidate_canonical_record_ids == (42,)


def test_edu_03_exact_enrichment_update(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, specialty="Физика", diploma_number="D-9")
    target = canonical_ref(7, specialty=None, diploma_number="D-1")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert match.semantically_equal is False
    action = plugin.choose_exact_action(match, proposal, target)
    assert action == RECONCILE_ACTION_UPDATE_VERSION


def test_edu_05a_year_only_zero_candidates(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="2019", institution="New School")
    match = plugin.match(proposal, ())
    assert match.match_kind == MATCH_KIND_NONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert proposal.normalized_content["started_at"] is None
    iq = proposal.normalized_content[QUALITY_KEY]["started_at"]
    assert iq == {"precision": "incomplete", "raw": "2019"}
    assert match.detail["reason"] == "INCOMPLETE_OR_YEAR_ONLY_DATE"


def test_edu_05b_year_only_one_candidate(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="2019")
    target = canonical_ref(11)
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.matched_canonical_record_id == 11
    assert match.candidate_canonical_record_ids == (11,)
    assert match.detail["reason"] == "INCOMPLETE_OR_YEAR_ONLY_DATE"


def test_edu_05c_digest_distinct_incomplete_vs_missing(
    plugin: EducationReconciliationPlugin,
) -> None:
    builder = CanonJsonV1DigestBuilder()
    p_2019 = build_proposal(plugin, year_from="2019", institution="A")
    p_2020 = build_proposal(plugin, year_from="2020", institution="A")
    p_missing = build_proposal(plugin, year_from="", institution="A")
    d1 = builder.payload_digest(p_2019.normalized_content)
    d2 = builder.payload_digest(p_2020.normalized_content)
    d3 = builder.payload_digest(p_missing.normalized_content)
    assert len({d1, d2, d3}) == 3


def test_edu_06_empty_institution(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, institution="   ")
    match = plugin.match(proposal, ())
    assert match.match_kind == MATCH_KIND_NONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.detail["reason"] == "INCOMPLETE_IDENTITY"


def test_edu_07_unknown_education_type(plugin: EducationReconciliationPlugin) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        plugin.build_proposal_refs(
            {"records": [intake_row(education_type="not-a-kind")]},
            "canon-json-v1",
        )
    assert exc.value.code == "INVALID_EDUCATION_TYPE"


def test_edu_08_different_kind_same_school(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, education_type="masters")
    target = canonical_ref(3, education_kind="basic")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_NONE
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH


def test_edu_09_casefold_institution(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, institution="мгу")
    target = canonical_ref(5, institution_name="МГУ")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.matched_canonical_record_id == 5


def test_edu_10_null_to_value_specialty(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, specialty="Химия")
    target = canonical_ref(8, specialty=None)
    match = plugin.match(proposal, (target,))
    assert match.semantically_equal is False
    assert plugin.choose_exact_action(match, proposal, target) == RECONCILE_ACTION_UPDATE_VERSION


def test_edu_11_choose_never_supersede(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, qualification="Магистр")
    target = canonical_ref(9, qualification="Бакалавр")
    match = plugin.match(proposal, (target,))
    assert plugin.choose_exact_action(match, proposal, target) == RECONCILE_ACTION_UPDATE_VERSION


def test_edu_17_document_type_omitted_null(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, document_type="")
    assert proposal.normalized_content["document_type"] is None
    refs = plugin.build_proposal_refs(
        {"records": [{k: v for k, v in intake_row().items() if k != "document_type"}]},
        "canon-json-v1",
    )
    assert refs[0].normalized_content["document_type"] is None


def test_edu_17a_document_type_enrichment(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, document_type="diploma")
    target = canonical_ref(12, document_type=None)
    match = plugin.match(proposal, (target,))
    assert match.match_confidence == MATCH_CONFIDENCE_HIGH
    assert plugin.choose_exact_action(match, proposal, target) == RECONCILE_ACTION_UPDATE_VERSION


def test_edu_17b_document_type_clearing(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, document_type="")
    target = canonical_ref(13, document_type="diploma")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.matched_canonical_record_id == 13
    assert match.candidate_canonical_record_ids == (13,)
    assert "document_type" in match.detail["clearing_fields"]


def test_edu_18_both_dates_missing_manual(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="", year_to="", institution="Alone")
    match = plugin.match(proposal, ())
    assert match.match_kind == MATCH_KIND_NONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.detail["reason"] == "BOTH_DATES_MISSING"


def test_edu_19a_blank_clear_exact_date(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="")
    target = canonical_ref(20, started_at="2015-09-01")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.matched_canonical_record_id == 20
    assert match.candidate_canonical_record_ids == (20,)
    assert "started_at" in match.detail["clearing_fields"]


def test_edu_19a_year_clear_exact_date(plugin: EducationReconciliationPlugin) -> None:
    proposal = build_proposal(plugin, year_from="2019")
    target = canonical_ref(21, started_at="2015-09-01")
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.matched_canonical_record_id == 21
    assert match.candidate_canonical_record_ids == (21,)
    assert "started_at" in match.detail["clearing_fields"]
    assert match.detail["reason"] == "INCOMPLETE_OR_YEAR_ONLY_DATE"


@pytest.mark.parametrize(
    ("field", "canonical_value", "proposal_kw"),
    [
        ("specialty", "Математика", {"specialty": ""}),
        ("qualification", "Бакалавр", {"qualification": ""}),
        ("diploma_number", "D-1", {"diploma_number": ""}),
        ("document_type", "diploma", {"document_type": ""}),
    ],
)
def test_edu_19b_e_clear_semantic_fields(
    plugin: EducationReconciliationPlugin,
    field: str,
    canonical_value: str,
    proposal_kw: dict,
) -> None:
    proposal = build_proposal(plugin, **proposal_kw)
    target = canonical_ref(30, **{field: canonical_value})
    match = plugin.match(proposal, (target,))
    assert match.match_kind == MATCH_KIND_EXACT_ONE
    assert match.match_confidence == MATCH_CONFIDENCE_LOW
    assert match.matched_canonical_record_id == 30
    assert field in match.detail["clearing_fields"]


def test_payload_alias_education_key(plugin: EducationReconciliationPlugin) -> None:
    refs = plugin.build_proposal_refs({"education": [intake_row()]}, "canon-json-v1")
    assert len(refs) == 1
    assert refs[0].proposal_index == 0


def test_dual_container_payload_rejected(plugin: EducationReconciliationPlugin) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        plugin.build_proposal_refs(
            {
                "records": [intake_row(institution="FromRecords")],
                "education": [intake_row(institution="FromEducation")],
            },
            "canon-json-v1",
        )
    assert exc.value.code == "INVALID_EDUCATION_PAYLOAD"


def test_invalid_payload_missing_list(plugin: EducationReconciliationPlugin) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        plugin.build_proposal_refs({"other": []}, "canon-json-v1")
    assert exc.value.code == "INVALID_EDUCATION_PAYLOAD"


def test_load_canonical_refs_rejects_unexpected_type(
    plugin: EducationReconciliationPlugin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    education = EducationRecord(
        person_id=1,
        education_kind=EDUCATION_KIND_BASIC,
        record_id=10,
        institution_name="Ok Uni",
        started_at=date(2015, 9, 1),
        completed_at=date(2019, 6, 30),
        updated_at=datetime(2026, 7, 24, 10, 0, 0),
    )
    unexpected = TrainingRecord(
        person_id=1,
        training_kind=TRAINING_KIND_COURSE,
        record_id=99,
        title="Wrong type in education section",
        updated_at=datetime(2026, 7, 24, 10, 0, 0),
    )

    class _FakeRepo:
        def load_active_records(self, person_id: int, section_code: str):
            del person_id, section_code
            return (education, unexpected)

    monkeypatch.setattr(
        education_mod,
        "SqlAlchemySectionReadRepository",
        lambda conn: _FakeRepo(),
    )

    with pytest.raises(ReconciliationValidationError) as exc:
        plugin.load_canonical_refs(MagicMock(), person_id=1, digest_algorithm_version="canon-json-v1")

    assert exc.value.code == "INVALID_CANONICAL_RECORD"
    assert "TrainingRecord" in str(exc.value)
    # Fail-closed: do not return a partial tuple that silently omitted the bad row.
