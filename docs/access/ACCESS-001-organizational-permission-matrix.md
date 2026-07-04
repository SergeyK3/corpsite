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

- **Organizational permission policy** — which `(client_scope_id, org_unit_id, catalog_position_id)` contours may bind to which `access_roles.code` on the Cabinet Permission Template baseline.
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
| P5 | **Director (`Директор`) does not automatically mean system admin.** Executive read visibility (ADR-045) is separate from sysadmin API and Cabinet baseline. |
| P6 | **Clinical department heads do not automatically receive HR operational permissions** (`HR_ENROLLMENT_MANAGER`). Personnel admin is an HR operational contour, not a default for clinical leadership positions. |
| P7 | **Unmapped Cabinet is allowed** until explicitly approved in this matrix. NULL template binding is data debt, not implicit deny, during shadow phase (ADR-053 I7). |
| P8 | **Engineering must not infer organizational policy.** Candidate matrices and resolver mechanics do not substitute for ops/architecture approval of this document. |

---

## 3. Approval workflow

```text
Draft → Reviewed → Approved
```

| Stage | Who | Outcome |
|-------|-----|---------|
| **Draft** | Architecture + HR/Ops authors | Matrix populated; all rows `pending` or `rejected`; no production inserts |
| **Reviewed** | Architecture review + HR/Ops stakeholders | Rationale validated; rows may move to `approved` or remain `pending`/`rejected` |
| **Approved** | Designated approvers (ops lead + architecture) | Document status → **Approved**; approved rows become OPS-030 insert list |

**Execution rule:** [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) may insert into `permission_template_contour_rule` **only** rows with `policy_status=approved` in this document at **Approved** document status.

Until this document is **Approved**, Phase 2.6b remains blocked regardless of engineering readiness (Phase 2.6a deployed).

---

## 4. Organizational permission matrix (initial inventory)

**Inventory basis:** active org-unique position contours from HR import / Phase 2.2 backfill (35 rows: 34 operational + 1 test). **Verify IDs on production (VPS) before OPS-030 execution.**

**Column `proposed_access_role_code`:** intended baseline if approved; `—` means no baseline proposed (remain unmapped).

