# ARCH-001 — Permission Template Model Investigation

## Status

**Draft — architecture investigation (supporting Accepted ADR-053)** — 2026-07-04

Investigation supporting **ADR-053** (Permission Template Binding Model). No implementation changes. Derived from production shadow observations (Phase 2.5b/2.5c), Accepted ADR-050/ADR-051, and Phase 2.1–2.4 engineering state.

| Field | Value |
|-------|-------|
| Trigger | Shadow mismatch: `legacy_codes=['HR_ENROLLMENT_MANAGER']`, `cabinet_codes=[]` for user_id=17; all 34 `permission_template` rows have `role_id IS NULL` |
| Output | [ADR-053 — Permission Template Binding Model](../adr/ADR-053-permission-template-binding-model.md) (**Accepted**) |
| Related | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md), [access-rbac assessment](./ARCH-001-access-rbac-assessment.md) §12 |

---

## 1. Executive summary

**Permission Template** is architecturally defined (ADR-050 I8, ADR-051 §5.2) as a named permission bundle **inside** Position Cabinet. **How** the bundle is stored, bound, and expanded into comparable permission codes was **deferred** to implementation — and the first engineering pass (Phase 2.1) introduced a **partial, transitional** model that is insufficient for shadow parity with legacy ADR-042 access resolution.

| Finding | Severity |
|---------|----------|
| Two parallel permission **namespaces** (`public.roles` vs `public.access_roles`) with no crosswalk | **Critical** for shadow/enforcement parity |
| Phase 2.2 backfill created templates with **empty binding** (`role_id IS NULL`) | **Expected** gap; blocks cabinet resolver output |
| Cabinet resolver emits `roles.code`; legacy resolver emits `access_roles.code` | **Systematic shadow mismatch** even after binding |
| Guards and `/auth/me` enrichment consume **`access_roles.code`** | Binding model must align with enforcement vocabulary |
| ADR-050/051 define **evaluation**, not **storage** | **ADR-053 required** before Phase 2.6 coding |

**Recommendation:** Adopt **ADR-053** as the binding contract. Phase 2.6 implements transitional binding via `access_role_id` on `permission_template`, position-level backfill, and read-path resolver alignment — **shadow only**, no enforcement cutover.

---

## 2. Problem statement

### 2.1. Architectural intent

From ARCH-001 §3.5–3.6 and ADR-051 §5:

```text
Person → Employment → Position Cabinet → Permission Template → Permissions → Effective Set
```

Baseline permissions must originate from **Cabinet Template**, not from Platform User attributes. Exception overlays (`access_grants`) may extend the set but must not replace Cabinet baseline (ADR-051 R17).

### 2.2. Production evidence (Phase 2.5c)

| Observation | Implication |
|-------------|-------------|
| Structural chain resolves: employee → mapping → cabinet → template row | Phase 2.1–2.2 schema/backfill is structurally sound |
| All 34 templates: `role_id IS NULL` | Phase 2.2 intentionally deferred binding; expansion returns empty |
| user_id=17: legacy `HR_ENROLLMENT_MANAGER`, cabinet `[]` | Shadow correctly reports mismatch; not a resolver bug |
| `HR_ENROLLMENT_MANAGER` ∈ `access_roles`, ∉ `public.roles` | Namespace split is the root cause beyond NULL binding |

### 2.3. Engineering vs architecture gap

Phase 2.1 migration (`k5l6m7n8o9p0`) defined:

```text
permission_template.role_id → public.roles(role_id)
```

Phase 2.3 resolver expands `role_id` → single `roles.code` permission. This was a reasonable **first guess** (ADR-050 analog: “codes analogous to `public.roles.code`”) but conflicts with:

1. **Enforcement vocabulary** — guards use `access_roles.code` (`HR_ENROLLMENT_MANAGER`, `SYSADMIN_CABINET`).
2. **ARCH-001 examples** — template codes include `HR_ENROLLMENT_MANAGER` (access namespace).
3. **Legacy effective access** — ROLE-targeted grants bridge `users.role_id` → `access_roles`, not `roles.code` as permission identity.

