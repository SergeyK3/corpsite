# ADR-043 Phase P1 — Production Gap Audit

## Статус

**Prepared** (2026-06-20) — audit only; no deploy performed.

## Цель

Зафиксировать разрыв между локальной реализацией ADR-042/043 и production VPS перед HR-пилотом на июньских данных.

## Методология

| Источник | Что проверено |
|----------|---------------|
| Git `HEAD` | Последний **закоммиченный** revision |
| `git status` | Незакоммиченные ADR-043 артефакты |
| `alembic heads` | Локальный target migration head |
| `README_DEPLOY.md`, `docs/deploy/frontend.md` | Production deploy baseline |
| `docs/adr/ADR-042-*`, `docs/adr/ADR-043-*` | Phase scope и acceptance |
| `tests/test_adr043_*` | Локальное test coverage |

**VPS baseline (inferred):** последний задокументированный production checkpoint — ADR-042 migrations до `w5x6y7z8a9b0`, frontend через `scripts/deploy_frontend.sh`, host `mmc.004.kz` (`/opt/projects/corpsite/app`). Прямой SSH-проверки `alembic current` на VPS в рамках P1 **не выполнялось** — deploy status помечен как *expected / unverified*.

---

## Executive summary

| Layer | Local (working tree) | Git remote (committed) | VPS (expected) | Gap severity |
|-------|---------------------|------------------------|----------------|--------------|
| ADR-042 B2–C1.1 | Implemented | Committed (`b5fd3bc`) | Likely deployed | **Low** — verify smoke |
| ADR-043 B2–C4.2 | Implemented | **Not committed** | **Not deployed** | **Critical** |
| Alembic head | `y7z8a9b0c1d2` | `w5x6y7z8a9b0` | Likely `w5x6y7z8a9b0` | **Critical** (2 migrations) |
| Personnel Lifecycle UI | Built locally | Not committed | Absent | **High** |
| HR pilot readiness | Dev-ready | Blocked on commit + deploy | Not ready | **Critical** |

**Blocking actions before pilot:**

1. Commit + push ADR-043 stack (code + migrations + UI + tests + docs).
2. VPS: `git pull` → `alembic upgrade head` → backend restart → frontend rebuild.
3. Post-deploy smoke (general + lifecycle-specific).

---

## Per-block audit

### ADR-042 Phase C1.1 (SysAdmin UI Polish)

> В спецификации P1 указано «C1.2» — в репозитории фаза задокументирована как **C1.1** (`ADR-042-phase-c1-1-polish.md`). Ниже — C1.1.

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally & committed** — `/admin/access/roles`, `/targets/search`, `/guard-mode`; Access tab polish; `adminNav.ts`; `/auth/me` flags |
| **Migration** | None (read-only endpoints) |
| **Deploy** | Expected on VPS with ADR-042 bundle; verify via `GET /api/admin/access/roles` |
| **Risk** | **Low** — regression unlikely; smoke in `README_DEPLOY.md` § ADR-042 |

**Evidence:** `docs/adr/ADR-042-phase-c1-1-polish.md`, `app/services/admin_reference_service.py`, `corpsite-ui/app/admin/system/`.

---

### ADR-043 Phase B2 — Personnel Lifecycle Schema

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — migration `x6y7z8a9b0c1` |
| **Migration** | `x6y7z8a9b0c1` — tables: `hr_source_files`, `hr_override_stewardship_rules`, `hr_review_overrides`, `hr_review_override_history`, `hr_personnel_change_events`, `hr_snapshot_effective_entries`; alters on `hr_import_batches`, `enrollment_queue` |
| **Deploy** | **Not on VPS** — requires `alembic upgrade x6y7z8a9b0c1` |
| **Risk** | **Critical** — all ADR-043 runtime depends on this DDL |

**Validation:** `docs/adr/ADR-043-phase-b2-validation.sql`, `tests/test_adr043_phase_b2_schema.py`.

---

### ADR-043 Phase B3 — Runtime Services & Effective Canonical

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `hr_effective_canonical_service.py`, `hr_review_override_service.py`, `hr_override_stewardship_service.py`, backfill service |
| **Migration** | Covered by B2 |
| **Deploy** | **Not on VPS** |
| **Risk** | **High** — override approve/reject, effective resolver |

**Tests:** `tests/test_adr043_phase_b3_runtime_services.py`.

---

### ADR-043 Phase C1 — Effective Monthly Diff

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `hr_effective_monthly_diff_service.py` |
| **Migration** | B2 (`hr_personnel_change_events`) |
| **Deploy** | **Not on VPS** |
| **Risk** | **High** — event materialization for lifecycle |

**Tests:** `tests/test_adr043_phase_c1_effective_monthly_diff.py`.

---

### ADR-043 Phase C2 — Person & Assignment Sync

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `hr_person_assignment_sync_service.py` |
| **Migration** | Uses ADR-042 `persons`, `person_assignments`, `employee_assignment_links` (already on VPS if ADR-042 deployed) |
| **Deploy** | **Not on VPS** (code) |
| **Risk** | **High** — integrity of person/assignment graph |

