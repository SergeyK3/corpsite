# WP-TD-005 — Operational sign-off и rollout checklist

| Поле | Значение |
|---|---|
| Scope | Только `APPLICANT_ONLY`; Employee execution запрещён |
| Engineering validation | **PASS** на disposable PostgreSQL 16, 2026-09-05 |
| Operational sign-off | **NOT APPROVED** |
| Feature flag | **OFF; включение этим документом не разрешено** |

Этот checklist не является разрешением на deployment или удаление данных. Все пункты выполняются в отдельном утверждённом change window. Любой незакрытый пункт сохраняет `TEST_PERSONNEL_DELETION_EXECUTION_ENABLED=OFF` и запрещает выдачу execution capability.

## A. Артефакт и схема

- [x] Единственная Alembic head в исходниках: `td005exec501`.
- [x] Upgrade → downgrade → upgrade доказан на пустых disposable DB из `template0`.
- [x] F-CATALOG smoke и неизвестный inbound FK/CASCADE fail closed доказаны на disposable schema.
- [x] PostgreSQL major тестов — 16; репозиторный `docker-compose.yml` использует PostgreSQL 16.
- [ ] Независимо подтвердить major и текущую Alembic revision целевой среды read-only проверкой; не использовать это подтверждение как автоматический allowlist update.
- [ ] Выполнить read-only preflight на наличие legacy command tombstones. Любая строка со старым caller-controlled `source_command_id` блокирует upgrade и требует отдельного решения; автоматический перенос запрещён.
- [ ] Зафиксировать reviewed F-CATALOG hash целевой revision. Любое отличие table/column/FK/`ON DELETE`/trigger/function/logical relation — STOP.

## B. Recovery и наблюдаемость

- [ ] Создать шифрованный pre-change `pg_dump -Fc`, проверить checksum, владельца, срок хранения и путь вне репозитория.
- [ ] На отдельной нерабочей БД выполнить restore drill и доказать читаемость control-plane, provenance, history, attempts и tombstones.
- [ ] Настроить alerts/dashboards только по безопасным кодам и technical IDs: `COMPLETED`, `REAPPROVAL_REQUIRED`, `FAILED`, незавершённый `INTENT`, serialization retry exhaustion, catalog/snapshot drift. SQL text, raw payload и PII запрещены.
- [ ] Проверить recovery-процедуру для `INTENT` без `RESULT`: никакого автоматического повторного DELETE; оператор сверяет request/audit и начинает новую ручную попытку только по утверждённой процедуре.
- [ ] Назначить incident owner и канал эскалации; rollback кода не считается восстановлением уже успешно удалённых данных.

## C. Permission и kill procedure

- [x] Кодовая матрица выдаёт `TEST_PERSONNEL_DELETION_EXECUTE` только `ADMIN`; `HR_HEAD` его не получает.
- [x] Approver/executor separation проверяется сервером.
- [ ] До rollout доказать запросом access-control, что capability не выдана ни одному пользователю целевой среды.
- [ ] Отрепетировать немедленный отзыв role grant/capability и проверить, что `/auth/me` возвращает `can_execute_test_personnel_deletion=false`.
- [ ] Отрепетировать kill sequence: flag OFF → рестарт/перезагрузка backend config → capability revoke → проверка `503 TD_EXECUTION_DISABLED` без DML.
- [ ] Назначить двух разных людей: `HR_HEAD` approver и `ADMIN` executor.

## D. Поэтапный rollout

- [ ] Получить отдельное письменное утверждение change window и список ответственных.
- [ ] Сделать backup и закрыть разделы A–C.
- [ ] Применить migrations при flag OFF и без execution capability; выполнить read-only catalog/provenance/control-plane validation.
- [ ] Развернуть backend/frontend при flag OFF; подтвердить, что ADMIN видит disabled кнопку с причиной «Исполнение удаления отключено», а `HR_HEAD` кнопку не видит.
- [ ] Повторить mocked frontend regression и disposable PostgreSQL suite на точном release artifact.
- [ ] Закрыть три существующих `no-explicit-any` в `corpsite-ui/lib/types.ts` отдельным type-cleanup изменением и получить зелёный file-level ESLint; Stage 7 не расширяет scope ради этого cleanup.
- [ ] Только после отдельного sign-off разрешить ограниченную выдачу capability и отдельное решение о включении flag. Настоящий документ такого разрешения не даёт.
- [ ] Для первой логической попытки использовать только заново созданный Manifest v2 request, новое approval и ручную подтверждающую фразу; v1/legacy и Employee requests запрещены.
- [ ] После результата сверить status, append-only EXECUTE history, INTENT/RESULT, table counts/hashes, tombstones и отсутствие dangling references; не выводить raw rows.

## E. Немедленный STOP

Остановить rollout и оставить flag OFF при любом из условий:

- revision/major/catalog hash не совпадает с reviewed allowlist;
- есть неизвестный FK, CASCADE, trigger, logical relation или relationship rule;
- provenance отсутствует, отозван или изменён;
- snapshot/approval/expiry/target count изменились;
- присутствует Employee/User, merge, BLOCK или mixed process;
- failed backup/restore drill, отсутствует monitoring либо capability revoke не доказан;
- regression/concurrency/fault-injection/build/lint не проходит;
- audit/tombstone содержит PII/raw payload или попытка не имеет durable INTENT/RESULT.

## F. Подписи будущего change window

| Роль | ФИО/technical identity | Дата | Решение |
|---|---|---|---|
| Engineering owner |  |  |  |
| DBA/Operations |  |  |  |
| Security/Privacy |  |  |  |
| HR_HEAD approver representative |  |  |  |
| ADMIN executor representative |  |  |  |

Пока все обязательные поля и checkbox не закрыты, итоговое решение: **NO-GO**.
