# OP-RES-006 — Personnel Orders Gap Analysis

WP: **OP-RES-006** (supporting artifact)  
Date: **2026-07-12**  
Mode: **Read-only analysis** — no code changes

---

## Purpose

Классифицировать компоненты текущего Personnel Orders production MVP относительно целевого Unified Document Engine.

**Classification legend:**

| Class | Meaning |
|---|---|
| **A** | Already reusable as Document Engine foundation |
| **B** | Reusable after extraction/refactoring |
| **C** | Personnel-specific — remains specialization |
| **D** | Temporary implementation debt |
| **E** | Missing for Operational Orders |

---

## 1. Document Structure

| Component | Class | Evidence | Notes |
|---|---|---|---|
| `PersonnelOrder` header model | **B** | `app/db/models/personnel_orders.py` | Extract to generic Document metadata |
| `PersonnelOrderItem` numbered items | **B** | same | Generalize to Order Item contract |
| Editorial blocks (`title`, `preamble`, `closing`, `body`, `basis`) | **A** | `personnel_order_*_editorial_blocks` | Matches OP-RES-005 override model |
| Structured basis (`personnel_order_item_bases`) | **C** | 7 HR basis enums | OO has different basis patterns |
| Legacy `personnel_order_localized_texts` | **D** | deprecated dual path | Converge to editorial blocks |
| Attachments (`SIGNED_SCAN`, `BASIS_DOCUMENT`) | **B** | `personnel_order_attachments` | Extend for OO structured artifacts |

---

## 2. Lifecycle

| Component | Class | Evidence | Notes |
|---|---|---|---|
| Status enum DRAFT→READY→SIGNED/REGISTERED→VOIDED | **A** | `personnel_orders.py` | Shared document lifecycle |
| `void_kind` CANCEL vs ANNUL | **A** | `void_service.py`, audit service | OO needs same semantics |
| Archive orthogonal flag | **A** | `archive_service.py`, `archive_guard` | Immutable archived docs |
| Lifecycle audit append-only | **A** | `personnel_order_lifecycle_audit` | Shared audit taxonomy |
| Hidden closed journal (`include_closed`) | **A** | `personnel_orders_query_service` | Reusable journal pattern |
| Return-to-DRAFT from READY | **D** | documented R1/R10, not implemented | Policy drift |
| Compensating order links | **E** | PO-LC-DEL-002 deferred | Needed for amendments |
| Approval/visa workflow | **E** | PO-003/PO-004 documented only | Optional future |

---

## 3. Bilingual / Editorial

| Component | Class | Evidence | Notes |
|---|---|---|---|
| `generated_text` / `override_text` / `effective_text` | **A** | `editorial/mapper.py` | Core editorial contract |
| Fingerprint + `review_status` (CURRENT/STALE/REVIEW_REQUIRED) | **A** | `editorial/fingerprint.py`, `stale.py` | Localization lifecycle |
| Scoped regeneration | **A** | `generation_service.py` | Reusable orchestration |
| READY gate bilingual check | **A** | `ready_gate.py` | Extend with BC001–BC025 |
| `kk-ru` render-time composition | **B** | `personnelOrderPrintLocalized.ts` | Generalize print language modes |
| RU-first translation workflow mode | **E** | OP-RES-005A | PO has symmetric generate only |
| BC bilingual consistency checks | **E** | OP-RES-005A | Conceptual; not in PO |

---

## 4. Generation

| Component | Class | Evidence | Notes |
|---|---|---|---|
| Generation orchestration (scoped, per-block) | **A** | `personnel_orders_editorial_service.py` | Shell reusable |
| HR generators (`generators.py`) | **C** | TK/HR legal text | OO needs separate registry |
| Item type registry (5 MVP types) | **C** | model enums + `personnelOrderItemFormRegistry.ts` | OO needs 14 families |
| Scenario-first entry | **E** | — | PO is item-first picker |
| Control meta-item generator | **E** | — | 92% OO docs |
| Clause library DB | **E** | hardcoded generators | Versioned templates planned |

---