**Tests:** `tests/test_adr043_phase_c2_person_assignment_sync.py` (transfer, rate, close, concurrent, dry-run).

---

### ADR-043 Phase C3 — Lifecycle Orchestrator

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `hr_personnel_lifecycle_service.py` |
| **Migration** | `y7z8a9b0c1d2` — `hr_personnel_lifecycle_runs` journal |
| **Deploy** | **Not on VPS** |
| **Risk** | **Critical** — single entry point for monthly cycle |

**Tests:** `tests/test_adr043_phase_c3_lifecycle_orchestrator.py`.

---

### ADR-043 Phase C4.1 — Personnel Lifecycle API

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `personnel_admin_router.py`, guards, query service |
| **Migration** | C3 journal (for run list) |
| **Deploy** | **Not on VPS** — `/admin/personnel/*` absent |
| **Risk** | **High** — required for UI and scripted smoke |

**Tests:** `tests/test_adr043_phase_c4_1_lifecycle_api.py`.

---

### ADR-043 Phase C4.2 — Personnel Lifecycle UI

| Dimension | Status |
|-----------|--------|
| **Code** | **Done locally, uncommitted** — `/admin/system/personnel-lifecycle`, API client, 4 tabs |
| **Migration** | None |
| **Deploy** | **Not on VPS** — requires frontend rebuild |
| **Risk** | **Medium** — pilot can fallback to API/curl, but HR UX depends on UI |

**Tests:** 30 vitest cases under `corpsite-ui/app/admin/system/`.

**Auth extension (uncommitted):** `/auth/me` → `has_personnel_admin`, `has_hr_governance`.

---

## Migration chain

```text
… → w5x6y7z8a9b0  (ADR-042 B5 — last COMMITTED head)
      ↓
    x6y7z8a9b0c1  (ADR-043 B2 — LOCAL ONLY)
      ↓
    y7z8a9b0c1d2  (ADR-043 C3 — LOCAL ONLY, current alembic head)
```

| Revision | VPS (expected) | Local DB (if upgraded) | Git committed |
|----------|----------------|------------------------|---------------|
| `w5x6y7z8a9b0` | Yes | Yes | Yes |
| `x6y7z8a9b0c1` | No | Maybe | **No** |
| `y7z8a9b0c1d2` | No | Maybe | **No** |

---

## Risk matrix (rollout)

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | ADR-043 not committed → VPS pull misses code | Certain | Critical | Commit + tag before deploy |
| R2 | Alembic skip → runtime 500 on missing tables | High | Critical | `alembic upgrade head` + validation SQL |
| R3 | Override history trigger breaks on prod PG version | Low | High | Run B2 validation SQL post-migrate |
| R4 | Lifecycle execute on wrong snapshot pair | Medium | High | Preview-first policy; pilot checklist |
| R5 | HR-only user lacks nav permission | Medium | Medium | Grant `HR_ENROLLMENT_MANAGER`; verify `/auth/me` |
| R6 | Frontend stale bundle (no C4.2 UI) | High | Medium | `sudo ./scripts/deploy_frontend.sh` |
| R7 | June data not promoted to approved snapshot | Medium | Critical | P1.3 pilot checklist gate |

---

## Pre-deploy verification commands (local)

```bash
# Committed vs working tree
git status
git log -1 --oneline

# Migration head
alembic heads
alembic history -r w5x6y7z8a9b0:head

# Backend tests (ADR-043)
python -m pytest tests/test_adr043_phase_b2_schema.py \
  tests/test_adr043_phase_b3_runtime_services.py \
  tests/test_adr043_phase_c1_effective_monthly_diff.py \
  tests/test_adr043_phase_c2_person_assignment_sync.py \
  tests/test_adr043_phase_c3_lifecycle_orchestrator.py \
  tests/test_adr043_phase_c4_1_lifecycle_api.py -q

# Frontend tests
cd corpsite-ui && npm test -- --run app/admin/system lib/adminNav
```

---

## VPS verification commands (post-deploy — not executed in P1)

```bash
cd /opt/projects/corpsite/app
git log -1 --oneline
alembic current
alembic heads

# Expect single head: y7z8a9b0c1d2
psql "$DATABASE_URL" -f docs/adr/ADR-043-phase-b2-validation.sql

curl -sS -H "Authorization: Bearer $TOKEN" \
  https://mmc.004.kz/api/admin/personnel/lifecycle/runs?limit=1
```

---

## Conclusion

Архитектурная разработка ADR-043 **завершена локально**, но **production gap критический**: код и миграции B2/C3 не закоммичены и не задеплоены. ADR-042 (включая C1.1 SysAdmin polish) вероятно уже на VPS, но требует confirm smoke.

**Следующий шаг:** P1 Deployment Plan → commit → controlled VPS rollout → June pilot (P1.3).

## Связанные документы

- [P1 Deployment Plan](./ADR-043-phase-p1-deployment-plan.md)
- [P1 Pilot Checklist](./ADR-043-phase-p1-pilot-checklist.md)
- [ADR-043 C4.2 UI](./ADR-043-phase-c4-2-personnel-lifecycle-ui.md)
- [README_DEPLOY.md](../../README_DEPLOY.md)
