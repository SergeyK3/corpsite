# DOCS-REORG-PLAN — Architecture Documentation Library Reorganization

## Status

**Draft (planning only)** — 2026-07-08

| Field | Value |
|-------|-------|
| **Purpose** | Inventory and phased plan for reorganizing `docs/` without breaking governance traceability |
| **Scope** | Architecture library (`docs/architecture`, `docs/access`, related registers, gitignore) |
| **Out of scope (this phase)** | File moves, `.gitignore` edits, commits, code changes, Cleanup Program execution, Personnel Orders implementation |
| **Authoritative ADR storage** | **`docs/adr/` remains canonical** — no physical move of ADR files in baseline plan |

---

## 1. Executive summary

| Metric | Count |
|--------|------:|
| **Tracked files under `docs/`** (git) | **193** |
| **Untracked files** (`docs/position-cabinet/`, gitignored) | **4** |
| **Tracked Markdown** | ~172 |
| **Tracked non-Markdown** (sql, html, png, docx, txt) | ~21 |

**Tracked by top-level directory:**

| Directory | Files | Role today |
|-----------|------:|------------|
| `docs/adr/` | 92 | Canonical ADR + validation SQL + misc |
| `docs/access/` | 32 | ACCESS registers, WP-B*, PC-*, governance, review board |
| `docs/architecture/` | 29 | ARCH-001 family, governance, WP-CLEAN*, misc |
| `docs/ops/` | 16 | Runbooks, audits, OPS-* |
| `docs/demo/` | 9 | Demo runbook + screenshots |
| `docs/roadmap/` | 3 | Implementation / ops roadmaps |
| `docs/deploy/` | 2 | Deploy docs (**unchanged**) |
| `docs/workshop/` | 2 | Management review slides (html) |
| `docs/` (root) | 8 | PILOT*, RBAC audit, legacy TZ artefacts |

**Core problem:** normative architecture, access policy, Position Cabinet product composition, governance WPs, and cleanup programme artefacts share flat or misleading paths (`docs/access` ≠ access-only).

**Recommended direction:** nested **`docs/architecture/`** as the long-lived *architecture library*, with **`docs/adr/`** unchanged as decision log; operational docs stay in `ops/`, `deploy/`, `roadmap/`.

---

## 2. Current structural problems

1. **`docs/access/` is overloaded** — contains ACCESS-001/002 (normative policy), Permission Domain Registry, Tier G governance, WP-B1…B4 lifecycle, Review Board briefs, and Position Cabinet registers (PC-MOD-001, GLOSS-B4-001, PC-MANIFEST, PC-PROFILE).

2. **`docs/architecture/` mixes layers** — foundation (ARCH-001), governance meta (ARCHITECTURE_GOVERNANCE), Cleanup Program (WP-CLEAN*, CLEAN-GATE-001), and unrelated drafts (WP-RT-002, IMPLEMENTATION_PLAN).

3. **Position Cabinet has no tracked home** — `docs/position-cabinet/` exists locally but is **gitignored** (`docs/*` without allowlist). PC-CONCEPT-001 cannot enter repo without policy change.

4. **Personnel domain is ADR-scattered** — lifecycle (042/043), HR events/orders (036/037), personal file/history (047), HR processes split (045), sync/import (038/040) live only under `docs/adr/` with no architecture-library index.

5. **Cross-link density** — WP-B* and ADR-050 link to `../architecture/…` and `./review-board/…`. Bulk moves without redirect stubs will break dozens of relative links.

6. **Duplicate governance concepts** — `ARCHITECTURE_GOVERNANCE.md` (architecture baseline) vs `GOVERNANCE-WORK-PACKAGE-LIFECYCLE.md` (Tier G WP process) vs `ACCESS-RATIFICATION-PROGRAM.md` (program charter) — related but stored in different trees.

---

## 3. Target structure (for evaluation)

