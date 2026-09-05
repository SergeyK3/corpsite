# WP-TD-005 — Поэтапный план execution для удаления тестовых претендентов

| Поле | Значение |
|---|---|
| Статус | **Этапы 1–5 реализованы; Stage 5 hardening завершён, feature flag выключен; этапы 6–7 не начаты** |
| Дата | 2026-09-05 |
| Основание | `test-personnel-data-deletion-approval-plan.md`, `WP-TD-004-test-personnel-deletion-relationship-matrix.md` |
| Scope | Только synthetic applicants без `Employee` и любых `BLOCK`-связей |

## 1. Правила выполнения плана

Каждый раздел ниже — отдельное небольшое задание Codex. Этап начинается только после успешного завершения и проверки предыдущего. Любая ошибка, неизвестная связь, schema drift, несовпадение hash/count или неполное доказательство безопасности останавливает работу; переход к следующему этапу запрещён.

Общие инварианты:

- manifest имеет тип `APPLICANT_ONLY`, корень `PERSON` и полный неизменяемый список всех application IDs каждого Person;
- Person допускается только при `person_status='active'`, `merged_into_person_id IS NULL`, отсутствии входящих merge-связей, `Employee` и любого `BLOCK`;
- претенденты и сотрудники не смешиваются в одном запросе; employee deletion остаётся отдельным будущим процессом;
- manifests прежних версий доступны только для просмотра, анализа и аудита, но никогда не исполняются и не обновляются автоматически до v2;
- все проверки выполняются сервером fail closed; UI, permission и `ON DELETE CASCADE` не считаются доказательством допустимости удаления.

## 2. Этап 1 — Manifest v2: PERSON-root и полный список applications

**Ожидаемые изменения**

- Ввести версионированный manifest v2 с `process_type=APPLICANT_ONLY`, корневым `person_id` и отдельным полным, отсортированным списком всех `application_id` этого Person.
- Включить в target-set hash версию формата, тип процесса, Person set и списки applications; сделать manifest и его projections неизменяемыми после фиксации.
- На create, submit, approve и будущий execute повторно доказывать равенство frozen application set фактическому полному application set каждого Person.
- Запретить включение `Employee`, смешанного типа целей, inactive/merged Person и неполного application set.

**Обязательные проверки**

- PostgreSQL-тесты ограничений, неизменяемости, детерминированной сортировки/hash и Person с нулём, одной и несколькими applications.
- Негативные тесты для пропущенной/лишней application, второго Person, merge drift, `Employee` и попытки изменить frozen target.
- Проверка, что любое изменение полного application set переводит запрос в `REAPPROVAL_REQUIRED` без DML.

**Gate**

Не переходить к этапу 2, пока manifest v2 нельзя атомарно создать и проверить, а все негативные сценарии не завершаются fail closed.

**Старые запросы**

Manifest v1/`LEGACY_MANIFEST` остаётся читаемым с исходными статусами и аудитом. Execute для него всегда отклоняется стабильным безопасным кодом; требуется новый v2 request и новое согласование `HR_HEAD`.

### Результат этапа 1 — 2026-09-05

**Завершено.** Добавлена revision `td005m1v2a01` поверх `b1c2d3e4f5a6`: request получил неизменяемые `manifest_version` и `process_type`, а канонические PERSON-roots сохраняются отдельно с полным строго возрастающим `application_ids[]`. Application-target rows оставлены как совместимая projection существующего preview/create/approval workflow.

Backend создаёт только manifest v2/`APPLICANT_ONLY`, считает target-set hash по Person и полному списку applications, повторно проверяет полноту перед submit/approve и отклоняет v1 submit/approve кодом `TD_MANIFEST_V1_READ_ONLY`. Старые requests остаются доступными для чтения с `manifest_read_only=true`, `approval_eligible=false`, `execution_eligible=false`; автоматического upgrade нет.

Проверено на одноразовых PostgreSQL-клонах: upgrade → downgrade → upgrade, одна Alembic head, 7 целевых тестов Manifest v2 и 224 существующих foundation/relationship regression-теста. Этап 2 разрешено планировать, но tombstone gate ещё не реализован и execution остаётся запрещён.

## 3. Этап 2 — PII-free tombstones

**Ожидаемые изменения**

