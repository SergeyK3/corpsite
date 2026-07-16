# ADR-054 NOTE — Intended Employment Lifecycle & Source of Truth

## Status

**Accepted** (architectural note)

| Field | Value |
|-------|-------|
| Parent ADR | [ADR-054](./ADR-054-personnel-personal-record-aggregate-model.md) |
| Context | Architectural Review «Заявитель → Работник», 2026-07-16 |
| Forward-flow | **COMPLETE** — ready for commit |
| Related migration | `m3n4o5p6q7r8_ppr_candidate_intended_employment` |

---

## Decision

Поля `intended_*` на envelope (`personnel_record_metadata`) описывают **предполагаемое трудоустройство до приказа о приёме**. Они **не являются** Employment Relationship и **не являются** operational placement.

### Lifecycle

| Phase | `intended_*` role |
|-------|-------------------|
| **До приказа HIRE** (CANDIDATE) | Editable planning data; defaults for HIRE order draft (`hire-defaults` API); visible in UI section «Предполагаемое трудоустройство» |
| **После Apply HIRE** (EMPLOYED) | **Historical record only** — preserved in DB, not used as Source of Truth |

### Source of Truth after Apply

После успешного Apply приказа HIRE источниками истины являются **исключительно**:

- `employees` (org_unit, position, rate, is_active, …)
- Employment Relationship (`hr_relationship_context`, operational status)
- `person_assignments`
- `employee_events` (юридически значимые кадровые события)

### Prohibited uses after Apply

Поля `intended_*` **не участвуют** в:

- API responses as placement data (Composite Read returns `intended_employment: null` for EMPLOYED)
- Query Layer calculations or roster placement
- UI current assignment display
- Personnel services (apply, transfer, termination logic)
- Payroll / staffing calculations
- Personnel order apply payload resolution

Apply HIRE resolves placement **only** from order item payload (`org_unit_id`, `position_id`, `employment_rate`), never from `intended_*`.

---

## Enforcement (implemented)

| Layer | Gate |
|-------|------|
| Read orchestrator | `intended_employment` slice only when `hr_relationship_context = CANDIDATE` |
| API `GET .../hire-defaults` | 404 unless CANDIDATE |
| API `PATCH .../intended-employment` | 409 unless CANDIDATE |
| Service | `_require_candidate_context()` on write; `load_hire_defaults` returns null unless CANDIDATE |
| UI | Intended section visible only when applicant banner active |

---

## Rationale

1. **Separation of planning vs employment** — intended employment is pre-contract intent; Apply creates legal employment fact.
2. **No dual SoT** — after hire, displaying intended alongside actual assignment would confuse operators and break invariants.
3. **Audit trail** — retaining `intended_*` in DB preserves what was planned at application time without polluting operational reads.
4. **EPIC-4 compatibility** — person-owned sections remain on same PPR; intended block is lifecycle-gated, not a separate aggregate.

---

## Consequences

### Positive

- Clear SoT boundary for forward-flow and future sections.
- Rehire / void can reference historical intended data if needed for audit UI (read-only, CANDIDATE-only APIs).

### Negative / follow-up

- VOID HIRE must restore CANDIDATE context to re-expose intended block — see [WP-PO-VOID-HIRE-001](../personnel-orders/work-packages/WP-PO-VOID-HIRE-001-hr-context-rollback.md).
- Optional future: explicit null-out or archive flag on `intended_*` after Apply (not required for SoT compliance).

---

## References

- [WP-PR-012 § R7](../architecture/WP-PR-012-ppr-implementation-roadmap.md) — Query API
- [WP-PO-HIRE-LIFECYCLE-BACKLOG-INDEX](../personnel-orders/work-packages/WP-PO-HIRE-LIFECYCLE-BACKLOG-INDEX.md)
- Tests: `tests/test_ppr_hire_from_applicant_apply.py`