---

## 3. Current permission namespaces (as-is)

### 3.1. Namespace map

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  public.roles                                                           │
│  Purpose: task routing, directory job identity, users.role_id           │
│  Codes: DEP_ADMIN, QM_HOSP, HR_HEAD, ECON_3, …                          │
│  ADR class: Transitional → Template definition catalog (ADR-051 §10 P5)   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ FK (Phase 2.1)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  permission_template.role_id  (currently NULL on all production rows)     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  public.access_roles                                                    │
│  Purpose: named access levels (ADR-042 overlay catalog)                 │
│  Codes: HR_ENROLLMENT_MANAGER, SYSADMIN_CABINET, ACCESS_ADMIN, …        │
│  ADR class: Transitional → exception layer only (ARCH-001 §12)          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ FK
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  public.access_grants                                                   │
│  target_type: USER | ROLE | EMPLOYEE | PERSON | …                       │
│  Production: HR_ENROLLMENT_MANAGER → ROLE:13 (DEP_ADMIN)                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ resolve_effective_access()
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Legacy effective permission codes (enforcement + shadow legacy side)     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2. Orthogonality (ADR-042 Phase A)

Task RBAC (`roles`) and Access Registry (`access_roles` / `access_grants`) answer **different questions**:

| Dimension | Task RBAC | Access Registry |
|-----------|-----------|-----------------|
| Question | Who sees/executes a task? | Who sees a module / admin action? |
| Primary table | `roles` | `access_roles` |
| Scope model | initiator, executor_role, dept | module, resource, org subtree |

**No crosswalk table exists.** ROLE-targeted grants (`target_type='ROLE'`) are the **only** structured bridge: they attach an **access role** to a **task role id**, not to a Position Cabinet.

### 3.3. Permission Template table (Phase 2.1)

| Column | Semantics today |
|--------|-----------------|
| `permission_template_id` | Surrogate PK |
| `position_cabinet_id` | UNIQUE — 1:1 with Cabinet |
| `role_id` | NULLable FK → `public.roles` — **only binding column** |
| `is_active` | Template active flag |

**Missing relative to architecture:** access-role binding, template code string, atomic permission rows, expansion policy reference.

---

## 4. Evaluation paths compared

### 4.1. Legacy path (authoritative today)

```text
Platform User
  → access_resolver_service.resolve_effective_access(user_id)
  → subjects: USER, ROLE(users.role_id), EMPLOYEE, PERSON, …
  → access_grants ⋈ access_roles
  → effective_role_code + matched_grants[].access_role_code
  → list_active_access_role_codes() → guards, /auth/me
```

**Permission identity:** `access_roles.code`.

### 4.2. Cabinet path (read-only / shadow today)

```text
Employee staffing (org_unit_id, catalog_position_id)
  → legacy_position_mapping → org_unique_position → position_cabinet
  → permission_template
  → JOIN roles ON role_id
  → _expand_effective_permissions() → [{ permission_code: roles.code }]
```

**Permission identity:** `roles.code` (single code per template).

**Non-goals preserved:** no `access_grants` fallback; no `users.role_id` input.

### 4.3. Shadow comparison

`cabinet_access_shadow_service.compare_legacy_and_cabinet_access()` compares **set equality** of:

| Side | Code source |
|------|-------------|
| Legacy | `effective_role_code` + `matched_grants[].access_role_code` |
| Cabinet | `effective_permissions[].permission_code` |

**Mismatch classes observed:**

| Class | Example |
|-------|---------|
| Empty cabinet | `legacy={HR_ENROLLMENT_MANAGER}`, `cabinet={}` — NULL `role_id` |
| Namespace mismatch | `legacy={HR_ENROLLMENT_MANAGER}`, `cabinet={DEP_ADMIN}` — even if `role_id=13` bound |
| Match (rare) | Only when codes coincidentally share same string in both tables |

---

## 5. Target Permission Template model (investigation conclusions)

