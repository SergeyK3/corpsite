# UDE-005 — Personnel Orders Lifecycle Gap Analysis

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation — Read-only**  
Mode: **No code changes**

---

## 1. Purpose

Read-only classification of Personnel Orders lifecycle components against Shared Lifecycle Core targets.

Classification: **A** reusable foundation · **B** extract/refactor later · **C** personnel-specific · **D** implementation debt · **E** missing for shared core

---

## 2. Summary Verdict

| Metric | Count |
|---|---|
| A — reusable foundation | 6 |
| B — extract/refactor later | 6 |
| C — personnel-specific | 4 |
| D — implementation debt | 4 |
| E — missing for shared core | 2 |

**Conclusion:** PO provides production-proven lifecycle foundation (states, void_kind, audit, archive). Gaps: signed snapshot, return-to-draft, separate sign step, lifecycle audit on all transitions. Operational Orders can use shared lifecycle via **adapter pattern** without PO big-bang refactor (UDE-006).

---

## 3. Component Analysis

### 3.1 Status Transitions — **A**

`app/db/models/personnel_orders.py`: DRAFT, READY_FOR_SIGNATURE, SIGNED, REGISTERED, VOIDED — matches UDE T022.

`personnel_orders_command_service.py`: mark_ready, register transitions proven.

### 3.2 Lifecycle Command/Service — **B**

Split across `personnel_orders_command_service`, `personnel_orders_void_service`, `personnel_orders_cancel_service`, `personnel_orders_archive_service`. Target: single LifecycleOrchestrator with PO adapters.

### 3.3 Lifecycle Audit — **A**

`personnel_order_lifecycle_audit_service.py`: append-only; actions CANCEL, ANNUL, ARCHIVE, RESTORE. Gap: mark_ready/register lack audit rows (**D**).

### 3.4 Cancel Endpoint — **B**

`personnel_orders_cancel_service.py`: granular permissions (CANCEL_OWN, CANCEL_SCOPE). Extract CancelPolicy; keep PO scope rules as specialization.

### 3.5 void_kind — **A**

`resolve_void_kind`: DRAFT/READY → CANCEL; SIGNED/REGISTERED → ANNUL. Matches UDE-005 ratified model.

### 3.6 Archive/Restore — **A**

`personnel_orders_archive_service.py`: orthogonal `archived_at`; REGISTERED/VOIDED archivable.

### 3.7 Immutable Archived Behavior — **A**

`personnel_order_archive_guard.py`: `assert_order_not_archived` on writes.

### 3.8 Ownership and Scope — **C/B**

Cancel: ownership + org scope (`personnel_order_cancel_scope_service`). Other lifecycle endpoints: broad admin permission (**D**).

### 3.9 READY Behavior — **D**

PO-EDIT docs mention READY editability; backend `EDITABLE_ORDER_STATUSES = {DRAFT}` only. UDE-005 target: READY read-only; ReturnToDraft for corrections.

### 3.10 SIGNED Snapshot — **E**

No immutable signed snapshot table/service. Register sets status only.

### 3.11 Registration Model — **C**

Register assigns type resolution and status; numbering in order_number field at register — PO-specific surface.

### 3.12 Journal Closed Filtering — **B**

UI/API filter for closed documents — JournalPolicy, not lifecycle core.

---

## 4. Technical Debts

| Debt | Class | Target resolution |
|---|---|---|
| READY editability drift | D | UDE-006: enforce write-lock; implement ReturnToDraft |
| UI "Annul" label for cancel | D | UX alignment in later WP |
| No audit on mark_ready/register | D | UDE-006 adapter adds audit |
| Broad admin on sign/register | D | Authority boundary in UDE-006 |
| Combined register shortcut | B | RegistrationAdapter preserves behavior |
| No signed snapshot | E | UDE-006+ implementation WP |

---

## 5. Reusable for Shared Core

| Component | File |
|---|---|
| State enum | `personnel_orders.py` ORDER_STATUSES |
| void_kind resolution | `personnel_order_lifecycle_audit_service.py` |
| Append-only audit | `personnel_order_lifecycle_audit` table |
| Archive guard | `personnel_order_archive_guard.py` |
| Cancel/Annul split | `cancel_service` + `void_service` |
| Archive orthogonality | `archive_service` |

---

## 6. Personnel-Specific (remain in specialization)

| Component | Reason |
|---|---|
| employee_events apply/void | Execution Projection |
| void chain ADR-035 | Annul policy |
| cancel scope by org subtree | CancelPolicy |
| item-level void | PO item semantics |
| HR authority grants | Authority specialization |

---

*Matrix: [`data/UDE-005-personnel-gap-matrix.csv`](./data/UDE-005-personnel-gap-matrix.csv)*  
*Diagram: [`diagrams/personnel-to-shared-lifecycle.svg`](./diagrams/personnel-to-shared-lifecycle.svg)*
