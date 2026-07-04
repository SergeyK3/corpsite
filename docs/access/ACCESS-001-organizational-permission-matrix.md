# ACCESS-001 — Organizational Permission Matrix

## Status

**Reviewed** — 2026-07-04

Organizational policy document. Defines **organizational permission domains**, **HR operational permission classes**, and which Position Cabinets may receive approved baseline `access_roles` bindings via `permission_template_contour_rule`. **No runtime effect by itself** — enforcement remains on legacy `access_grants` until ADR-051 cutover phases. **Approved** status is required before OPS-030 / Phase 2.6b execution. **Reviewed** does not unblock [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) or Phase 2.6b.

| Field | Value |
|-------|-------|
| Depends on | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (**Accepted**) — Cabinet ownership |
| Depends on | [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Accepted**) — resolver evaluation |
| Depends on | [ADR-053](../adr/ADR-053-permission-template-binding-model.md) (**Accepted**) — binding model |
| Related | [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) (**Reviewed**) — management responsibilities (orthogonal) |
| Enables | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) — Phase 2.6b execution (gated on **Approved**) |
| Related | [ADR-042 DEP_ADMIN role grants](../adr/ADR-042-dep-admin-role-grants.md), [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) |
| Governance | Architecture acceptance complete — no architectural blockers; stakeholder review toward **Approved** |

---

## 1. Scope

This document covers:

- **Organizational permission policy** — which `(client_scope_id, org_unit_id, catalog_position_id)` contours may bind to which `access_roles.code` on the Cabinet Permission Template baseline, and under which **permission domain / class** (§5).
- **Source for OPS-030** — only rows marked `policy_status=approved` in this matrix may be inserted into `permission_template_contour_rule`.
- **Governance input for ADR-053 AC3** — satisfies the ops mapping annex requirement when status reaches **Approved**.

This document does **not**:

- Change application code, schema, migrations, or runtime authorization.
- Define **management responsibilities**, management hierarchy, subtree governance, or derived management authorities — that is [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) (**Reviewed**).
- Insert contour rules or update `permission_template` directly.
- Replace `access_grants` as the current enforcement authority (Phase 2.6a / legacy path).

---

## 2. Organizational policy layers (governance stack)

Explanatory only — **no runtime effect**.

```text
Position Cabinet (contour)
        │
        ▼
┌───────────────────────────────────────┐
│  ACCESS-002 (Reviewed)                 │
│  Management Responsibilities          │
└─────────────────┬─────────────────────┘
                  ▼
┌───────────────────────────────────────┐
│  Derived Management Authorities       │
│  (implementation-derived; not         │
│   normative in ACCESS-001)            │
└─────────────────┬─────────────────────┘
                  ▼
┌───────────────────────────────────────┐
│  ACCESS-001 (this document)           │
│  Organizational Permission Domains    │
│  + HR operational permission classes  │
└─────────────────┬─────────────────────┘
                  ▼
        Approved access_roles
        (baseline Cabinet Template binding)
                  ▼
        Future Runtime Enforcement
        (ADR-051 / ADR-053 cutover — separate program)
```

**Governance rule:** ratify **management responsibilities** in ACCESS-002 and **permission domains / classes** in ACCESS-001 independently. Neither layer substitutes for the other.

---

## 3. Relationship to ACCESS-002

[ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) (**Reviewed**) and ACCESS-001 are **orthogonal** policy layers on the same Position Cabinet contour.

| Layer | Owner | Governs |
|-------|-------|---------|
| **ACCESS-002** | Management governance | Management **responsibilities**; management **hierarchy**; **subtree** scope; **derived management authorities** |
| **ACCESS-001** | Organizational permissions | **Organizational permission domains**; **HR operational permission classes**; approved **`access_roles`** baseline binding policy |

**ACCESS-002 owns:**

- Management responsibilities (personnel, tasks, execution, results, organizational information, delegation).
- Management hierarchy and reporting vertical.
- Subtree management principle.
- Derived management authority capability groups.

**ACCESS-001 owns:**

- Organizational permission domains — primarily HR-related operational permissions (§5).
- Which contours may receive approved `access_roles.code` on Cabinet Permission Template baseline.
- Separation of кадровое решение / оформление / контроль / informational permission boundaries.

