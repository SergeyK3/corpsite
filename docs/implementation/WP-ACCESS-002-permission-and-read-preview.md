# WP-ACCESS-002 — permission и read-only access preview

Дата: 2026-09-22
Статус: реализовано локально; PostgreSQL integration tests ожидают отдельную test-БД.

## Что реализовано

* Добавлен permission code USER_ACCESS_ADMIN в registry и API auth-me projection
  has_user_access_admin.
* Добавлена миграция ua002accessadmin: создаёт только catalog row access_roles.
  Она не создаёт пользователей, не создаёт access grants и не назначает permission
  Platform Role.
* Добавлен GET /directory/personnel/employees/{employee_id}/access.
* Добавлен GET /directory/personnel/employees/{employee_id}/access/termination-preview.
* Добавлены tests/test_wp_access_002_read_preview.py и решения в исходную
  спецификацию.

## Изменённые файлы

* app/security/admin_permissions.py
* app/auth.py
* app/directory/router.py
* app/directory/employee_access_routes.py
* app/services/employee_access_read_service.py
* alembic/versions/ua002_user_access_admin_permission.py
* tests/test_wp_access_002_read_preview.py
* docs/implementation/account-access-lifecycle.md
* этот отчёт.

## Контракт endpoint-ов

### GET /directory/personnel/employees/{employee_id}/access

Требует действующий JWT и эффективный USER_ACCESS_ADMIN через существующий
access resolver; legacy ADMIN, HR_HEAD, privileged configuration и имя роли не
являются bypass. Находит Employee по route parameter и разрешает ровно один
users.employee_id. При отсутствии User, отсутствии Person или нескольких User
отвечает 409 с контролируемым code; при отсутствии Employee — 404.

Успешный ответ содержит employee_id, person_id, user_id, has_linked_user,
employee_is_active, is_active, must_change_password, lock_active, lock_reason,
automatic_lock_active (только при подтверждённом brute_force происхождении),
locked_until, token_version, has_active_assignment и generated_at. Поле
manual_lock_active намеренно не выдаётся: существующая схема не позволяет
надёжно отличить ручную блокировку от иных причин. Он не отдаёт login,
hash/password, token, Telegram/Google идентификатор, ИИН, телефон или email.

### GET /directory/personnel/employees/{employee_id}/access/termination-preview

Использует то же permission. Это aggregate-only read projection: при неясной
linkage он возвращает linkage_state и warning, не выбирая произвольного User.
Ответ содержит безопасную связь Person/Employee/User, активное assignment,
наличие applied approved employee_events TERMINATION с order_id, counts и
warnings. Он ничего не меняет.

## Правила counts preview

* unfinished_personal_tasks: только onboarding checklist items с явным
  assignee_user_id и не terminal status. Ролевые tasks не входят.
* active_personal_approvals: tasks, где approver_user_id совпадает с User и
  task_statuses.is_terminal=false.
* active_incoming_document_assignments: incoming_document_assignments для User
  с completed_at и cancelled_at равными null.
* pending_notifications_deliveries: сумма PENDING rows notifications,
  task_event_deliveries и onboarding notification deliveries.
* active_direct_grants_by_target_type: действующие, временно валидные grants
  для конкретных USER, EMPLOYEE, PERSON и его ASSIGNMENT целей, отдельно по
  target type. Role/position/org-unit grants не считаются персональными.

Для каждого optional dependency возвращается dependency_status. Если таблица
существует и проверка выполнена, пустой набор даёт count=0 и status=available.
Если таблица отсутствует либо источник нельзя проверить, count=null,
status=unavailable и добавляется warning
DEPENDENCY_SOURCE_UNAVAILABLE:<dependency>. Отсутствующая таблица никогда не
интерпретируется как отсутствие зависимостей. Для direct grants все четыре
target-type count становятся null, если нельзя подтвердить access_grants или
набор персональных assignments.
Правила не назначают преемника, не закрывают работу и не объявляют dependency
блокирующей: это решение отложено для WP-ACCESS-005.

