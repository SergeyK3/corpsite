# OPS Backlog

Операционные и UX-задачи вне текущих ADR-фаз. Нумерация: `OPS-NNN`.

## Program status (2026-06-22)

| Area | Status |
|------|--------|
| **ADR-044** (Identity Reconciliation R1–R2.5g) | **Complete** — implementation phases closed; R3 post-R2 validation gate remains planned in ADR, not active OPS work |
| **Telegram bot (OPS-007 series)** | **Complete** through OPS-007b VPS validation |
| **Operations UI localization (OPS-008)** | **Complete** — R2.5g Identity Operations panel |
| **Regular tasks catch-up & run journal (OPS-009 program)** | **Complete** — through OPS-009.34 (monthly E2E verified on prod) |
| **Organizational Policy Layer (ACCESS-001 / ACCESS-002)** | **Architecture design complete** — both **Reviewed**; active phase: [Policy Ratification](../access/ACCESS-RATIFICATION-PROGRAM.md); runtime blocked until **Approved** |
| **Phase 2.6b / OPS-030** | **Blocked** — ACCESS-001 **Approved** + ADR-053 AC3; Phase 2.6a complete |

---

## Summary

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| [OPS-007](#ops-007--telegram-bot-operational-audit) | Telegram Bot Operational Audit | — | **Complete** |
| [OPS-007a](#ops-007a--internal-bot-api) | Internal Bot API | — | **Complete** |
| [OPS-007b](#ops-007b--vps-telegram-validation) | VPS Telegram Validation | — | **Complete** |
| [OPS-008](#ops-008--ui-localization-cleanup) | UI Localization Cleanup (R2.5g Operations) | — | **Complete** |
| [OPS-009](#ops-009--regular-tasks-catch-up--run-journal-program) | Regular Tasks — Catch-up & Run Journal Program | High | **Complete** |
| [OPS-010](#ops-010--telegram-user-acceptance-testing) | Telegram User Acceptance Testing | Medium | **Open** |
| [OPS-011](#ops-011--telegram-legacy-bindings-removal) | Telegram Legacy Bindings Removal | Low | **Deferred** |
| [OPS-012](#ops-012--test-suite-stabilization) | Test Suite Stabilization | Low | **Open** |
| [OPS-013](#ops-013--regular-task-run-journal-cleanup) | Regular Task Run Journal Cleanup | Low | **Backlog** |
| [OPS-015](#ops-015--long-task-title-rendering) | Long Task Title Rendering | Low | **Backlog** |
| [OPS-016](#ops-016--template-view-cleanup) | Template View Cleanup | Low | **Backlog** |
| [OPS-017](#ops-017--catch-up-backup-warning-ux) | Catch-up Backup Warning UX | Low | **Backlog** |
| [OPS-018](#ops-018--catch-up-historical-deadline-semantics) | Catch-up Historical Deadline Semantics | Medium | **Discussion** |
| [OPS-019](#ops-019--catch-up-filter-observability) | Catch-up Filter Observability | Low | **Backlog** |
| [OPS-021](#ops-021--catch-up-form-ux-periodicity-first-layout) | Catch-up Form UX — Periodicity-first | Medium | **Complete** |
| [OPS-026.5](#ops-0265--unified-system-health-dashboard) | Unified System Health Dashboard | Medium | **Backlog** |
| [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) | Policy Ratification Program (ACCESS-001 / ACCESS-002) | High | **Active (planning)** |
| [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | Organizational Permission Matrix (Phase 2.6b policy) | High | **Reviewed** |
| [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) | Organizational Management Authority Model (future scope policy) | Medium | **Reviewed** |
| [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | Permission Template Contour Binding (Phase 2.6b) | High | **Blocked (ACCESS-001 Approved + AC3)** |
| [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md) | Org-unit allowed positions (Future ADR) | Medium | **Proposed** |

---

## Completed

### OPS-007 — Telegram Bot Operational Audit

**Статус:** **Complete** (2026-06-21)

**Deliverables:**

- [OPS-007 audit report](../ops/OPS-007-telegram-bot-operational-audit.md)
- [Integrity SQL](../ops/OPS-007-telegram-integrity-audit.sql)
- `scripts/ops/ops007_telegram_integrity_counts.py`

Read-only architecture, DB, permission, and command inventory. Production integrity counts captured in OPS-007b.

---

### OPS-007a — Internal Bot API

**Статус:** **Complete** (2026-06-21)

**Scope:** Unify Telegram identity on `users.telegram_id`; internal bot API (`/internal/bot/*`) with `INTERNAL_API_TOKEN`.

**Key changes:**

- `app/tg_bot_internal_router.py`, `app/security/bot_internal_auth.py`
- Bot client migrated to internal paths (`corpsite_api.py`)
- `/unbind` clears DB; legacy JSON gated behind `TELEGRAM_LEGACY_JSON_BINDINGS`
- Tests: `tests/test_ops007a_telegram_bot_internal.py`

**Commits (reference):** `4741f9c`, hotfix `b2c50ee` (events_poller import)

---

### OPS-007b — VPS Telegram Validation

**Статус:** **Complete** — **PASS** (2026-06-21)

**Deliverables:**

- [OPS-007b validation report](../ops/OPS-007b-vps-telegram-validation.md)
- `scripts/ops/ops007b_vps_telegram_validation.py`

**Verified on VPS (mmc.004.kz):** backend + bot active; internal routes return 403 without token; legacy JSON disabled; integrity script passed; bot `API_BASE_URL=http://127.0.0.1:8000`.

---

### OPS-008 — UI Localization Cleanup

**Статус:** **Complete** (2026-06-21)

**Scope delivered:** ADR-044 R2.5g Identity Operations UI — full Russian presentation layer for user-facing labels, badges, filters, drawers, and tooltips. API enum values unchanged.

**Modules:**

| Module | Route | Status |
|--------|-------|--------|
| Identity Operations | `/admin/system/personnel-identity/operations` | Localized |
| Operations dashboard, runs/items history, repair preview, re-run execute | tabs in `UserLinkageOperationsClient` | Localized |
| Label layer | `userLinkageOperationsLabels.ts` | Russian display maps for operations, statuses, actions, diagnosis |

**Out of scope (unchanged, may be future OPS):** User Linkage Review tab, Personnel Lifecycle EN strings, Enrollment, Security Audit — see original OPS-008 draft scope in git history if needed.

**Commit (reference):** `f03b28f`

---

### OPS-009 — Regular Tasks Catch-up & Run Journal Program

**Приоритет:** High  
**Статус:** **Complete** (program closed 2026-06-25)

**Program scope:** Regular-task catch-up ACL, origin metadata, Safe Catch-Up UI, admin task visibility, run journal outcome observability, monthly template lifecycle, catch-up template filter, production investigations and fixes.

**Base deliverable (2026-06-21):** sysadmin run journal ACL + task origin metadata — commit `7a6f4ed`.

**ADR:** [ADR-020](../adr/ADR-020-regular-tasks-contract-v1.md) — metadata block section.

#### Sub-items

| Sub-ID | Title | Status | Deliverable |
|--------|-------|--------|-------------|
| OPS-009.14 | Run #39 factual report | **Complete** | `scripts/ops/ops_009_14_run39_facts.py` |
| OPS-009.15 | Executor role fix (tasks 10009/10010) | **Complete** | `scripts/ops/ops_009_15_*`, commits `3e531af`, `c5a0b65` |
| OPS-009.18c | Admin account unlock | **Complete** | `scripts/ops/ops_009_18c_*`, commit `388a8ae` |
| OPS-009.19 | Weekly period investigation | **Complete** | session 2026-06-22 (no standalone report file) |
| OPS-009.20 | Admin task visibility + Catch-Up UI RU | **Complete** | `dc9c6dd`, prod run #40/#41 |
| OPS-009.21 | Run journal outcome observability | **Complete** | `83a3621` |
| OPS-009.22 | Legacy task #10006 investigation | **Complete** | [OPS-009.22 investigation](../ops/OPS-009.22-task-10006-investigation.md) |
| OPS-009.30–009.32 | Monthly template E2E (create/edit/save/catch-up/tasks) | **Complete** | prod verification 2026-06-25 |
| OPS-009.33 | Catch-up template filter verification | **Complete** | Network trace + root-cause analysis |
| OPS-009.34 | Catch-up template filter runtime fix | **Complete** | router → filters → SQL; regression tests |

**Program outcome:** Safe Catch-Up verified on prod; ADMIN sees all tasks via `scope=team`; run journal shows task lifecycle outcome counts. Monthly workflow E2E on prod: Template → Preview → Live Run → Task Creation → Task View. Template filter (`regular_task_id`) confirmed: `templates_total=1`, single task created.

#### POST-OPS review (2026-06-25)

**Confirmed working on production:**

- Monthly templates: create, edit, save, catch-up preview/live, task creation.
- Template filter (OPS-009.34): selecting template #12 → `templates_total=1`, `templates_due=1`, one task created.
- Executor role selector: human-readable dropdown in production.
- Schedule type switching: weekly/monthly/yearly rebuilds `schedule_params` JSON correctly.

**No critical defects** in the monthly contour after OPS-009.34.

**Backlog candidates** from review → [OPS-015](#ops-015--long-task-title-rendering) … [OPS-019](#ops-019--catch-up-filter-observability).

---

## Open / deferred

### OPS-010 — Telegram User Acceptance Testing

**Приоритет:** Medium  
**Статус:** **Open**

**Goal:** Validate Telegram workflows with a real employee account.

**Scope:**

- `/start`, `/whoami`
- `/tasks`, `/events`, `/history`
- Notification delivery (delivery queue / events poller)
- Bind / unbind workflow (web bind code + bot `/bind`, admin `/unbind`)

**Success criteria:** Real employee successfully receives and interacts with task notifications end-to-end.

**Prerequisites:** OPS-007b PASS (met).

**Notes:** First operational validation with human user; complements read-only OPS-007b automation.

---

### OPS-011 — Telegram Legacy Bindings Removal

**Приоритет:** Low  
**Статус:** **Deferred**

**Goal:** Remove remaining optional JSON binding fallback (`bindings.json`, `bot_bindings.json` poller path).

**Current state:** `TELEGRAM_LEGACY_JSON_BINDINGS` disabled by default on VPS; `get_binding()` returns `None` unless flag set.

**Prerequisite:** Successful OPS-010 and production observation period.

**Out of scope until deferred → open:** deleting on-disk JSON files used for non-auth cursors/state.

---

### OPS-012 — Test Suite Stabilization

**Приоритет:** Low  
**Статус:** **Open**

**Goal:** Investigate and fix known pre-existing failing/flaky test(s).

**Known item:**

- `corpsite-ui/app/directory/personnel/_components/ImportNormalizedRecordDrawer.test.tsx` — duplicate `—` match (`getByText("—")` ambiguity)

**Notes:** Not related to ADR-044 or Telegram changes. Observed during OPS-008 `npm test` run (127/128 pass).

---

### OPS-013 — Regular Task Run Journal Cleanup

**Приоритет:** Low  
**Статус:** Backlog

**Goal:** Allow admin to archive/delete obsolete run records safely.

**Reason:** Run journal accumulates dry-runs and obsolete catch-up runs.

**Non-goal (current fix):** No destructive action in UI without backend archive/delete design.

---

### OPS-015 — Long Task Title Rendering

**Приоритет:** Low  
**Статус:** **Backlog**

**Problem:** Long task titles truncate in the task card header (e.g. «Подготовить Ежемесячный отчет по протоколам МДГ → Ам…»).

**Scope to analyze:**

- Drawer header
- Table rendering
- Mobile layout

**Options:** multi-line wrap, tooltip, adaptive title block.

**Non-urgent:** cosmetic UX; does not block monthly workflow.

---

### OPS-016 — Template View Cleanup

**Приоритет:** Low  
**Статус:** **Backlog**

**Problem:** In template **view** mode, executor role appears twice: numeric «ID роли исполнителя» block and separate «Исполнитель» label. Edit mode already uses human-readable role dropdown.

**Proposal:** Show human-readable role in view mode; keep `role_id` only in technical/service info if needed at all.

**Reference:** `TemplateViewPanel.tsx`, `RegularTasksAdminClient.tsx`.

---

### OPS-017 — Catch-up Backup Warning UX

**Приоритет:** Low  
**Статус:** **Backlog**

**Problem:** Catch-up confirm step shows: «Рекомендуется выполнить резервную копию БД… (на VPS: `scripts/backup_db.sh`)» — opaque for non-ops users.

**Options:**

- User-facing Russian copy without shell paths
- Move `scripts/backup_db.sh` to tooltip or admin-only hint
- Show warning only to System Administrator role

**Reference:** `CatchUpRunClient.tsx` confirm section.

---

### OPS-018 — Catch-up Historical Deadline Semantics

**Приоритет:** Medium  
**Статус:** **Discussion** (no code change until business rule agreed)

**Observed case (prod):**

| Field | Value |
|-------|-------|
| Reporting period | 01.04.2026–30.04.2026 |
| Task created | 25.06.2026 |
| Due date | 30.04.2026 |

**Current behavior:** catch-up preserves historical period deadline — logically correct for reporting period, but executor receives a newly created task already overdue.

**Options (pick one after stakeholder review):**

1. Keep historical deadline (status quo).
2. Store original deadline + actual creation date + catch-up flag.
3. Special display mode: «Создано догоняющим запуском».

**Explicit non-goal now:** do not change deadline logic without ADR/ops sign-off.

---

### OPS-019 — Catch-up Filter Observability

**Приоритет:** Low  
**Статус:** **Backlog**

**Origin:** OPS-009.34 — frontend sent `regular_task_id`, backend dropped it; diagnosis required Network + `resolved` inspection.

**Improvement:** Always surface applied catch-up filters in API response and run journal:

- `resolved.regular_task_id`
- `resolved.org_unit_id`
- `resolved.executor_role_id`
- `resolved.org_group_id`

**Goal:** Faster ops investigations without guessing which filters were applied at runtime.

**Reference:** `CatchUpReviewPanel`, run journal `stats.catch_up`, catch-up API `resolved` payload.

---

### OPS-021 — Catch-up Form UX: Periodicity-first layout

**Приоритет:** Medium  
**Статус:** **Complete** (2026-06-25)

**Delivered:** Periodicity-first form layout; dynamic period selector per schedule type (weekly/monthly/yearly); executor label «Исполнитель»; payload mapping via `preset` + `manual`/`run_for_date` without backend changes.

**Modules:** `CatchUpRunClient.tsx`, `catchUpPeriodOptions.ts`, `i18n.ts`.

---

### OPS-026.5 — Unified System Health Dashboard

**Приоритет:** Medium  
**Статус:** **Backlog**

**Summary:** После реализации отдельных operational panels (Scheduler Status, Telegram Status) возникла необходимость объединить состояние основных подсистем в единую страницу здоровья системы.

**Goal:** Создать единый Dashboard состояния системы, позволяющий системному администратору за несколько секунд оценить состояние всех ключевых сервисов.

**Предварительный состав модулей:**

- Backend API
- Scheduler
- Telegram Bot
- Database
- Storage
- AI / OCR (по мере появления)
- Email notifications (если появятся)
- Google Drive / внешние интеграции
- Background workers / future services

**Для каждого модуля предусмотреть:**

- статус GREEN / YELLOW / RED;
- краткое описание причины;
- время последней успешной проверки;
- переход к детальной панели (например Telegram Status Panel).

**Принципы:**

- Использовать существующие backend health API.
- Не обращаться напрямую из frontend к systemd, journalctl, docker, SSH.
- Health Dashboard должен быть агрегатором, а не источником диагностики.

**Start gate:** Не начинать разработку сейчас. Начинать только после стабилизации следующих operational panels или появления не менее 3–4 health modules.

---

## ADR-046 — Org-unit allowed positions (Future)

**Status:** Proposed — not scheduled  
**Priority:** Medium  
**Reference:** [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md)

**Goal:** Разделить три семантики должностей:

- глобальный справочник (`public.positions`);
- должности, **разрешённые/типичные** для отделения (`org_unit_allowed_positions` — future);
- должности, **уже используемые** сотрудниками (`employees` + scoped `GET /positions?org_unit_id=`).

**Interim (Phase 3I):** Enrollment Wizard fallback на global catalog при пустом scoped-списке (`103be25`).

**Non-goals now:** миграция, изменение semantics `GET /positions?org_unit_id=`, admin UI для junction table.

---

## ADR-044 — backlog alignment

All ADR-044 **implementation** phases through **R2.5g** are **complete**. No ADR-044 build phases remain in active OPS backlog.

| Phase | Status |
|-------|--------|
| R1a–R1b | Complete |
| R2.1–R2.4 | Complete |
| R2.5a–R2.5g | Complete |
| R3 post-R2 validation gate | Planned (ADR track; not OPS-scheduled) |

Reference: [ADR-044 R2.5 Operations Architecture](../adr/ADR-044-r2.5-operations-architecture.md).

---

## Architecture milestones

### Position Cabinet — Organizational Policy Layer (2026-07-04)

**Milestone:** Position Cabinet architectural baseline complete; Organizational Policy Layer architecture review complete.

**Active governance phase:** [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) — Reviewed → Approved for ACCESS-001 and ACCESS-002.

| Document | Status | Role |
|----------|--------|------|
| [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) | **Active (planning)** | Ratification work packages, approval sequence, completion criteria |
| [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) | **Reviewed** | Management responsibilities; hierarchy; subtree; derived authorities |
| [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | **Reviewed** | Organizational permission domains; HR operational classes; `access_roles` binding policy |

**Outcome:**

- Accepted architecture (ARCH-001, ADR-050 / ADR-051 / ADR-053) unchanged; **Architecture Freeze** remains in effect.
- **Architecture Design** phase for the Organizational Policy Layer is **closed**.
- **Policy Ratification** is the next active governance phase — see [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md).
- **Runtime implementation remains blocked** until policy reaches **Approved** (ACCESS-001 **Approved** required for Phase 2.6b / [OPS-030](../ops/OPS-030-permission-template-contour-binding.md)).
- [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) feeds a **separate** future management-authority program; **Approved** ACCESS-002 does **not** unblock Phase 2.6b or OPS-030.
- Phase 2.6a complete; Phase 2.6b and OPS-030 **remain blocked** (ACCESS-001 **Approved** + [ADR-053 AC3](../adr/ADR-053-permission-template-binding-model.md#11-acceptance-criteria-ratified)).

---

### ACCESS-001 — Organizational Permission Matrix (Phase 2.6b policy)

**Статус:** **Reviewed** — 2026-07-04

**Scope:** Architecture / organizational policy only. Defines organizational permission domains, HR operational permission classes, and approved `access_roles` baseline binding policy. **No runtime effect by itself.** **Reviewed** does not unblock OPS-030 or Phase 2.6b.

**Document:** [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md)

**Program:** [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) — Track B work packages (WP-B1–B8, WP-X1–X3).

**Deliverables (TODO — Policy Ratification):**

- Stakeholder review of §5 **permission domains** and §7 matrix (Reviewed → Approved)
- Ratify permission domains (кадровое решение / оформление / контроль / informational boundary) and map to `access_roles` or future codes
- Resolve pending rows for HR head `(73, 86)` and deputy admin `(78, 77)` — **no `approved` rows until class + code agreed**
- Define separate **кадровое решение** model for Director (not `HR_ENROLLMENT_MANAGER`, not `SYSADMIN_CABINET`)
- Satisfy ADR-053 AC3 ops mapping annex when document reaches **Approved**

**Blocks:** [OPS-030](#ops-030--permission-template-contour-binding-phase-26b) — execution forbidden until ACCESS-001 reaches **Approved** and rows have `policy_status=approved`.

**Does not block:** [ACCESS-002](#access-002--organizational-management-authority-model) or future management-authority implementation — orthogonal policy track.

---

### ACCESS-002 — Organizational Management Authority Model

**Статус:** **Reviewed** — 2026-07-04

**Scope:** Architecture / organizational policy only. Defines **management authority classes** (visibility, task management, execution control, analytics, delegation), **hierarchy model**, and **subtree management principle** for Position Cabinets. **No runtime effect by itself.**

**Document:** [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md)

**Program:** [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) — Track A work packages (WP-A1–A8); prerequisite for future management-authority implementation only; **does not** unblock Phase 2.6b or OPS-030.

**Deliverables (TODO — Policy Ratification):**

- Stakeholder review toward **Approved** (Reviewed → Approved)
- Ratify §3 **management responsibilities** and §6 **subtree rules**
- Build future contour → responsibility → subtree matrix (mirror ACCESS-001 §7 — not started)
- Define delegation policy (§3.5) and executive vs line-head class combinations (§3.6)
- Align with ADR-010 reporting vertical and ADR-042 E1 visibility migration path

**Prerequisite for:** Future management-authority implementation (Management Scope Resolver, legacy `org_unit_managers` / `users.unit_id` retirement, Cabinet-scoped task and analytics boundaries). **No OPS runbook yet.**

**Does not block:** [ACCESS-001](#access-001--organizational-permission-matrix-phase-26b-policy) or [OPS-030](#ops-030--permission-template-contour-binding-phase-26b) — baseline `access_roles` binding and Phase 2.6b contour execution remain on the ACCESS-001 track only.

**Related (orthogonal):**

| Track | Document | Concern |
|-------|----------|---------|
| Baseline access permissions | [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | `access_roles` → Template contour binding |
| Phase 2.6b data execution | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | Insert approved ACCESS-001 rows only |
| Management scope policy | **ACCESS-002** (this item) | Subtree governance classes — future implementation |

---

### OPS-030 — Permission Template Contour Binding (Phase 2.6b)

**Статус:** **Blocked (ACCESS-001 Reviewed — Approved required + ADR-053 AC3 Pending)** — 2026-07-04

**Scope:** Ops data publication only. Phase 2.6a engineering (schema, resolver read-path, backfill mechanism) is accepted separately; **production binding is not complete** until OPS-030 executes.

**Deliverables (TODO):**

- Approved `(org_unit_id, catalog_position_id) → access_role_id` mapping annex
- Insert rows into `permission_template_contour_rule`
- Re-apply backfill migration / UPDATE
- Run `sql/validation/adr053_phase2_6_permission_template_binding_validation.sql`
- Observe shadow parity with `CABINET_ACCESS_SHADOW_MODE=true`

**Runbook placeholder:** [OPS-030](../ops/OPS-030-permission-template-contour-binding.md)

**Gates:** Governed by [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) (WP-X3). Runtime remains blocked until all gates close.

1. [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) — §5 permission domains defined; document **Approved**; only `policy_status=approved` rows may be inserted. **Reviewed** alone does not satisfy this gate.
2. [ADR-053 AC3](../adr/ADR-053-permission-template-binding-model.md#11-acceptance-criteria-ratified) — ops mapping published and approved before production data backfill.

[ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) **Approved** is **not** a gate for OPS-030 or Phase 2.6b.

---

## Investigations Index

| ID | Subject | Verdict | Report |
|----|---------|---------|--------|
| OPS-007 | Telegram bot operational audit | Findings remediated in OPS-007a/007b | [OPS-007 audit](../ops/OPS-007-telegram-bot-operational-audit.md) |
| OPS-009.22 | Task #10006 «Phase3b E2E delivery test» | **C — Test artifact; Soft Archive recommended** | [OPS-009.22 investigation](../ops/OPS-009.22-task-10006-investigation.md) |
| — | RBAC visibility issue #118 | Closed | [RBAC visibility audit](../RBAC_VISIBILITY_118_AUDIT.md) |

---

## Tracking

| Event | Date |
|-------|------|
| OPS-007 audit complete | 2026-06-21 |
| OPS-007a + OPS-007b complete | 2026-06-21 |
| OPS-008 complete | 2026-06-21 |
| Backlog refreshed (OPS-010–012 added) | 2026-06-21 |
| OPS-009.20 Safe Catch-Up + admin scope deployed | 2026-06-22 |
| OPS-009.21 run journal outcome shipped | 2026-06-22 |
| OPS-009.22 task #10006 investigation complete | 2026-06-22 |
| OPS-009 program closed; OPS-009.24 backlog reconciliation | 2026-06-22 |
| ADR-046 proposed (org-unit allowed positions) | 2026-06-22 |
| OPS-009.30–009.34 monthly E2E + template filter fix verified on prod | 2026-06-25 |
| POST-OPS review; OPS-015–019 added to backlog | 2026-06-25 |
| OPS-021 catch-up form periodicity-first layout | 2026-06-25 |
| OPS-026.5 Unified System Health Dashboard added to backlog | 2026-06-25 |
| ACCESS-002 Organizational Management Authority Model advanced to Reviewed | 2026-07-04 |
| ACCESS-001 Organizational Permission Matrix advanced to Reviewed | 2026-07-04 |
| Position Cabinet Organizational Policy Layer — architecture review complete | 2026-07-04 |
