# WP-ACCESS-001 — инвентаризация жизненного цикла доступа

Дата: 2026-09-22
Статус: read-only inventory и технический план, без реализации.

## Краткое резюме

Контур уже содержит связку Person → Employee → User, назначения, access-grants, security audit, password login, PBKDF2-HMAC-SHA256, self-service change, JWT с token_version, автоматический lockout и legacy admin lock/unlock/force-password-change. Единого lifecycle пока нет.

Главные расхождения: admin reset — stub; mandatory-change выключен по умолчанию; увольнение деактивирует Employee/User, но не увеличивает token version, не обрабатывает dependencies и не пишет security audit; Telegram проверяет лишь is_active; Google OAuth/login отсутствует (есть только google_login). Нет employee-scoped access commands, preview, CAS/idempotency journal, scheduled termination, UI в карточке и USER_ACCESS_ADMIN.

AGENTS.md в корне/доступном дереве не найден. Исходная спецификация прочитана полностью; прочитаны ADR-013, ADR-042 B3/B5, ADR-023, ADR-020, кадровые ADR/WP, termination verification и scheduler runbook. Старые ADR местами имеют повреждённую локальную кодировку, поэтому их технические положения сверены с кодом.

## Требование концепции → фактическое состояние

| Требование | Уже есть | Не хватает / расхождение |
|---|---|---|
| Self-service пароль | POST /auth/password-change, current password, PBKDF2, FOR UPDATE, token_version++, audit, Profile UI/tests | Policy лишь 8–200 символов, confirmation и запрет current-password reuse; общей policy-службы нет |
| Temporary password/admin reset | Колонки и AdminPasswordResetPlan | issue_temporary_password всегда NotImplementedError; нет CSPRNG delivery, once-only UI и expiry check |
| Mandatory change | must_change_password, admin force flag, route helper | Enforcement flag по default false; нет отдельной initial-password страницы |
| JWT revoke | Новый JWT содержит DB token_version; protected dependency сравнивает claim | Termination не bump-ит; Telegram не валидирует version |
| Password login | Проверяет is_active, lock и password | temp_password_expires_at нигде не проверяется |
| Google login | users.google_login | OAuth endpoint/provider callback/verifier не найден |
| Telegram access | Binding + bot identity + is_active check | Нет is_user_locked, token_version, must-change проверки |
| Auto lockout | failed counter, default threshold 5, brute-force audit | locked_until не устанавливается; unlock не сбрасывает counter |
| Manual lock | /admin/users/{id}/lock и unlock, audit и bump | Смешан с auto lock; нет employee scope/CAS/idempotency/manual provenance |
| Termination basis | Applied personnel-order TERMINATION создаёт approved employee event | Нет access preview/scheduler/dependency handling/JWT revoke |
| Grants | Soft revoke access_grants | Termination ничего не отзывает |
| Audit | Generic/domain audits и sanitized security_audit_log | Нет command id, lifecycle event types и dependency snapshot |
| Delayed idempotent work | Scheduler journals; preview/run journals; PPR outbox SKIP LOCKED | Нет durable user-access command/termination queue |
| USER_ACCESS_ADMIN | access_roles/grants + permission helpers | Code, seed, UI projection и approval policy отсутствуют |

## Карта фактических моделей, файлов и интерфейсов

| Слой | Фактическая модель / файл |
|---|---|
| Person | persons.person_id; canonical identity/status/provenance, DDL alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py |
| Employee | employees.person_id → persons.person_id; is_active, dates, operational_status, org unit/position |
| Assignment | person_assignments.person_id → persons.person_id; active/primary/lifecycle/date model; нет FK на Employee |
| User | users.employee_id → employees.employee_id, role_id → roles.role_id; link migration c3d8e12a5f01; unique one User per Employee не подтверждён |
| Legacy role | roles, один users.role_id; не равен permission access role |
| Permission | access_roles + access_grants; targets USER/EMPLOYEE/PERSON/ASSIGNMENT/POSITION/ORG_UNIT/ROLE, resolver выбирает MAX rank |
| Password/JWT | app/auth.py: /auth/login, /auth/password-change, /auth/me, get_current_user, hasher |
| Policy | app/security/auth_policy.py: lockout/version/must-change |
| Admin users | app/api/admin_router.py, app/services/admin_users_service.py: lock, unlock, force-password-change |
| Permissions | app/security/admin_permissions.py, access_resolver_service.py, access_grant_service.py |
| Telegram | app/tg_bind.py, app/security/bot_internal_auth.py, app/tg_bot_internal_router.py |
| Password UI | corpsite-ui/app/profile/_components/ProfilePageClient.tsx, PasswordChangePanel.tsx, corpsite-ui/lib/api.ts |
| Admin UI | corpsite-ui/app/admin/system/_components/tabs/UsersTab.tsx |
| Termination | personnel_orders_apply_service.py, employee_termination_verification_service.py, employees_routes.py |

