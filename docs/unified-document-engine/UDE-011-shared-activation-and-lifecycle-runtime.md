# UDE-011 — Shared Activation & Lifecycle Runtime

WP: **UDE-011**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-010 ✓

> First WP where Shared Runtime performs lifecycle orchestration. **Read-only evaluation. No production behavior change.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| `app/document_engine/lifecycle/` runtime | PO write-path changes |
| Activation + lifecycle evaluation models | Persistence / ORM |
| PromotionPolicy, RegistrationPolicy, ReadinessPolicy | API / UI changes |
| DocumentEngineLifecycleFacade | Promotion/Registration commands |
| Lifecycle rules + gates (evaluation only) | Draft Workspace runtime |
| Compatibility + dependency tests | Operational Orders runtime |

---

## 2. Architecture

```text
Personnel Orders (System of Record)
        ↓
Read Adapters (UDE-008)
        ↓
Shared Read Services (UDE-009)
        ↓
Shared Editorial Runtime (UDE-010)
        ↓
Shared Activation & Lifecycle Runtime (UDE-011)  ← NEW
        ↓
Future Document Aggregate (OO)
```

**Dependency direction:** Editorial → Lifecycle. Lifecycle never imports PO, ORM, adapters, or API.

---

## 3. UDE-004 / UDE-005 Review Findings

| Area | Architecture target | Runtime implementation | Classification |
|---|---|---|---|
| Activation | Birth ceremony at commit | `ActivationDecision` — eligibility only | Aligned (read-only) |
| Promotion | Materialization from OfficialDraft | `PromotionPolicy` — no Document created | Aligned |
| Document Birth | DocumentId at activation | **No DocumentId** in UDE-011 | Aligned — deferred to write runtime |
| Lifecycle Bootstrap | DRAFT initial state | Rules model DRAFT entry | Aligned |
| READY gates | CURRENT locales, E* validation | `ReadinessPolicy` + `ValidationResult` | Aligned |
| Signed Snapshot | Immutable at SIGNED | `SignedSnapshotDescriptor` — eligibility only | Aligned |
| Registration | From SIGNED only | `RegistrationPolicy` — no number assigned | Aligned |
| Cancel / Annul | CANCEL vs ANNUL void_kind | `LifecycleGate.CANCEL` / `ANNUL` rules | Aligned |
| Archive | Orthogonal ACTIVE/ARCHIVED | Evaluated via `LifecycleGate.ARCHIVE` | Aligned |
| PO lifecycle | Five states + archive | `DocumentLifecycleState` + `ArchiveState` | Aligned |

No blocking incompatibilities. No production fixes applied.

---

## 4. Lifecycle Models

| Model | Purpose |
|---|---|
| `ActivationDecision` | Activation eligibility — no DocumentId |
| `LifecycleDecision` | Allowed transitions + blockers for current state |
| `LifecycleTransition` | Single transition evaluation |
| `LifecycleGate` | Gate identifier (MARK_READY, SIGN, REGISTER, etc.) |
| `LifecycleViolation` | Blocking lifecycle finding |
| `PromotionReadiness` | OfficialDraftSnapshot promotion eligibility |
| `RegistrationReadiness` | Registration eligibility — no number |
| `LifecycleEvaluation` | Full evaluation aggregate |
| `SignedSnapshotDescriptor` | Signed snapshot eligibility |

See [`data/UDE-011-lifecycle-models.csv`](./data/UDE-011-lifecycle-models.csv).

---

## 5. Services

| Service | Input | Output |
|---|---|---|
| `ActivationService` | `OfficialDraftSnapshot` | `ActivationDecision` |
| `LifecycleEvaluationService` | `EditorialDocument` + `LifecycleReadModel` | `LifecycleEvaluation` |
| `ReadinessPolicy` | Draft/editorial inputs | violations + `ValidationResult` |
| `PromotionPolicy` | `OfficialDraftSnapshot` | `PromotionReadiness` |
| `RegistrationPolicy` | `LifecycleReadModel` | `RegistrationReadiness` |
| `LifecycleRules` | Current/target states | structural transition rules |
| **`DocumentEngineLifecycleFacade`** | read/editorial snapshots | **`DocumentEngineLifecycleSnapshot`** |

---

## 6. Readiness Rules

| Check | Gate | Blocker code |
|---|---|---|
| Mandatory locales (ru, kk) | PROMOTION | E_LOCALE_MISSING |
| Effective text non-empty | PROMOTION | E_EFFECTIVE_EMPTY |
| Review CURRENT only | PROMOTION | E_REVIEW_* |
| Staleness not blocking | PROMOTION | E_STALENESS_* |
| Metadata order_number/date | PROMOTION | E_METADATA_* |
| item_count > 0 | PROMOTION | E_ITEMS_REQUIRED |
| workspace_reference present | ACTIVATION | E_WORKSPACE_REF |
| Editorial sections present | MARK_READY | E_SECTIONS_REQUIRED |

See [`data/UDE-011-readiness-matrix.csv`](./data/UDE-011-readiness-matrix.csv).

---

## 7. Lifecycle Gates

| Gate | From state(s) | To state | VoidKind |
|---|---|---|---|
| MARK_READY | DRAFT | READY_FOR_SIGNATURE | — |
| RETURN_TO_DRAFT | READY_FOR_SIGNATURE | DRAFT | — |
| SIGN | READY_FOR_SIGNATURE | SIGNED | — |
| REGISTER | SIGNED | REGISTERED | — |
| CANCEL | DRAFT, READY_FOR_SIGNATURE | VOIDED | CANCEL |
| ANNUL | SIGNED, REGISTERED | VOIDED | ANNUL |
| ARCHIVE | any (orthogonal) | — | — |
| ACTIVATION | pre-document | — | — |
| PROMOTION | DRAFT context | — | — |

See [`data/UDE-011-lifecycle-gates.csv`](./data/UDE-011-lifecycle-gates.csv).

---

## 8. Facade

`DocumentEngineLifecycleFacade` — single public entry:

| Method | Returns |
|---|---|
| `from_read_snapshot(snapshot)` | `DocumentEngineLifecycleSnapshot` |
| `from_editorial_snapshot(editorial, read)` | `DocumentEngineLifecycleSnapshot` |
| `from_detail(detail, ...)` | via read + editorial chain |

`DocumentEngineLifecycleSnapshot` contains: `activation`, `evaluation`, `promotion_readiness`, `registration_readiness`, `lifecycle_decision`.

---

## 9. Production Files Changed

**None.** All changes additive under `app/document_engine/lifecycle/` and tests/docs.

---

## 10. Test Commands

```bash
pytest tests/document_engine/lifecycle/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
```

---

## 11. Handoff to OO-IMP-001

| UDE-011 deliverable | OO-IMP-001 use |
|---|---|
| `DocumentEngineLifecycleFacade` | Document Aggregate consumer entry |
| `ActivationDecision` | Write runtime activation gate |
| `PromotionReadiness` | Promotion command precondition |
| `LifecycleEvaluation` | Lifecycle orchestration input |
| `LifecycleRules` | Transition policy enforcement |

**Ready for OO-IMP-001:** Yes — Shared Runtime stack (UDE-007–011) complete for read/evaluation layer. Write runtime is next consumer layer.

---

## 12. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