**Explicit rules:**

- Approving an `access_roles` binding in ACCESS-001 **does not** approve any ACCESS-002 management responsibility, and vice versa.
- ACCESS-001 **does not** establish management authority, management hierarchy, or subtree governance.
- ACCESS-002 **does not** define or approve `access_roles` baseline bindings.

**Visibility boundary:**

| Concept | Policy owner | Runtime (transitional) |
|---------|--------------|------------------------|
| **Management visibility** (personnel oversight, subtree scope) | **ACCESS-002** — responsibility for personnel (§3.1) → derived visibility | Future consumer; ADR-042 E1 as-is until cutover |
| **HR oversight visibility** (see кадровые процессы for control) | **ACCESS-001** — §5.3 permission domain | ADR-045 / access baseline when approved |
| **HR informational visibility** (line staff process outcomes) | **ACCESS-001** — §5.4 permission domain boundary only | Does not assign management remit; see ACCESS-002 for line-head management scope |

Neither document redefines the other.

---

## 4. Principles

| # | Principle |
|---|-----------|
| P1 | **Permission is assigned to Position Cabinet**, not Platform User, Person, or Employment occupant. |
| P2 | **Current occupants and individual grants are not source of truth** for baseline binding. `users.role_id`, user-specific `access_grants`, and shadow mismatch evidence may inform review but must not be copied onto Templates (ADR-053 §3.4). |
| P3 | **`access_grants` remain exception overlay** during Phase 2.6 and until subsystem cutover (ADR-053 §3.5). Template baseline + grants union at future enforcement only. |
| P4 | **No `SYSADMIN_CABINET` from organizational position alone.** System administration is break-glass / explicit sysadmin policy, not an automatic attribute of executive titles. |
| P5 | **Director (`Директор`) / Acting Director does not automatically mean system admin** and **does not receive `HR_ENROLLMENT_MANAGER` merely by title.** Executive read scope (ADR-045) is separate from sysadmin API, from HR processing, and from ACCESS-002 management responsibilities. |
| P6 | **`HR_ENROLLMENT_MANAGER` means кадровое оформление** (HR department processing / enrollment execution), **not кадровое решение** (executive approval of hire, transfer, dismiss, acting appointment). |
| P7 | **Director / Acting Director requires a separate кадровое решение permission class** if executive approval authority is modeled on Cabinet baseline. That class is **not** defined in this Draft; do not substitute `HR_ENROLLMENT_MANAGER` or `SYSADMIN_CABINET`. |
| P8 | **Deputy administrative / legal oversight is not HR processing.** Roles such as «Зам по адм вопросам» may belong to **кадровый контроль / наблюдение** (§5.3) — an **HR oversight visibility permission domain**, not enrollment execution. **Management visibility** over personnel/subtree is governed by ACCESS-002, not §5.3. |
| P9 | **Line department heads are not HR processing.** Clinical, laboratory, and other line heads must not receive `HR_ENROLLMENT_MANAGER` as Cabinet baseline. §5.4 **линейное информирование** defines an **informational permission domain boundary only** — it does **not** assign line-management responsibility; management visibility scope is **ACCESS-002** exclusively. |
| P10 | **Unmapped Cabinet is allowed** until explicitly approved in this matrix. NULL template binding is data debt, not implicit deny, during shadow phase (ADR-053 I7). |
| P11 | **Engineering must not infer organizational policy.** Candidate matrices and resolver mechanics do not substitute for ops/architecture approval of this document. |
| P12 | **ACCESS-001 and ACCESS-002 are orthogonal.** Baseline permission approval does not approve management responsibilities; ACCESS-002 Reviewed status does not approve `access_roles` bindings. |

---

## 5. Organizational permission domains (HR operational classes)

Owner policy (2026-07-04): organizational **permission domains** — primarily **HR-related operational permissions** — are **separated by function**. A Position Cabinet baseline must map to the **correct domain / class** before any `access_roles.code` is approved. Current `access_roles` catalog is transitional (ADR-053); not every domain has a dedicated code yet — gaps are recorded here as policy debt, not engineering assignments.