```
docs/
  architecture/
    README.md                          # Index + navigation (new)

    foundation/
      ARCH-001-*.md
      ARCHITECTURE_GOVERNANCE.md
      IMPLEMENTATION_PLAN.md           # optional — or roadmap/

    access/
      ACCESS-001-*.md
      ACCESS-002-*.md
      PERMISSION-DOMAIN-REGISTRY.md
      ACCESS-RATIFICATION-PROGRAM.md

    position-cabinet/
      PC-CONCEPT-001-*.md
      PC-CONCEPT-001-review-notes.md
      PC-MOD-001-*.md
      PC-MANIFEST-001-*.md
      PC-PROFILE-001-*.md
      GLOSS-B4-001-*.md
      README.md                        # links to ADR-050, ADR-051, ADR-053 in docs/adr/

    personnel/
      README.md                        # index by subdomain
      personnel-lifecycle/             # WP/assessments + links to ADR-042/043
      personnel-orders/                # future registers; today link ADR-036/037
      personnel-history/               # ADR-047 cluster links
      hr-import-sync/                  # ADR-038/040 cluster links
      acting-assignments/              # ADR-043-C2, ADR-051 links
      vacations/                       # placeholder — no dedicated register yet

    governance/
      GOVERNANCE-WORK-PACKAGE-LIFECYCLE.md
      TIER-G-GOVERNANCE-PROGRESS-REPORT.md
      review-board/
      wp-access/                       # WP-B1…B4 (optional subfolder)

    cleanup/                           # frozen — move only with Cleanup Program owner approval
      WP-CLEAN-*
      CLEAN-GATE-001-*

    DOCS-REORG-PLAN.md                 # this file (planning meta)

  adr/                                 # UNCHANGED canonical storage
    ADR-*.md
    *.sql

  deploy/                              # UNCHANGED
  ops/                                 # UNCHANGED (cross-link only)
  roadmap/                             # UNCHANGED or merge index into architecture/README
  demo/                                # UNCHANGED
  workshop/                            # UNCHANGED
  position-cabinet/                    # INTERIM option (Phase 0) before full nested move
```

**ADR-050 / ADR-051 / ADR-053:** remain in `docs/adr/`. Position Cabinet and access sections **link** to them; optional `architecture/position-cabinet/ADR-INDEX.md` lists canonical paths.

---

## 4. Document type taxonomy

| Type | ID pattern | Typical future home |
|------|------------|---------------------|
| **ARCH** | `ARCH-001-*`, assessments | `architecture/foundation/` |
| **Governance meta** | `ARCHITECTURE_GOVERNANCE` | `architecture/foundation/` or `architecture/governance/` |
| **ACCESS** | `ACCESS-001`, `ACCESS-002` | `architecture/access/` |
| **Register / glossary** | `PERMISSION-DOMAIN-REGISTRY`, `GLOSS-*` | `architecture/access/` or domain folder |
| **Concept** | `PC-CONCEPT-*` | `architecture/position-cabinet/` |
| **Product composition** | `PC-MOD-*`, `PC-MANIFEST-*`, `PC-PROFILE-*` | `architecture/position-cabinet/` |
| **ADR** | `ADR-*` | **`docs/adr/` only** |
| **WP (governance)** | `WP-B*` | `architecture/governance/wp-access/` |
| **WP (cleanup)** | `WP-CLEAN-*`, `CLEAN-GATE-*` | `architecture/cleanup/` (frozen) |
| **WP (other)** | `WP-RT-*` | domain folder or stay until classified |
| **Closure / ratification** | `*-CLOSURE-REPORT`, `*-RATIFICATION-PACKAGE` | alongside parent WP |
| **Review board** | `review-board/*`, `PD-5.*` | `architecture/governance/review-board/` |
| **Audit / investigation** | `*-audit*`, `DEBT-DATA-*` | stay near subject or `ops/` |
| **Deploy** | `docs/deploy/*` | unchanged |
| **Ops runbook** | `docs/ops/*`, `OPS-*` | unchanged |
| **Roadmap** | `docs/roadmap/*` | unchanged (+ index links) |
| **Pilot** | `docs/PILOT_*` | unchanged (root allowlist) |

---

## 5. Inventory — `docs/architecture/` (29 tracked)

