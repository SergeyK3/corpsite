# UDE-009 — Shared Read Services and Document Read Model

WP: **UDE-009**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-008 ✓

> First WP where Shared Runtime performs real domain work. **Read-only. No production behavior change.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| `app/document_engine/read_models/` shared read models | PO write-path changes |
| `app/document_engine/read_services/` read services | Operational Order services |
| `DocumentEngineReadFacade` public entry point | API / UI / PDF / HTML changes |
| Read service compatibility harness | ORM / schema / migration changes |
| Dependency rules + unit/compatibility tests | Write services |
| Documentation and inventory matrices | Editorial Runtime (UDE-010) |

---

## 2. Architecture

```text
Personnel Orders (System of Record)
        ↓ read dicts / optional DB supplement
Personnel Read Adapters (UDE-008)
        ↓ adapter views / PersonnelReadBundle
Shared Runtime Contracts (UDE-007)
        ↓
Shared Read Services (UDE-009)  ← NEW
        ↓ shared read models
DocumentEngineReadFacade  ← single public entry
        ↓
Future Consumers
(OO, Shared UI, Reporting, Search, APIs)
```

**Dependency direction:** PO → Adapters → Read Services → Read Models. Read services never import PO ORM, PO services, or API layers.

---

## 3. Read Service Inventory

| Service | Module | Adapter | Returns |
|---|---|---|---|
| DocumentReadService | `document.py` | PersonnelReadAdapter / PersonnelDocumentAdapter | `DocumentReadModel` |
| LifecycleReadService | `lifecycle.py` | PersonnelLifecycleAdapter | `LifecycleReadModel` |
| LocalizationReadService | `localization.py` | PersonnelLocaleAdapter | `LocaleReadModel` |
| AuditReadService | `audit.py` | PersonnelAuditAdapter | `AuditReadModel` |
| PrintReadService | `print.py` | PersonnelPrintAdapter | `PrintReadModel` |
| ItemReadService | `item.py` | PersonnelItemAdapter | `Tuple[ItemReadModel, ...]` |
| **DocumentEngineReadFacade** | `facade.py` | **All via PersonnelReadAdapter** | **`DocumentEngineReadSnapshot`** |

See [`data/UDE-009-read-service-inventory.csv`](./data/UDE-009-read-service-inventory.csv).

---

## 4. Read Models

Runtime read models — not persistence, not ORM, not API DTOs.

| Model | Module | Key fields |
|---|---|---|
| DocumentReadModel | `document.py` | document_id, kind, lifecycle, archive, void_kind, metadata |
| LifecycleReadModel | `lifecycle.py` | document_id, lifecycle_state, archive_state, void_kind |
| LocaleReadModel | `locale.py` | blocks (effective/override/generated/staleness), snapshots |
| AuditReadModel | `audit.py` | append-only events tuple |
| PrintReadModel | `print.py` | status_mark, printable, records (metadata only) |
| ItemReadModel | `item.py` | backend/display types, event_subject, payload |

See [`data/UDE-009-read-models.csv`](./data/UDE-009-read-models.csv).

---

## 5. Facade Architecture

`DocumentEngineReadFacade` is the **single public entry point** for Shared Runtime read operations.

| Method | Input | Output |
|---|---|---|
| `from_detail(detail, ...)` | PO detail dict + optional supplement/editorial/audit | `DocumentEngineReadSnapshot` |
| `from_bundle(bundle)` | `PersonnelReadBundle` from adapters | `DocumentEngineReadSnapshot` |

`DocumentEngineReadSnapshot` aggregates all read models in one frozen snapshot.

**No `from_order_id` on facade** — keeps read services independent of PO service imports. Integration tests use `PersonnelReadAdapter.from_order_id` at the adapter layer.

---

## 6. Dependency Rules

### Read services MUST NOT import

- `app.db`
- `app.directory`
- `app.api`
- `app.services.personnel*`
- `app.services.operational*`
- `sqlalchemy`, `fastapi`, `pydantic`

### Read services MAY import

- `app.document_engine.adapters.*`
- `app.document_engine.contracts.*`
- `app.document_engine.value_objects.*`
- `app.document_engine.read_models.*`

### PO runtime MUST NOT import

- `app.document_engine.read_services`
- `app.document_engine.read_models`

Enforced by `tests/document_engine/read_services/test_read_service_dependency_rules.py`.

---

## 7. Compatibility Harness

Extended chain for UDE-009:

```text
Legacy PO detail
    ↓ (UDE-008 harness)
PersonnelReadBundle (adapter views)
    ↓ (UDE-009 harness)
DocumentEngineReadSnapshot (read models)
```

`compare_bundle_to_read_snapshot()` verifies adapter views and read models are 1:1.

Known gaps from UDE-007/008 (void_kind API supplement) are preserved — not auto-fixed.

---

## 8. Coverage Matrix

| Area | Unit tests | Compatibility | Dependency |
|---|---|---|---|
| DocumentReadService | ✓ | ✓ | ✓ |
| LifecycleReadService | ✓ | ✓ | ✓ |
| LocalizationReadService | ✓ | ✓ | ✓ |
| AuditReadService | ✓ | ✓ | ✓ |
| PrintReadService | ✓ | ✓ | ✓ |
| ItemReadService | ✓ | ✓ | ✓ |
| DocumentEngineReadFacade | ✓ | ✓ | ✓ |

See [`data/UDE-009-coverage.csv`](./data/UDE-009-coverage.csv).

---

## 9. Production Files Changed

**None.** All changes are additive under:

- `app/document_engine/read_models/`
- `app/document_engine/read_services/`
- `tests/document_engine/read_services/`
- `docs/unified-document-engine/`

PO services, routes, models, frontend — unchanged.

---

## 10. Test Commands

```bash
pytest tests/document_engine/read_services/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
```

---

## 11. Handoff to UDE-010

**UDE-010 — Shared Editorial & Localization Runtime**

| UDE-009 deliverable | UDE-010 use |
|---|---|
| `LocalizationReadService` + `LocaleReadModel` | Editorial runtime input shapes |
| `DocumentEngineReadFacade` | Consumer entry point |
| `StalenessState` / `TextSourceType` in read models | Localization policy enforcement |
| Read service compatibility harness | Regression guard during editorial extraction |

**Ready for UDE-010:** Yes — Shared Runtime is now a reusable read layer independent of PO internals.

---

## 12. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