| client_scope_id | org_unit_id | org_unit_name | catalog_position_id | position_name | proposed_access_role_code | policy_status | rationale | notes |
|-----------------|-------------|---------------|---------------------|---------------|---------------------------|---------------|-----------|-------|
| 1 | 42 | Хирургия 1 | 74 | Заведующий хирургическим отделением 1 | — | rejected | Clinical dept head; task RBAC / visibility only; no HR operational baseline | Do not bind `HR_ENROLLMENT_MANAGER` by title alone |
| 1 | 43 | Хирургия 2 | 75 | Заведующий хирургическим отделением 2 | — | rejected | Clinical dept head | Same as row above |
| 1 | 44 | Гинекология | 64 | Заведующий гинекологическим отделением | — | rejected | Clinical dept head | Shadow coords (44,64) must not drive grant-copy binding |
| 1 | 45 | Химиотерапия 1 | 71 | Заведующий отделением химиотерапии 1 | — | rejected | Clinical dept head | |
| 1 | 46 | Химиотерапия 2 | 72 | Заведующий отделением химиотерапии 2 | — | rejected | Clinical dept head | |
| 1 | 47 | Опухоли головы | 68 | Заведующий отделением опухолей головы и шеи | — | rejected | Clinical dept head | |
| 1 | 48 | Паллиатив | 73 | Заведующий паллиативным отделением | — | rejected | Clinical dept head | |
| 1 | 49 | Радиология | 69 | Заведующий отделением радиологии | — | rejected | Clinical dept head | |
| 1 | 50 | Инсультный | 66 | Заведующий инсультным отделением | — | rejected | Clinical dept head | |
| 1 | 53 | Реабилитация | 70 | Заведующий отделением реабилитации | — | rejected | Clinical dept head | |
| 1 | 54 | ЦАХ | 67 | Заведующий отделением амбулаторной хирургии | — | rejected | Clinical dept head | |
| 1 | 55 | Диспансер | 9 | Дворник | — | rejected | Non-admin operational title; no access baseline | |
| 1 | 55 | Диспансер | 65 | Заведующий диспансерным отделением | — | rejected | Clinical / dept head; ADR-045 read scope ≠ personnel admin | |
| 1 | 56 | Приемное | 88 | Руководитель приемного отделения | — | rejected | Operational manager; no approved access_registry baseline | |
| 1 | 62 | Аптека | 63 | Заведующий аптекой | — | rejected | No organizational access baseline defined | |
| 1 | 68 | Отдел статистики | 1 | Архивариус | — | pending | Shared catalog placeholder (`position_id=1`); ambiguous across units | Await positions sync / staffing clarification |
| 1 | 68 | Отдел статистики | 61 | Аналитик ЭРОБ | — | pending | Task-role namespace (`STAT_EROB_ANALYTICS`); no `access_roles` equivalent | |
| 1 | 68 | Отдел статистики | 81 | зам рук-ля отдела статистики | — | pending | Task-role namespace only | |
| 1 | 68 | Отдел статистики | 87 | Руководитель отдела статистики | — | pending | Task-role namespace only | |
| 1 | 72 | Отдел менеджмента и качества | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 72 | Отдел менеджмента и качества | 85 | Руководитель ОВЭиПД | — | pending | QM task contour; no matching `access_roles.code` | Separate QM policy decision if ever needed |
| 1 | 73 | Отдел кадров | 86 | Руководитель отдела кадров | HR_ENROLLMENT_MANAGER | pending | HR operational contour by position title (ADR-045); candidate for initial 2.6b wave | Requires AC3 / matrix approval |
| 1 | 75 | Бухгалтерия | 1 | Архивариус | — | pending | Shared catalog placeholder | |
| 1 | 75 | Бухгалтерия | 8 | Главный бухгалтер | — | pending | Finance role; no access baseline policy | |
| 1 | 76 | Экономический | 84 | Руководитель | — | pending | Generic title; `ECON_*` task roles only | |
| 1 | 76 | Экономический | 90 | экономист1 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 91 | экономист2 | — | pending | Task-only contour | |
| 1 | 76 | Экономический | 92 | экономист3 | — | pending | Task-only contour | |
| 1 | 77 | Отдел госзакупок | 84 | Руководитель | — | pending | No organizational access baseline defined | |
| 1 | 78 | Администрация | 62 | Директор | SYSADMIN_CABINET | rejected | P4/P5: Director ≠ sysadmin; executive visibility ≠ `SYSADMIN_CABINET` | Explicit rejection of sysadmin-from-title |
| 1 | 78 | Администрация | 77 | Зам по адм вопросам | HR_ENROLLMENT_MANAGER | pending | DEP-admin staffing contour; ADR-042 intent as **position rule** (not ROLE-grant copy) | Candidate for initial 2.6b wave; AC3 review |
| 1 | 78 | Администрация | 78 | Зам по диспансеру и внутр экспертизе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 79 | Зам по лечебной работе | — | pending | Deputy clinical role; no baseline policy | |
| 1 | 78 | Администрация | 80 | Зам по стратегии | — | pending | Deputy role; no baseline policy | |
| 1 | 230 | e1_pos_unit | 217 | E1 Test Position | — | rejected | Engineering / test contour | Exclude from production bind |

### 4.1. Matrix summary (initial)

| policy_status | Row count |
|---------------|-----------|
| **approved** | 0 |
| **pending** | 18 |
| **rejected** | 17 |
| **Total** | 35 |

No row is **approved** in Draft status. Initial 2.6b candidates (`HR_ENROLLMENT_MANAGER` on rows 73/86 and 78/77) remain **pending** until this document completes Reviewed → Approved workflow.

---

## 5. Relationship to ADR-053 and OPS-030

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
| **ACCESS-001** (this document) | **Organizational policy** — approved contour → `access_role_code` matrix |
| [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | **Execution** — insert approved rows, rerun backfill, validation SQL, shadow observation |

ADR-053 AC3 requires an ops mapping annex **before production data backfill**. ACCESS-001 is that annex once status is **Approved**.

---

## 6. Explicit execution rule (OPS-030)

> **OPS-030 may insert into `permission_template_contour_rule` only rows that appear in §4 with `policy_status=approved`, and only when this document status is Approved.**

Inserts derived from engineering candidate matrices, shadow logs, `users.role_id`, or individual `access_grants` are **forbidden**.

---

## 7. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Draft — organizational permission matrix; 35 contours; 0 approved |