User is SQL-first: no unified ORM User model. Runtime access code uses SQL. Checked users fields:

| Field | Status/use |
|---|---|
| is_active | Present; checked by password login and JWT dependency |
| must_change_password | Present/default false; changed by self-change/force; enforcement flag |
| password_changed_at | Present; written on self-change |
| temp_password_expires_at | Present; cleared on self-change; issuance/check absent |
| failed_login_count | Present, nonnegative constraint; increment/reset-success |
| locked_at, locked_until, locked_reason | Present; lock active while locked_at and until is null/future; reason constrained |
| token_version | Present/default 1; JWT issue and self-change/lock/unlock/force bumps |

Relevant additional columns are login, password_hash, google_login, Telegram fields and linkage/role/unit identifiers. No values, hashes, tokens or personal data were read or emitted.

## Все способы входа и activity checks

1. Password: /auth/login normalizes login, rejects inactive/locked/no-hash/invalid password, records login audit, then issues JWT with current version.
2. JWT protected requests: get_current_user verifies signature/expiry, resolves DB User, rejects missing/inactive/locked account, validates exact claim version, then runs must-change route guard. All routes using Depends(get_current_user) inherit it. Not every router was mechanically proven; legacy internal paths remain, contrary to ADR-013's intended JWT-only final state.
3. Google: no actual Google auth implementation found. google_login is an identity/contact/linkage field; blocked-Google acceptance test is pending provider implementation.
4. Telegram bot-bound identity: require_bot_bound_user needs internal token and X-Telegram-User-Id, maps users.telegram_id, rejects inactive and service accounts. It does not call lock/version/must-change checks. Person-level person_telegram_bindings and activations are separate historical identity tables.

## Self-service password change

PasswordChangeRequest has current/new/confirmation. Subject is only current JWT user. hash_password is PBKDF2-HMAC-SHA256, random 16-byte salt, 200,000 iterations; verification is constant-time. Policy: current length 1–200; new 8–200; equality confirmation; new differs from current verified hash.

One engine.begin transaction locks the User with FOR UPDATE, rechecks active/current password, writes new hash and password_changed_at, clears must-change/temp expiry, increments version and emits sanitized PASSWORD_CHANGED. Profile UI calls the endpoint, clears session and redirects to /login. Tests: tests/test_self_service_password_change.py and ProfilePageClient.password.test.tsx.

## Блокировка и JWT

Failed password login increments counter transactionally; at threshold it sets locked_at and locked_reason=brute_force, emitting LOGIN_FAILED/USER_LOCKED. Success resets counter. locked_until is read but not assigned.

Legacy lock_user sets lock/reason/version; unlock_user clears lock fields/version; force_password_change sets flag/version. All use SAL but lack active-state guard, employee linkage, CAS and command UUID. Manual and automatic state share locked_*; only reason distinguishes them.

A standard JWT is invalid immediately after bump. Personnel-order termination only sets users.is_active=false, without a bump. Requests will reject while inactive, but accidental later reactivation could revive old tokens.

## Фактический workflow увольнения

Two different flows exist.

* Applied personnel order is the best authoritative-basis candidate. _apply_termination in personnel_orders_apply_service.py sets employees.is_active=false, date_to=effective_date, sets linked Users inactive, and appends employee_events TERMINATION, lifecycle_status=APPROVED, with effective date/order/item/pre-state metadata. It does not close assignments/revoke grants/transfer dependencies/unbind identity/bump version/write security audit.
* Termination verification (employee_termination_records, endpoint PATCH /directory/employees/{id}/termination-verification) is a verification flow for already inactive historic import records. It requires facts, creates the approved event and has its own audit. It is not an access-termination command and only has a date.

HR sync recognises TERMINATED_PERSON, but no evidence was found that it terminates user access. Recommended source is an applied, approved personnel-order event, pending decision on void/reversal. Current basis is a DATE rather than timestamp; the requested Asia/Almaty effective-time rule must be made explicit.

## Dependencies inventory

