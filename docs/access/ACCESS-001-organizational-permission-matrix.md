# ACCESS-001 — Organizational Permission Matrix

## Status

**Draft** — 2026-07-04

Organizational policy document. Defines which Position Cabinets may receive baseline `access_roles` bindings via `permission_template_contour_rule`. **No runtime effect by itself** — enforcement remains on legacy `access_grants` until ADR-051 cutover phases.

| Field | Value |
|-------|-------|
| Depends on | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (**Accepted**) — Cabinet ownership |
| Depends on | [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Accepted**) — resolver evaluation |
| Depends on | [ADR-053](../adr/ADR-053-permission-template-binding-model.md) (**Accepted**) — binding model |
| Enables | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) — Phase 2.6b execution |
| Related | [ADR-042 DEP_ADMIN role grants](../adr/ADR-042-dep-admin-role-grants.md), [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) |

---

## 1. Scope

This document covers:

- **Organizational permission policy** — which `(client_scope_id, org_unit_id, catalog_position_id)` contours may bind to which `access_roles.code` on the Cabinet Permission Template baseline, and under which **permission class** (§3).
- **Source for OPS-030** — only rows marked `policy_status=approved` in this matrix may be inserted into `permission_template_contour_rule`.
- **Governance input for ADR-053 AC3** — satisfies the ops mapping annex requirement when status reaches **Approved**.

This document does **not**:

- Change application code, schema, migrations, or runtime authorization.
- Insert contour rules or update `permission_template` directly.
- Replace `access_grants` as the current enforcement authority (Phase 2.6a / legacy path).

---

## 2. Principles

| # | Principle |
|---|-----------|
| P1 | **Permission is assigned to Position Cabinet**, not Platform User, Person, or Employment occupant. |
| P2 | **Current occupants and individual grants are not source of truth** for baseline binding. `users.role_id`, user-specific `access_grants`, and shadow mismatch evidence may inform review but must not be copied onto Templates (ADR-053 §3.4). |
| P3 | **`access_grants` remain exception overlay** during Phase 2.6 and until subsystem cutover (ADR-053 §3.5). Template baseline + grants union at future enforcement only. |
| P4 | **No `SYSADMIN_CABINET` from organizational position alone.** System administration is break-glass / explicit sysadmin policy, not an automatic attribute of executive titles. |
| P5 | **Director (`Директор`) / Acting Director does not automatically mean system admin** and **does not receive `HR_ENROLLMENT_MANAGER` merely by title.** Executive read visibility (ADR-045) is separate from sysadmin API and from HR processing. |
| P6 | **`HR_ENROLLMENT_MANAGER` means кадровое оформление** (HR department processing / enrollment execution), **not кадровое решение** (executive approval of hire, transfer, dismiss, acting appointment). |
| P7 | **Director / Acting Director requires a separate кадровое решение permission class** if executive approval authority is modeled on Cabinet baseline. That class is **not** defined in this Draft; do not substitute `HR_ENROLLMENT_MANAGER` or `SYSADMIN_CABINET`. |
| P8 | **Deputy administrative / legal oversight is not HR processing.** Roles such as «Зам по адм вопросам» may belong to **кадровый контроль / наблюдение** — visibility over processes, not enrollment execution — unless explicitly delegated otherwise. |
| P9 | **Line department heads are not HR processing.** Clinical, laboratory, and other line heads may receive **линейное информирование** (informational visibility on outcomes for their staff only). That is separate from `HR_ENROLLMENT_MANAGER` and must not be bound as HR operational baseline. |
| P10 | **Unmapped Cabinet is allowed** until explicitly approved in this matrix. NULL template binding is data debt, not implicit deny, during shadow phase (ADR-053 I7). |
| P11 | **Engineering must not infer organizational policy.** Candidate matrices and resolver mechanics do not substitute for ops/architecture approval of this document. |

---

## 3. Классы кадровых и управленческих полномочий

Owner policy (2026-07-04): кадровые полномочия are **separated by function**. A Position Cabinet baseline must map to the **correct class** before any `access_roles.code` is approved. Current `access_roles` catalog is transitional (ADR-053); not every class has a dedicated code yet — gaps are recorded here as policy debt, not engineering assignments.

### 3.1. Кадровое решение

| Aspect | Policy |
|--------|--------|
| **Typical holders** | Director / Acting Director (`Директор` / исполняющий обязанности) |
| **Meaning** | Right and duty to **approve** кадровые решения: hire, transfer, dismiss, appoint acting duties |
| **Not the same as** | HR document preparation, enrollment execution, sysadmin API, or line informational visibility |
| **ACCESS-001 stance (Draft)** | Requires a **separate decision/approval permission class** on Cabinet baseline. **Not modeled** in this Draft. **`HR_ENROLLMENT_MANAGER` must not represent this class.** |