### 5.1. Layered model

Permission Template is **not** a single FK — it is a **configuration record** with three conceptual layers:

| Layer | Question | Phase |
|-------|----------|-------|
| **L1 — Binding** | Which catalog entry defines this Cabinet's baseline bundle? | **Phase 2.6 (ADR-053 transitional)** |
| **L2 — Expansion** | How does binding become atomic Permissions? | Phase 4+ (policy table / role_permissions) |
| **L3 — Union** | How do multiple Cabinets combine? | **ADR-051** (defined: set union) |

ADR-053 covers **L1** and transitional **L2** (single-code emission for shadow). Full atomic expansion remains future work.

### 5.2. Binding options evaluated

| Option | Description | Pros | Cons | Verdict |
|--------|-------------|------|------|---------|
| **A. `role_id` only** | Current Phase 2.1 | Already deployed | Wrong namespace for enforcement; HR codes absent | **Insufficient** |
| **B. `access_role_id` only** | FK → `access_roles` | Matches guards and legacy codes; ARCH-001 examples | Task routing metadata separate | **Recommended transitional primary** |
| **C. `template_code` TEXT** | Standalone code string | Flexible | Duplicate catalog; validation harder | Defer to target state |
| **D. Crosswalk table** | `roles ↔ access_roles` mapping | No schema change on template | Indirect; position-specific templates awkward | Supplement only |
| **E. Duplicate codes in `roles`** | Insert `HR_ENROLLMENT_MANAGER` into `roles` | Reuses existing FK | Pollutes task namespace; conflates orthogonal catalogs | **Reject** |
| **F. Atomic permission rows** | `permission_template_permissions` | ADR-051 §5.2 target | Large scope; no seed data | **Target state**, not Phase 2.6 |

### 5.3. Recommended transitional binding (ADR-053)

```text
permission_template
  ├── position_cabinet_id  (1:1, ADR-050 I8)
  ├── access_role_id       (nullable FK → access_roles)  ← primary for shadow/enforcement parity
  ├── role_id              (nullable FK → roles)          ← optional task-routing metadata; secondary
  └── is_active
```

**Precedence for permission code emission:**

1. If `access_role_id` set → emit `access_roles.code`.
2. Else if `role_id` set → emit `roles.code` (legacy engineering compat).
3. Else → empty expansion; shadow reports `cabinet_unresolved` / mismatch.

**Invariant:** Template binding is **Cabinet-scoped**, derived from **Position identity**, never copied from Platform User grants.

### 5.4. Relationship to `access_grants`

| Mechanism | Classification | Phase 2.6 |
|-----------|----------------|-----------|
| Cabinet Template binding | **Baseline** (target) | Populate via position rules |
| ROLE-targeted grants | **Transitional bridge** | **Retain unchanged** |
| USER-targeted grants | **Exception / break-glass** | Retain |
| Shadow comparison | Diagnostics | Compare baseline template codes vs legacy grant codes |

**End state (ADR-051 §10 Phase 5):** grants narrow to exceptions; Template on Cabinet is sole baseline. Phase 2.6 does **not** remove grants.

### 5.5. Expansion model (transitional vs target)

| Stage | Expansion rule |
|-------|----------------|
| **Transitional (Phase 2.6)** | One `permission_code` per template = bound catalog code |
| **Target (future ADR)** | Template → N atomic Permissions (module, action, visibility, routing) per ADR-051 §5.2 step 2 |

`access_role_permissions` (deferred in ADR-042 B1) may become the expansion source for access-role-bound templates.

---

## 6. Backfill derivation principles (position-level)

Binding must **not** be copied from `users.role_id` or user-specific grants.