- Добавить append-only tombstones для `personnel_record_events`: event ID, тип, timestamp и digest.
- Добавить detached append-only tombstones для `ppr_command_executions`: command ID/type/status и digests request/result без raw payload.
- Добавить append-only tombstones для разрешённого early `personnel_application_lifecycle_audit`: application ID, action, timestamp, technical actor ID и metadata digest.
- Определить retention contract и атомарное правило: tombstone создаётся и проверяется в той же транзакции до удаления исходной строки; отсутствие tombstone оставляет связь `BLOCK`.

**Обязательные проверки**

- Тесты неизменяемости tombstones, детерминированности digest, уникальности source IDs и rollback при конфликте/ошибке.
- Автоматическая проверка PII: tombstone не содержит ФИО, ИИН, телефоны, e-mail, raw metadata/request/result или восстановимый payload.
- Тесты полноты: число и hash tombstones совпадают с frozen source set; повторная запись идемпотентна либо безопасно отклонена.

**Gate**

Не переходить к этапу 3, пока для каждого `TOMBSTONE_REQUIRED` класса не доказаны полнота, PII-free состав, append-only защита и атомарный rollback.

**Старые запросы**

Появление tombstone support не делает v1/legacy requests исполнимыми. Ранее согласованный v2 request требует нового fingerprint и повторного согласования, если tombstone policy/version не входили в его approval hash.

### Результат этапа 2 — 2026-09-05

**Завершено.** Добавлена revision `td005tomb201` поверх `td005m1v2a01` с тремя detached tombstone-таблицами для `personnel_record_events`, `ppr_command_executions` и разрешённых early-событий `personnel_application_lifecycle_audit`. В них сохраняются только technical source IDs, тип/действие, статус, исходные timestamps, допустимый numeric actor technical ID и SHA-256 digests. Единственная FK каждой tombstone-таблицы ведёт к сохраняемому deletion request с Manifest v2/`APPLICANT_ONLY`; FK на `Person` и application отсутствуют.

Запись реализована отдельным transaction-neutral backend-сервисом, который не подключён к route, endpoint или execution workflow. Canonical digest детерминирован; повторная запись того же source ID с тем же содержимым идемпотентна, а конфликт request/digest отклоняется. `UPDATE`, `DELETE` и `TRUNCATE` запрещены PostgreSQL triggers; downgrade с сохранёнными tombstones также закрыт. Raw payload/comment/metadata и другие PII не переносятся, исходные строки не удаляются.

Проверено только на одноразовых PostgreSQL-клонах: upgrade → downgrade → upgrade, запрет downgrade с сохранёнными tombstones, одна Alembic head `td005tomb201`, 9 целевых tombstone-тестов, совместный набор этапов 1–2 (`16 passed`) и 246 существующих migration/foundation/relationship regression-тестов. Tombstone gate этапа 2 закрыт; execution остаётся запрещён до последовательного завершения этапов 3–7 и всех gates WP-TD-004.

## 4. Этап 3 — Provenance, catalog и relationship fingerprint

**Ожидаемые изменения**

- Требовать active append-only provenance с artifact hash; `LEGACY_MANIFEST` оставить только для анализа/approval.
- Реализовать `F-CATALOG`: policy version, allowlisted Alembic revisions, ожидаемые tables/columns, значимые FK и защитные triggers.
- Ввести versioned server-owned registry FK и логических связей, включая `personnel`, `contacts`, `key_contacts`, `employees_import_stage`, polymorphic targets и транзитивные satellites из WP-TD-004.
- Сформировать canonical batch fingerprint из `F-ROOT`, `F-ROW`, `F-JOIN`, `F-CONTROL`, `F-CATALOG`, полного application set, provenance, tombstones и preserved-audit digests.
- Оставить `access_grants`, blobs и неизвестные связи `BLOCK`; `intake_submitted` допускать только с active provenance и действующей `submitted_synthetic_confirmed=true` attestацией `HR_HEAD`.

**Обязательные проверки**

- PostgreSQL catalog-тесты для добавленного/изменённого/удалённого FK, column, trigger, logical relation и несовместимой Alembic revision.
- Тесты детерминированности fingerprint и изменения hash при любом значимом row/catalog/policy drift.
- Проверки, что preserved `SET NULL` audit до detach содержит достаточные technical IDs/digests; иначе связь становится `BLOCK`.
- Негативные тесты для отсутствующего/неактивного provenance, неверного artifact hash, `access_grants`, blob и неизвестного satellite.

