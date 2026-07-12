# UDE-012 — Shared Write Runtime and Document Aggregate Foundation

WP: **UDE-012**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-011 ✓

> Final Shared Runtime WP. Write orchestration in-memory only. **No production wiring.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| `app/document_engine/write/` runtime | PO write-path changes |
| Command models + mutation plans | Persistence / ORM / SQL |
| Runtime DocumentAggregate | API / UI / FastAPI endpoints |
| Write Orchestrator + Command Policies | Operational Orders implementation |
| Runtime Domain Events (not persisted) | Production connection |
| DocumentEngineWriteFacade | Migrations |

---

## 2. Architecture — Complete Shared Runtime Stack

```text
Read Adapters (UDE-008)
        ↓
Read Services (UDE-009)
        ↓
Editorial Runtime (UDE-010)
        ↓
Lifecycle Runtime (UDE-011)
        ↓
Write Runtime (UDE-012)  ← NEW
        ↓
Future Document Aggregate (OO-IMP-001)
```

**Dependency direction:** Lifecycle → Write. Write never imports PO, ORM, adapters, or API.

---

## 3. UDE-004 / UDE-005 / UDE-011 Review Findings

| Area | Architecture | UDE-012 runtime | Classification |
|---|---|---|---|
| Activation | DocumentId at commit | `CreateDocumentCommand` plans `doc:{workspace}` ID in memory | Aligned — deferred persist |
| Promotion | Materialization | `PromoteDraftCommand` + `PromotionResult` | Aligned |
| Lifecycle bootstrap | DRAFT initial | Aggregate starts DRAFT | Aligned |
| MarkReady / Sign / Register | Transition commands | Command policies + mutation plans | Aligned |
| Cancel / Annul | void_kind CANCEL/ANNUL | `CancelDocumentCommand` / `AnnulDocumentCommand` | Aligned |
| Archive | Orthogonal | `ArchiveDocumentCommand` / `RestoreDocumentCommand` | Aligned |
| Domain events | Audit streams | Runtime events only — not written | Gap — by design |
| Persistence | Atomic commit | **No persistence** | Aligned — OO-IMP-001 |

No blocking incompatibilities. No production fixes applied.

---

## 4. Command Models

| Command | Purpose |
|---|---|
| `CreateDocumentCommand` | Activate from official draft |
| `PromoteDraftCommand` | Promote draft to runtime aggregate |
| `MarkReadyCommand` | DRAFT → READY_FOR_SIGNATURE |
| `ReturnToDraftCommand` | READY → DRAFT |
| `SignDocumentCommand` | READY → SIGNED |
| `RegisterDocumentCommand` | SIGNED → REGISTERED |
| `CancelDocumentCommand` | DRAFT/READY → VOIDED (CANCEL) |
| `AnnulDocumentCommand` | SIGNED/REGISTERED → VOIDED (ANNUL) |
| `ArchiveDocumentCommand` | ACTIVE → ARCHIVED |
| `RestoreDocumentCommand` | ARCHIVED → ACTIVE |

All immutable frozen dataclasses.

---

## 5. Command Results

| Result | Purpose |
|---|---|
| `LifecycleMutationPlan` | Planned state change + events |
| `CreateResult` | Activation planning outcome |
| `PromotionResult` | Promotion planning outcome |
| `RegistrationResult` | Registration planning outcome |
| `WriteEvaluation` | Unified orchestrator outcome |

No side effects — plans only.

---

## 6. Runtime Document Aggregate

| Model | Purpose |
|---|---|
| `DocumentAggregate` | In-memory aggregate root |
| `AggregateMetadata` | Runtime metadata (not ORM) |
| Locale blocks from `OfficialDraftSnapshot` | Editorial snapshot embedded |
| `validation_state` | `ValidationResult` from lifecycle gates |

---

## 7. Domain Events (runtime only)

`DocumentActivated`, `DocumentPromoted`, `DocumentMarkedReady`, `DocumentReturnedToDraft`, `DocumentSigned`, `DocumentRegistered`, `DocumentCancelled`, `DocumentAnnulled`, `DocumentArchived`, `DocumentRestored`

Not written to audit persistence.

---

## 8. Write Orchestrator

`WriteOrchestrator.plan(command, aggregate, draft, lifecycle_snapshot)`:
1. Delegates to `CommandPolicy` per command type
2. Uses `DocumentEngineLifecycleSnapshot` for gate evaluation
3. Returns `WriteEvaluation` with `LifecycleMutationPlan`
4. `apply_plan_in_memory()` returns new aggregate — no DB

---

## 9. Write Facade

`DocumentEngineWriteFacade`:
| Method | Purpose |
|---|---|
| `build_context_from_detail(...)` | Full upstream snapshot chain |
| `plan_command(command, context)` | Plan any write command |
| `create_from_draft(context)` | Activation planning |
| `promote_from_draft(context)` | Promotion planning |

---

## 10. Production Files Changed

**None.** All changes additive under `app/document_engine/write/` and tests/docs.

---

## 11. Test Commands

```bash
pytest tests/document_engine/write/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
```

---

## 12. Shared Runtime Completion

UDE-007 through UDE-012 complete the Shared Runtime:

| Layer | WP | Entry Point |
|---|---|---|
| Contracts | UDE-007 | `app.document_engine` |
| Read Adapters | UDE-008 | `PersonnelReadAdapter` |
| Read Services | UDE-009 | `DocumentEngineReadFacade` |
| Editorial | UDE-010 | `DocumentEngineEditorialFacade` |
| Lifecycle | UDE-011 | `DocumentEngineLifecycleFacade` |
| Write | UDE-012 | `DocumentEngineWriteFacade` |

**Ready for OO-IMP-001** without additional Shared Runtime components.

---

## 13. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
