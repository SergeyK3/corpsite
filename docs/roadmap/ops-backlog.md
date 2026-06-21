# OPS Backlog

Операционные и UX-задачи вне текущих ADR-фаз. Нумерация: `OPS-NNN`.

## Program status (2026-06-21)

| Area | Status |
|------|--------|
| **ADR-044** (Identity Reconciliation R1–R2.5g) | **Complete** — implementation phases closed; R3 post-R2 validation gate remains planned in ADR, not active OPS work |
| **Telegram bot (OPS-007 series)** | **Complete** through OPS-007b VPS validation |
| **Operations UI localization (OPS-008)** | **Complete** — R2.5g Identity Operations panel |

---

## Summary

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| [OPS-007](#ops-007--telegram-bot-operational-audit) | Telegram Bot Operational Audit | — | **Complete** |
| [OPS-007a](#ops-007a--internal-bot-api) | Internal Bot API | — | **Complete** |
| [OPS-007b](#ops-007b--vps-telegram-validation) | VPS Telegram Validation | — | **Complete** |
| [OPS-008](#ops-008--ui-localization-cleanup) | UI Localization Cleanup (R2.5g Operations) | — | **Complete** |
| [OPS-010](#ops-010--telegram-user-acceptance-testing) | Telegram User Acceptance Testing | Medium | **Open** |
| [OPS-011](#ops-011--telegram-legacy-bindings-removal) | Telegram Legacy Bindings Removal | Low | **Deferred** |
| [OPS-012](#ops-012--test-suite-stabilization) | Test Suite Stabilization | Low | **Open** |

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

## Tracking

| Event | Date |
|-------|------|
| OPS-007 audit complete | 2026-06-21 |
| OPS-007a + OPS-007b complete | 2026-06-21 |
| OPS-008 complete | 2026-06-21 |
| Backlog refreshed (OPS-010–012 added) | 2026-06-21 |