## Permission и migration

Migration продолжает head adm001canonicalroles, потому что это current
canonical administrative-platform-role branch. Независимый head
dxe002vacation01 не объединён. Upgrade делает INSERT access_roles with
ON CONFLICT only. Downgrade отказывается удалить permission при существующих
grants и удаляет role только при их отсутствии: он не выполняет неявный revoke.

Документ зафиксировал: permission предоставляется в дальнейшем только
персональным grant утверждённому пользователю; первый кандидат — будущий
подтверждённый основной system-owner account, резервный персональный admin
account — отдельный финальный production action. No automatic grant exists.

## Проверки

* python -m py_compile для нового service, router, permission/auth modules —
  успешно.
* Проверка регистрации routes через import app.main — успешно: оба exact path
  присутствуют. `alembic heads` подтвердил два независимых head:
  `ua002accessadmin` и `dxe002vacation01`; merge не создан. `git diff --check`
  успешно (только предупреждения Git о CRLF в посторонних файлах).
* pytest tests/test_wp_access_002_read_preview.py был запущен, но protection
  проекта завершил запуск до collection: TEST_DATABASE_URL не задан. Это
  ожидаемая защита от использования DATABASE_URL/dev/prod; тесты и migration
  не исполнялись против какой-либо БД. После уточнения WP-ACCESS-002 добавлены
  проверки count=null/status=unavailable/warning при недоступном optional source
  и отсутствия manual_lock_active в access-state; они ожидают отдельную test-БД.
* Штатная инструкция проекта найдена в tests/README.md: pytest использует
  TEST_DATABASE_URL, валидирует loopback и имя *_test/-test и сам привязывает
  engine к test-БД. В этой среде TEST_DATABASE_URL не задан, команда psql и
  локальная служба PostgreSQL не обнаружены. Поэтому ua002 upgrade/downgrade/
  повторный upgrade, проверка catalog/grants и PostgreSQL integration suites
  не запускались; DATABASE_URL не подменялся.
* Последняя фактическая команда для требуемой группы была:
  `python -m pytest -q tests/test_wp_access_002_read_preview.py
  tests/test_adr045_hr_head_auth_me.py tests/test_adr042_phase_b3_access_resolver.py
  tests/test_control_list_export_permission_migration.py`. Она завершилась до
  collection тем же сообщением `TEST_DATABASE_URL is required...`; ни один
  тест и ни одна миграция не исполнялись против БД.

Для продолжения владелец должен предоставить локальную PostgreSQL test-БД и
задать только `TEST_DATABASE_URL` с loopback-host и именем, оканчивающимся на
`_test`/`-test` (например, `corpsite_test`). Штатная команда создания из
tests/README.md — `psql "postgresql://<user>:<password>@127.0.0.1:5432/postgres" -c
"CREATE DATABASE corpsite_test;"`. Для миграций без изменения переменной
`DATABASE_URL` следует использовать явный Alembic Config с
`sqlalchemy.url=$env:TEST_DATABASE_URL` (как это делают существующие migration
tests), затем запускать `python -m pytest -q` с тем же TEST_DATABASE_URL.

### Попытка isolated PostgreSQL 16 (2026-09-22)

Для дополнительной проверки создан отдельный Docker-контейнер
`corpsite-wp-access-002-test-pg16` (`postgres:16`) с loopback mapping
`127.0.0.1:55432`, отдельной БД `corpsite_wp_access_002_test` и случайным
паролем, который не записывался в Git или этот документ. Перед созданием
подтверждено, что `55432` свободен; существующие `corpsite-pg` (`5432`) и
`neuro-hr-postgres` не изменялись. Контейнер не подключался к production.

