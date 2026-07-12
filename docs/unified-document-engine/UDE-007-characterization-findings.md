# UDE-007 — Characterization Findings

WP: **UDE-007**  
Date: **2026-07-12**  
Status: **Implementation complete (local)**

Findings from characterization baseline. **No fixes applied** in UDE-007.

---

## F-001 — RATE_CHANGE is UI-only alias

| Field | Value |
|---|---|
| Classification | **Documentation drift** |
| Observed behavior | Backend `MVP_ITEM_TYPE_CODES` does not include `RATE_CHANGE`. UI maps `RATE_CHANGE` → `TRANSFER` with `to_rate` payload. |
| Evidence | `test_personnel_orders_characterization_item_registry.py`; `personnelOrderItemFormRegistry.ts` |
| Action | Document in adapter mapping (UDE-008); do not add RATE_CHANGE to backend registry without separate WP |

---

## F-002 — HIRE new-employee path is partial

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | `employee_id` may be omitted on HIRE item create; registration requires `employee_id` on all items. |
| Evidence | `test_personnel_orders_characterization_hire.py`; `personnel_orders_command_service.py` |
| Action | UDE-008 adapter must preserve `employee_id` authority; PartyReference mapping is read-only |

---

## F-003 — No synthetic lifecycle audit on draft create

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | Creating a DRAFT order does not append lifecycle audit rows. |
| Evidence | `test_personnel_orders_characterization_audit.py` |
| Action | UDE-008 must not fabricate activation events for legacy PO rows |

---

## F-004 — Shared lifecycle enum parity

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | `DocumentLifecycleState` and `VoidKind` values match PO `ORDER_STATUSES` and `VOID_KINDS` exactly. |
| Evidence | `tests/document_engine/test_value_objects.py`; characterization lifecycle tests |
| Action | Safe for UDE-008 read adapters; do not replace PO enums in write-path |

---

## F-005 — P0 E2E gaps remain intentional

| Field | Value |
|---|---|
| Classification | **Technical debt** (pre-existing) |
| Observed behavior | Full HIRE and TERMINATION apply→history→rollback E2E not covered; TRANSFER E2E exists in WP-PO-006. |
| Evidence | Coverage matrix `UDE-007-characterization-coverage.csv` |
| Action | Optional future WP; not blocking UDE-008 read adapters |

---

## F-007 — void_kind not exposed in detail API response

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | After cancel, `order.status` is `VOIDED` in API response but `void_kind` is persisted in DB only (not in `PersonnelOrderHeader`). |
| Evidence | `test_personnel_orders_characterization_lifecycle.py` |
| Action | UDE-008 read adapter may surface `void_kind`; do not change API schema in UDE-007 |

---

## F-008 — DIRECTORY_PRIVILEGED does not grant cancel

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | `DIRECTORY_PRIVILEGED_USER_IDS` allows admin read/write on orders but cancel requires `PERSONNEL_ORDERS_CANCEL_OWN` or `CANCEL_SCOPE`. |
| Evidence | `test_personnel_orders_characterization_ownership.py` |
| Action | Adapter authority mapping must use explicit cancel grants |

---

## F-009 — TRANSFER allows null employee_id at item create

| Field | Value |
|---|---|
| Classification | **Confirmed behavior** |
| Observed behavior | Non-HIRE item types accept `employee_id=null` at create; registration enforces employee_id. |
| Evidence | `test_personnel_orders_characterization_hire.py` |
| Action | Document in compatibility baseline; not a defect |