### 3.2. Кадровое оформление

| Aspect | Policy |
|--------|--------|
| **Typical holders** | HR department / кадровая служба (`Отдел кадров`) |
| **Meaning** | Prepares documents, performs enrollment, executes кадровые процессы (ADR-045 «Кадровые процессы» contour) |
| **Transitional code (candidate only)** | `HR_ENROLLMENT_MANAGER` — **if and only if** approved for a specific HR-service Cabinet contour |
| **ACCESS-001 stance (Draft)** | HR head contour `(73, 86)` is **pending** class confirmation; likely this class, not approved yet |

### 3.3. Кадровый контроль / наблюдение

| Aspect | Policy |
|--------|--------|
| **Typical holders** | Deputy for administrative affairs, legal service, other authorized oversight roles |
| **Meaning** | May **see** кадровые процессы for control/compliance; **does not execute** HR processing |
| **Not the same as** | `HR_ENROLLMENT_MANAGER` unless explicit organizational delegation is approved |
| **ACCESS-001 stance (Draft)** | Deputy admin contour `(78, 77)` is **pending** class confirmation; **likely this class**, not `HR_ENROLLMENT_MANAGER`, unless delegation is explicitly approved |

### 3.4. Линейное информирование

| Aspect | Policy |
|--------|--------|
| **Typical holders** | Heads of clinical, laboratory, and other line departments |
| **Meaning** | May see **results** of relevant кадровые процессы for **their own staff only** (department-scoped informational visibility) |
| **Not the same as** | HR processing (`HR_ENROLLMENT_MANAGER`) or executive decision authority |
| **ACCESS-001 stance (Draft)** | Line head contours remain **rejected** for `HR_ENROLLMENT_MANAGER`. Informational visibility is a **separate** policy/model (e.g. ADR-042 visibility assignments), not Cabinet HR-processing baseline |

### 3.5. Mapping to Phase 2.6 contour rules

Only after a contour’s **permission class** is agreed and a matching `access_roles.code` (or future atomic permission set) is approved may the row move to `policy_status=approved`. **Class clarification precedes OPS-030 insert.**

---

## 4. Approval workflow

```text
Draft → Reviewed → Approved
```

| Stage | Who | Outcome |
|-------|-----|---------|
| **Draft** | Architecture + HR/Ops authors | Matrix populated; all rows `pending` or `rejected`; no production inserts |
| **Reviewed** | Architecture review + HR/Ops stakeholders | Rationale validated; rows may move to `approved` or remain `pending`/`rejected` |
| **Approved** | Designated approvers (ops lead + architecture) | Document status → **Approved**; approved rows become OPS-030 insert list |

**Execution rule:** [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) may insert into `permission_template_contour_rule` **only** rows with `policy_status=approved` in §5 at **Approved** document status, and only after the row’s **permission class** (§3) is ratified.

Until this document is **Approved**, Phase 2.6b remains blocked regardless of engineering readiness (Phase 2.6a deployed).

---

## 5. Organizational permission matrix (initial inventory)

**Inventory basis:** active org-unique position contours from HR import / Phase 2.2 backfill (35 rows: 34 operational + 1 test). **Verify IDs on production (VPS) before OPS-030 execution.**

**Column `proposed_access_role_code`:** intended baseline if approved; `—` means no baseline proposed (remain unmapped).