| Current path | Type | Recommended future section | Move? |
|--------------|------|----------------------------|-------|
| `ARCH-001-position-permission-model.md` | ARCH | `foundation/` | Phase 2 |
| `ARCH-001-foundation-summary.md` | ARCH | `foundation/` | Phase 2 |
| `ARCH-001-foundation-consolidation-review.md` | ARCH / review | `foundation/` | Phase 2 |
| `ARCH-001-assessment-program.md` | ARCH | `foundation/` | Phase 2 |
| `ARCH-001-implementation-roadmap.md` | ARCH / roadmap | `foundation/` or link from `roadmap/` | Phase 2 / link-only |
| `ARCH-001-access-rbac-assessment.md` | ARCH assessment | `foundation/` | Phase 2 |
| `ARCH-001-permission-template-model-investigation.md` | ARCH investigation | `foundation/` | Phase 2 |
| `ARCH-001-personnel-employment-assessment.md` | ARCH assessment | `foundation/` or `personnel/` | Phase 2 |
| `ARCH-001-platform-user-identity-assessment.md` | ARCH assessment | `foundation/` | Phase 2 |
| `ARCH-001-positions-org-structure-assessment.md` | ARCH assessment | `foundation/` | Phase 2 |
| `ARCH-001-task-subsystem-assessment.md` | ARCH assessment | `foundation/` | Phase 2 |
| `ARCHITECTURE_GOVERNANCE.md` | governance | `foundation/` | Phase 2 |
| `IMPLEMENTATION_PLAN.md` | plan | `foundation/` or `roadmap/` link | Phase 3 — classify |
| `implementation/PHASE-2-readiness-review.md` | review | `foundation/implementation/` | Phase 3 |
| `WP-RT-002-regular-task-temporal-model-draft.md` | WP draft | stay or `foundation/tasks/` | Phase 3 |
| `CLEAN-GATE-001-cleanup-decision-gate.md` | cleanup governance | `cleanup/` | **Phase 4 — Cleanup owner only** |
| `WP-CLEAN-PROGRAM-REVIEW.md` | cleanup WP | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-001-personnel-domain-assessment.md` | cleanup WP | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-003A-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-003B-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-003C-CCR003-audit.md` | cleanup audit | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-003D-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-004-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-005A-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-005B-doc-audit-report.md` | cleanup audit | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-005B-post-removal-report.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-005C-kickoff-readiness.md` | cleanup WP | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-005C-plan.md` | cleanup WP | `cleanup/` | **Do not move until approved** |
| `WP-CLEAN-PHASE2-CLOSURE-REPORT.md` | cleanup closure | `cleanup/` | **Do not move until approved** |
| `DOCS-REORG-PLAN.md` | planning meta | stay at `architecture/` root | **Already here** |

---

## 6. Inventory — `docs/access/` (32 tracked)

| Current path | Type | Recommended future section | Move? |
|--------------|------|----------------------------|-------|
| `ACCESS-001-organizational-permission-matrix.md` | ACCESS | `architecture/access/` | Phase 2 |
| `ACCESS-002-organizational-management-authority-model.md` | ACCESS | `architecture/access/` | Phase 2 |
| `ACCESS-RATIFICATION-PROGRAM.md` | governance program | `architecture/access/` or `governance/` | Phase 2 |
| `PERMISSION-DOMAIN-REGISTRY.md` | register | `architecture/access/` | Phase 2 |
| `GOVERNANCE-WORK-PACKAGE-LIFECYCLE.md` | governance | `architecture/governance/` | Phase 2 |
| `TIER-G-GOVERNANCE-PROGRESS-REPORT.md` | governance report | `architecture/governance/` | Phase 2 |
| `GLOSS-B4-001-position-cabinet-vocabulary.md` | glossary | `architecture/position-cabinet/` | Phase 2 |
| `PC-MOD-001-position-cabinet-functional-composition.md` | PC product | `architecture/position-cabinet/` | Phase 2 |
| `PC-MANIFEST-001-position-cabinet-functional-manifest.md` | PC product | `architecture/position-cabinet/` | Phase 2 |
| `PC-PROFILE-001-position-cabinet-functional-profiles.md` | PC product | `architecture/position-cabinet/` | Phase 2 |
| `WP-B1-CLOSURE-REPORT.md` | WP closure | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md` | WP ratification | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B2-BINDING-PRINCIPLES-REVIEW.md` | WP review | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B3-CLOSURE-REPORT.md` | WP closure | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B3-PROBLEM-SPACE-REVIEW.md` | WP review | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B3-PROGRAM-INITIATION.md` | WP initiation | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md` | investigation | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B4-CLOSURE-REPORT.md` | WP closure | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md` | concept review | `architecture/position-cabinet/` or `wp-access/` | Phase 3 |
| `WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md` | decision | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B4-POSITION-CABINET-CONTOUR-BINDING.md` | WP normative | `architecture/position-cabinet/` | Phase 3 |
| `WP-B4-PROBLEM-SPACE-REVIEW.md` | WP review | `architecture/governance/wp-access/` | Phase 3 |
| `WP-B4-RATIFICATION-PACKAGE.md` | WP ratification | `architecture/governance/wp-access/` | Phase 3 |
| `review-board/REVIEW-BOARD-BRIEF-TEMPLATE.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/PD-5.2-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/PD-5.3-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/PD-5.4-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/WP-B2-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/WP-B3-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/WP-B3-SESSION-1-REVIEW-BOARD-RECORD.md` | review board record | `architecture/governance/review-board/` | Phase 3 |
| `review-board/WP-B4-REVIEW-BOARD-BRIEF.md` | review board | `architecture/governance/review-board/` | Phase 3 |
| `review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md` | review board record | `architecture/governance/review-board/` | Phase 3 |