This section defines **organizational permission policy only**. It does **not** define general management authority, management hierarchy, or subtree governance ([ACCESS-002](./ACCESS-002-organizational-management-authority-model.md)).

### 5.1. Кадровое решение

| Aspect | Policy |
|--------|--------|
| **Typical holders** | Director / Acting Director (`Директор` / исполняющий обязанности) |
| **Meaning** | Right and duty to **approve** кадровые решения: hire, transfer, dismiss, appoint acting duties |
| **Not the same as** | HR document preparation, enrollment execution, sysadmin API, management visibility (ACCESS-002), or line informational permission domain (§5.4) |
| **ACCESS-001 stance (Draft)** | Requires a **separate decision/approval permission class** on Cabinet baseline. **Not modeled** in this Draft. **`HR_ENROLLMENT_MANAGER` must not represent this class.** |

### 5.2. Кадровое оформление

| Aspect | Policy |
|--------|--------|
| **Typical holders** | HR department / кадровая служба (`Отдел кадров`) |
| **Meaning** | Prepares documents, performs enrollment, executes кадровые процессы (ADR-045 «Кадровые процессы» contour) |
| **Transitional code (candidate only)** | `HR_ENROLLMENT_MANAGER` — **if and only if** approved for a specific HR-service Cabinet contour |
| **ACCESS-001 stance (Draft)** | HR head contour `(73, 86)` is **pending** class confirmation; likely this class, not approved yet |

### 5.3. Кадровый контроль / наблюдение (HR oversight visibility)

| Aspect | Policy |
|--------|--------|
| **Domain** | **HR oversight visibility** — organizational **permission domain** (ACCESS-001). **Not** management visibility (ACCESS-002). |
| **Typical holders** | Deputy for administrative affairs, legal service, other authorized oversight roles |
| **Meaning** | May **see** кадровые процессы for HR control/compliance within approved HR operational scope; **does not execute** HR processing |
| **Not the same as** | `HR_ENROLLMENT_MANAGER` unless explicit organizational delegation is approved; **not** ACCESS-002 personnel/subtree management visibility |
| **ACCESS-001 stance (Draft)** | Deputy admin contour `(78, 77)` is **pending** class confirmation; **likely this class**, not `HR_ENROLLMENT_MANAGER`, unless delegation is explicitly approved. Management responsibilities for deputy admin (personnel oversight, organizational information) are governed by **ACCESS-002**, not this permission domain |
| **Runtime (transitional)** | ADR-045 / access baseline when approved — not policy owner |

### 5.4. Линейное информирование (informational permission domain)

| Aspect | Policy |
|--------|--------|
| **Domain** | **HR informational permission domain** — defines what baseline **`access_roles` binding must not grant** to line heads. **Does not** assign line-management responsibility or management authority. |
| **Typical holders** | Heads of clinical, laboratory, and other line departments (for permission-boundary purposes only) |
| **Meaning** | Organizational permission boundary: line heads may need **information** on results of relevant кадровые процессы for their own staff — expressed as a **permission domain**, not as management remit |
| **Not the same as** | HR processing (`HR_ENROLLMENT_MANAGER`), executive decision authority (§5.1), or ACCESS-002 management responsibilities |
| **Management visibility scope** | Governed **exclusively** by [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) — **responsibility for personnel** (§3.1) and related management responsibilities (§3.7 line-head proposal). ACCESS-001 does **not** establish management authority |
| **ACCESS-001 stance (Draft)** | Line head contours remain **rejected** for `HR_ENROLLMENT_MANAGER`. No approved `access_roles` baseline for §5.4 in this Draft — informational domain is a **negative boundary** (what not to bind), not an approved code assignment |
| **Runtime (transitional)** | [ADR-042 Phase E1](../adr/ADR-042-phase-e1-visibility-scope.md) visibility assignments — **runtime mechanism only**; organizational policy owner for management visibility is **ACCESS-002** |

### 5.5. Mapping to Phase 2.6 contour rules

Only after a contour’s **permission domain / class** is agreed and a matching `access_roles.code` (or future atomic permission set) is approved may the row move to `policy_status=approved`. **Class clarification precedes OPS-030 insert.**

---

## 6. Approval workflow

```text
Draft → Reviewed → Approved
```