| client_scope_id | org_unit_id | org_unit_name | catalog_position_id | position_name | proposed_access_role_code | policy_status | rationale | notes |
|-----------------|-------------|---------------|---------------------|---------------|---------------------------|---------------|-----------|-------|
| 1 | 42 | Хирургия 1 | 74 | Заведующий хирургическим отделением 1 | — | rejected | Line dept head — class: **линейное информирование** (if any), not HR processing | Reject `HR_ENROLLMENT_MANAGER`; informational visibility is separate and dept-scoped |
| 1 | 43 | Хирургия 2 | 75 | Заведующий хирургическим отделением 2 | — | rejected | Line dept head — **линейное информирование** | Same as row above |
| 1 | 44 | Гинекология | 64 | Заведующий гинекологическим отделением | — | rejected | Line dept head — **линейное информирование** | Shadow coords (44,64) must not drive grant-copy binding |
| 1 | 45 | Химиотерапия 1 | 71 | Заведующий отделением химиотерапии 1 | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 46 | Химиотерапия 2 | 72 | Заведующий отделением химиотерапии 2 | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 47 | Опухоли головы | 68 | Заведующий отделением опухолей головы и шеи | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 48 | Паллиатив | 73 | Заведующий паллиативным отделением | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 49 | Радиология | 69 | Заведующий отделением радиологии | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 50 | Инсультный | 66 | Заведующий инсультным отделением | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 53 | Реабилитация | 70 | Заведующий отделением реабилитации | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 54 | ЦАХ | 67 | Заведующий отделением амбулаторной хирургии | — | rejected | Line dept head — **линейное информирование** | |
| 1 | 55 | Диспансер | 9 | Дворник | — | rejected | Non-admin operational title; no access baseline | |
| 1 | 55 | Диспансер | 65 | Заведующий диспансерным отделением | — | rejected | Line dept head — **линейное информирование** | ADR-045 read scope ≠ HR processing |
| 1 | 56 | Приемное | 88 | Руководитель приемного отделения | — | rejected | Operational manager; no approved access_registry baseline | |
| 1 | 62 | Аптека | 63 | Заведующий аптекой | — | rejected | No organizational access baseline defined | |
| 1 | 68 | Отдел статистики | 1 | Архивариус | — | pending | Shared catalog placeholder (`position_id=1`); ambiguous across units | Await positions sync / staffing clarification |
| 1 | 68 | Отдел статистики | 61 | Аналитик ЭРОБ | — | pending | Task-role namespace (`STAT_EROB_ANALYTICS`); no `access_roles` equivalent | |
| 1 | 68 | Отдел статистики | 81 | зам рук-ля отдела статистики | — | pending | Task-role namespace only | |
| 1 | 68 | Отдел статистики | 87 | Руководитель отдела статистики | — | pending | Task-role namespace only | |
| 1 | 72 | Отдел менеджмента и качества | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 72 | Отдел менеджмента и качества | 85 | Руководитель ОВЭиПД | — | pending | QM task contour; no matching `access_roles.code` | Separate QM policy decision if ever needed |
| 1 | 73 | Отдел кадров | 86 | Руководитель отдела кадров | HR_ENROLLMENT_MANAGER | pending | Class TBD — **likely кадровое оформление** (§3.2); transitional code candidate only | Do not approve until class + code mapping ratified; not кадровое решение |
| 1 | 75 | Бухгалтерия | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 75 | Бухгалтерия | 8 | Главный бухгалтер | — | pending | Finance role; no access baseline policy | |
| 1 | 76 | Экономический | 84 | Руководитель | — | pending | Generic title; `ECON_*` task roles only | |
| 1 | 76 | Экономический | 90 | экономист1 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 91 | экономист2 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 92 | экономист3 | — | pending | Task-only contour | |
| 1 | 77 | Отдел госзакупок | 84 | Руководитель | — | pending | No organizational access baseline defined | |
| 1 | 78 | Администрация | 62 | Директор | SYSADMIN_CABINET | rejected | P4/P5/P7: Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` | Reject `SYSADMIN_CABINET`; requires separate **кадровое решение** permission class (§3.1) — not defined in Draft |
| 1 | 78 | Администрация | 77 | Зам по адм вопросам | — | pending | Class TBD — **likely кадровый контроль / наблюдение** (§3.3), not HR processing by default | Do not bind `HR_ENROLLMENT_MANAGER` unless explicit delegation approved; ADR-042 ROLE grant is not position policy |
| 1 | 78 | Администрация | 78 | Зам по диспансеру и внутр экспертизе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 79 | Зам по лечебной работе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 80 | Зам по стратегии | — | pending | Deputy role; no baseline policy | |
| 1 | 230 | e1_pos_unit | 217 | E1 Test Position | — | rejected | Engineering / test contour | Exclude from production bind |

### 5.1. Matrix summary (initial)

| policy_status | Row count |
|---------------|-----------|
| **approved** | 0 |
| **pending** | 18 |
| **rejected** | 17 |
| **Total** | 35 |

No row is **approved** in Draft status. HR head `(73, 86)` and deputy admin `(78, 77)` remain **pending** pending **permission class** clarification (§3). No OPS-030 inserts until classes, codes, and row approvals are ratified.

---

## 6. Relationship to ADR-053 and OPS-030

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
| **ACCESS-001** (this document) | **Organizational policy** — permission classes (§3) and approved contour → `access_role_code` matrix (§5) |
| [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | **Execution** — insert approved rows, rerun backfill, validation SQL, shadow observation |

ADR-053 AC3 requires an ops mapping annex **before production data backfill**. ACCESS-001 is that annex once status is **Approved**.

---

## 7. Explicit execution rule (OPS-030)

> **OPS-030 may insert into `permission_template_contour_rule` only rows that appear in §5 with `policy_status=approved`, and only when this document status is Approved.**

Inserts derived from engineering candidate matrices, shadow logs, `users.role_id`, or individual `access_grants` are **forbidden**.

---

## 8. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Draft — organizational permission matrix; 35 contours; 0 approved |
| 2026-07-04 | 0.2 | §3 permission classes (кадровое решение / оформление / контроль / линейное информирование); principles P5–P11; matrix notes updated; 0 approved |
