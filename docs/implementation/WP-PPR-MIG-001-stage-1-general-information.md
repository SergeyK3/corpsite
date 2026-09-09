# WP-PPR-MIG-001 — Этап 1: общие сведения

| Статус | **Implemented — Ready for Visual Review** |
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
