# PIF Roadmap — Personnel Intake Framework

## Status

**Active roadmap** — initiated 2026-07-08; updated 2026-07-24 to reflect **partial production implementation**.

Program roadmap for Personnel Intake Framework. Work packages below show **documentation ✅**, **partial implementation 🟡**, or **not started ⬜**.

| Field | Value |
|-------|-------|
| Predecessor | [PMF Pilot Freeze](../personnel-migration/PMF-PILOT-FREEZE.md) |
| Architecture baseline | [PIF-001](./PIF-001-personnel-intake-framework.md) |
| PMF status | Frozen — pilot-ready; no feature development |
| Production | Partial — invitation through preview-PDF; commit not done |

---

## 1. Program overview

```text
PIF-1  Architecture          ✅ docs; aligns with partial impl
  ↓
PIF-2  Data Model            🟡 draft JSON in production; canonical catalog TBD
  ↓
PIF-3  Invitation            🟡 link/token/revoke/reissue implemented
  ↓
PIF-4  Electronic Form       🟡 static React form; not FormDefinition-driven
  ↓
PIF-5  HR Review             🟡 section review + on-behalf edit; not full diff UI
  ↓
PIF-6  Commit                ⬜ not implemented
  ↓
PIF-7  Generated Documents   🟡 preview-PDF at review ✅; post-commit PDF ⬜
  ↓
Pilot                     ⬜
```

**Goal:** electronic intake for new hires — candidate self-service → HR review → canonical personnel data → generated personal sheet PDF (post-commit target).

---

## 2. Work packages

### PIF-1 — Architecture ✅ (documentation ratified)

| Item | Deliverable | Status |
|------|-------------|--------|
| PIF-001 | Personnel Intake Framework | ✅ Doc; updated for partial impl |
| PIF-002 | Electronic Personal Sheet concept | ✅ Doc; updated for partial impl |
| PIF-003 | Dynamic Form Model (target) | ✅ Doc; production = static form |
| PIF-004 | Data Ownership policy | ✅ Doc; partial enforcement |
| PIF-2A | Candidate UX specification | ✅ Doc + [demo/](./demo/) prototype |
| PMF-PILOT-FREEZE | PMF freeze record | ✅ |
| PIF-roadmap | This document | ✅ |

**Exit criteria:** architecture documents ratified; canonical domain model defined; PMF position documented. **Met for documentation.** Implementation tracked per WP below.

---

### PIF-2 — Data Model 🟡 (partial)

**Objective:** define canonical personnel data schema and intake draft storage — **data-first**, not form-first.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Canonical domain schema | D1–D12 attribute catalog (D12 military in production form) | ⬜ Design doc |
| Intake case entity | Case lifecycle, token reference, form version binding | 🟡 `personnel_applications` + intake link/draft tables |
| Draft storage model | Hybrid: typed core attributes + repeatable section rows | 🟡 JSON draft payload in production |
| Commit mapping spec | `canonical_path` → `person_*` table mapping | ⬜ |
| FormDefinition v1 | Metadata for `new_hire_full` profile (PIF-003) | ⬜ |
| ADR-048 alignment doc | Person creation timing at commit | ⬜ |

**Dependencies:** PIF-1.

**Non-goals:** Full Alembic redesign in this WP alone; UI.

**Exit criteria:** schema design reviewed; mapping from EPS sections to person tables complete; FormDefinition v1 covers S1–S6 + S9 for minimal pilot. **Not met.**

---

### PIF-3 — Invitation 🟡 (partial)

**Objective:** HR creates intake case; candidate receives secure personal link.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Create case API | HR initiates case with org/position context | 🟡 Personnel application registration |
| Token service | Opaque token, TTL, revoke, one-time activation | 🟡 Issue/revoke/reopen link |
| Personal link | URL generation and validation | 🟡 `/intake/{token}` |
| Case lifecycle FSM | `INVITED` → `IN_PROGRESS` | 🟡 Application + link/draft statuses |
| HR case list | Basic queue in Кадровые процессы | 🟡 Applicants / application detail |