| Priority | Rule |
|----------|------|
| 1 | **Position staffing pattern** — map `(org_unit_id, catalog_position_id)` to intended `access_role_id` via ops-approved catalog |
| 2 | **ROLE-grant inventory (informative only)** — active `access_grants` with `target_type='ROLE'` may **inform** ops contour rules by showing which task-role contours receive which access roles at User resolution time. This inventory must **not** copy grant `target_id` / `access_role_id` pairs onto Templates; binding remains derived from **position identity** per [ADR-053 §3.4](../adr/ADR-053-permission-template-binding-model.md#34-binding-population-rules-backfill) |
| 3 | **Explicit exception list** — manual mapping for ambiguous pairs; document in ops runbook |

Validation: every binding references an **active** `access_roles` row; NULL binding allowed only for explicitly documented unmapped cabinets.

---

## 7. Gap analysis vs Accepted ADRs

| ADR | What it defines | Gap |
|-----|-----------------|-----|
| **ADR-050** | Template **location** inside Cabinet; 1:1; not on User/Person | **No storage/binding columns** |
| **ADR-051** | Load Template; expand; union; shadow migration Phase 2 | **“Platform policy” for expansion undefined**; defers schema |
| **ADR-042** | `access_roles` / `access_grants` overlay | Orthogonal; ROLE grants are transitional bridge |
| **ARCH-001 §3.5** | Template examples include access-role codes | Implies unified permission **vocabulary**, not `roles`-only FK |

**Conclusion:** Accepted ADRs **authorize** Phase 2.6 as shadow-policy-debt work (ADR-051 §10 Phase 2) but **do not specify** physical binding. **ADR-053 closes the specification gap** without amending ADR-050 entity contracts or ADR-051 evaluation semantics.

---

## 8. ADR-051 amendment vs new ADR-053

| Approach | Assessment |
|----------|------------|
| **Amend ADR-051** | ADR-051 scope is resolver **evaluation** and migration **phases**; binding storage is ADR-050 **configuration** concern. Amendment would blur Appendix A boundary. |
| **New ADR-053** | Clean separation: ADR-050 = where; ADR-053 = what is stored; ADR-051 = how evaluated. **Recommended.** |
| **ADR-050 amendment** | Not required — I8 (“Template inside Cabinet”) unchanged; ADR-053 adds engineering contract under same invariant. |

ADR-051 receives a **cross-reference only** (Related documents + Appendix C pointer), not a semantic change.

---

## 9. Phase alignment

| Phase | Binding work | Enforcement |
|-------|--------------|-------------|
| 2.1–2.2 | Schema + empty templates | None |
| 2.3–2.4 | Read resolver + shadow | Legacy only |
| **2.6** | **ADR-053 binding + backfill + resolver emission** | **Legacy only; shadow parity** |
| 3 | Employment FK retarget | Legacy only |
| 4–5 | Atomic expansion; subsystem shadow | Legacy authoritative |
| 6+ | Cutover per subsystem | Cabinet baseline |

---

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Silent drift: binding copied from User grants | ADR-053 invariant + validation SQL |
| Premature grant removal | Explicit non-goal; grants untouched in Phase 2.6 |
| Namespace regression after cutover | Transitional precedence rules documented; target ADR for atomic permissions |
| Incorrect position→role mapping | Idempotent backfill; ops exception list; shadow monitoring |
| Dual FK confusion | Document precedence; tests for each path |

---

## 11. Open questions resolved by this investigation

| Question | Resolution |
|----------|------------|
| Should Template bind via `role_id` or `access_role_id`? | **Primary: `access_role_id`** for parity; `role_id` optional metadata |
| Is crosswalk table required? | **No** for Phase 2.6; optional supplement |
| Can Phase 2.6 proceed without new ADR? | **Not safely** — engineering appendix insufficient for governance traceability |
| Does shadow require matching namespaces? | **Yes** — compare `access_roles.code` on both sides in transitional period |
| Is empty `role_id` after backfill valid? | **No** for shadow parity; NULL binding is **unmapped**, not “default deny template” |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial investigation — Phase 2.6 / ADR-053 input |
| 2026-07-04 | 0.2 | §6 priority 2 aligned with ADR-053 §3.4 — grant inventory informative only |
| 2026-07-04 | 0.3 | ADR-053 ratified Accepted — investigation output reference updated |