Фактически выполнена команда (пароль намеренно скрыт):

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg2://wp_access_002_test:<redacted>@127.0.0.1:55432/corpsite_wp_access_002_test'
python -c "... cfg.set_main_option('sqlalchemy.url', $env:TEST_DATABASE_URL); command.upgrade(cfg, 'heads')"
```

`upgrade heads` не дошёл до `ua002accessadmin`: existing migration
`h5c6d7e8f9a0_hr_head_incoming_info_read_grant_correction` остановила чистую
БД с ошибкой `requires exactly one role with code HR_HEAD, found 0`. Общая
Alembic transaction была откатана (таблица `alembic_version` отсутствует).
В репозитории не найден штатный full-database bootstrap: существующие migration
tests создают prerequisite `HR_HEAD` и active user вручную внутри теста, а
доступный seed рассчитан на уже подготовленную БД. Создавать такие role/user/
grant вручную для обхода migration precondition не стали.

Поэтому проверка `USER_ACCESS_ADMIN` в `access_roles`, отсутствие automatic
`access_grants`, downgrade до `adm001canonicalroles`, повторный upgrade и
требуемый pytest-набор не выполнялись. Итог pytest для этой попытки:
passed=0, failed=0, skipped=0, not-run=4 files (migration precondition).
Ни production, ни рабочая локальная БД не запрашивались и не изменялись.

### Historical migration correction h5c6d7e8f9a0 (2026-09-22)

Исходная остановка `upgrade heads` произошла в
`h5c6d7e8f9a0_hr_head_incoming_info_read_grant_correction`: чистая БД не
содержала `HR_HEAD`, а revision требовала ровно одну такую role и active user
для `granted_by_user_id`. Анализ parent `g4b5c6d7e8f9`, child
`i6j7k8l9m0n1`, related permission/grant migrations, migration tests и Git
history классифицировал h5 как **one-time data correction**, а не schema/DDL
migration: она исправляет старую привязку `INCOMING_INFO_READ` от hard-coded
`role_id=14` к стабильному `roles.code='HR_HEAD'` на уже populated installation.

Минимальное исправление h5: при отсутствии `HR_HEAD` (`count=0`) или active
grantor migration делает no-op; не создаёт role, user или grant. При ровно одной
role и active user сохранены прежние lookup, effective-grant/idempotency и
inconsistent-active-grant проверки; множественные HR_HEAD и missing/inactive
permission продолжают приводить к ошибке. Downgrade остался безопасным DELETE
по correction reason и является no-op, если записи нет.

В изолированной `corpsite_wp_access_002_test` сначала выполнен explicit
Alembic upgrade до `g4b5c6d7e8f9`, затем:

```text
python -m pytest -q tests/test_h5_hr_head_incoming_info_read_grant_correction_migration.py
3 passed in 0.52s
```

Три test cases покрывают: чистую БД без HR_HEAD/users, HR_HEAD без active user,
применение при всех prerequisites, повтор без дубликата и downgrade в skipped/
applied cases. Fixtures создавали synthetic roles/users/grant только внутри
изолированной test-БД и были откатаны.

После повторного пересоздания только этой test-БД `alembic upgrade heads`
прошёл h5, но остановился на следующей revision
`i6j7k8l9m0n1_hr_head_incoming_info_register_grant` с
`requires exactly one role with code HR_HEAD, found 0`. Эта revision имеет
аналогичный data-correction prerequisite, но не была изменена: её исправление
не входит в ограниченное поручение по h5. Поэтому до отдельного решения по
i6j7… не выполнены подтверждение heads `ua002accessadmin`/`dxe002vacation01`,
проверка USER_ACCESS_ADMIN/automatic grants, ua002 downgrade/re-upgrade и
согласованный WP-ACCESS-002 pytest-набор.

### Read-only inventory: historical clean-bootstrap risks after h5 (2026-09-22)

Статически проверены все revisions по двум путям от `h5c6d7e8f9a0` до
`ua002accessadmin` и `dxe002vacation01`, включая SQL/PLpgSQL, Python
`RuntimeError` и downgrade. Под «blocker» ниже понимается именно отсутствие
production/seed data на чистой БД, а не intentional schema-integrity guard.

| Revision | Назначение / тип | Требуемые данные | Поведение на чистой БД | Риск изменения / рекомендуемое отсутствие предусловий | Regression test |
|---|---|---|---|---|---|
| `i6j7k8l9m0n1` | HR_HEAD `INCOMING_INFO_REGISTER` role-grant; historical data grant | ровно один `HR_HEAD`, active user-grantor, existing active permission | **Подтверждённый blocker**: exception при `HR_HEAD=0` | Низкий для no-op именно grant correction; сохранить errors для duplicate/inactive permission | Да: no-role, no-user, applied, repeat, downgrade |
| `p1q2r3s4t5u6` | seed `HR_reg` + персональная Oserova correction | user `oserova.aa` только для UPDATE/grant | Safe no-op для отсутствующего target user; role catalog создаётся | Не блокер clean bootstrap; downgrade удаляет только named reason | Да, только idempotency/target-absent при отдельной доработке |
| `w6x7y8z9a0b1` | `CONTROL_LIST_EXPORT` catalog + HR_HEAD grant; смешанная schema/catalog + data seed | один `HR_HEAD`, active grantor | Потенциальный blocker после i6 | Нельзя целиком no-op: потеряется permission catalog. Разделить catalog creation и conditional grant отдельным решением | Да |
| `y8z9a0b1c2d3` | WP-TD-002 tables + permissions + ADMIN/HR_HEAD grants; смешанная foundation | один `ADMIN`, один `HR_HEAD`, active grantor | Потенциальный blocker | Нельзя no-op: foundation tables/permissions обязательны для feature. Нужен design: catalog/schema без grants либо sanctioned bootstrap | Да |
| `td005audit401` | WP-TD-005 audit schema; schema migration с ownership validation | intact WP-TD-002 execute permission + ADMIN role grant | Блокируется только вследствие отсутствия/пропуска `y8` grants | Не исправлять отдельно до решения по y8; guard защищает semantic contract | Да, после решения y8 |
| `td006afnd601` | system-identity foundation; schema + migration-owned technical identity | один `ADMIN`, active user | Потенциальный blocker | Не data correction: создаёт обязательную technical identity. Требует отдельного clean-bootstrap решения, не фиктивного grantor | Да |
| `s0p0r0e0v0f0` | PPR Stage 0 schema + HR_HEAD permission grant | `HR_HEAD`, active grantor | Потенциальный blocker | Нельзя просто skip: DDL и grant находятся в одной transaction. Разделить schema/catalog от conditional grant | Да |
| `s1g0e1n2r3a4` | PPR Stage 1 schema + HR_HEAD grant | `HR_HEAD`, active grantor | Потенциальный blocker | То же: schema must remain, grant should be conditional only после решения policy | Да |
| `s2e1d2u3c4a5` | PPR Stage 2 schema + HR_HEAD grant | `HR_HEAD`, active grantor | Потенциальный blocker | То же | Да |
| `s2e2f3g4h5i6` | activation existing `education` PMF domain; data activation, не role grant | ровно одна pre-seeded disabled domain с exact configuration | Potential bootstrap dependency | Не делать no-op автоматически: это intentional configuration validation; нужен documented PMF bootstrap owner | Да |
| `ppr3training001` | PPR Stage 3 schema extension + two HR_HEAD grants | `HR_HEAD`, active grantor | Потенциальный blocker | То же, что Stage 0–2 | Да |
| `ppr005hdept01` | org-unit/department recoding seed correction | expected ROOT/DISP organization seed and matching unit state | Potential bootstrap dependency, если prerequisite seed отсутствует/конфликтует | Не data no-op: migration intentionally normalizes seed. Нужен declared org bootstrap; test clean graph | Да |
| `adm001` / `emp001` / `qmt001` / `ua002` / `dxe001` / `dxe002` | catalog/schema migrations и guarded downgrades | только собственные schema/catalog prerequisites | Не требуют production role/user/grant для upgrade | Не blockers по отсутствию identities; downgrades намеренно block on references/data | Existing tests sufficient; ua002 test remains pending heads |

`i6` **не является единственным** оставшимся blocker. Есть конечная однотипная
группа role/user-dependent grant migrations (`i6`, `w6`, `y8`, `s0`, `s1`,
`s2`, `ppr3training001`, `td006`), но она не может быть безопасно исправлена
одинаковым no-op: `w6`, `y8`, Stage 0–3 и `td006` также несут DDL/catalog or
mandatory technical-identity semantics. Кроме неё имеются отдельные explicit
seed/configuration dependencies `s2e2` и `ppr005hdept01`.

Минимальный предлагаемый **отдельный** пакет (не реализован): (1) применить к
`i6` тот же conditional data-grant rule, что к h5; (2) принять проектное
решение, создаёт ли sanctioned clean bootstrap canonical roles/one technical
grantor, либо migrations разделяются на unconditional schema/catalog и
conditional grants; (3) добавить disposable clean-DB chain test для каждого
пакета; (4) отдельно зафиксировать owner/bootstrap `education` domain и org
units. Без этого решения завершить clean bootstrap без фиктивных данных нельзя.

### Проверка разрешённой локальной clone source (2026-09-22)

Перед согласованным `pg_dump | psql` подтверждено, что source `corpsite-pg`
и destination `corpsite-wp-access-002-test-pg16` — разные Docker containers:
source опубликован только как `127.0.0.1:5432` и является Compose service
текущего local workspace; destination опубликован как `127.0.0.1:55432` и
помечен `purpose=wp-access-002-test`. Техническая metadata source показала
БД `corpsite` и DB user `postgres`; пароли и data не выводились.

Read-only запрос `SELECT version_num FROM public.alembic_version` в source
вернул единственную revision `qmt001trainingexpert`. Это не ожидаемый набор
предыдущих heads `adm001canonicalroles` и `dxe002vacation01`. По обязательному
stop rule copy не создавалась: `corpsite_wp_access_002_test` не пересоздавалась,
`pg_dump`, restore, Alembic upgrade/downgrade, `stamp` и pytest не выполнялись.
Source не изменялся.

### Read-only source graph check before clone (2026-09-22)

`qmt001trainingexpert` существует в checkout:
`qmt001_training_expert_platform_role.py`, `down_revision=emp001employee`.
Это catalog-only neutral role migration без implicit permissions/grants. Read-only
`alembic current --verbose` against local `corpsite` подтвердил тот же revision;
`alembic heads` вернул `ua002accessadmin` и `dxe002vacation01`, а
`alembic branches` показал штатный branchpoint `ppr005qnotedetails01` с
ветвями `dxe001framework01` и `pce001cardedit`.

Статический граф: `qmt001trainingexpert` является предком
`ua002accessadmin`; прямой pending path —
`qmt001trainingexpert → adm001canonicalroles → ua002accessadmin`.
Она не является предком `dxe002vacation01`, но обе линии имеют известный
общий ancestor `ppr005qnotedetails01`; недостающая sibling branch штатно
применяется Alembic как `ppr005qnotedetails01 → dxe001framework01 →
dxe002vacation01`. Unknown revision, graph gap и необходимость `stamp` не
обнаружены.

Все ранее инвентаризированные identity/data blockers (`i6`, `w6`, `y8`,
`td005*`, `td006`, PPR Stage 0–3) лежат до `qmt001trainingexpert`, то есть
уже применены в source и не входят в pending path clone. Pending migrations
для copy: `adm001canonicalroles`, `ua002accessadmin`, `dxe001framework01`,
`dxe002vacation01`; из них historical data corrections нет.

**SAFE_COPY_CANDIDATE.** Копирование намеренно не начато. Для следующего,
отдельно подтверждённого шага предлагаются две distinct test DB inside
`corpsite-wp-access-002-test-pg16`: (1)
`corpsite_wp_access_002_migration_clone_test` для clone/upgrade/downgrade;
(2) `corpsite_wp_access_002_pytest_clone_test` для pytest, поскольку fixtures
могут изменять data. После проверки удалять только эти exact DB: сначала
закрыть/terminate их sessions, затем drop pytest copy, затем drop migration
copy; source `corpsite` и другие containers не трогать.

* Test source покрывает: explicit personal grant; ADMIN/HR_HEAD/no-permission
  denial; resolved linkage; preview read-only invariant; role tasks excluded;
  sensitive keys absent; migration has no access_grants INSERT.

## Основной системный аккаунт

Идентификация не выполнена: безопасно подтверждённая отдельная local test-БД
недоступна (нет TEST_DATABASE_URL). Production и DATABASE_URL не запрашивались.
Поэтому user_id/login/employee_id/person_id кандидата не выводятся и grant не
создавался.

## Вопросы и ограничения

* Existing locked_* columns do not preserve independent manual-block provenance.
  Projection therefore returns only lock_active, lock_reason, locked_until and
  automatic_lock_active when locked_reason exactly confirms brute_force;
  WP-ACCESS-004 must decide separate fields/history for a manual lock.
* Employee→User is not guaranteed unique by schema; state endpoint deliberately
  returns 409 instead of choosing one. Preview exposes only warning/state.
* approved termination event is treated as applied only when employee_events has
  APPROVED TERMINATION and non-null order_id. При недоступном источнике поле
  возвращается null с warning, а не false. Archive verification and HR sync do
  not qualify.
* Temporary-password expiry, reassignment, termination, JWT revocation,
  scheduler, Telegram changes and restoration are deliberately not implemented.

No state-changing access operation, production access/change, commit, push or
deploy was performed. Existing dirty-worktree changes were preserved.

### Final isolated-clone verification attempt (2026-09-22)

The authorized clone source was local `corpsite` in `corpsite-pg`; the target
was the isolated `corpsite_wp_access_002_test` database in
`corpsite-wp-access-002-test-pg16`. The source was used only as the producer
of a streamed `pg_dump --no-owner --no-acl`; no source write, migration, or
test was performed.

The restore could not create four unique indexes because the restored local
data contains duplicate keys in the corresponding import/match tables.  The
streaming command continued after these PostgreSQL errors, so the target was
not a faithful or valid copy for migration and integration testing.  To avoid
testing against a partially restored schema, the following steps were **not**
run: `alembic upgrade heads`, head/permission/grant checks, UA002 downgrade
and re-upgrade, and the agreed pytest set.  This is a local source-data/clone
integrity blocker, not a diagnosed WP-ACCESS-002 or h5 migration defect; no
code change was made to bypass it.

The temporary database and its dedicated test container/volume are removed
after this record.  `git diff --check` and `git status --short` are then run;
all pre-existing dirty-worktree changes remain untouched.

Actual final checks: `git diff --check` completed with exit code 0 (only
line-ending and inaccessible pre-existing temporary-directory warnings were
emitted); `git status --short` confirms the worktree remains dirty and was not
cleaned or reset.  Cleanup completed for exactly
`corpsite_wp_access_002_test`, `corpsite-wp-access-002-test-pg16`, and its
verified anonymous Docker volume.  A final read-only container listing no
longer contains the test container; `corpsite-pg` remains healthy on loopback,
and a read-only query confirmed its `corpsite` database remains available.

### Minimal empty-PostgreSQL fixture check (2026-09-22)

One new isolated PostgreSQL 16 container was created with its single empty
database `corpsite_wp_access_002_test`; no source dump was restored and no
Alembic command was run.  For the pytest child process only,
`TEST_DATABASE_URL` pointed to that loopback database.  The project pytest
DB-guard was allowed to rebind the application engine to the same test target;
the process-level `DATABASE_URL` used for guard comparison was a non-routable,
non-test dummy URL, never the workspace or production URL.

Command attempted:

```powershell
python -m pytest -q tests/test_wp_access_002_read_preview.py
```

Result: **1 passed, 6 errors**.  The six endpoint tests reached the standard
`seed` fixture and stopped because an empty database has no `public.roles`
table.  The one passing test is the static UA002 migration-policy check.  No
runtime endpoint assertion could therefore run, so runtime endpoints are
**not verified** by this minimal check.  Per the requested condition, the
related auth/me and access-resolver tests were not started because this file
did not pass.

`ua002` remains statically checked: it registers `USER_ACCESS_ADMIN` without
an automatic grant.  A complete clean-chain migration/integration check is
separately blocked by the historical bootstrap problem.  Independently, the
previous source-restore attempt is blocked by four conflicting unique indexes;
that is a local-data restoration task, not a WP-ACCESS-002 defect.  No
historical migration, local duplicate, fixture, or infrastructure behavior was
changed to bypass either blocker.

The empty test database, this test container, and its owned Docker volume are
removed after the test result is recorded.

### Schema-only runtime check (2026-09-22)

For the final runtime attempt, one new PostgreSQL 16 container with the single
`corpsite_wp_access_002_test` database received a streamed schema-only restore
from local `corpsite`:

```powershell
pg_dump --schema-only --no-owner --no-acl corpsite | psql ...corpsite_wp_access_002_test
```

No source data was copied, no full restore was performed, and no Alembic
command was run.  A read-only check confirmed `public.roles` exists in the
test database.  With `TEST_DATABASE_URL` set only for the pytest process and
the project DB guard binding the application engine exclusively to that target,
the following set was run (a second `--tb=no` run recorded concise totals):

```powershell
python -m pytest -q --tb=no `
  tests/test_wp_access_002_read_preview.py `
  tests/test_adr045_hr_head_auth_me.py `
  tests/test_adr042_phase_b3_access_resolver.py
```