**Gate**

Не переходить к этапу 4 при неполном registry, неподдерживаемой revision, недетерминированном fingerprint или любом неизвестном inbound/logical link.

**Старые запросы**

Запрос без текущих provenance, catalog и relationship policy versions не исполняется. Изменение любой версии аннулирует старое approval и требует нового v2 request либо `REAPPROVAL_REQUIRED` с повторным рассмотрением.

### Результат этапа 3 — 2026-09-05

**Завершено.** Добавлена revision `td005fp3v101` поверх `td005tomb201`. Provenance получил append-only состояния `ACTIVE`/`REVOKED`, строго возрастающую версию и защиту от `UPDATE`, `DELETE` и `TRUNCATE`. Future-execution readiness требует последнюю active PERSON-provenance текущего environment с валидным artifact SHA-256; отсутствие, отзыв, новая версия или новый artifact hash меняют fingerprint. `LEGACY_MANIFEST` и запросы со старой fingerprint version остаются читаемыми, но не могут считаться пригодными к будущему execution.

Добавлены versioned server-owned `WP-TD-CATALOG/v1`, relationship policy `WP-TD-005-APPLICANT/v1` и fingerprint `WP-TD-RELATIONSHIP/v2`. `F-CATALOG` фиксирует совместимую Alembic revision, полный контракт значимых columns с defaults/collations, FK и `ON DELETE`, определения защитных triggers и их functions, а также versioned registry физических и legacy logical relations. Allowlist использует статический reviewed hash и закрывается при неизвестной revision, table/column/FK/trigger/function/logical-link drift или неполном/неизвестном rule.

Canonical relationship fingerprint включает PERSON-root Manifest v2 и полный application set, F-ROOT/F-ROW/F-JOIN, PERSON-provenance, catalog/policy versions и полный отсортированный registry действий `DELETE`/`BLOCK`/`PRESERVE`. Добавлены отдельный `BLOCK` для inactive/merged root и отдельные rules для ранее неявных order/onboarding/migration, Employee-context, security и каждой перечисленной User satellite; polymorphic `access_grants` и legacy logical relations учитываются явно. Fingerprint и catalog hash фиксируются в request и approval decision; изменение данных, provenance, policy, catalog или состава manifest требует нового согласования.

Проверено только на одноразовых PostgreSQL-клонах: upgrade → downgrade → upgrade, одна Alembic head `td005fp3v101`, 15 целевых Stage 3 тестов, совместный набор этапов 1–3 (`31 passed`), полный 116-rule relationship behavior suite и 186 существующих migration/foundation regression-тестов. Этап 3 закрыт; запись tombstones, физическое удаление, execution endpoint, кнопка и Employee-процесс не добавлялись. Переход к этапу 4 допустим как отдельное задание, но execution остаётся запрещён до завершения этапов 4–7 и всех gates WP-TD-004.

## 5. Этап 4 — Permission и append-only EXECUTE audit

**Ожидаемые изменения**

- Защитить execution отдельной permission `TEST_PERSONNEL_DELETION_EXECUTE`; назначать её только утверждённым ADMIN grants, без role-name bypass.
- Сохранить separation of duties: исполнитель не является одобрившим `HR_HEAD`; `HR_HEAD` не исполняет удаление.
- Добавить append-only audit action `EXECUTE` и PII-free result projection: request/execution IDs, actor technical IDs, before/after hashes, policy/catalog versions, counts по таблицам и result code.
- Аудировать успешные, отклонённые и повторные попытки так, чтобы audit переживал domain deletion и поддерживал идемпотентное чтение результата.

**Обязательные проверки**

- Permission matrix tests для ADMIN, `HR_HEAD`, пользователя без capability и пользователя с конфликтом ролей.
- Тесты append-only guards, PII-free projection, полноты success/failure result и невозможности изменить/удалить audit.
- Проверка, что permission не обходит manifest, approval, provenance, fingerprint или relationship gates.

**Gate**

Не переходить к этапу 5, пока не доказаны server-side capability check, separation of duties и неизменяемая аудитная запись каждого execution outcome.

**Старые запросы**

Наличие permission никогда не разрешает исполнить v1/legacy request. Такая попытка получает отказ и отдельную PII-free audit-запись без domain DML.

