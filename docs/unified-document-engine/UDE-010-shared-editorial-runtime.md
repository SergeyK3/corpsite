# UDE-010 — Shared Editorial & Localization Runtime

WP: **UDE-010**  
Date: **2026-07-12**  
Status: **Complete (local — not committed)**  
Prerequisite: UDE-009 ✓

> First WP where Shared Runtime forms a common editorial model. **Read-only. No production behavior change.**

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| `app/document_engine/editorial/` runtime | PO write-path changes |
| Editorial models + services | Persistence / ORM |
| OverrideResolver, ReviewPolicy, FingerprintService | API / UI changes |
| OfficialDraftBuilder (no DocumentId) | Text generation / regeneration |
| DocumentEngineEditorialFacade | Draft Workspace runtime |
| Compatibility + dependency tests | Lifecycle Runtime (UDE-011) |

---

## 2. Architecture

```text
Personnel Orders (System of Record)
        ↓
Read Adapters (UDE-008)
        ↓
Shared Read Services (UDE-009)
        ↓
Shared Editorial Runtime (UDE-010)  ← NEW
        ↓
Future Write Workflows (OO, Draft Workspace)
```

**Dependency direction:** Read Layer → Editorial Runtime. Editorial never imports PO, ORM, adapters, or API.

---

## 3. UDE-003 Review Findings

| Area | UDE-003 target | PO / UDE-009 actual | Classification |
|---|---|---|---|
| Official Draft Package | No DocumentId; workspace_ref | `OfficialDraftSnapshot.workspace_reference` | Aligned |
| Generated → Effective | `override ?? generated` | `OverrideResolver` + adapter `effective_text` | Aligned |
| Override | Manual layer with provenance | `EditorialOverride.is_active` | Aligned |
| Review State | CURRENT / STALE / REVIEW_REQUIRED | `ReviewState` enum + adapter `review_status` | Aligned |
| Staleness | Granular staleness reasons | `StalenessState` from adapter; PO maps STALE → fingerprint mismatch | Partial — PO coarser |
| Fingerprint | source_fingerprint + generator_version | Runtime SHA-256 + adapter `source_fingerprint` | Aligned (read-only) |
| Editorial Audit | Three-audit model | Not in read layer yet — deferred to UDE-011+ | Gap — documented |
| Legacy snapshots | Secondary channel | `LocaleReadModel.snapshots` preserved, not in OfficialDraft | Aligned (A-004) |

No blocking incompatibilities. No production fixes applied.

---

## 4. Editorial Models

| Model | Purpose |
|---|---|
| `EditorialDocument` | Shared editorial document view |
| `EditorialSection` | Scope/item block grouping |
| `EditorialLocale` | Per-locale editorial blocks |
| `EditorialBlock` | Generated/override/effective/review per block |
| `EditorialOverride` | Manual override layer |
| `EditorialFingerprint` | Deterministic runtime fingerprint |
| `ReviewState` | CURRENT / STALE / REVIEW_REQUIRED / UNKNOWN |
| `OfficialDraftSnapshot` | Promotion handoff — no DocumentId |

See [`data/UDE-010-editorial-models.csv`](./data/UDE-010-editorial-models.csv).

---

## 5. Services

| Service | Input | Output |
|---|---|---|
| `EditorialService` | `DocumentEngineReadSnapshot` | `EditorialDocument` |
| `LocalizationService` | `LocaleReadModel` | `LocalizationView` + `EditorialLocale` |
| `FingerprintService` | Block semantic inputs | `EditorialFingerprint` |
| `OverrideResolver` | generated + override | effective text |
| `ReviewPolicy` | adapter review_status + staleness | `ReviewState` |
| `OfficialDraftBuilder` | read snapshot | `OfficialDraftSnapshot` |
| **`DocumentEngineEditorialFacade`** | read snapshot / detail dict | **`DocumentEngineEditorialSnapshot`** |

---

## 6. Override Policy

```text
effective_text = override_text ?? generated_text
is_active = override_text is not empty
```

Implemented in `OverrideResolver` per UDE-003 §4. Observable PO behavior preserved via adapter `effective_text`.

---

## 7. Review Policy

| Source | Mapping |
|---|---|
| Adapter `review_status` CURRENT | `ReviewState.CURRENT` |
| Adapter `review_status` STALE | `ReviewState.STALE` |
| Adapter `review_status` REVIEW_REQUIRED | `ReviewState.REVIEW_REQUIRED` |
| Adapter `review_status` GENERATION_FAILED | `ReviewState.REVIEW_REQUIRED` |
| Adapter `staleness_state` | Fallback when review_status unknown |
| Fingerprint mismatch + override | `ReviewState.REVIEW_REQUIRED` (compute fallback) |
| Unrecognized | `ReviewState.UNKNOWN` |

See [`data/UDE-010-review-policies.csv`](./data/UDE-010-review-policies.csv).

---

## 8. Fingerprint Model

Deterministic runtime SHA-256 over canonical payload:

```text
generator_key | generator_version | scope | block_type | order_item_id | generated_text
```

- `FingerprintService.compute_runtime_fingerprint()` — no database hash
- `source_fingerprint` from adapter preserved for comparison
- `has_generated_changed()` — detects semantic input drift

---

## 9. Official Draft Builder

`OfficialDraftSnapshot` assembled from read models:

- **No DocumentId** — uses `workspace_reference` (opaque `po:{id}` ref)
- Contains locale blocks with generated/override/effective/review/fingerprint
- `item_count` from read snapshot items
- `draft_metadata` from document metadata

Not a Document Aggregate — promotion handoff artifact per UDE-003.

---

## 10. Facade

`DocumentEngineEditorialFacade` — single public entry:

| Method | Returns |
|---|---|
| `from_read_snapshot(snapshot)` | `DocumentEngineEditorialSnapshot` |
| `from_detail(detail, ...)` | via `DocumentEngineReadFacade` → editorial |

`DocumentEngineEditorialSnapshot` contains: `editorial`, `localization`, `official_draft`.

---

## 11. Dependency Rules

Editorial runtime **must not** import: `app.db`, `app.api`, `app.directory`, `app.services.*`, `app.document_engine.adapters`, sqlalchemy, fastapi, pydantic.

Editorial runtime **may** import: `read_models`, `read_services`, `contracts`, `value_objects`.

Enforced by `tests/document_engine/editorial/test_editorial_dependency_rules.py`.

---

## 12. Production Files Changed

**None.** All changes additive under `app/document_engine/editorial/` and tests/docs.

---

## 13. Test Commands

```bash
pytest tests/document_engine/editorial/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
```

---

## 14. Handoff to UDE-011

**UDE-011 — Shared Lifecycle Runtime & Draft Activation**

| UDE-010 deliverable | UDE-011 use |
|---|---|
| `OfficialDraftSnapshot` | Promotion / activation input |
| `EditorialDocument` + `ReviewState` | Lifecycle gate inputs |
| `DocumentEngineEditorialFacade` | Consumer entry point |
| Compatibility harness | Regression guard |

**Ready for UDE-011:** Yes.

---

## 15. Commit Boundary

Commit, push, and deploy were **not** performed per WP instructions.
