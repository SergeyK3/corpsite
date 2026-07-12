# UDE-007 — Shared Runtime Contracts and PO Characterization Baseline

WP: **UDE-007**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-006 ✓  
HEAD at start: `58be212`

> First Unified Document Engine WP with code changes. **Production Personnel Orders behavior unchanged.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| Minimal `app/document_engine/` shared runtime package | PO ORM / schema / API / UI changes |
| First-wave value objects and contracts | Write adapters |
| Unit tests for shared contracts | Operational Orders runtime |
| P0 PO characterization baseline | Document aggregate runtime |
| Dependency guard test | Lifecycle orchestrator |
| Implementation record and matrices | Commit / push / deploy |

---

## 2. Codebase Review Summary

### Backend conventions observed

| Pattern | Project convention |
|---|---|
| Cross-cutting pure domain | Top-level package (`app/org_scope/`) |
| Multi-module domain logic | `app/services/<domain>/` subpackage |
| Status codes | Module-level `UPPER_SNAKE` strings in ORM models |
| Enums | `str, Enum` sparingly (`app/errors.py`, `app/org_scope/types.py`) |
| Immutable VOs | `@dataclass(frozen=True, slots=True)` |
| API boundary | Pydantic in `app/directory/*_schemas.py` only |
| Tests | `tests/test_wp_po_*` at repo root |

### Package placement decision

**Selected:** `app/document_engine/` (parallel to `app/org_scope/`)

**Rationale:** UDE shared contracts are persistence-free domain types, not service orchestration. Mirrors `org_scope` boundary. Does not compete with `app/services/personnel_orders_*` write-path.

**Rejected for UDE-007:** `app/services/document_engine/` — reserved for future orchestration services (UDE-009+).

---

## 3. Implemented Runtime Contracts

| Contract | Location |
|---|---|
| DocumentId | `value_objects/identity.py` |
| DocumentKind | `value_objects/identity.py` |
| DocumentSpecialization | `value_objects/identity.py` |
| DocumentLifecycleState | `value_objects/lifecycle.py` |
| ArchiveState | `value_objects/lifecycle.py` |
| VoidKind | `value_objects/lifecycle.py` |
| LocaleCode | `value_objects/localization.py` |
| StalenessState | `value_objects/localization.py` |
| TextSourceType | `value_objects/provenance.py` |
| PartyReferenceType | `contracts/party.py` |
| PartyReference | `contracts/party.py` |
| ValidationSeverity | `contracts/validation.py` |
| ValidationIssue | `contracts/validation.py` |
| ValidationResult | `contracts/validation.py` |

**Total:** 14 runtime types (first wave only).

---

## 4. Deferred Contracts

| Contract | Reason |
|---|---|
| Document aggregate | No consumer; UDE-008 adapters read PO directly |
| ExecutionObligation | No consumer; forbidden in UDE-007 |
| Scenario Registry / Generation Engine | OO runtime not started |
| Lifecycle Orchestrator | Architecture only (UDE-005) |
| Draft Workspace / Editorial Engine | UDE-002/003 architecture only |
| LocaleRepresentation / EffectiveText | Read view shapes deferred to UDE-008 |
| LifecycleAuditEventRecord | Adapter read model in UDE-008 |

See [`data/UDE-007-runtime-contract-inventory.csv`](./data/UDE-007-runtime-contract-inventory.csv).

---

## 5. Characterization Coverage

### New backend tests

| File | Area |
|---|---|
| `test_personnel_orders_characterization_lifecycle.py` | Statuses, cancel, void_kind |
| `test_personnel_orders_characterization_archive.py` | Archive, immutability, restore |
| `test_personnel_orders_characterization_journal.py` | Journal closed filter |
| `test_personnel_orders_characterization_localization.py` | RU/KK editorial independence |
| `test_personnel_orders_characterization_item_registry.py` | MVP item types, RATE_CHANGE rejection |
| `test_personnel_orders_characterization_hire.py` | HIRE without employee_id |
| `test_personnel_orders_characterization_audit.py` | Audit append-only, GET success |
| `test_personnel_orders_characterization_ownership.py` | cancel.own vs privileged |