| Category | Actual relationship | Access-lifecycle handling needed |
|---|---|---|
| Tasks | tasks.initiator_user_id, created_by_user_id, approver_user_id; normal execution by executor_role_id; reports submitted/approved user | Preview personal active approval/report work; retain history; role tasks stay on role |
| Onboarding | checklist assignee_user_id/assignee_employee_id | Inventory nonterminal personal items, explicit successor/close plan |
| Incoming documents | document addressee/controller; active incoming_document_assignments.assignee_user_id | Preview/reassign/cancel via workflow, preserve documents/history |
| Approvals | task approver/report approval, incoming workflow assignment | Only outstanding actionable personal approvals need policy |
| Notifications | notifications, task event recipients/deliveries keyed by User | Preserve history; decide pending cancel/suppress/transfer |
| Onboarding notifications | recipients/deliveries keyed by User, PENDING/SENT statuses | Include pending deliveries in preview |
| Direct grants | polymorphic access_grants, soft revoke | Revoke direct User/Employee and decide Person/Assignment; never globally revoke role/position/org-unit grants |
| Google/Telegram | google_login; user Telegram, tg_bindings, person bindings/activations | Preserve history; enforce access gate; decide whether termination revokes binding |

Employee documents, personnel orders, HR events/audits, supervisors and manager links are historical references. Preview should count them when actionable, not rewrite them.

## Audit

audit_log supplies generic before/after records. Domain audit includes task events/deliveries, onboarding audit/notifications, incoming audit repository, personnel-order lifecycle/editorial audit and termination-record audit. security_audit_log is append-only through security_audit_service.py; it has actor/target User/Person/Employee, request context, success/failure and metadata sanitizer rejecting password/token/secret/hash keys.

Add SAL CHECK/service event types: PASSWORD_RESET_ISSUED, PASSWORD_RESET_EXPIRED, USER_TEMPORARILY_BLOCKED, ACCESS_TERMINATION_SCHEDULED, ACCESS_TERMINATED, ACCESS_TERMINATION_FAILED, ACCESS_RESTORED. Metadata: command id, basis/event id, old/new safe flags/version, fingerprint, successor IDs/counts — never credentials/secrets/full command payload.

## Scheduler, CAS and idempotency

The established scheduler is systemd timer → scripts/ops/run_regular_tasks_cron.sh → /internal/regular-tasks/run → run_regular_tasks_generation_tx, journalling regular_task_runs/items. It runs 08:30 Asia/Almaty daily; catch-up is separate. It is task-specific, not a durable generic queue.

Reuse closer patterns: preview/run journals in linkage/personnel lifecycle, unique idempotency keys in enrollment/deletion, and ppr_migration_projection_outbox_worker.py using FOR UPDATE SKIP LOCKED. Do not overload regular_task_runs.

Create user_access_commands: unique UUID command_id, command type, employee/user, actor/technical executor, expected token version, canonical payload hash, redacted result/state, timestamps/failure code. Same id+hash returns original result; same id+different hash is 409. Each access state change bumps version.

For delayed termination, add user_access_terminations: command/employee/user/approved HR event, effective UTC + source timezone, status, attempts/lease/error code and preview fingerprint/plan. Worker claims due records with FOR UPDATE SKIP LOCKED, marks PROCESSING with lease, executes same service transaction, reclaims expired lease. CAS/fingerprint/HR-basis difference becomes review/conflict, not automatic stale retry.

## Предлагаемые transaction boundaries

* Reset/block/unblock/restore: one transaction: lock command and User FOR UPDATE, resolve exactly one User through route Employee, recheck version/state, mutate User, command result, SAL and ordinary audit. Plain temporary password only lives in immediate response after commit; never in journal.
* Preview: read-only resolve Employee/Person/exact User/assignment and actionable dependencies; return canonical SHA-256 fingerprint and version.
* Immediate termination: one DB transaction locks command, Employee, User, active assignment and dependency rows in deterministic order; validates approved/effective HR event, CAS and fingerprint; executes approved reassign/revoke workflow, closes assignment via HR service, deactivates User and bumps version; records audit; rolls back entirely on a conflict/failure.
* Scheduled termination: durable schedule creation transaction, then claimed worker transaction as above. Existing daily task timer cannot meet arbitrary effective timestamp without a separately approved worker/cadence.

## Proposed API (not implemented)

GET  /directory/personnel/employees/{employee_id}/access  
GET  /directory/personnel/employees/{employee_id}/access/termination-preview  
POST /directory/personnel/employees/{employee_id}/access/password-reset  
POST /directory/personnel/employees/{employee_id}/access/block  
POST /directory/personnel/employees/{employee_id}/access/unblock  
POST /directory/personnel/employees/{employee_id}/access/terminate  
POST /directory/personnel/employees/{employee_id}/access/restore