**Dependencies:** PIF-2 (case entity) — partially satisfied.

**Exit criteria:** HR can create invitation; candidate can open link and reach form. **Largely met.**

---

### PIF-4 — Electronic Form 🟡 (partial)

**Objective:** dynamic form rendering and candidate self-service entry.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| FormDefinition loader | Versioned metadata load | ⬜ Target PIF-003 |
| Form renderer | Section/field/validation/dictionary/visibility (PIF-003) | 🟡 Static React + `INTAKE_STEPS` (9 steps) |
| Draft autosave | Persist on edit | ✅ |
| Client validation | UX validation from shared rule catalog | 🟡 Per-section TS + date validation |
| Submit flow | Hard validation → `SUBMITTED` | ✅ |
| RU/KZ localization | Label bundles | ⬜ |
| Applicant re-edit | After HR return | ✅ |
| HR on-behalf edit | Edit draft for applicant | ✅ |
| Photo upload | Secure storage + PDF embed | ✅ [PIF-PHOTO](./PIF-PHOTO-storage.md) |
| Military block | D12 basic fields | ✅ In production form |

**Dependencies:** PIF-2, PIF-3 — partially satisfied.

**Exit criteria:** candidate completes core sections; draft persisted; submit transitions state. **Largely met** for pilot scope; FormDefinition loader **not met**.

---

### PIF-5 — HR Review 🟡 (partial)

**Objective:** HR verification, correction, revision request.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Review UI | Same form + provenance display | 🟡 Section review + on-behalf drawer |
| HR field override | With audit (`hr_correction`) | 🟡 On-behalf save + audit (partial) |
| Revision request | Section-scoped return to candidate | 🟡 Section rework + director revision |
| Approval gate | `APPROVED` state | 🟡 Application workflow statuses |
| Diff view | Candidate vs HR values | ⬜ |

**Dependencies:** PIF-4 — partially satisfied.

**Exit criteria:** HR can review, correct, return, and approve submitted intake. **Partially met** (no full diff/provenance UI).

---

### PIF-6 — Commit ⬜

**Objective:** atomic write from approved intake to canonical personnel store.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Intake Commit orchestrator | TX boundary; separate from PMF Commit Engine | ⬜ |
| Person resolver | Create/link per ADR-048 | ⬜ |
| Section writers | D1–D12 → `person_*` | ⬜ |
| Record events | `personnel_record_events` emission | ⬜ |
| Provenance | Reuse PMF-2 patterns where applicable | ⬜ |
| Confirm dialog | HR explicit commit trigger | ⬜ |

**Dependencies:** PIF-2, PIF-5.

**Reuse from PMF (patterns only, no code change in freeze):** provenance writer, record event emitter, transaction conventions.

**Exit criteria:** approved intake → Person + section records; case `COMMITTED`; visible in Personnel Card read path. **Not met.**

---

### PIF-7 — Generated Documents

**Status:** 🟡 preview-PDF at review ✅; post-commit PDF ⬜

**Objective:** produce printed personal sheet PDF from personnel data.

| Deliverable | Description | Status |
|-------------|-------------|--------|
| PDF template | Official-form layout as **projection** of domains | 🟡 Preview layout implemented |
| Render pipeline | HTML → PDF (Playwright) | ✅ Preview at review step |
| Locale support | RU / KZ output | ⬜ RU only in preview |
| **Pre-commit preview trigger** | Draft PDF at review (candidate + HR) | ✅ Production |
| **Post-commit trigger** | Auto-generate on commit from canonical | ⬜ Future |
| Storage | Link to `files` / person document section | ⬜ Preview streamed, not archived |

**Dependencies:** PIF-4 for preview; PIF-6 for post-commit PDF.

**Exit criteria (full WP):** commit produces downloadable Personal Sheet PDF matching **canonical** data. **Not met.** Preview-PDF exit criteria **met** for draft review.

---

### Pilot

**Objective:** controlled production trial with real new hires.

