# ADR-053 — Permission Template Binding Model

## Status

**Accepted** — 2026-07-04

Binding and transitional expansion contract for **Permission Template** configuration inside Position Cabinet. Closes the specification gap left by [ADR-050](./ADR-050-organization-position-cabinet-model.md) (location) and [ADR-051](./ADR-051-cabinet-access-resolution.md) (evaluation), without amending their core decisions.

| Field | Value |
|-------|-------|
| Depends on | [ADR-050](./ADR-050-organization-position-cabinet-model.md) (**Accepted**) — Template inside Cabinet, 1:1 |
| Depends on | [ADR-051](./ADR-051-cabinet-access-resolution.md) (**Accepted**) — Template load, expand, union |
| Enables | Phase 2.6 shadow parity; future atomic permission expansion; enforcement cutover preparation |
| Investigation | [ARCH-001 Permission Template Model Investigation](../architecture/ARCH-001-permission-template-model-investigation.md) |
| Related | [ADR-042 Phase B](./ADR-042-phase-b1-schema-design.md), [ADR-042 dep-admin grants](./ADR-042-dep-admin-role-grants.md), [access-rbac assessment](../architecture/ARCH-001-access-rbac-assessment.md) §12 |

### Explicitly out of scope

| Topic | Owner |
|-------|-------|
| Cabinet Access Resolver union semantics, vacancy, acting | **ADR-051** |
| Position / Cabinet lifecycle | **ADR-050** |
| Authentication, JWT, `/auth/me` shape | ADR-042 B5 |
| Enforcement cutover; route guard migration | ADR-051 §10 Phase 3+ |
| Atomic permission row storage (`access_role_permissions`, template permission tables) | Future ADR / Phase 4+ |
| Employment FK retarget | Phase 3 program |
| Removal or mutation of `access_grants` | ADR-051 §10 Phase 5 |

---

## 1. Problem Statement

[ADR-050](./ADR-050-organization-position-cabinet-model.md) defines **where** Permission Template lives (inside Position Cabinet, 1:1). [ADR-051](./ADR-051-cabinet-access-resolution.md) defines **how** loaded Templates are expanded and unioned into an Effective Permission Set. Neither ADR specifies:

1. **Which catalog** defines the Template's named permission bundle during migration.
2. **How** Template binding is populated for org-unique Positions created in Phase 2.2.
3. **Which permission code namespace** shadow comparison and future enforcement must use for parity with legacy ADR-042 resolution.

Phase 2.1 engineering introduced `permission_template.role_id → public.roles`. Production state (Phase 2.5c):

- All active templates have `role_id IS NULL`.
- Legacy path emits `access_roles.code` (e.g. `HR_ENROLLMENT_MANAGER`).
- Cabinet path emits nothing or would emit `roles.code` — a **different namespace**.
- Shadow mode correctly reports systematic mismatch; this is a **specification gap**, not a resolver defect.

Without a binding contract, Phase 2.6 implementation risks **silent architecture drift** (user-centric backfill, wrong catalog FK, or premature grant removal).

---

## 2. Context

### 2.1. Authoritative chain (unchanged)

```text
Platform User (auth) → Person → Employment → Position Cabinet → Permission Template → Permissions → Effective Set
```

Permission Template is **configuration on Cabinet**, never assigned to Platform User or Person (ADR-050 I8, ADR-051 R5).

### 2.2. Two transitional catalogs

| Catalog | Table | Typical codes | Current enforcement use |
|---------|-------|---------------|-------------------------|
| Task / directory role | `public.roles` | `DEP_ADMIN`, `QM_HOSP`, `ECON_3` | `users.role_id`, task routing |
| Access role | `public.access_roles` | `HR_ENROLLMENT_MANAGER`, `SYSADMIN_CABINET` | Guards, `access_grants`, `/auth/me` admin flags |