Actual result: **1 passed, 0 failed, 13 errors, 0 skipped**.  The 13 errors
all occurred in the standard `seed` fixture before endpoint assertions: it
creates an `org_units` row with `group_id=1`, while the schema-only database
has no corresponding `deps_group` bootstrap row.  Thus runtime endpoint
behaviour remains **not verified**.  The missing bootstrap data is neither a
WP-ACCESS-002 defect nor in scope to repair; no application, fixture,
historical migration, or local source data was changed.  The temporary
database, container, and its owned volume are removed after this record.

### Final fixture correction result (2026-09-22)

Changed only `tests/conftest.py`: `seed` now creates a disposable
`deps_group` with `INSERT ... RETURNING`, passes that generated identifier to
`create_unit`, and removes the group after its unit. It no longer assumes
`group_id=1` exists.

With a fresh one-database PostgreSQL 16 container and the same schema-only
restore, the requested test set returned: **1 passed, 4 failed, 6 errors,
3 skipped**. The prior `deps_group` foreign-key error is resolved. The six
WP-ACCESS-002 errors now occur before endpoint assertions because that test's
`access_case` fixture selects an existing `positions` row from the empty
schema-only database. This is test bootstrap outside the requested minimal
`seed` correction, not a direct WP-ACCESS-002 runtime defect; it was not
expanded further. No production seed, migration, working database, or
application access logic was changed.

Final fixture run: `tests/test_wp_access_002_read_preview.py` — **6 passed, 1 failed, 0 errors, 0 skipped**; the remaining ambiguity assertion conflicts with the schema-only `uq_users_employee_id` uniqueness constraint, so it was not masked and the conditional related-test run was not started.

Final results: `tests/test_wp_access_002_read_preview.py` — **7 passed**; `tests/test_adr045_hr_head_auth_me.py` plus `tests/test_adr042_phase_b3_access_resolver.py` — **0 passed, 4 failed, 0 errors, 3 skipped**.

Final combined result: **11 passed, 0 failed, 0 errors, 3 skipped**. The four former access-resolver failures all lacked the pre-seeded `ACCESS_OBSERVER`, `ACCESS_MANAGER`, or `ACCESS_ADMIN` catalogue rows; the resolver test module now creates and removes only those rows. The combined run also exposed a seed role-ID collision with privileged configuration, fixed by moving ephemeral seed role IDs above the configured reserved range before creation.
