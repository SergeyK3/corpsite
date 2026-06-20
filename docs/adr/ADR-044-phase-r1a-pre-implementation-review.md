# ADR-044 B1/B2 — Pre-Implementation Review (R1a)

## Статус

**Review complete** (2026-06-20) — gate document before coding ADR-044 B1/B2.  
No code, no migrations executed, no PR.

## Связанные документы

| Document | Role |
|----------|------|
| [ADR-044 Ratified](./ADR-044-identity-reconciliation.md) | Architecture |
| [R1a Blueprint](./ADR-044-phase-r1a-implementation-blueprint.md) | Accepted implementation spec |
| [Impact Analysis](./ADR-044-impact-analysis-match-key.md) | Namespace constraints |

---

## 1. Source precedence review (P1 → P5)

### 1.1. Verdict

**Precedence chain is architecturally correct** for R1a, with **one mandatory implementation rule** and **two operational caveats**.

### 1.2. Authoritative semantics (aligned with ADR-043)

| Priority | Source | What R1a must read | Correct? |
|----------|--------|-------------------|----------|
| **P1** | `hr_review_overrides` | `field_path = 'identity.iin'`, `status = 'active'`, `scope_key = 'PERSON:{canonical_person_key}'` | ✓ |
| **P2** | `hr_snapshot_effective_entries` | `effective_payload.iin` on **active snapshot**, roster row keyed by **canonical `match_key`** | ✓ |
| **P3** | `hr_canonical_snapshot_entries` | Column `iin` or `payload.iin` for roster entry | ✓ |
| **P4** | `employee_identities` | `identity_type = 'IIN'`, `valid_to IS NULL`, 12 digits | ✓ |
| **P5** | `hr_change_events` | Column `iin`, latest by `event_at` for `employee_id` or `match_key` | ✓ |

**P1 is NOT read via `persons.match_key`.**  
Override scopes follow **canonical `person_key`** (`emp:{id}` / `iin:{12}` / `name:…`), same as `hr_effective_canonical_service._person_scope_key()` and `resolve_effective_person()`.

### 1.3. P1 — `identity.iin` override (detailed)

**Existing ADR-043 behavior** (`hr_effective_canonical_service.py`):

1. Load canonical roster entry by `person_key` (canonical `match_key`).
2. Build `scope_keys = ['PERSON:{person_key}']`.
3. Load active overrides for those scope keys.
4. `apply_overrides_to_payload()` maps `identity.iin` → payload key `iin` via `field_path_to_payload_key()`.

**R1a must mirror this exactly** for P1 resolution. Tier-2 `identity.iin` overrides require evidence per ADR-043 B2 validation §4 — R1a only **reads** active rows; does not approve pending.

| Scenario | Expected P1 behavior |
|----------|---------------------|
| Override `PERSON:emp:26` + `identity.iin` active | **Wins** over canonical column and raw payload |
| Override on `PERSON:name:…` (legacy scope) | **Not found** via canonical lookup — known pre-R1b gap; report WARN |
| Pending override only | **Ignored** (not active) — fall through to P2 |
| Override value non-12-digit after normalize | **Invalid** — treat as absent; WARN |

### 1.4. P1 vs P2 interaction (critical)

**P2 effective cache already embeds P1** when cache is fresh (`refresh_snapshot_effective_entries` applies overrides before persist).

| Approach | Recommendation |
|----------|----------------|
| Read P2 only after cache refresh | Valid if R1a.0 refreshes active snapshot cache |
| Explicit P1 query before P2 | **Preferred** — handles stale cache (override `updated_at > computed_at`) |
| Call `resolve_effective_person(person_key=canonical_key)` | **Safest** — single code path with ADR-043; use for integration tests |

**Ratified implementation rule for B1:**

```text
1. Resolve canonical_person_key for person (via employees.employee_id → emp:{id}, etc.)
2. P1: SELECT active override identity.iin WHERE scope_key = 'PERSON:' || canonical_person_key
3. If P1 hit → normalize → use (source_tag = P1)
4. Else P2: read hr_snapshot_effective_entries.effective_payload.iin for active snapshot + match_key
5. Else P3 → P4 → P5 per blueprint
```