| Parameter | Target |
|-----------|--------|
| Scope | 5–10 new hires |
| Form profile | `new_hire_minimal` or `new_hire_full` |
| HR operators | 2 trained users |
| Parallel paths | PMF education import continues independently |
| Success metrics | Zero double-entry; commit success rate; HR time per intake |
| Feedback | [PILOT_FEEDBACK_TEMPLATE](../PILOT_FEEDBACK_TEMPLATE.md) |

**Dependencies:** PIF-3 through PIF-7.

---

## 3. Timeline (indicative, not committed)

| Phase | WP | Relative order | Production |
|-------|-----|----------------|------------|
| Architecture | PIF-1 | Done (docs) | Aligns with impl |
| Foundation | PIF-2 | In progress | Draft JSON only |
| Candidate path | PIF-3 → PIF-4 | Largely underway | 🟡 Partial |
| HR path | PIF-5 → PIF-6 | Review partial; commit ⬜ | 🟡 / ⬜ |
| Output | PIF-7 | Preview ✅; post-commit ⬜ | 🟡 |
| Validation | Pilot | Blocked on PIF-6 | ⬜ |

No calendar dates assigned — sequencing only.

---

## 4. Relationship to PMF roadmap

| PMF (frozen) | PIF (active) |
|--------------|--------------|
| PMF-4F.1 History | Not started; deferred |
| PMF-4F.2 Advanced Mapping | Not started; deferred |
| PMF-4F.3 Lifecycle Ops | Not started; deferred |
| PMF Education pilot | Continues in controlled mode |
| PMF-7 Service Record plugin | Deferred |

PMF and PIF **share** Personal File target (ADR-047) but **different entry points**:

- PMF: Import staging → migration session → commit
- PIF: Invitation → electronic form → HR review → commit

---

## 5. Risk register (preliminary)

| Risk | Mitigation |
|------|------------|
| Duplicate Person on rehire | IIN match + HR confirm (PIF-004) |
| Form metadata drift | FormDefinition versioning (PIF-003) |
| Scope creep (full paper form) | Canonical domain model; phased sections |
| Commit engine duplication | Shared provenance/event patterns; separate orchestrator |
| PMF/PIF confusion | Clear architecture map (PIF-001 §6) |

---

## 6. Document index

| Code | Document |
|------|----------|
| PMF-FREEZE | [PMF-PILOT-FREEZE.md](../personnel-migration/PMF-PILOT-FREEZE.md) |
| PIF-001 | [PIF-001-personnel-intake-framework.md](./PIF-001-personnel-intake-framework.md) |
| PIF-002 | [PIF-002-electronic-personal-sheet.md](./PIF-002-electronic-personal-sheet.md) |
| PIF-003 | [PIF-003-dynamic-form-model.md](./PIF-003-dynamic-form-model.md) |
| PIF-004 | [PIF-004-data-ownership.md](./PIF-004-data-ownership.md) |
| PIF-2A | [PIF-2A-electronic-intake-ux-specification.md](./PIF-2A-electronic-intake-ux-specification.md) |
| PIF-2B | [demo/](./demo/) — static HTML prototype |
| PIF-ROADMAP | This document |

---

## 7. Recommended next engineering Work Package

**→ PIF-6 — Intake Commit** (after stabilising PIF-5 review UX)

Rationale:

1. Candidate path (PIF-3/4) and preview-PDF (PIF-7 partial) are **sufficiently pilot-ready** for HR feedback.
2. Without commit, intake data does not reach canonical `person_*` — the main business value gap.
3. PIF-2 canonical catalog and FormDefinition (PIF-003 target) should proceed **in parallel** but must not block commit MVP.
4. Post-commit PDF (PIF-7 remainder) follows commit once canonical projection is stable.

### Near-term deliverables

| # | Deliverable |
|---|-------------|
| 1 | Intake commit orchestrator + ADR-048 Person linkage |
| 2 | `PIF-2-003-commit-mapping-matrix.md` — draft path → `person_*` |
| 3 | HR diff / provenance view (PIF-5 completion) |
| 4 | FormDefinition v1 extraction from production `INTAKE_STEPS` (optional parallel) |
