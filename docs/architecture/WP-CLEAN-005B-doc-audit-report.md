# WP-CLEAN-005B — Post-Cleanup Documentation Audit

| Field | Value |
|-------|-------|
| Date | 2026-07-07 |
| Scope | Documentation audit after Professional Documents Demo retirement (CCR-008 + CCR-023) |
| Prerequisite for | WP-CLEAN-005C kickoff |
| Runtime changes | **None** (docs only) |

---

## 1. Objective

Verify that `docs/` no longer instructs operators or developers to use the removed ADR-034 demo HTTP API (`GET /directory/professional-documents*`), `professional_documents_service.py`, or `listProfessionalDocuments*` client exports.

---

## 2. Grep inventory (`docs/`)

Patterns: `professional-documents`, `personnel_demo_routes`, `professional_documents_service`, `listProfessionalDocuments`

| File | Match | Status | Action |
|------|-------|--------|--------|
| `docs/demo/HR-DEMO-LOCAL-RUNBOOK.md` | `professional-documents` (API table, screenshot name) | **Требовало обновления** | Rewritten — Track B primary; ADR-034 in Appendix A (historical) |
| `docs/adr/ADR-037-employee-documents-registry.md` | `professional-documents*` (deprecated table, endpoints §, acceptance, review decisions) | **Требовало обновления** | Updated — demo endpoints marked **removed** (005B) |
| `docs/architecture/WP-CLEAN-001-personnel-domain-assessment.md` | `personnel_demo_routes`, `professional_documents*` | **Смешанный** | §3.3 router class → Core; §7 runtime row → removed |
| `docs/architecture/WP-CLEAN-PROGRAM-REVIEW.md` | `professional-documents`, `listProfessionalDocuments` (§6 scan snapshot) | **Исторический** | §6 annotated as pre-005B scan; §9 rec #5 closed |
| `docs/architecture/WP-CLEAN-004-post-removal-report.md` | `listProfessionalDocuments*` | **Исторический** | No edit — documents 004-era state before 005B |
| `docs/architecture/WP-CLEAN-005B-post-removal-report.md` | All patterns (removal evidence) | **Исторический** | Stale-reference note resolved by this audit |
| `docs/architecture/WP-CLEAN-005A-post-removal-report.md` | `listProfessionalDocuments` (forward ref to 005B) | **Исторический** | No edit |
| `docs/architecture/CLEAN-GATE-001-cleanup-decision-gate.md` | CCR-008 gate row | **Актуальна** | Gate satisfied — no edit |
| `docs/adr/ADR-047-personnel-personal-file-architecture.md` | `professional_documents` (demo layer note) | **Актуальна** | Correctly notes demo tables ≠ production SoT |
| `docs/adr/ADR-047-appendix-*.md` | `person_professional_documents` (target model) | **Актуальна** | Unrelated to removed demo API |

**Out of scope (not `docs/`):** `corpsite-ui/.../demoApi.client.ts` may still contain stale exports — runtime hygiene outside this audit; `personnelJournalApi.client.ts` is clean (CCR-023 complete).

---

## 3. Reference status summary

| Category | Count | Files |
|----------|-------|-------|
| **Актуальна** | 3 | CLEAN-GATE-001, ADR-047 family |
| **Историческая** (retain as evidence) | 4 | WP-CLEAN-004/005A/005B reports, PROGRAM-REVIEW §6 scan |
| **Требовало обновления** | 3 | HR-DEMO-LOCAL-RUNBOOK, ADR-037, WP-CLEAN-001 |
| **Требовало удаления** | 0 | — |

---

## 4. Documents updated in this audit

| Document | Change |
|----------|--------|
| [HR-DEMO-LOCAL-RUNBOOK.md](../demo/HR-DEMO-LOCAL-RUNBOOK.md) | Track B runbook; ADR-034 archived in Appendix A |
| [ADR-037](../adr/ADR-037-employee-documents-registry.md) | Demo endpoints → removed; acceptance checklist synced |
| [WP-CLEAN-001](./WP-CLEAN-001-personnel-domain-assessment.md) | `personnel_demo_routes` → Core; runtime validation row updated |
| [WP-CLEAN-PROGRAM-REVIEW](./WP-CLEAN-PROGRAM-REVIEW.md) | §6 historical note; doc hygiene rec closed |
| [WP-CLEAN-005B report](./WP-CLEAN-005B-post-removal-report.md) | Stale runbook note resolved |

---

## 5. Professional Documents Demo — closure statement

| CCR | Artifact | Runtime | Docs |
|-----|----------|---------|------|
| CCR-008 | `GET /directory/professional-documents*`, `professional_documents_service.py` | **Removed** (005B) | **Synced** (this audit) |
| CCR-023 | `listProfessionalDocuments*` in `personnelJournalApi.client.ts` | **Removed** (005B) | **Synced** |

**Family status: CLOSED.** Optional orphan local tables (`certificate_types`, `employee_certificates`) remain a DBA hygiene topic — not part of demo contour.

---

## 6. Readiness for WP-CLEAN-005C

Demo contour documentation gate **cleared**. Proceed to [WP-CLEAN-005C plan](./WP-CLEAN-005C-plan.md) — CCR-006/007 legacy import retirement (execution blocked on access logs + DBA audit; planning only in this pass).

---

*End of doc audit report.*
