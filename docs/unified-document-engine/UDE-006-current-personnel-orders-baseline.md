# UDE-006 — Current Personnel Orders Baseline

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation — Read-only**  
Authority: **This document is the compatibility authority for all UDE migration decisions.**

---

## 1. Purpose

Freeze **actual production behavior** of Personnel Orders MVP as read-only baseline. No code changes.

---

## 2. Backend Baseline

### 2.1 Models and Tables

| Table | Role |
|---|---|
| `personnel_orders` | Header: status, void_kind, archive, registration, signer |
| `personnel_order_items` | Numbered items with employee_id, payload JSONB |
| `personnel_order_localized_texts` | Legacy locale text columns |
| `personnel_order_editorial_blocks` | Order-level editorial (WP-PO-EDIT) |
| `personnel_order_item_editorial_blocks` | Item body/basis editorial |
| `personnel_order_item_bases` | Basis policy attachments |
| `personnel_order_attachments` | File references |
| `personnel_order_prints` | PDF generation records |
| `personnel_order_lifecycle_audit` | Append-only lifecycle audit |
| `employee_events` | Execution projection (linked by order_id) |

Source: `app/db/models/personnel_orders.py`

### 2.2 Lifecycle States (factual)

`DRAFT` | `READY_FOR_SIGNATURE` | `SIGNED` | `REGISTERED` | `VOIDED`

Archive: `archived_at IS NOT NULL` → `is_archived: true` (orthogonal)

### 2.3 API Endpoints (authoritative)

| Method | Path | Behavior |
|---|---|---|
| GET | `/personnel-orders` | Journal; default hides VOIDED + archived |
| POST | `/personnel-orders` | Create DRAFT |
| GET/PATCH | `/personnel-orders/{id}` | Read / edit header (DRAFT only) |
| POST/PATCH | `/personnel-orders/{id}/items` | Item CRUD (DRAFT only) |
| POST | `…/ready-for-signature` | DRAFT → READY (editorial gate) |
| POST | `…/register` | DRAFT/READY → SIGNED or REGISTERED |
| POST | `…/apply` | SIGNED/REGISTERED → employee_events |
| POST | `…/cancel` | DRAFT/READY → VOIDED (CANCEL); scoped perms |
| POST | `…/void` | SIGNED/REGISTERED → VOIDED (ANNUL); cascade |
| POST | `…/archive` | REGISTERED/VOIDED → archived |
| POST | `…/restore` | Unarchive |
| GET | `…/lifecycle-audit` | Audit list |
| Editorial | `…/editorial/*` | Generate, patch, reset blocks |

Source: `app/directory/personnel_orders_routes.py`

### 2.4 Service Layer

| Service | Responsibility |
|---|---|
| `personnel_orders_command_service` | Draft CRUD, ready, register |
| `personnel_orders_void_service` | Annul + item void + event cascade |
| `personnel_orders_cancel_service` | Cancel with CANCEL_OWN/SCOPE |
| `personnel_orders_archive_service` | Archive/restore |
| `personnel_order_lifecycle_audit_service` | Append-only audit |
| `personnel_orders_apply_service` | Employee event application |
| `personnel_orders_editorial/*` | Generation, ready gate, editorial |

### 2.5 Lifecycle Transitions (factual)

```text
CREATE → DRAFT
DRAFT → READY (ready-for-signature)
DRAFT/READY → SIGNED|REGISTERED (register; shortcut)
SIGNED|REGISTERED → employee_events (apply; status unchanged)
DRAFT|READY → VOIDED (cancel; void_kind=CANCEL)
SIGNED|REGISTERED → VOIDED (void; void_kind=ANNUL)
REGISTERED|VOIDED → archived (orthogonal)
```

**Not implemented:** ReturnToDraft, separate Sign step, lifecycle audit on mark_ready/register

### 2.6 Error Codes (lifecycle-related)

| Code | Context |
|---|---|
| ORDER_NOT_CANCELLABLE | Cancel from wrong status |
| ORDER_ALREADY_VOIDED | Idempotent guard |
| ORDER_ALREADY_APPLIED | Cancel blocked |
| CANCEL_PERMISSION_DENIED / CANCEL_SCOPE_DENIED | Authority |
| ORDER_NOT_ARCHIVABLE / ORDER_ALREADY_ARCHIVED | Archive |
| ORDER_ARCHIVED | Write on archived |
| READY_GATE_FAILED | Editorial gate |
| VOID_CHAIN_BLOCKED | ADR-035 |

### 2.7 Registration Semantics

- `order_number` nullable until register
- Register resolves `order_type_code` from items
- Target status: `SIGNED` or `REGISTERED` via payload
- No separate immutable signed snapshot table

### 2.8 Authority

- Most endpoints: `require_personnel_admin_or_403`
- Cancel: `PERSONNEL_ORDERS_CANCEL_OWN` | `PERSONNEL_ORDERS_CANCEL_SCOPE`
- Archive: `PERSONNEL_ORDERS_ARCHIVE`
- Restore: `PERSONNEL_ORDERS_RESTORE`
- Cancel scope: `personnel_order_cancel_scope_service` (org subtree)

---

## 3. Frontend Baseline

| Area | Implementation |
|---|---|
| Journal | `PersonnelOrdersPageClient` + `PersonnelOrdersTable` |
| Closed filter | `include_closed` checkbox; legacy `include_archived` alias |
| Editor | `PersonnelOrderDetailDrawer`, `PersonnelOrderItemEditor` |
| Lifecycle | `PersonnelOrderLifecycleActions`, void/cancel/archive dialogs |
| Applied badge | Derived `linkedEventCount > 0`, not status |
| Archived badge | `PersonnelOrderArchivedBadge` |
| Writable check | `isWritablePersonnelOrder(status, is_archived)` → DRAFT + not archived |
| Editorial | Editorial API client; RU/KK independent editing |
| HTML Preview | Print document components |
| PDF | Route `orders/[orderId]/pdf`; language query param |

Routes preserved: `/directory/personnel/orders`, journal, documents

---

## 4. Rendering Baseline

| Layer | File / Route |
|---|---|
| Print VM | `personnelOrderPrintViewModel.ts` |
| Language modes | `personnelOrderPrintLanguage.ts` (kk, ru) |
| HTML | `personnelOrderPdfHtml.ts` |
| PDF data | `personnelOrderPdfData.server.ts` |
| PDF render | Playwright Chromium via `personnelOrderPdfRenderer` |
| Watermark | VOIDED → «АННУЛИРОВАН» in print VM |
| Status marks | draft / unsigned / cancelled |
| Effective text | override → generated per editorial state |

**Constraint:** Playwright PDF contour unchanged by UDE migration.

---

## 5. Derived UX States (not enum)

| State | Condition |
|---|---|
| Applied | `employee_events` linked with APPROVED |
| Editable | `status=DRAFT` && !archived |
| Registerable | DRAFT or READY |
| Applyable | SIGNED/REGISTERED && !applied |

---

## 6. Baseline Authority Statement

Any UDE migration decision that would change observable behavior documented here requires:

1. Explicit ratified implementation WP
2. Characterization test update
3. Compatibility harness pass

UDE-006 does **not** authorize such changes.

---

*Evidence: PO-LC-DEL-001, UDE-005 gap analysis, production code read 2026-07-12*