### New frontend tests

| File | Area |
|---|---|
| `personnelOrdersApi.client.characterization.test.ts` | include_closed defaults |
| `personnelOrderPrint.characterization.test.ts` | Print VM bilingual / voided marks |

### Existing tests already covering baseline

18 `test_wp_po_*` backend files and 15 frontend PO test files (see [`data/UDE-007-characterization-coverage.csv`](./data/UDE-007-characterization-coverage.csv)).

---

## 6. Test Commands

```bash
# Shared contract tests
pytest tests/document_engine/ -q

# PO characterization baseline
pytest tests/personnel_orders/characterization/ -q

# PO regression subset (existing suite)
pytest tests/test_wp_po_lc_del_004_cancel_api.py -q
pytest tests/test_wp_po_lc_del_005_archive_api.py -q
pytest tests/test_wp_po_lc_del_005a_archived_immutability_api.py -q
pytest tests/test_wp_po_lc_del_006_journal_closed_filter_api.py -q
pytest tests/test_wp_po_edit_002_editorial_api.py -q
pytest tests/test_wp_po_006_e2e_validation.py -q

# Frontend characterization (if added)
cd corpsite-ui && npm test -- personnelOrdersApi.client.characterization.test.ts personnelOrderPrint.characterization.test.ts
```

---

## 7. Findings

See [`UDE-007-characterization-findings.md`](./UDE-007-characterization-findings.md).

No production defects fixed. No blocking incompatibilities found.

---

## 8. Dependency Rules

| Rule | Enforcement |
|---|---|
| `document_engine` must not import PO/OO modules | `tests/document_engine/test_dependency_rules.py` |
| `document_engine` must not import ORM/API/SQLAlchemy/FastAPI/Pydantic | AST import inspection test |
| PO must not import `document_engine` in UDE-007 | Intentional — no production consumer yet |

---

## 9. Production Files Changed

**None.**

All changes are additive:

- `app/document_engine/**` (new)
- `tests/document_engine/**` (new)
- `tests/personnel_orders/characterization/**` (new)
- `corpsite-ui/.../*.characterization.test.ts` (new)
- `docs/unified-document-engine/UDE-007-*` (new)
- `docs/unified-document-engine/data/UDE-007-*.csv` (new)
- `docs/unified-document-engine/README.md` (updated)

---

## 10. Compatibility Conclusion

| Criterion | Result |
|---|---|
| PO production behavior unchanged | ✓ |
| PO persistence unchanged | ✓ |
| PO API/UI/PDF unchanged | ✓ |
| No synthetic audit history | ✓ |
| No legacy regeneration | ✓ |
| Shared package isolated | ✓ |
| Characterization P0 baseline | ✓ |

**Personnel Orders remains compatibility authority.** Shared contracts exist in parallel only.

---

## 11. Handoff to UDE-008

**UDE-008 — Shared Read-only Adapters for Personnel Orders**

| UDE-007 deliverable | UDE-008 use |
|---|---|
| `DocumentLifecycleState`, `VoidKind`, `ArchiveState` | Map PO rows → shared read view |
| `PartyReference` | `employee_id` → `PartyReference(PERSON, …)` read mapping |
| `LocaleCode`, `StalenessState`, `TextSourceType` | Editorial/locale read adapter |
| `ValidationResult` | Adapter-side shape validation (read-only) |
| Characterization baseline | Adapter parity tests against fixed PO behavior |
| Dependency guard | Extend to adapter package boundaries |

**Ready for UDE-008:** Yes — contracts and characterization baseline provide safe foundation for read-only adapters without PO write-path coupling.

---

## 12. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