---

## 7. Inventory — untracked `docs/position-cabinet/` (gitignored)

| Path | Type | Status | Recommended action |
|------|------|--------|-------------------|
| `PC-CONCEPT-001-unified-position-cabinet-concept.md` | concept (Draft) | local only | Phase 0: allowlist + commit |
| `PC-CONCEPT-001-review-notes.md` | review notes | local only | Phase 0: allowlist + commit |
| `PC-CONCEPT-001-Единая-концепция-Position-Cabinet-v0.1.docx` | source artefact | local only | Phase 0: allowlist (optional) |
| `PC-CONCEPT-001-Unified-Position-Cabinet-Concept-v0.1.docx` | source artefact | local only | Phase 0: allowlist (optional) |

**Long-term:** merge into `docs/architecture/position-cabinet/` (Phase 2) or keep flat `docs/position-cabinet/` with allowlist — decision required before Phase 2.

---

## 8. Inventory — key registers & ADR clusters (stay in `docs/adr/`)

### 8.1 Position Cabinet & access (link-only from architecture library)

| ADR | Title (short) | Link from |
|-----|---------------|-----------|
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Organization Position & Position Cabinet | `position-cabinet/README` |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Cabinet Access Resolution | `position-cabinet/README`, `access/` |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | Permission Template Binding Model | `access/`, `foundation/` |
| [ADR-007](../adr/ADR-007-MVP-matrix-personal-cabinets.md) | MVP matrix personal cabinets (legacy term) | historical link only |

### 8.2 Personnel domain (index via `architecture/personnel/README` — no ADR moves)

| Subdomain | Primary ADRs | Dedicated register today? |
|-----------|--------------|---------------------------|
| **Personnel lifecycle** | ADR-042 (11 files), ADR-043 (17 files) | WP in ADR phases only |
| **HR processes split** | ADR-045 | ADR only |
| **Personnel orders / HR events** | ADR-036, ADR-037, ADR-032, ADR-035 | **No PC/ARCH register** — orders covered by ADR-036 model |
| **Personnel history / personal file** | ADR-047 (+ appendices, sql) | ADR only |
| **HR import / sync** | ADR-038 (7 files), ADR-040, ADR-041 | roadmap + ADR |
| **Acting / assignments** | ADR-043 phase C2, ADR-051 | ADR only |
| **Vacations** | — | **No documents found** — placeholder folder only |
| **Identity reconciliation** | ADR-044 (10 files), ADR-048 | ADR only |