| Stage | Who | Outcome |
|-------|-----|---------|
| **Draft** | Architecture + HR/Ops authors | Matrix populated; all rows `pending` or `rejected`; no production inserts |
| **Reviewed** | Architecture review + HR/Ops stakeholders | Rationale validated; rows may move to `approved` or remain `pending`/`rejected` |
| **Approved** | Designated approvers (ops lead + architecture) | Document status → **Approved**; approved rows become OPS-030 insert list |

**Execution rule:** [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) may insert into `permission_template_contour_rule` **only** rows with `policy_status=approved` in §7 at **Approved** document status, and only after the row’s **permission domain / class** (§5) is ratified.

Until this document is **Approved**, Phase 2.6b remains blocked regardless of engineering readiness (Phase 2.6a deployed).

---

## 7. Organizational permission matrix (initial inventory)

**Inventory basis:** active org-unique position contours from HR import / Phase 2.2 backfill (35 rows: 34 operational + 1 test). **Verify IDs on production (VPS) before OPS-030 execution.**

**Column `proposed_access_role_code`:** intended baseline if approved; `—` means no baseline proposed (remain unmapped).

| client_scope_id | org_unit_id | org_unit_name | catalog_position_id | position_name | proposed_access_role_code | policy_status | rationale | notes |
|-----------------|-------------|---------------|---------------------|---------------|---------------------------|---------------|-----------|-------|
| 1 | 42 | Хирургия 1 | 74 | Заведующий хирургическим отделением 1 | — | rejected | Line dept head — §5.4 domain boundary only; not HR processing | Reject `HR_ENROLLMENT_MANAGER`; management scope → ACCESS-002 |
| 1 | 43 | Хирургия 2 | 75 | Заведующий хирургическим отделением 2 | — | rejected | Line dept head — §5.4 domain boundary | Same as row above |
| 1 | 44 | Гинекология | 64 | Заведующий гинекологическим отделением | — | rejected | Line dept head — §5.4 domain boundary | Shadow coords (44,64) must not drive grant-copy binding |
| 1 | 45 | Химиотерапия 1 | 71 | Заведующий отделением химиотерапии 1 | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 46 | Химиотерапия 2 | 72 | Заведующий отделением химиотерапии 2 | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 47 | Опухоли головы | 68 | Заведующий отделением опухолей головы и шеи | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 48 | Паллиатив | 73 | Заведующий паллиативным отделением | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 49 | Радиология | 69 | Заведующий отделением радиологии | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 50 | Инсультный | 66 | Заведующий инсультным отделением | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 53 | Реабилитация | 70 | Заведующий отделением реабилитации | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 54 | ЦАХ | 67 | Заведующий отделением амбулаторной хирургии | — | rejected | Line dept head — §5.4 domain boundary | |
| 1 | 55 | Диспансер | 9 | Дворник | — | rejected | Non-admin operational title; no access baseline | |
| 1 | 55 | Диспансер | 65 | Заведующий диспансерным отделением | — | rejected | Line dept head — §5.4 domain boundary | ADR-045 read scope ≠ HR processing |
| 1 | 56 | Приемное | 88 | Руководитель приемного отделения | — | rejected | Operational manager; no approved access_registry baseline | |
| 1 | 62 | Аптека | 63 | Заведующий аптекой | — | rejected | No organizational access baseline defined | |
| 1 | 68 | Отдел статистики | 1 | Архивариус | — | pending | Shared catalog placeholder (`position_id=1`); ambiguous across units | Await positions sync / staffing clarification |
| 1 | 68 | Отдел статистики | 61 | Аналитик ЭРОБ | — | pending | Task-role namespace (`STAT_EROB_ANALYTICS`); no `access_roles` equivalent | |
| 1 | 68 | Отдел статистики | 81 | зам рук-ля отдела статистики | — | pending | Task-role namespace only | |
| 1 | 68 | Отдел статистики | 87 | Руководитель отдела статистики | — | pending | Task-role namespace only | |
| 1 | 72 | Отдел менеджмента и качества | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 72 | Отдел менеджмента и качества | 85 | Руководитель ОВЭиПД | — | pending | QM task contour; no matching `access_roles.code` | Separate QM policy decision if ever needed |
| 1 | 73 | Отдел кадров | 86 | Руководитель отдела кадров | HR_ENROLLMENT_MANAGER | pending | Class TBD — **likely кадровое оформление** (§5.2); transitional code candidate only | Do not approve until class + code mapping ratified; not кадровое решение |
| 1 | 75 | Бухгалтерия | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 75 | Бухгалтерия | 8 | Главный бухгалтер | — | pending | Finance role; no access baseline policy | |
| 1 | 76 | Экономический | 84 | Руководитель | — | pending | Generic title; `ECON_*` task roles only | |
| 1 | 76 | Экономический | 90 | экономист1 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 91 | экономист2 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 92 | экономист3 | — | pending | Task-only contour | |
| 1 | 77 | Отдел госзакупок | 84 | Руководитель | — | pending | No organizational access baseline defined | |
| 1 | 78 | Администрация | 62 | Директор | SYSADMIN_CABINET | rejected | P4/P5/P7: Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` | Reject `SYSADMIN_CABINET`; requires separate **кадровое решение** permission class (§5.1) — not defined in Draft |
| 1 | 78 | Администрация | 77 | Зам по адм вопросам | — | pending | Class TBD — **likely кадровый контроль / наблюдение** (§5.3), not HR processing by default | §5.3 HR oversight domain; management remit → ACCESS-002; ADR-042 ROLE grant is not position policy |
| 1 | 78 | Администрация | 78 | Зам по диспансеру и внутр экспертизе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 79 | Зам по лечебной работе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 80 | Зам по стратегии | — | pending | Deputy role; no baseline policy | |
| 1 | 230 | e1_pos_unit | 217 | E1 Test Position | — | rejected | Engineering / test contour | Exclude from production bind |

### 7.1. Matrix summary (initial)

| policy_status | Row count |
|---------------|-----------|
| **approved** | 0 |
| **pending** | 18 |
| **rejected** | 17 |
| **Total** | 35 |

No row is **approved** at **Reviewed** status. HR head `(73, 86)` and deputy admin `(78, 77)` remain **pending** pending **permission domain / class** clarification (§5). No OPS-030 inserts until document reaches **Approved**, classes are ratified, codes agreed, and row approvals complete.

---

## 8. Relationship to ADR-053 and OPS-030

```text
ADR-053          ACCESS-001              OPS-030                    Database
(binding         (organizational         (execution                 (permission_template_
 model)           policy)                 runbook)                   contour_rule)
    │                 │                       │                            │
    │  defines HOW    │  defines WHICH        │  inserts ONLY              │
    │  binding works  │  contours MAY bind    │  approved rows             │
    └─────────────────┴───────────────────────┴────────────────────────────┘