Do **not** invert P2 before P1 when cache may be stale.

### 1.5. Caveats (not blockers)

| # | Caveat | Mitigation in B1/B2 |
|---|--------|---------------------|
| C1 | Legacy overrides scoped to `PERSON:name:…` invisible to canonical P1 lookup | WARN in dry-run; document until R1b |
| C2 | Person without employee link: canonical key may be `iin:` or `name:` only | Resolve via `persons.match_key` only for **finding** canonical row, not for override scope unless match_key equals canonical key |
| C3 | Multiple employees per person (rare) | Pick operational employee per blueprint; WARN if >1 active |

### 1.6. Precedence sign-off

| Question | Answer |
|----------|--------|
| Is P1 → P5 order correct? | **Yes** |
| Is P1 correct for `identity.iin`? | **Yes**, with canonical scope_key |
| Additional research needed? | **No** |

---

## 2. Files, services, modules touched

### 2.1. New artifacts (B1/B2)

| Path | B1 | B2 | Purpose |
|------|:--:|:--:|---------|
| `app/services/identity_reconciliation_service.py` | ✓ | ✓ | Scan, resolve IIN, dry-run, execute |
| `app/api/personnel_admin_schemas.py` | ✓ | — | Request/response DTOs (or `identity_reconciliation_schemas.py`) |
| `app/api/personnel_admin_router.py` | ✓ | — | `GET/POST .../identity/reconciliation/r1a` endpoints |
| `scripts/run_identity_reconciliation_r1a.py` | — | ✓ | CLI executor (pattern: `repair_hr_import_employee_bindings.py`) |
| `tests/test_adr044_phase_r1a_identity_materialization.py` | ✓ | ✓ | Unit + integration |
| `docs/adr/ADR-044-phase-r1a-validation.sql` | — | ✓ | Gates G1–G10, V1a–V1f |
| `docs/runbooks/identity-reconciliation-r1a.md` | — | ✓ | Operator runbook |
| `alembic/versions/*_adr044_b2_reconciliation_schema.py` | — | ✓ | `identity_reconciliation_runs`, `_items` |
| `alembic/versions/*_adr044_b2_audit_event_types.py` | — | ✓ | Extend `chk_sal_event_type` (or combined migration) |

### 2.2. Modified artifacts

| Path | Change | Phase |
|------|--------|-------|
| `app/services/security_audit_service.py` | Add `PERSON_IIN_RECONCILED`, optional `IDENTITY_RECONCILIATION_RUN` to `_ALLOWED_EVENT_TYPES` | B2 |
| `app/main.py` | Only if new router file (unlikely — extend personnel_admin) | B1 |
| `docs/adr/ADR-042-phase-b2-validation.sql` | Optional §16 R1a post-checks (or keep separate ADR-044 SQL) | B2 |

### 2.3. Read-only dependencies (reuse, do not fork logic)

| Path | Reuse |
|------|-------|
| `app/services/hr_effective_canonical_service.py` | `apply_overrides_to_payload`, `_load_active_overrides_for_scope_keys`, `_person_scope_key`, `resolve_effective_person`, `get_active_snapshot` via canonical service |
| `app/services/hr_canonical_snapshot_service.py` | `get_active_snapshot`, `compute_roster_match_key` (canonical key derivation) |
| `app/services/hr_import_roster_promotion_service.py` | `_insert_employee_identity` semantics (extract shared helper recommended) |
| `app/db/engine.py` | Connection / transactions |
| `app/security/personnel_admin_guard.py` | API auth (`require_personnel_admin_api`) |

### 2.4. Explicitly NOT touched in B1/B2

| Area | Reason |
|------|--------|
| `hr_person_assignment_sync_service.py` | C2 unchanged; benefits from R1a data |
| `hr_effective_monthly_diff_service.py` | C1 unchanged |
| `persons.match_key` writers | R1b deferred |
| `users.employee_id` | R2 deferred |
| `corpsite-ui` | B4 Identity health panel — out of B1/B2 scope |
| Enrollment / lifecycle orchestrator | No business rule changes |

---

## 3. Change impact matrix

