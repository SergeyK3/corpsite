# WP-TD-005 — Поэтапный план execution для удаления тестовых претендентов

| Поле | Значение |
|---|---|
| Статус | **Implementation plan — execution запрещён до закрытия всех gates** |
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

Не переходить к этапу 6, пока backend не проходит все PostgreSQL integration и failure-injection tests; endpoint остаётся недоступным для production grants.

**Старые запросы**

Backend принимает только manifest v2 и `APPLICANT_ONLY`. Для v1/legacy используется стабильный non-retryable отказ с указанием создать и заново согласовать v2 request; auto-conversion запрещён.

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

Схема `b1c2d3e4f5a6` на момент этого плана не готова к execution. Готовность наступает только после последовательного закрытия этапов 1–7 и всех gates WP-TD-004; сам этот документ не разрешает миграции, API, UI, DML или удаление данных.
