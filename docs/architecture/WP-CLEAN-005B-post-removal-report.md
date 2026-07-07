# WP-CLEAN-005B — Legacy Demo API Finalization Report (CCR-008 + CCR-023)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | Unified retirement of ADR-034 professional-documents **demo contour** |
| CCR | CCR-008 (backend), CCR-023 (frontend dead exports) |
| Status | **Complete** |
| Gate policy | [CLEAN-GATE-001](./CLEAN-GATE-001-cleanup-decision-gate.md) G1–G7 |

---

## 0. Pre-flight — CCR-008 ↔ CCR-023 dependency re-audit

### Question

Does CCR-023 still depend on completing CCR-008 before removal, as recorded in [WP-CLEAN-PROGRAM-REVIEW](./WP-CLEAN-PROGRAM-REVIEW.md)?

### Evidence (2026-07-07)

| Layer | CCR-008 | CCR-023 |
|-------|---------|---------|
| Artifact | `GET /directory/professional-documents*`, `professional_documents_service.py`, demo route tests | `listProfessionalDocuments*` exports in `personnelJournalApi.client.ts` |
| Production UI | **Not used** since ADR-037 Phase 1A (`documentsApi.client.ts`) | **0 importers** (grep confirmed) |
| Call relationship | HTTP API target | Client adapter pointing at CCR-008 endpoints |
| Shared contour | ADR-034 local demo, superseded by ADR-037 | Same demo API family |

### Conclusion

**Dependency confirmed at contour level** — CCR-023 is the frontend adapter stub for the CCR-008 demo API. They form one logical demo contour.

| Dependency type | Status |
|-----------------|--------|
| Hard runtime blocker (023 cannot be removed first) | **No** — 0 UI callers; removing exports first would not break production |
| Program / G5 ordering (demo API family) | **Yes** — still valid |
| Recommended 005B execution order | **CCR-008 backend first**, then **CCR-023 exports** — finalizes API surface before removing client stubs |

**Decision:** Execute WP-CLEAN-005B as a **single cleanup package** (backend → frontend stubs). No order change requires separate approval.

**Out of 005B scope (unchanged):** demo DB tables (`certificate_types`, `employee_certificates`), `scripts/local_demo/adr034_*`, Alembic stub `e4a1c92b7d10` — schema/local artifacts without HTTP surface.

---

## 1. CCR-008 — Legacy demo backend

### G1 — Inventory

| Check | Result |
|-------|--------|
| CCR register match | CCR-008 → demo routes + service ✓ |
| Routes | `GET /directory/professional-documents`, `/availability` in `personnel_demo_routes.py` |
| Service | `app/services/professional_documents_service.py` |
| Co-located production route | `GET /directory/personnel-events` — **must preserve** |

### G2 — Reference audit

| Check | Result |
|-------|--------|
| UI callers of demo endpoints | **0** (production uses `documentsApi.client.ts`) |
| CCR-023 exports | Only remaining frontend references (dead) |
| Backend importers of service | `personnel_demo_routes.py` only |
| Tests | `tests/test_personnel_demo_routes.py` — 3 demo tests + 4 personnel-events tests |

### G3 — Classification

**Legacy demo runtime** — safe to remove routes/service; **not** Dead for entire `personnel_demo_routes.py` module (personnel-events remains Core).

### G4 — Removal

| Action | Detail |
|--------|--------|
| Modified | `app/directory/personnel_demo_routes.py` — removed demo routes/imports; kept `/personnel-events` |
| Deleted | `app/services/professional_documents_service.py` |
| Modified | `tests/test_personnel_demo_routes.py` — removed 3 demo tests + helper |

---

## 2. CCR-023 — Deprecated frontend exports

### G1–G3

| Check | Result |
|-------|--------|
| Exports | `listProfessionalDocuments`, `fetchProfessionalDocumentsAvailability`, related types |
| Importers | **0** |
| Classification | **Dead** — confirmed |

### G4 — Removal

Removed demo export block from `personnelJournalApi.client.ts` (journal API exports preserved).

---

## 3. G5 — Build verification

| Command | Result |
|---------|--------|
| `python -m pytest tests/test_personnel_demo_routes.py -q` | **4 passed** |
| `npm run build` (corpsite-ui) | **Pass** (exit 0) |
| `npm test` | **499/499 passed**, 75 files |
| Post-removal grep | No runtime refs to demo routes/service/exports |

---

## 4. G6 — Rollback readiness

Pre-removal commit: `a9fcf5d74f901522e4fe0d998a40d6d538e8153e`

```bash
git checkout a9fcf5d74f901522e4fe0d998a40d6d538e8153e -- \
  app/directory/personnel_demo_routes.py \
  app/services/professional_documents_service.py \
  tests/test_personnel_demo_routes.py \
  corpsite-ui/app/directory/personnel/_lib/personnelJournalApi.client.ts
```

---

## 5. G7 — Documentation

| Artifact | Update |
|----------|--------|
| CCR-008 register | Status → **removed** (runtime API) |
| CCR-023 register | Status → **removed** |
| [CCR-008 marker](../deprecated/personnel/CCR-008-professional-documents-demo.md) | Updated — removed |
| [CCR-023 marker](../deprecated/personnel/CCR-023-personnel-journal-demo-exports.md) | Created — removed |
| [INDEX](../deprecated/personnel/INDEX.md) | Synced |
| [WP-CLEAN-PROGRAM-REVIEW](./WP-CLEAN-PROGRAM-REVIEW.md) | 005B complete |

**Stale reference (resolved):** `docs/demo/HR-DEMO-LOCAL-RUNBOOK.md` updated in [doc audit](./WP-CLEAN-005B-doc-audit-report.md) (2026-07-07).

---

## 6. Runtime impact

- **Removed:** ADR-034 demo HTTP API (`/directory/professional-documents*`).
- **Unchanged:** Personnel journal (`/directory/personnel-events`), ADR-037 documents UI/API, production employee CRUD.
- **Orphan schema:** Local demo tables may still exist in dev DBs; no application code reads them via demo API.

---

## 7. Readiness for WP-CLEAN-005C

**Ready** for legacy import retirement (CCR-006/007) as a **separate** gated WP — requires access logs + DBA audit. Demo contour (008/023) is closed. Doc audit: [WP-CLEAN-005B-doc-audit-report](./WP-CLEAN-005B-doc-audit-report.md). Plan: [WP-CLEAN-005C-plan](./WP-CLEAN-005C-plan.md).

---

*End of WP-CLEAN-005B report.*