| Change | Migration? | Runtime impact | Backward compatible? | Production risk |
|--------|:----------:|----------------|----------------------|-----------------|
| **B1: identity_reconciliation_service (read-only dry-run API)** | No | None until invoked | ✓ | **None** |
| **B1: Admin API dry-run endpoints** | No | Sysadmin-only; no hot path | ✓ | **Low** |
| **B2: DDL reconciliation tables** | **Yes** | None on existing queries | ✓ (additive) | **Low** |
| **B2: security_audit event type CHECK extend** | **Yes** | None until audit write | ✓ | **Low** |
| **B2: R1a execute (UPDATE persons.iin)** | No | **Write batch**; pauses not required if per-person TX | ✓ schema | **Medium** (data) |
| **B2: INSERT employee_identities** | No | **Write batch**; respects `uq_employee_identities_iin_active` | ✓ | **Medium** |
| **B2: CLI script** | No | Manual ops invocation | ✓ | **Medium** (operator) |
| **Extract shared `_insert_employee_identity`** | No | Refactor only if done | ✓ | **Low** |
| **Validation SQL file** | No | Manual psql | ✓ | **None** |

### 3.1. Migration scope (B2 only)

Single Alembic revision (or two chained) creating:

```text
identity_reconciliation_runs
identity_reconciliation_items
+ indexes + FK to users/persons
+ chk_sal_event_type extension (PERSON_IIN_RECONCILED, optional run events)
```

**No changes** to `persons`, `employee_identities`, `employees` DDL.

### 3.2. Runtime / hot path

R1a execute is **offline batch** — not on request path for tasks, auth, HR import, lifecycle API (except explicit admin trigger).  
Deploy B1 (dry-run only) to production **before** R1a execute is safe.

### 3.3. Backward compatibility

| Concern | Assessment |
|---------|------------|
| API clients | New endpoints only; no breaking changes |
| Existing persons rows | Only NULL `iin` updated |
| C2 sync | **Improved** (IIN fallback) |
| match_key | **Unchanged** — required invariant |
| Rollback | CSV + reconciliation journal |

---

## 4. Local execution checklist

**Environment:** Docker PG (`corpsite-pg`) or local `DATABASE_URL`, pilot DB snapshot.

### Phase A — Pre-dev baseline

- [ ] `git status` clean; branch for ADR-044 B1/B2 created
- [ ] `alembic current` = `y7z8a9b0c1d2` (or documented head)
- [ ] Active canonical snapshot exists: `SELECT snapshot_id, status FROM hr_canonical_snapshots WHERE status = 'active'`
- [ ] Record baseline metrics (blueprint §6): persons iin coverage, resolvable gap count
- [ ] Export pre-R1a CSV: `persons(person_id, iin, match_key)`, `employee_identities`

### Phase B — B1 implementation verification

- [ ] Unit tests: IIN normalize, precedence P1→P5, conflict classes
- [ ] `scan_r1a_candidates(dry_run=True)` returns report without writes
- [ ] API dry-run: `POST /admin/personnel/identity/reconciliation/r1a/preview` (or equivalent)
- [ ] Verify Әбітаев (person_id=115): classified `APPLY`, IIN `800115300290`, match_key unchanged in preview
- [ ] G1–G4 blocking queries return expected counts on pilot DB

### Phase C — B2 migration (local)

- [ ] `alembic upgrade head` — reconciliation tables created
- [ ] `security_audit_log` accepts `PERSON_IIN_RECONCILED` in test insert
- [ ] Rollback migration tested on throwaway DB: `alembic downgrade -1`

### Phase D — B2 execute (local pilot DB only)

- [ ] **Dry-run** CLI/API — HR review exception list
- [ ] Pause lifecycle execute (recommended)
- [ ] **Execute** R1a on local pilot DB
- [ ] Post-validate: `docs/adr/ADR-044-phase-r1a-validation.sql` — empty violations
- [ ] V1e: zero match_key drift vs pre-export
- [ ] Idempotent re-run → 0 writes
- [ ] C2 smoke: `_find_person('emp:26', iin='800115300290')` resolves person 115
- [ ] `pytest tests/test_adr044_phase_r1a_* tests/test_adr043_phase_c2_* -q`

### Phase E — Rollback drill (local)

