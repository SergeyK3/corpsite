# Unified Document Engine (UDE)

Shared document lifecycle contracts and evaluation runtime used by Operational Orders and Personnel Orders adapters.

**Runtime package:** `app/document_engine/`

---

## Implementation status

| Consumer | WP | Status |
|---|---|---|
| Operational Orders | OO-IMP-001–003B | Complete — promotion + workspace freeze |
| Operational Orders | **OO-IMP-004** | **Complete (local)** — `CREATED` → `READY_FOR_SIGNATURE` |
| Personnel Orders | UDE adapters | Read-only characterization; PO tables unchanged |

---

## Shared contracts (UDE-001 / UDE-005)

| Contract | Location |
|---|---|
| `DocumentLifecycleState` | `app/document_engine/value_objects/lifecycle.py` |
| `PartyReference` | `app/document_engine/contracts/party.py` |
| `ValidationResult` | `app/document_engine/contracts/validation.py` |
| `LifecycleRules` | `app/document_engine/lifecycle/lifecycle_rules.py` |

Five-state model: `DRAFT`, `READY_FOR_SIGNATURE`, `SIGNED`, `REGISTERED`, `VOIDED`.

OO maps post-promotion **`CREATED`** ↔ UDE **`DRAFT`** at the lifecycle service boundary.

---

## OO-IMP-004 integration

First native OO lifecycle persistence using UDE semantics:

- Service: `app/operational_orders/services/lifecycle_service.py`
- Validation: `app/operational_orders/validation/signature_readiness_validation.py`
- Audit: `operational_order_lifecycle_audit` (separate from promotion/draft audit)
- Migration head: `a1b2c3d4e5f6`

Record: [`../operational-orders/implementation/OO-IMP-004-ready-for-signature.md`](../operational-orders/implementation/OO-IMP-004-ready-for-signature.md)

---

## Next work packages

| WP | Title |
|---|---|
| OO-UI-001 | Operational Orders UI (signature readiness surfaces) |
| OO-IMP-005 | Signing workflow |
| OO-IMP-005+ | Revision Command and Version 2+ |

Personnel Orders convergence remains deferred per UDE-006.
