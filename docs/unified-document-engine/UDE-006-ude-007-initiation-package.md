# UDE-007 — Initiation Package

WP: **UDE-007** (prepared by UDE-006)  
Date: **2026-07-12**  
Status: **Ready for initiation**  
Prerequisite: UDE-006 ✓

> **UDE-007 is the first WP permitted to write code.** It must not change production behavior.

---

## 1. WP Title

**UDE-007 — Shared Runtime Contracts and PO Characterization Baseline**

---

## 2. Purpose

Introduce shared UDE runtime contract modules and expand PO characterization test baseline — **without changing observable Personnel Orders behavior**.

---

## 3. Allowed Actions

| Allowed | Detail |
|---|---|
| Create new modules | `app/ude/` or `app/shared/document_engine/` (path TBD in UDE-007) |
| Create contract types | Python TypedDict/dataclass/enums mirroring UDE-001/005 |
| Create test files | New characterization and contract tests |
| Create docs | UDE-007 completion report |
| Read existing PO code | All personnel_orders_* files |

---

## 4. Forbidden Actions

| Forbidden | Detail |
|---|---|
| Modify PO services | No changes to command/void/cancel/archive |
| Modify PO routes | No API changes |
| Modify PO models/ORM | No schema change |
| Modify frontend | No UI changes |
| SQL migrations | None |
| Change lifecycle behavior | Status transitions unchanged |
| Change PDF/HTML | Playwright and print VM unchanged |
| Fabricate audit | No backfill |
| Wire adapters to production | Contract + test only; adapters stub optional |

---

## 5. Contracts to Implement First (Priority)

| Priority | Contract | Source |
|---|---|---|
| P0 | DocumentLifecycleState | UDE-005 |
| P0 | ArchiveState | UDE-005 |
| P0 | VoidKind | UDE-005 |
| P0 | LifecycleCommand enum (conceptual) | UDE-005 |
| P0 | LifecycleError taxonomy | UDE-005 §25 |
| P1 | DocumentId / DocumentKind | UDE-001 |
| P1 | LocaleRepresentation view shape | UDE-003 |
| P1 | LifecycleAuditEventRecord | UDE-005 §18 |
| P2 | Capability constants | UDE-006 authority |
| P2 | SyntheticActivationMetadata | UDE-006 §6 |

---

## 6. Characterization Tests Required

Minimum P0 from UDE-006:

| Test | Source |
|---|---|
| Lifecycle transitions | Extend existing `test_wp_po_*` |
| Cancel/annul void_kind | `test_wp_po_lc_del_004` |
| Archive immutability | `test_wp_po_lc_del_005a` |
| Journal include_closed | API test |
| Authority cancel scope | Existing + document |

New in UDE-007:

| Test | Purpose |
|---|---|
| Baseline inventory test | Assert endpoint list unchanged |
| Contract parity test | PO status enum == shared DocumentLifecycleState |
| void_kind resolver parity | Shared helper matches `resolve_void_kind` |

Optional stub:

| Test | Purpose |
|---|---|
| Adapter parity placeholder | Skip until UDE-008 |

---

## 7. Acceptance Criteria

1. All **existing** PO tests pass unchanged
2. New contract module(s) importable without side effects
3. Shared lifecycle enums match PO `ORDER_STATUSES` exactly
4. Shared `resolve_void_kind` logic matches PO production function
5. Characterization test matrix T001–T005 documented as covered or gap-listed
6. No new HTTP endpoints
7. No database migrations
8. CI green on main branch criteria

---

## 8. Verification Commands

```bash
# Existing PO test suites (must remain green)
pytest tests/test_wp_po_lc_del_004_cancel_api.py -q
pytest tests/test_wp_po_lc_del_005_archive_api.py -q
pytest tests/test_wp_po_lc_del_005a_archived_immutability_api.py -q
pytest tests/test_wp_po_edit_002_editorial_api.py -q
pytest tests/test_wp_po_006_e2e_validation.py -q

# New UDE-007 contract tests (to be created)
pytest tests/ude/ -q
```

---

## 9. Commit Boundary

- Single or few commits: `docs(ude): UDE-007 ...` + `feat(ude): shared contracts ...` + `test(ude): characterization baseline ...`
- No PO behavior commits mixed in
- Deploy: **not required** for UDE-007 (contracts unused in production paths)

---

## 10. Deliverables

| Artifact | Path |
|---|---|
| Main report | `docs/unified-document-engine/UDE-007-shared-runtime-contracts.md` |
| Contract module | `app/ude/contracts/` (or agreed path) |
| Tests | `tests/ude/` |
| Characterization inventory | `docs/unified-document-engine/UDE-007-characterization-inventory.md` |
| Readiness CSV | `docs/unified-document-engine/data/UDE-007-readiness.csv` |

---

## 11. Handoff from UDE-006

| Input | Use |
|---|---|
| Baseline doc | Compatibility authority |
| Adapter model | Informs contract shapes only |
| Extraction units U001–U005 | First implementations |
| Test matrix T001–T018 | Coverage plan |
| G001–G024 guarantees | Acceptance constraints |

---

## 12. Out of Scope for UDE-007

- UDE-008 adapters (read implementations)
- OO-IMP-001
- PO-CONV-001
- Signed snapshot persistence
- ReturnToDraft implementation

---

*Prepared by UDE-006 — not executed in UDE-006*