These catalogs are **orthogonal** (ADR-042 Phase A). ROLE-targeted `access_grants` bridge them at **User resolution time** — not at Cabinet configuration time. There is **no** crosswalk table.

### 2.3. Production shadow evidence

| Fact | Interpretation |
|------|----------------|
| 34 templates, all `role_id IS NULL` | Phase 2.2 deferred binding by design |
| user_id=17: legacy `HR_ENROLLMENT_MANAGER`, cabinet `[]` | Empty binding → empty expansion |
| `HR_ENROLLMENT_MANAGER` ∈ `access_roles` only | Task-role FK cannot represent this code without namespace pollution |

### 2.4. Boundary with ADR-051

| Concern | ADR-053 (this ADR) | ADR-051 |
|---------|-------------------|---------|
| Template storage / binding columns | **Defines** | Consumes |
| Expansion to permission codes (transitional) | **Defines** | Consumes |
| Union across Cabinets | — | **Defines** |
| Shadow vs enforcement authority | Defines parity **vocabulary** | Defines shadow **phase** timing |
| Exception grant overlay | References coexistence | **Defines** extend-not-replace (R17) |

---

## 3. Decision

Adopt a **transitional Permission Template binding model** with the following contracts:

### 3.1. Binding identity

1. Each Position Cabinet has **exactly one** Permission Template record (ADR-050 1:1 — unchanged).
2. Template binding expresses the Cabinet's **baseline named permission bundle** — not Platform User attributes.
3. **Primary transitional binding** is `access_role_id` → `public.access_roles(access_role_id)`.
4. **Secondary optional binding** `role_id` → `public.roles(role_id)` may coexist as **non-authoritative metadata** (e.g. task-routing documentation). When **both** `access_role_id` and `role_id` are populated, **`access_role_id` is authoritative** for permission code emission; `role_id` must **not** override or supplement emitted permission codes.
5. At least one of `access_role_id` or `role_id` should be populated before shadow parity is expected for a Cabinet; **both NULL** means **unmapped** (not implicit deny template — expansion returns empty set).

### 3.2. Transitional expansion rule

When Cabinet Access Resolver loads Template **T**:

| Condition | Emitted `permission_code` | Source label |
|-----------|---------------------------|--------------|
| `T.access_role_id` set and access role active | `access_roles.code` | `permission_template_access_role` |
| Else `T.role_id` set and role exists | `roles.code` | `permission_template_role` |
| Else | *(empty)* | — |

**Phase 2.6 scope:** one permission code per Template (single-element expansion). Full atomic Permission expansion (module, action, visibility, routing) is **deferred** to a future ADR implementing ADR-051 §5.2 step 2.

### 3.3. Shadow parity vocabulary

When `CABINET_ACCESS_SHADOW_MODE` is enabled (ADR-051 §10 Phase 2):

- **Legacy side** codes = `access_roles.code` from `resolve_effective_access()` (unchanged).
- **Cabinet side** codes = transitional expansion output per §3.2.
- **Match** requires set equality on these codes for the same user at evaluation time T.
- Namespace mismatch (`roles.code` vs `access_roles.code` for semantically equivalent access) is an **expected transitional mismatch class** until binding uses `access_role_id`.

Shadow outcome does **not** affect authorization.

### 3.4. Binding population rules (backfill)

Template binding is populated by **Position identity**, not by Platform User:

| Allowed | Forbidden |
|---------|-----------|
| Map `(org_unit_id, catalog_position_id)` → intended `access_role_id` | Copy binding from `users.role_id` |
| Derive from ops-approved staffing catalog / contour rules | Copy from user-specific `access_grants` |
| Explicit manual exception list for ambiguous pairs | Infer from current occupant's login |

Backfill migrations must be **idempotent** and **re-runnable** (same standard as ADR-050 Phase 2.2).

### 3.5. Coexistence with `access_grants`

