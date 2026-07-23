# tests/ppr/test_wp_pr_015_read_path.py
"""WP-PR-015 read-path unit tests — DTO serialization and section mapping."""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.api.ppr_mappers import composite_to_response, summary_to_response
from app.api.ppr_schemas import PprExternalEmploymentRecordResponse
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_SOURCE_IMPORT_ROW,
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    VERIFICATION_STATUS_PENDING,
)
from app.ppr.domain.identity_models import (
    INPUT_KIND_PERSON_ID,
    IdentityResolution,
    PersonIdentitySnapshot,
    RESULT_DIRECT,
)
from app.ppr.domain.models import PPR_LIFECYCLE_CREATED
from app.ppr.domain.person_models import PersonGeneralReadSnapshot
from app.ppr.domain.section_models import (
    ExternalEmploymentRecord,
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
)
from app.ppr.read.models import (
    PprAdditionalReadSlice,
    PprCompositeReadMetadata,
    PprCompositeReadModel,
    PprCompositeSummary,
    PprSectionAggregation,
)


def _identity(person_id: int = 42) -> tuple[PersonIdentitySnapshot, IdentityResolution]:
    snapshot = PersonIdentitySnapshot(
        person_id=person_id,
        person_status="active",
        merged_into_person_id=None,
        match_key="test-key",
        iin=None,
    )
    resolution = IdentityResolution(
        input_kind=INPUT_KIND_PERSON_ID,
        input_id=person_id,
        employee_id=None,
        source_person_id=person_id,
        resolved_person_id=person_id,
        merge_redirected=False,
        merge_chain=(person_id,),
        result_code=RESULT_DIRECT,
    )
    return snapshot, resolution


def _general(person_id: int = 42) -> PersonGeneralReadSnapshot:
    now = datetime.now(UTC)
    return PersonGeneralReadSnapshot(
        person_id=person_id,
        full_name="Test Person",
        last_name=None,
        first_name=None,
        middle_name=None,
        birth_date=None,
        iin=None,
        created_at=now,
        updated_at=now,
    )


def _empty_section(section_code: str) -> PprSectionAggregation:
    return PprSectionAggregation(section_code=section_code, active=())


def test_external_employment_record_response_serializes_canonical_fields() -> None:
    now = datetime.now(UTC)
    record = ExternalEmploymentRecord(
        record_id=7,
        person_id=42,
        record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name="ТОО «Пример»",
        department_name="Бухгалтерия",
        position_title="Инженер",
        employment_type="full_time",
        started_at=date(2018, 3, 1),
        ended_at=date(2020, 12, 31),
        notes="Кадровая запись",
        employee_context_id=99,
        source_system=EXTERNAL_EMPLOYMENT_SOURCE_IMPORT_ROW,
        source_id="import-row-123",
        provenance={"batch_id": "b-1", "actor": "hr-import"},
        verification_status=VERIFICATION_STATUS_PENDING,
        lifecycle_status="active",
        created_at=now,
        updated_at=now,
    )
    identity, resolution = _identity()
    composite = PprCompositeReadModel(
        person_id=42,
        employee_id=99,
        materialized=True,
        lifecycle_state=PPR_LIFECYCLE_CREATED,
        hr_relationship_context=None,
        envelope_version=1,
        envelope_created_at=now,
        envelope_updated_at=now,
        identity=identity,
        identity_resolution=resolution,
        general=_general(),
        education=_empty_section(SECTION_CODE_PPR_EDUCATION),
        training=_empty_section(SECTION_CODE_PPR_TRAINING),
        family=_empty_section(SECTION_CODE_PPR_FAMILY),
        external_employment=PprSectionAggregation(
            section_code=SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
            active=(record,),
        ),
        military=_empty_section(SECTION_CODE_PPR_MILITARY),
        events=None,
        intended_employment=None,
        additional=PprAdditionalReadSlice.empty(),
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=42,
            merge_redirected=False,
        ),
    )

    response = composite_to_response(
        composite,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
    )

    section = response.sections[SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]
    assert section.section_code == SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY
    assert len(section.active) == 1
    item = section.active[0]
    assert isinstance(item, PprExternalEmploymentRecordResponse)

    assert item.record_id == 7
    assert item.record_kind == EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE
    assert item.employer_name == "ТОО «Пример»"
    assert item.department_name == "Бухгалтерия"
    assert item.position_title == "Инженер"
    assert item.employment_type == "full_time"
    assert item.started_at == date(2018, 3, 1)
    assert item.ended_at == date(2020, 12, 31)
    assert item.notes == "Кадровая запись"
    assert item.employee_context_id == 99
    assert item.source_system == EXTERNAL_EMPLOYMENT_SOURCE_IMPORT_ROW
    assert item.source_id == "import-row-123"
    assert item.provenance == {"batch_id": "b-1", "actor": "hr-import"}
    assert item.verification_status == VERIFICATION_STATUS_PENDING
    assert item.lifecycle_status == "active"
    assert item.created_at == now
    assert item.updated_at == now

    # person_id is provided by composite identity, not duplicated per record.
    assert response.identity.resolved_person_id == 42
    assert response.identity.employee_context_id == 99
    assert "person_id" not in PprExternalEmploymentRecordResponse.model_fields

    assert section.superseded == []
    assert section.voided == []


