"""Fractional training hours remain exact and JSON serializable in business audit."""
import json
from decimal import Decimal

from app.ppr.application.event_builder import build_section_event
from app.ppr.domain.section_models import TrainingRecord, SectionMutationResult, MUTATION_KIND_INSERT


def test_training_audit_preserves_decimal_hours():
    event = build_section_event(person_id=1, actor_id="2", command_id="fractional-training",
        correlation_id=None, employee_context_id=None,
        mutation=SectionMutationResult(record=TrainingRecord(person_id=1, training_kind="course",
            hours=Decimal("36.125")), mutation_kind=MUTATION_KIND_INSERT))
    payload = json.loads(json.dumps(event.payload))
    assert payload["after"]["hours"] == "36.125"