1. **`access_grants` remain authoritative** for all enforcement during Phase 2.6 and until ADR-051 Phase 3 subsystem cutover.
2. Cabinet Template binding defines **baseline** permissions for future enforcement — not current runtime.
3. ROLE-targeted grants (e.g. `HR_ENROLLMENT_MANAGER` → `ROLE:13`) remain valid transitional bridges; Phase 2.6 **does not revoke or rewrite** them.
4. At enforcement cutover (future), effective set = **union(Template permissions, exception grants)** per ADR-051 R17 — grants **extend**, not replace, Cabinet baseline.

### 3.6. Target-state direction (informative)

Long term (ADR-051 §10 Phase 5):

- `public.roles` narrows to Template **definition catalog** or retires as User assignment target.
- `access_roles` narrows to **exception** vocabulary or merges into atomic permission policy — separate decision.
- Template may evolve to **atomic permission rows** without changing Cabinet ownership invariant.

This ADR does **not** mandate target catalog merge — only transitional binding sufficient for shadow parity.

### 3.7. Transitional vs ARCH-001 §12 end-state

Binding via `access_role_id` → `public.access_roles` is **Phase 2.6 transitional only**. It enables shadow parity with the current ADR-042 enforcement vocabulary and does **not** override [ARCH-001 §12](../architecture/ARCH-001-access-rbac-assessment.md) / [access-rbac assessment §12](../architecture/ARCH-001-access-rbac-assessment.md), where `access_roles` / `access_grants` narrow to an **exception overlay** in the target architecture.

| Phase | `access_roles` role relative to Template |
|-------|----------------------------------------|
| **Phase 2.6 (this ADR)** | Transitional binding catalog for Template permission identity and shadow comparison |
| **Target (ADR-051 §10 Phase 5+)** | Exception layer; Cabinet baseline from Template atomic permissions |

A **future ADR** is required before:

- atomic Permission expansion (module, action, visibility, routing) per ADR-051 §5.2 step 2, and
- final catalog merge or retirement of transitional FK binding columns.

Accepting ADR-053 does **not** pre-commit the end-state catalog design.

---

## 4. Invariants

| ID | Invariant |
|----|-----------|
| I1 | Permission Template belongs to **Position Cabinet**, not User/Person/Employment |
| I2 | **One** Template row per Cabinet (1:1) |
| I3 | Binding is **Cabinet-scoped** — stable across occupant changes (ADR-050 I13) |
| I4 | **No User attributes** in binding derivation rules |
| I5 | `access_role_id` references **active** access role when populated |
| I6 | Transitional expansion is **deterministic** — same Template → same codes |
| I7 | Empty binding → empty expansion; not an authorization deny signal in shadow mode |
| I8 | Phase 2.6 changes are **read-path / data only** — no enforcement flip |

---

## 5. Rules (R1–R12)

| ID | Rule |
|----|------|
| R1 | **Primary binding catalog** for permission identity during migration is `access_roles` |
| R2 | `role_id` on Template is **optional non-authoritative metadata** — must not be sole binding if shadow parity with access grants is required; never authoritative when `access_role_id` is also populated |
| R3 | **Precedence:** when both FKs are populated, `access_role_id` is **solely authoritative** for permission code emission; `role_id` is ignored for emission |
| R4 | Shadow compares **access-role vocabulary** on legacy side; cabinet side must emit same vocabulary when bound |
| R5 | **Unmapped template** (`both NULL`) is a data debt state — not a valid steady-state for production cabinets with active staffing |
| R6 | Backfill derives binding from **position-level** rules only |
| R7 | **No synthetic duplication** of `access_roles.code` into `public.roles` for FK convenience |
| R8 | Resolver must **not** read `access_grants` in cabinet baseline path (ADR-051 non-goal preserved) |
| R9 | Inactive Template (`is_active=false`) → empty expansion (ADR-051 missing/inactive handling) |
| R10 | Liquidated Position → Cabinet excluded before Template load (ADR-051 — unchanged) |
| R11 | Exception grants may produce **legacy codes not present** in Template — valid until cutover; shadow may report mismatch until baseline populated or grant retired |
| R12 | Engineering changes require **validation SQL** proving binding coverage before production backfill |