```

| Document | Role |
|----------|------|
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | **Binding model** — `access_role_id` on Template, contour rule table, backfill rules, shadow vocabulary |
| **ACCESS-001** (this document) | **Organizational permission policy** — permission domains / classes (§5) and approved contour → `access_role_code` matrix (§7) |
| [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | **Execution** — insert approved rows, rerun backfill, validation SQL, shadow observation |

ADR-053 AC3 requires an ops mapping annex **before production data backfill**. ACCESS-001 is that annex once status is **Approved**. ACCESS-002 **Reviewed** does not affect Phase 2.6b blockers.

---

## 9. Explicit execution rule (OPS-030)

> **OPS-030 may insert into `permission_template_contour_rule` only rows that appear in §7 with `policy_status=approved`, and only when this document status is Approved.**

Inserts derived from engineering candidate matrices, shadow logs, `users.role_id`, or individual `access_grants` are **forbidden**.

---

## 10. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Draft — organizational permission matrix; 35 contours; 0 approved |
| 2026-07-04 | 0.2 | §3 permission classes (кадровое решение / оформление / контроль / линейное информирование); principles P5–P11; matrix notes updated; 0 approved |
| 2026-07-04 | 0.3 | Aligned with Reviewed ACCESS-002 — §2 governance stack; §3 relationship; §5 permission domains; HR vs management visibility boundary; section renumbering |
| 2026-07-04 | — | **Reviewed** — final architecture acceptance completed; no architectural blockers identified; advanced Draft → Reviewed; no runtime effect |