### Результат этапа 4 — 2026-09-05

**Завершено.** Зарезервированная foundation permission `TEST_PERSONNEL_DELETION_EXECUTE` включена в действующую capability matrix как отдельное право: default role grant остаётся только у `ADMIN`, `HR_HEAD` его не получает, а `/auth/me` публикует `can_execute_test_personnel_deletion`. Request, approve и execute capabilities вычисляются независимо; наличие execute capability не создаёт route, endpoint или UI-кнопку.

Добавлен неподключённый к workflow server-side contract проверки исполнителя: executor обязан быть active `ADMIN` с execute permission и не может совпадать с пользователем, записавшим действующее `APPROVE`-решение как `HR_HEAD`. Проверка сверяет frozen approval version и hashes, но сама ничего не исполняет.

Revision `td005audit401` расширяет сохраняемую history действием `EXECUTE`, добавляет защиту от `TRUNCATE` и строгий PII-free INSERT contract. Projection допускает только request/executor technical IDs, approved manifest/fingerprint/policy/catalog versions и hashes, отсортированные table counts, before/after hashes, opaque UUID idempotency key, server timestamp, result и безопасный error code. ФИО, ИИН, контакты, raw payload, произвольные поля и тексты ошибок отклоняются PostgreSQL guard/check; `UPDATE`, `DELETE` и `TRUNCATE` запрещены. Transaction-neutral writer не подключён к route или workflow: одинаковый key/content возвращает сохранённую projection, другой content отклоняется.

Проверено только на одноразовых PostgreSQL-клонах: upgrade → downgrade → upgrade, одна Alembic head `td005audit401`, 8 целевых permission/API/audit-тестов, совместный набор этапов 1–4 (`39 passed`) и полный regression suite (`341 passed`). В тестах EXECUTE rows всегда откатывались вместе с одноразовыми клонами; рабочая БД не изменялась. Этап 4 закрыт, но физическое удаление, tombstone writes, execution endpoint, кнопка и Employee-процесс не добавлялись.

## 6. Этап 5 — Транзакционный execution backend

**Ожидаемые изменения**

- Реализовать один applicant-only execution command/API только для approved manifest v2; повторный вызов завершённого request возвращает сохранённый результат и ничего не удаляет.
- Открывать новую `SERIALIZABLE` транзакцию, блокировать request и root Person rows; при недостаточности SSI применять единый доказанный per-Person advisory-lock protocol для всех writers.
- В `R0` повторно проверить environment/revision, permission, separation of duties, status/expiry/version, target hash, полный application set, provenance, attestations, `F-CATALOG`, fingerprint и отсутствие всех `BLOCK`.
- В той же транзакции создать/проверить tombstones и выполнить только explicit DELETE по frozen IDs в порядке WP-TD-004: drafts (`D1`), links (`D2`), разрешённые journals, metadata (`D3`), все applications (`D4`), Person (`D5`).
- Для каждого шага применять `RETURNING`, expected count/hash; перед commit проверить исчезновение roots, сохранность audit/provenance, ожидаемый `SET NULL` и отсутствие dangling logical references.
- Любое расхождение полностью откатывает DML; data drift переводит request в `REAPPROVAL_REQUIRED`, безопасная техническая ошибка фиксируется как failed attempt без частичного удаления.

**Обязательные проверки**

- PostgreSQL integration tests полного порядка `R0/D1…D5`, атомарности tombstone+delete, rollback на каждом шаге и отсутствия неявного cascade cleanup.
- Негативные тесты для stale/expired approval, неверной confirmation, count/hash drift, нового child row, `Employee`, merge, `BLOCK`, повторного и параллельного execute.
- Проверка идемпотентности, точных counts/result hash и отсутствия domain DML при любом precondition failure.

**Gate**

Не переходить к этапу 6, пока backend не проходит все PostgreSQL integration и failure-injection tests; feature flag остаётся выключенным по умолчанию и не включается до отдельного rollout-решения этапа 7.

**Старые запросы**

Backend принимает только manifest v2 и `APPLICANT_ONLY`. Для v1/legacy используется стабильный non-retryable отказ с указанием создать и заново согласовать v2 request; auto-conversion запрещён.

**Результат этапа 5 (реализован)**