---

## 6. Expected implementation artifacts (Phase 2.6 — not this ADR's code)

| Artifact | Purpose |
|----------|---------|
| Additive migration: `permission_template.access_role_id` | Primary binding column |
| Idempotent backfill migration | Position-level binding population |
| `cabinet_access_resolver_service` update | §3.2 expansion precedence |
| `sql/validation/adr050_phase2_6_permission_template_binding_validation.sql` | Ops verification |
| Tests: resolver + shadow parity fixtures | Prevent regression |
| Ops runbook appendix | Exception mappings, rollback |

**No** changes to guards, `/auth/me`, JWT, frontend, or grant tables in Phase 2.6.

---

## 7. Migration strategy (architectural phases)

| Phase | Binding work | Enforcement authority |
|-------|--------------|----------------------|
| 2.1–2.2 | Template row exists; binding empty | Legacy |
| 2.3–2.4 | Read resolver; shadow hook | Legacy |
| **2.6** | **ADR-053 binding + backfill + emission alignment** | **Legacy** |
| 3 | Employment FK retarget | Legacy |
| 4–5 | Atomic expansion; subsystem shadow | Legacy per subsystem |
| 6+ | Cutover | Cabinet baseline + exception grants |

### 7.1. Rollback (Phase 2.6)

| Step | Action |
|------|--------|
| Code | Revert resolver to pre-2.6 emission rules |
| Data | Set `access_role_id = NULL` via downgrade migration |
| Schema | Drop column via Alembic downgrade |
| Auth impact | **None** — legacy path untouched |

---

## 8. Consequences

### Positive

- Closes ADR-050/051 specification gap with governance traceability.
- Enables meaningful shadow parity metrics before enforcement cutover.
- Preserves Cabinet-owned binding invariant — no User-centric drift.
- Aligns Template vocabulary with existing guards and ADR-042 access catalog.

### Negative / costs

- Dual FK period (`role_id` + `access_role_id`) adds complexity until `role_id` metadata is retired or repurposed.
- Position-level backfill requires ops rules — not fully derivable from schema alone.
- Transitional single-code expansion understates future atomic permission model — follow-on ADR needed.

### Neutral

- Does not change ADR-051 evaluation algorithm (union, vacancy, acting).
- Does not require ARCH-001 amendment — implements §3.5 intent.
- ADR-051 remains Accepted; cross-reference added only.

---

## 9. Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| `role_id` only (status quo) | Wrong namespace; cannot emit `HR_ENROLLMENT_MANAGER` |
| Duplicate access codes in `roles` | Pollutes task catalog; blurs orthogonality |
| Crosswalk table only, no `access_role_id` on template | Indirect; poor fit for position-specific templates |
| Bind from user's current grants | Violates Cabinet ownership; occupant-dependent |
| Amend ADR-051 in place | Blurs resolver vs storage boundary (Appendix A) |
| Skip ADR; implement directly | Silent drift risk; no governance anchor |

---

## 10. Relationship to ADR-051

