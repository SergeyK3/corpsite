# WP-PPR-MIG-001 — Этап 1: общие сведения

| Статус | **Implemented — Accepted after Visual Review** |
|---|---|
| Основание | Program plan, Stage 0 frozen cohort, WP-PPR-IDENTITY-001 |

## Состав и граница

Подтверждённый mapping: `full_name`, `last_name`, `first_name`, `middle_name`,
`iin`, `birth_date` из normalized control-list payload в одноимённые пустые поля
`persons`. ФИО на части разбирается только как два или три неинициальных токена.
Контакты, кадровые отношения, образование и остальные sections не входят в Stage 1.

## Draft execution и visibility

PREVIEW создаёт отдельный Stage 1 run и private participant drafts. До ACCEPTED
они не меняют Person/PPR; employee read paths не используют таблицы draft, а HR_HEAD
с `PPR_STAGE1_GENERAL_MANAGE` видит source/current/proposal. Каждый execute-next
обрабатывает одну позицию. Ошибка переводит run в `PAUSED_ON_ERROR`; после исправления
повтор начинается с этой позиции.

## Acceptance

Перед acceptance сервер заново выводит и блокирует весь cohort в SERIALIZABLE
транзакции. Любой stale link/source или canonical conflict откатывает всё. При успехе
заполняются только всё ещё пустые Person fields, при отсутствии materialized PPR
создаётся envelope в `COLLECTING`, добавляется safe PPR event, run становится ACCEPTED.

## Принятие после visual review

Локальный visual pilot в `corpsite_test` принят 2026-09-09: Stage 1 run №15 переведён в `ACCEPTED`. Это подтверждает результат синтетического тестового контура, а не является production-принятием.

Проверены и приняты следующие сценарии:

- черновые значения видны HR_HEAD, а до `ACCEPTED` канонические Person/PPR и представление сотрудника не изменяются;
- конфликт канонического непустого значения останавливает run, показывает конкретное конфликтующее поле и переводит выполнение в паузу;
- pause/resume повторяет остановленную позицию и не изменяет ранее успешно обработанных участников;
- org scope применяется fail-closed; run вне scope не открывается;
- принятие повторно валидирует набор и атомарно переносит все подтверждённые значения либо полностью откатывается при stale/conflict;
- итоговый экран после `ACCEPTED` текстом показывает принятие, записанные данные, сохранённое «Было в карточке», время организации и не раскрывает полный ИИН;
- повторное принятие уже принятого run не создаёт новых записей или PPR-событий.

Финальная локальная регрессия: PostgreSQL Stage 0/1 — 9 passed; frontend Stage 0/1 — 8 passed.