All mutations include command_id, expected_token_version, reason/basis and safe operation data. Client user_id, person_id, role and login never choose target. Require explicit USER_ACCESS_ADMIN; use 409 for CAS/replay-payload/fingerprint conflict. Read projection returns safe state/version/expiry/block/dependency summary only.

## Proposed migrations (not created)

1. Seed USER_ACCESS_ADMIN only, add it to permission code/projection; no broad grants.
2. Add manual_blocked_at, manual_blocked_by_user_id, manual_block_reason (or approved history table), keeping auto locked_*.
3. Add user_access_commands.
4. Add user_access_terminations with event FKs, state/lease/indexes.
5. Extend SAL event type CHECK and query indexes.
6. Investigate duplicate linkage before any partial unique active User-per-Employee constraint. Do not merge Alembic branches for this work.

## Alembic graph

alembic heads returned two heads: adm001canonicalroles and dxe002vacation01. alembic branches reports branchpoint ppr005qnotedetails01 with descendants pce001cardedit and dxe001framework01; data-exchange continues to the second head. Access baseline lies on the long main chain from u3v4w5x6y7z8. New migration parent must be selected after reconciling intended deployment graph; it must not merge heads merely for this feature.

## Test plan

Backend/service: state resolver/transitions; exact Employee→User resolution; permission; shared password policy/CSPRNG redaction; temporary expiry; canonical payload hash; CAS/replay/conflict; dependency fingerprint; all auth gates; approved HR basis; restore requires new assignment.

PostgreSQL integration: reset→temporary login→change→relogin; expiry/reuse; old JWT rejection; lock/unlock/terminate preserve role/history and revoke JWT; atomic rollback on handover failure; duplicate/lease worker cases; draft/voided/future HR basis; Telegram/future Google cannot bypass state gate.

Vitest: employee panel permission/state buttons; preview/reason/confirmation; 409 refresh; plaintext shown once and never stored; mandatory-change navigation gate; dialog behavior; preserve existing Profile logout test.

## Risks

* Legacy platform role, access grants and privileged env fallbacks must not become another role-name authorization path.
* User-to-Employee may be ambiguous; assignments attach to Person, so naive joins can target wrong account.
* Current personnel-order code directly deactivates User; integrating without a service boundary risks double mutation and void/restore conflict.
* is_active=false does not identify termination cause.
* Date-only HR basis conflicts with timestamp/timezone requirement.
* Telegram bypasses JWT middleware; Google provider is absent.
* Existing scheduler is daily/task-specific.
* Multiple audits should be correlated, not rewritten or deleted.

## DECISION_REQUIRED

1. Confirm authoritative source: only applied approved personnel-order TERMINATION, or also verified archive/HR sync; define void/reversal.
2. Define effective time: Asia/Almaty or organisation zone; how date-only order maps to instant.
3. Approve separate manual-block fields; decide auto-lock expiry and whether unlock resets failed counter.
4. Define successor/cancel policy for approvals, incoming assignments, pending deliveries and direct grant target types.
5. Decide retain-versus-revoke Telegram bindings and define Google provider contract.
6. Identify named operators receiving USER_ACCESS_ADMIN; no automatic ADMIN/HR_HEAD/ACCESS_ADMIN grant is recommended.
7. Approve worker hosting/cadence/service identity for arbitrary effective time.
8. Decide restore: reactivate old User or new/linkage flow; recommended old direct grants never return automatically.

## Small follow-up work packages

1. WP-ACCESS-002: ADR decisions; permission + safe access read/preview API and tests.
2. WP-ACCESS-003: shared policy, temporary reset and mandatory-change gate.
3. WP-ACCESS-004: separate manual block and shared password/JWT/Telegram gates.
4. WP-ACCESS-005A: immediate approved-HR-event termination with preview/journal/handover.
5. WP-ACCESS-005B: scheduled worker, lease/idempotency/observability/runbook.
6. WP-ACCESS-006: restore against new HR basis/role/grant review.
7. WP-ACCESS-007: isolated test-DB rehearsal and separately authorized rollout.

## Checks and scope confirmation

* Fully read docs/implementation/account-access-lifecycle.md; searched for AGENTS.md (none).
* Reviewed targeted ADR/auth/personnel/permission/audit/scheduler documentation; application code, UI, migrations and relevant test sources.
* Inspected Alembic heads, branches and history; reviewed DDL for core/dependent tables.
* Only read-only repository/Git/Alembic inspection commands were run. No database query was needed: migration DDL and runtime SQL establish the local schema contract without risking an unverified configured database target.

No application code, migration, existing documentation, local DB, production, commit, push or deploy was changed. The sole created artifact is this report; pre-existing dirty-worktree changes were left untouched.

