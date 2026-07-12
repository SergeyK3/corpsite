# UDE-008 — Shared Read-only Adapters for Personnel Orders

WP: **UDE-008**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-007 ✓

> First WP where Shared Runtime Contracts gain a real consumer. **Read-only. No production behavior change.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| `app/document_engine/adapters/personnel/` read adapters | PO write-path changes |
| `PersonnelReadAdapter` facade | Operational Order adapters |
| Compatibility harness | API / UI / PDF / HTML changes |
| Adapter + dependency tests | ORM / schema / migration changes |
| Documentation and mapping matrices | Synthetic audit fabrication |

---

## 2. Architecture

```text
Personnel Orders (compatibility authority)
        ↓ read dicts / optional DB supplement
PersonnelReadAdapter (facade)
        ↓
Personnel*Adapter (document, party, lifecycle, locale, item, audit, print)
        ↓
Shared Runtime Contracts (UDE-007)
        ↓
future UDE-009 Shared Services
```

**Dependency direction:** PO → Adapter → Shared Contracts. Shared contracts never import PO.

---

## 3. Implemented Adapters

| Adapter | Module | Input |
|---|---|---|
| PersonnelDocumentAdapter | `document.py` | Order header dict + optional supplement |
| PersonnelPartyAdapter | `party.py` | Item `employee_id` → `PartyReference` |
| PersonnelLifecycleAdapter | `lifecycle.py` | `status`, `is_archived`, `void_kind` |
| PersonnelLocaleAdapter | `locale.py` | Editorial state + `localized_texts` |
| PersonnelItemAdapter | `item.py` | Item dicts (incl. RATE_CHANGE display alias) |
| PersonnelAuditAdapter | `audit.py` | Lifecycle audit rows |
| PersonnelPrintAdapter | `print.py` | Print records + status mark |
| **PersonnelReadAdapter** | `read_adapter.py` | **Single public entry** |
| CompatibilityHarness | `compatibility.py` | Legacy detail vs adapter bundle diff |

---

## 4. Contracts First Used by Consumer

All 14 UDE-007 runtime types are now consumed through adapters:

`DocumentId`, `DocumentKind`, `DocumentSpecialization`, `DocumentLifecycleState`, `ArchiveState`, `VoidKind`, `LocaleCode`, `StalenessState`, `TextSourceType`, `PartyReferenceType`, `PartyReference`, `ValidationSeverity/Issue/Result` (reserved for UDE-009 validation services).

---

## 5. Mapping Summary

### Direct mappings

- Lifecycle statuses — 1:1 with `DocumentLifecycleState`
- Archive — `is_archived` → `ArchiveState`
- Locales — `ru`/`kk` → `LocaleCode`
- Item backend types — unchanged registry values

### Transformations required

| PO | Adapter behavior |
|---|---|
| `void_kind` missing from API header | `_supplement.fetch_order_supplement()` |
| `employee_id` | `PartyReference(PERSON)` with `po_role=event_subject` |
| `review_status` | → `StalenessState` |
| `TRANSFER` + rate-only payload | `display_item_type_code=RATE_CHANGE` (read alias) |
| Print `status` | → `status_mark` (`draft`/`unsigned`/`cancelled`/`none`) |

See [`data/UDE-008-read-mapping.csv`](./data/UDE-008-read-mapping.csv).

---

## 6. Findings

| ID | Classification | Finding |
|---|---|---|
| A-001 | Confirmed behavior | `void_kind` requires DB supplement — API gap from UDE-007 F-007 |
| A-002 | Confirmed behavior | `employee_id` is event subject; adapter tags `po_role=event_subject` |
| A-003 | Confirmed behavior | RATE_CHANGE is display alias only; backend remains TRANSFER |
| A-004 | Confirmed behavior | Two text channels: editorial blocks (primary) + legacy `localized_texts` |
| A-005 | Confirmed behavior | Print adapter maps metadata only; no backend PDF generation |

No blocking incompatibilities. No production fixes applied.

---

## 7. Production Files Changed

**None.** All changes are additive under `app/document_engine/adapters/` and tests/docs.

PO services, routes, models, frontend — unchanged.

---

## 8. Test Commands

```bash
pytest tests/document_engine/adapters/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
pytest tests/test_wp_po_lc_del_004_cancel_api.py tests/test_wp_po_lc_del_005_archive_api.py -q
```

---

## 9. Handoff to UDE-009

**UDE-009 — Shared Editorial & Localization Runtime Services**

| UDE-008 deliverable | UDE-009 use |
|---|---|
| `PersonnelLocaleAdapter` views | Editorial service input shapes |
| `PersonnelReadAdapter.from_order_id` | Service integration test harness |
| `StalenessState` / `TextSourceType` mapping | Localization runtime policies |
| Compatibility harness | Regression guard during service extraction |

**Ready for UDE-009:** Yes — read adapters provide stable PO → shared views without write-path coupling.

---

## 10. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