## 5. Execution / Apply

| Component | Class | Evidence | Notes |
|---|---|---|---|
| `apply_service` → `employee_events` | **C** | `personnel_orders_apply_service.py` | HR-specific projection |
| Void snapshot rollback (HIRE/TRANSFER/TERMINATION) | **C** | `void_service.py` | HR-specific rules |
| Execution obligation model | **E** | — | OO core semantic |
| Execution projection adapter | **E** | — | Generic handoff descriptor |

---

## 6. Preview / PDF

| Component | Class | Evidence | Notes |
|---|---|---|---|
| `PersonnelOrderPrintViewModel` | **A** | `personnelOrderPrintViewModel.ts` | Single projection for HTML+PDF |
| Playwright PDF renderer | **A** | `personnelOrderPdfRenderer.ts` | Swap document builder |
| Status watermarks | **B** | print VM | void_kind-aware needed |
| Immutable signed PDF storage | **E** | PO-PDF-001 future | Ephemeral today |
| DOCX export | **E** | — | Future renderer |

---

## 7. Access / Scope

| Component | Class | Evidence | Notes |
|---|---|---|---|
| `created_by` ownership | **A** | model + cancel service | Shared ownership |
| CANCEL_OWN / CANCEL_SCOPE | **A** | `personnel_order_cancel_scope_service.py` | Reusable pattern |
| ARCHIVE / RESTORE grants | **A** | `auth.py`, UI flags | Wired for PO |
| Blanket `require_personnel_admin_or_403` | **D** | most routes | Granular grants deferred |
| Role-first party model | **E** | employee_id centric | OO needs PartyReference |

---

## 8. Summary Matrix

| Area | A (reuse) | B (extract) | C (PO-specific) | D (debt) | E (missing) |
|---|---:|---:|---:|---:|---:|
| Structure | 1 | 3 | 1 | 1 | 0 |
| Lifecycle | 5 | 0 | 0 | 1 | 2 |
| Editorial | 4 | 1 | 0 | 0 | 2 |
| Generation | 1 | 0 | 2 | 0 | 4 |
| Execution | 0 | 0 | 2 | 0 | 2 |
| Rendering | 2 | 1 | 0 | 0 | 2 |
| Access | 3 | 0 | 0 | 1 | 1 |
| **Total** | **16** | **5** | **5** | **3** | **13** |

Machine-readable: [`data/OP-RES-006-current-to-target-gap-matrix.csv`](./data/OP-RES-006-current-to-target-gap-matrix.csv)

---

## 9. OP-RES-006 Conclusions

### Already foundation (Class A) — 16 components

Editorial model, staleness, lifecycle/audit/archive, void_kind, print VM, PDF renderer, generation orchestration, ownership/cancel scope.

### Must extract (Class B) — 5 components

Document metadata abstraction, command service patterns, print language modes, attachment generalization, watermark alignment.

### Stay personnel-specific (Class C) — 5 components

HR generators, basis policy, apply/void rollback, item form registry, employee-centric payloads.

### Fix before/during convergence (Class D) — 3 items

Legacy localized texts, READY editability drift, blanket admin guard.

### Build for Operational Orders (Class E) — 13 capabilities

Scenario taxonomy, obligation model, control meta-item, OO registries, projection adapter, bilingual BC checks, translation workflow mode, compensating links, approvals (optional), signed PDF storage, DOCX export, role-first parties, structured attachment obligations.

---

## 10. Key File Index

| Area | Path |
|---|---|
| Models | `app/db/models/personnel_orders.py` |
| Routes | `app/directory/personnel_orders_routes.py` |
| Editorial | `app/services/personnel_orders_editorial/` |
| Lifecycle | `personnel_orders_command_service.py`, `void_service.py`, `archive_service.py` |
| Audit | `personnel_order_lifecycle_audit_service.py` |
| UI | `corpsite-ui/app/directory/personnel/_lib/personnelOrder*.ts` |
| Docs | `docs/personnel-orders/architecture/PO-003`, `PO-EDIT-001`, `PO-LC-DEL-002` |