def test_external_employment_record_response_preserves_per_record_employee_context_id() -> None:
    now = datetime.now(UTC)
    record_with_context = ExternalEmploymentRecord(
        record_id=11,
        person_id=42,
        record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name="Employer A",
        position_title="Role A",
        started_at=date(2017, 1, 1),
        employee_context_id=1001,
    )
    record_without_context = ExternalEmploymentRecord(
        record_id=12,
        person_id=42,
        record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name="Employer B",
        position_title="Role B",
        started_at=date(2016, 1, 1),
        employee_context_id=None,
    )
    record_other_context = ExternalEmploymentRecord(
        record_id=13,
        person_id=42,
        record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name="Employer C",
        position_title="Role C",
        started_at=date(2015, 1, 1),
        employee_context_id=2002,
    )
    identity, resolution = _identity()
    composite = PprCompositeReadModel(
        person_id=42,
        employee_id=1001,
        materialized=True,
        lifecycle_state=PPR_LIFECYCLE_CREATED,
        hr_relationship_context=None,
        envelope_version=1,
        envelope_created_at=now,
        envelope_updated_at=now,
        identity=identity,
        identity_resolution=resolution,
        general=_general(),
        education=_empty_section(SECTION_CODE_PPR_EDUCATION),
        training=_empty_section(SECTION_CODE_PPR_TRAINING),
        family=_empty_section(SECTION_CODE_PPR_FAMILY),
        external_employment=PprSectionAggregation(
            section_code=SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
            active=(record_with_context, record_without_context, record_other_context),
        ),
        military=_empty_section(SECTION_CODE_PPR_MILITARY),
        events=None,
        intended_employment=None,
        additional=PprAdditionalReadSlice.empty(),
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=42,
            merge_redirected=False,
        ),
    )

    response = composite_to_response(
        composite,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
    )
    items = response.sections[SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY].active
    assert [item.record_id for item in items] == [11, 12, 13]
    assert [item.employee_context_id for item in items] == [1001, None, 2002]
    assert response.identity.employee_context_id == 1001


def test_external_employment_record_response_defaults_source_system() -> None:
    record = ExternalEmploymentRecord(
        record_id=1,
        person_id=42,
        record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name="Employer",
        position_title="Role",
        started_at=date(2019, 1, 1),
    )
    now = datetime.now(UTC)
    identity, resolution = _identity()
    composite = PprCompositeReadModel(
        person_id=42,
        employee_id=None,
        materialized=True,
        lifecycle_state=PPR_LIFECYCLE_CREATED,
        hr_relationship_context=None,
        envelope_version=1,
        envelope_created_at=now,
        envelope_updated_at=now,
        identity=identity,
        identity_resolution=resolution,
        general=_general(),
        education=_empty_section(SECTION_CODE_PPR_EDUCATION),
        training=_empty_section(SECTION_CODE_PPR_TRAINING),
        family=_empty_section(SECTION_CODE_PPR_FAMILY),
        external_employment=PprSectionAggregation(
            section_code=SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
            active=(record,),
        ),
        military=_empty_section(SECTION_CODE_PPR_MILITARY),
        events=None,
        intended_employment=None,
        additional=PprAdditionalReadSlice.empty(),
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=42,
            merge_redirected=False,
        ),
    )

    response = composite_to_response(
        composite,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
    )
    item = response.sections[SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY].active[0]
    assert item.source_system == EXTERNAL_EMPLOYMENT_SOURCE_MANUAL
    assert item.source_id is None
    assert item.provenance is None


def test_summary_includes_external_employment_active_count() -> None:
    now = datetime.now(UTC)
    identity, resolution = _identity()
    summary = PprCompositeSummary(
        person_id=42,
        employee_id=None,
        materialized=True,
        lifecycle_state=PPR_LIFECYCLE_CREATED,
        hr_relationship_context=None,
        identity=identity,
        identity_resolution=resolution,
        full_name="Test Person",
        education_active_count=0,
        training_active_count=0,
        family_active_count=0,
        external_employment_active_count=3,
        military_active_count=0,
        recent_event_count=1,
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=42,
            merge_redirected=False,
        ),
    )

    response = summary_to_response(
        summary,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
    )
    assert response.external_employment_active_count == 3