[ADR-051 Appendix C — Permission Template binding (ADR-053)](./ADR-051-cabinet-access-resolution.md#appendix-c--permission-template-binding-adr-053) **already exists** and records the boundary between resolver mechanics (ADR-051) and Template binding semantics (this ADR). No amendment to ADR-051 §5.1–§5.3 or §10 is required when ADR-053 is Accepted.

| Concern | ADR-051 | ADR-053 |
|---------|---------|---------|
| Template location | ADR-050 | — |
| Template binding storage | Deferred → Appendix C | **Defined** |
| Template load + expand | **Defined** | Transitional expand rule |
| Shadow parity vocabulary | Phase 2 mentioned | **Defined** |

No change to ADR-051 §5.1 union semantics, §5.3 determinism target, or §10 migration phase ordering.

---

## 11. Acceptance criteria (ratified)

ADR-053 was **Accepted** on 2026-07-04 following architecture review (edits E1–E5 complete). Ratification status:

| # | Criterion | At acceptance |
|---|-----------|---------------|
| AC1 | [ADR-051 Appendix C](./ADR-051-cabinet-access-resolution.md#appendix-c--permission-template-binding-adr-053) boundary confirmed — resolver mechanics unchanged; binding semantics owned by ADR-053 | **Met** |
| AC2 | Phase 2.6 scope remains **read-path / shadow only** — no enforcement cutover, no guard, JWT, `/auth/me`, or frontend changes | **Met** (contract); implementation gated separately |
| AC3 | **Ops mapping annex or runbook reference** (position / staffing contour → `access_role_id`) published and approved **before Phase 2.6 production data backfill** | **Pending** — gate for backfill, not for ADR ratification |

Acceptance of ADR-053 authorizes the binding **contract** only. Phase 2.6 implementation and production backfill remain gated by AC2 (implementation discipline) and AC3 (ops mapping) plus engineering validation (R12).

---

## 12. Decision log

| Date | Decision |
|------|----------|
| 2026-07-04 | **Proposed ADR-053** — Permission Template binding model from Phase 2.5c shadow findings and ARCH-001 investigation |
| 2026-07-04 | **Primary binding:** `access_role_id` → `access_roles` for transitional permission identity |
| 2026-07-04 | **Secondary binding:** retain optional `role_id` for task metadata; precedence documented |
| 2026-07-04 | **Shadow vocabulary:** compare `access_roles.code` sets; Phase 2.6 read-path only |
| 2026-07-04 | **Backfill:** position-level derivation; explicit ban on User-grant copying |
| 2026-07-04 | **Grants untouched** in Phase 2.6 — baseline vs overlay separation preserved |
| 2026-07-04 | **Architecture review edits** — §3.7 transitional clause; §11 acceptance criteria; §10 Appendix C factual fix; dual-FK precedence clarified |
| 2026-07-04 | **Accepted ADR-053** — architecture review complete; binding contract ratified for Phase 2.6 |

---

## Appendix A — Transitional vs target binding

```text
TRANSITIONAL (Phase 2.6 — this ADR)
──────────────────────────────────
permission_template
  position_cabinet_id  → 1:1 Cabinet
  access_role_id     → access_roles.code  ──► permission_code (authoritative when set)
  role_id            → roles.code (optional metadata only; non-authoritative for emission)

TARGET (future — separate ADR)
──────────────────────────────
permission_template
  position_cabinet_id  → 1:1 Cabinet
  permission_rows[]    → atomic Permissions (module, action, visibility, routing)
  (catalog FKs retired or demoted to definition-only)
```

---

## Appendix B — Shadow mismatch taxonomy

| mismatch_type (diagnostic) | Cause | Phase 2.6 remedy |
|------------------------------|-------|------------------|
| `permission_template_unmapped` | Both binding FKs NULL | Backfill `access_role_id` |
| `permission_code_set_mismatch` | Bound code ≠ legacy grant codes | Correct binding or document exception grant |
| `namespace_mismatch` | `roles.code` emitted instead of `access_role.code` | Apply §3.2 precedence |
| `cabinet_unresolved` | Broken structural chain | Fix mapping/cabinet — not binding ADR |
| `match` | Sets equal | Steady state for shadow |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial proposed ADR — Permission Template binding model |
| 2026-07-04 | 0.2 | Architecture review edits (E1–E5): §3.7, §10–§12, dual-FK precedence |
| 2026-07-04 | 1.0 | Status Proposed → Accepted — architecture review ratification |