Добавлен `POST /directory/test-personnel-deletion/requests/{request_id}/execute` с обязательными opaque UUID `idempotency_key` и точной фразой `УДАЛИТЬ {request_number} / {target_count}`. Endpoint доступен только активному `ADMIN` с `TEST_PERSONNEL_DELETION_EXECUTE` и по умолчанию закрыт `TEST_PERSONNEL_DELETION_EXECUTION_ENABLED=false`; UI и employee execution не добавлялись.

Revision `td005exec501` добавляет terminal status `COMPLETED`, append-only execution attempts, разрешённые EXECUTE audit transitions и PostgreSQL advisory-lock guards для legacy Person relations без FK. Execution выполняет повторный fail-closed `R0` в новой `SERIALIZABLE` транзакции, блокирует request/approval/Person/frozen Application и server-owned relationship tables, проверяет manifest/provenance/catalog/fingerprint/approval/attestation и отсутствие всех `BLOCK`. Drift атомарно фиксируется как `REAPPROVAL_REQUIRED`, обнуляет approval timestamps, увеличивает version и сохраняет безопасный EXECUTE audit без DELETE.

Разрешённый путь выполняет только explicit `DELETE … RETURNING` по frozen IDs в порядке `D1 → D2 → tombstones → journals → D3 → D4 → D5`, сверяет count/hash каждого source set, before/after IDs/count/digests всех `PRESERVE` rules и допустимые `SET NULL`, сохраняет request/targets/manifest/decision/history/provenance и записывает PII-free `TD_EXECUTION_COMPLETED` audit в той же транзакции. До domain transaction коммитится append-only `INTENT`; успех/`REAPPROVAL_REQUIRED` получает `RESULT` в domain transaction, а после rollback надёжно сохраняются `RESULT=TD_EXECUTION_FAILED` и безопасный audit. Crash между ними оставляет обнаруживаемый незавершённый `INTENT`. Одинаковый UUID/content возвращает сохранённую projection; тот же UUID с другим payload даёт `409`; для `COMPLETED` только исходный UUID replayable, новый UUID связывается с failed attempt и получает `409 TD_EXECUTE_ALREADY_COMPLETED`.

После adversarial hardening F-CATALOG учитывает каждый входящий FK к любой D1–D5/journal delete table независимо от владельца и `ON DELETE`; неизвестный `CASCADE` даёт catalog drift до DELETE. Caller-controlled `ppr_command_executions.command_id` больше не сохраняется: tombstone содержит server-generated numeric source PK и SHA-256 source-reference digest с DB constraints. UUID-контракт принимает любой канонический UUID, включая v7. Downgrade выполняет preflight `COMPLETED`/несовместимых EXECUTE transitions/attempts/command tombstones до изменения constraints и fail closed на непустой несовместимой схеме.

Upgrade также fail closed, если в старой command-tombstone таблице уже есть строки с caller-controlled `source_command_id`: автоматический перенос потенциальной PII запрещён. Перед rollout требуется отдельный read-only preflight и утверждённое решение по таким legacy tombstones; удалять или преобразовывать их эта revision не пытается.

PostgreSQL-набор покрывает template0 migration roundtrip, single head/F-CATALOG, неизвестный FK-child с `ON DELETE CASCADE`, feature flag/API/permission/separation, success с тремя tombstone-классами, PII-shaped command IDs, DB digest constraint, v1/legacy/expired/Employee/drift, durable intent, replay/conflict/completed-key policy, rollback fault injection после каждого шага, параллельный execute, конкурентные FK и logical inserts, реальные User/onboarding, photo/file, incoming document/attachment, personnel order, operational-order signing, verification, Telegram и security-grant строки, а также допустимые applicant-only `PRESERVE`/`SET NULL` контуры. Employee-only PRESERVE-контуры остаются недостижимыми для успешного applicant execution, потому что `EMPLOYEE_PRESENT` раньше переводит запрос в `REAPPROVAL_REQUIRED`; их строки не мутируются.

Все PostgreSQL-проверки запускаются только при явно заданном `TEST_DATABASE_URL` на loopback и с test-именем. Рабочий `.env` не читается. Каждый модульный DB fixture создаёт новую пустую БД `test_corpsite_td005_<random>_test` через `CREATE DATABASE … TEMPLATE template0`, применяет Alembic и добавляет только synthetic fixtures; копирование исходной БД или реальных данных отсутствует. При нарушении URL-условий guard завершает тест до создания engine/соединения/DDL. Feature flag остаётся выключенным по умолчанию; переход к UI/этапу 6 этим результатом не разрешён автоматически.