**Personnel Orders note:** no standalone `Personnel Orders` architecture register exists yet. Future home: `architecture/personnel/personnel-orders/` with README linking ADR-036 §orders, ADR-037, UI route `/directory/personnel/orders` (implementation out of scope).

### 8.3 Full ADR catalogue

All **92 files** in `docs/adr/` — **do not move**. Maintain thematic index in `architecture/personnel/README.md` and `architecture/README.md`.

---

## 9. Other tracked `docs/` areas (minimal change)

| Directory | Files | Recommendation |
|-----------|------:|----------------|
| `docs/deploy/` | 2 | **No change** |
| `docs/ops/` | 16 | **No change**; add links from architecture indexes where relevant |
| `docs/roadmap/` | 3 | **No change**; `POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md` cross-links ARCH-001 |
| `docs/demo/` | 9 | **No change** |
| `docs/workshop/` | 2 | **No change** |
| `docs/PILOT_*`, `RBAC_VISIBILITY_118_AUDIT.md` | 6 | **No change** (explicit gitignore allowlist) |
| Legacy TZ (`tz_final_v1.txt`, docx) | 2 | **Do not move** — historical; consider `docs/archive/` in later phase |

---

## 10. Proposed move matrix (summary)

| Phase | Action | Files affected | Physical move? |
|-------|--------|----------------|----------------|
| **0** | gitignore allowlist for `docs/position-cabinet/`; commit PC-CONCEPT-001 Draft | 4 | No (new tracking) |
| **1** | Add `architecture/README.md`, `position-cabinet/README.md`, `personnel/README.md` (indexes + links only) | 3 new | No |
| **2** | Move foundation + access + PC registers from flat paths into nested `architecture/*` | ~25 | Yes |
| **3** | Move governance + WP-B + review-board | ~22 | Yes |
| **4** | Move WP-CLEAN* into `architecture/cleanup/` | 14 | **Only with Cleanup Program approval** |
| **5** | Optional stub at old paths (`docs/access/README.md` → redirect) | stubs | Link preservation |

---

## 11. Files that should NOT be moved

| Category | Reason |
|----------|--------|
| **`docs/adr/**`** | Canonical ADR storage by project convention |
| **`docs/deploy/**`** | Operational deploy domain |
| **`docs/ops/**`** | Runbooks — separate lifecycle |
| **`WP-CLEAN-*`, `CLEAN-GATE-*`** | Cleanup Program — explicit freeze until owner approves |
| **`docs/PILOT_*`, RBAC audit** | Root allowlist + pilot workflow |
| **Validation SQL in `docs/adr/`** | Paired with ADR; move breaks review packs |
| **Personnel Orders implementation docs** | None in repo yet; future registers TBD |

---

## 12. Required `.gitignore` changes (not applied yet)

Current pattern (simplified):

```gitignore
docs/
!docs/
docs/*
!docs/adr/
!docs/adr/**
!docs/architecture/
!docs/architecture/**
!docs/access/
!docs/access/**
…
```

**Phase 0 minimum:**

```gitignore
!docs/position-cabinet/
!docs/position-cabinet/**
```

**Phase 2+ (if nested under architecture):** allowlist may be redundant if files live under already-allowed `docs/architecture/**`. If keeping flat `docs/position-cabinet/`, retain explicit allowlist.

**Optional later:**

```gitignore
!docs/personnel/          # only if top-level personnel/ created outside architecture/
```

**After Phase 2–3:** consider **removing** `!docs/access/` once `docs/access/` is empty and replaced by stubs — low priority.

---

## 13. Link breakage risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| ADR → `../architecture/ARCH-001-*` | **High** (~50+ links in ADR-050 alone) | `git mv` + batch link update; or stub files at old paths |
| WP-B cross-links (`./WP-B3-*`, `./review-board/*`) | **High** | Move WP as a **folder unit**; update relative paths in one PR |
| `ARCHITECTURE_GOVERNANCE` → ADR links | Medium | ADR paths unchanged — safe |
| External bookmarks / Review Board PDFs | Medium | Keep 301-style markdown stubs: `docs/access/README.md` |
| CI / scripts referencing paths | Low | `rg 'docs/access'` before Phase 2 |
| PC-CONCEPT-001 → Related links | Low | Already uses relative `../architecture/`, `../access/` — update when PC moves |