- [ ] Restore `persons.iin` from CSV for sample person
- [ ] DELETE inserted `employee_identities` by audit identity_id list
- [ ] Confirm state matches pre-R1a export

---

## 5. Deployment checklist

### 5.1. Prerequisites

| # | Gate | Owner |
|---|------|-------|
| 1 | B1/B2 merged; local pytest green | Dev |
| 2 | Pre-implementation review approved (this doc) | Tech lead |
| 3 | ADR-043 RC1 already on target env | Ops |
| 4 | VPS DB backup < 24h | Ops |
| 5 | HR sign-off on dry-run report | HR |
| 6 | Maintenance note: R1a execute window | HR + Ops |

### 5.2. Deploy sequence (code + schema only)

```text
1. git push → VPS git pull
2. alembic upgrade head          (B2 DDL + audit event types)
3. Backend restart
4. Deploy B1 API available — dry-run only first
5. NO R1a execute on VPS until local execute validated
```

**Frontend:** no deploy required for B1/B2 (API/CLI only).

### 5.3. VPS R1a execute sequence (after local proof)

| Step | Action |
|------|--------|
| 1 | `pg_dump -Fc` pre-R1a backup |
| 2 | Export pre-R1a CSV to `/var/backups/corpsite/` |
| 3 | Run dry-run on VPS; compare with local report |
| 4 | HR sign-off on VPS dry-run |
| 5 | Pause lifecycle execute |
| 6 | Execute R1a (CLI or admin API) |
| 7 | Run `ADR-044-phase-r1a-validation.sql` |
| 8 | Record metrics in `identity_reconciliation_runs` |
| 9 | **June Pilot Phase 5** unblocked |

### 5.4. Rollback triggers

| Condition | Action |
|-----------|--------|
| V1b duplicate IIN > 0 | Stop; L1 CSV restore |
| V1e match_key drift > 0 | **Critical** — L1 restore + code fix |
| Unexpected write count >> dry-run | Stop batch; investigate |
| EI global unique violation | Stop; merge queue |

### 5.5. Post-deploy monitoring

- [ ] `identity_reconciliation_runs.status = completed`
- [ ] M1 coverage ≥ target (blueprint §6)
- [ ] ADR-042 B2 validation §5 still empty
- [ ] No new errors in lifecycle execute smoke
- [ ] Limitation register updated (R1b/R2 still pending)

---

## 6. Implementation decisions (frozen for B1/B2)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | P1 lookup uses `PERSON:{canonical_person_key}` | ADR-043 parity |
| D2 | Explicit P1 before P2 when cache stale possible | Override wins over stale effective |
| D3 | Reuse `hr_effective_canonical_service` helpers | No duplicated override logic |
| D4 | Per-person transaction on execute | Partial success + safe rollback |
| D5 | CLI + Admin API both exposed | Ops script + UI later |
| D6 | No UI in B1/B2 | Minimize scope |
| D7 | No `persons.match_key` write | R1a invariant |
| D8 | Legacy `PERSON:name:` overrides not auto-migrated | R1b scope |

---

## 7. Gate to start coding

| Criterion | Status |
|-----------|--------|
| Source precedence verified | ✓ |
| Module list complete | ✓ |
| Impact matrix reviewed | ✓ |
| Local checklist ready | ✓ |
| Deployment checklist ready | ✓ |
| No open architectural questions | ✓ |

**Recommendation:** **Proceed with ADR-044 B1 implementation** (dry-run service + tests), then **B2** (migration + execute + CLI).

---

## Appendix — Canonical person_key resolution for R1a

```text
INPUT: person_id

1. SELECT employees WHERE person_id = :id AND operational_status IN (draft, active, suspended)
2. IF employee_id found:
     canonical_person_key = 'emp:' || employee_id
     Load roster entry on active snapshot WHERE match_key = canonical_person_key
3. ELIF persons.match_key matches roster entry on active snapshot:
     canonical_person_key = persons.match_key
4. ELSE:
     Try iin:/name: from persons.match_key for P3 lookup only
5. P1 scope_key = 'PERSON:' || canonical_person_key
```

Case **Әбітаев**: employee_id=26 → canonical_person_key=`emp:26` → P1 scope `PERSON:emp:26` → P2 effective row `match_key=emp:26`.