Итоговый изолированный guard + WP-TD-005 regression suite: `106 passed`; `git diff --check` чист, Alembic имеет одну head `td005exec501`. Повторный adversarial review не выявил незакрытых Critical/High/Medium/Low findings в scope этапа 5.

## 7. Этап 6 — Кнопка «Удалить одобренных тестовых претендентов»

**Ожидаемые изменения**

- В общей панели сисадмина показать для подходящего v2 request кнопку с точным названием **«Удалить одобренных тестовых претендентов»**.
- Capability-gate кнопки совпадает с server-side `TEST_PERSONNEL_DELETION_EXECUTE`; дополнительно UI требует `APPROVED`, действующий approval, v2, applicant-only type и доступный backend gate.
- Перед отправкой потребовать подтверждающую фразу с номером request или количеством Person; блокировать двойной submit и показывать неизменяемые approval/hash/count и результат исполнения.
- Не добавлять employee execution в MVP. Название будущей отдельной кнопки **«Удалить одобренных тестовых сотрудников»** резервируется для отдельного процесса в той же панели и общей очереди `HR_HEAD`.

**Обязательные проверки**

- Page-level regression tests на фактическое количество и точный текст кнопки: ровно одна applicant execution button только для допустимого v2 request и ни одной employee execution button в MVP.
- Тесты hidden/disabled states для отсутствующей capability, v1/legacy, drift/reapproval, expiry, non-approved/completed request и pending backend gate.
- Тесты confirmation, single-submit, ошибок backend и отсутствия оптимистического показа `COMPLETED` до подтверждённого ответа.

**Gate**

Не переходить к этапу 7 и не включать кнопку пользователям, пока page-level tests и server-side authorization tests не проходят совместно.

**Старые запросы**

Для v1/legacy request кнопка исполнения не отображается; UI показывает причину несовместимости и действие создания нового v2 request. UI не предлагает миграцию или повторное использование старого approval.

## 8. Этап 7 — PostgreSQL regression/concurrency tests и rollout

**Ожидаемые изменения**

- Добавить полный PostgreSQL regression suite для manifest, tombstones, provenance, catalog/relationship fingerprint, permission/audit и execution transaction.
- Добавить управляемые concurrency scenarios: создание application/child/BLOCK row между approval и execute, конкурирующие writers, два execute, deadlock/serialization retry и advisory-lock contract при его использовании.
- Зафиксировать compatibility tests: v1/legacy всегда non-executable; Employee и mixed requests всегда blocked; неизвестный schema/catalog drift всегда fail closed.
- Rollout выполнять поэтапно: сначала миграции и read-only validation, затем backend без выданной execution capability, затем ограниченный grant после PostgreSQL smoke checks и операционного sign-off.
- Определить kill procedure через отзыв execution capability/отключение applicant command. Rollback кода не пытается восстанавливать уже атомарно удалённые данные; результат остаётся в append-only audit/tombstones.

**Обязательные проверки**

- Все regression и concurrency tests проходят на PostgreSQL той же major version и совместимой Alembic revision, что production; SQLite не является приёмочной средой.
- Повторные прогоны подтверждают отсутствие flaky races, partial commits, dangling references, PII в projections и расхождений counts/hash.
- До выдачи capability проверены backup/restore runbook, monitoring безопасных result codes, отзыв permission и ручная сверка catalog compatibility.

**Gate**

Execution нельзя включать, если не пройден хотя бы один regression/concurrency/smoke test, revision отсутствует в allowlist, не закрыт operational sign-off или не проверена процедура немедленного отзыва capability.

**Старые запросы**

Rollout не меняет их статус и не делает их исполнимыми. Production smoke/regression suite обязательно доказывает отказ v1/legacy до выдачи execution capability.

## 9. Готовность execution

Baseline-схема `b1c2d3e4f5a6` не готова к execution. Этапы 1–4 добавляют revisions `td005m1v2a01`, `td005tomb201`, `td005fp3v101` и `td005audit401`, но готовность наступит только после последовательного закрытия этапов 5–7 и всех gates WP-TD-004. Физическое удаление, запись tombstones из execution, execution endpoint и кнопка удаления не создавались; audit writer и tombstones не подключены к execution.