**Recommended:** one phase = one PR + `rg -l 'docs/access/'` link audit + optional stub directory for 6 months.

---

## 14. Safe execution order

1. **Approve this plan** (architecture review / Review Board informational).
2. **Phase 0** — `.gitignore` allowlist + track PC-CONCEPT-001 + review notes (+ optional DOCX sources).
3. **Phase 1** — README indexes only (no moves); validate navigation.
4. **Phase 2** — move `foundation/`, `access/`, `position-cabinet/` registers; update links; leave stubs in `docs/access/` for deprecated paths.
5. **Phase 3** — move governance + WP-B + review-board as atomic tree.
6. **Phase 4** — Cleanup subtree (separate approval).
7. **Phase 5** — remove stub files after link audit window.

**Do not** combine Phase 2 and Phase 4 in one release.

---

## 15. Minimal safe first step (recommended)

| Step | Action | Rationale |
|------|--------|-----------|
| 1 | Add `!docs/position-cabinet/` to `.gitignore` | Unblocks PC-CONCEPT-001 in git without restructuring |
| 2 | Commit `PC-CONCEPT-001-unified-position-cabinet-concept.md` (Draft) + `PC-CONCEPT-001-review-notes.md` | Preserves new conceptual direction |
| 3 | Add short `docs/position-cabinet/README.md` (index + links to PC-MOD-001, ADR-050/051, ARCH-001) | Navigation without moves |
| 4 | **Do not** move `docs/access/*` or WP-B* yet | Avoids mass link breakage |
| 5 | **Do not** touch WP-CLEAN* or Personnel Orders code/docs | Per program constraints |

This delivers immediate value (tracked Position Cabinet concept) while deferring large reorg to Phase 2+.

---

## 16. Open decisions for architecture review

1. **Flat vs nested Position Cabinet path** — `docs/position-cabinet/` (interim) vs `docs/architecture/position-cabinet/` (target).
2. **Fate of `docs/access/` directory** — delete after migration vs permanent redirect stub.
3. **Personnel Orders register** — create `PC-*` / `ARCH-*` register or remain ADR-036-linked only.
4. **DOCX sources in git** — track binary DOCX or Markdown-only policy.
5. **IMPLEMENTATION_PLAN.md** — architecture vs roadmap ownership.

---

## Appendix A — Related documents (special attention)

| ID | Current path | Future section |
|----|--------------|----------------|
| ARCH-001 (primary) | `docs/architecture/ARCH-001-position-permission-model.md` | `foundation/` |
| ARCHITECTURE_GOVERNANCE | `docs/architecture/ARCHITECTURE_GOVERNANCE.md` | `foundation/` |
| ACCESS-001 | `docs/access/ACCESS-001-organizational-permission-matrix.md` | `access/` |
| ACCESS-002 | `docs/access/ACCESS-002-organizational-management-authority-model.md` | `access/` |
| PC-MOD-001 | `docs/access/PC-MOD-001-position-cabinet-functional-composition.md` | `position-cabinet/` |
| PC-CONCEPT-001 | `docs/position-cabinet/PC-CONCEPT-001-unified-position-cabinet-concept.md` | `position-cabinet/` (Phase 0) |
| ADR-050 | `docs/adr/ADR-050-organization-position-cabinet-model.md` | **stay in adr/** |
| ADR-051 | `docs/adr/ADR-051-cabinet-access-resolution.md` | **stay in adr/** |
| ADR-053 | `docs/adr/ADR-053-permission-template-binding-model.md` | **stay in adr/** |
| WP-B1…B4 | `docs/access/WP-B*` | `governance/wp-access/` (Phase 3) |
| WP-CLEAN* | `docs/architecture/WP-CLEAN*` | `cleanup/` (Phase 4 — frozen) |
| Review board | `docs/access/review-board/*` | `governance/review-board/` (Phase 3) |

---

## Document history

| Date | Change |
|------|--------|
| 2026-07-08 | Initial inventory and phased reorg plan (planning only; no moves applied) |
