ADR-022 — Events Delivery Queue as Single Source of Truth
Status

Accepted

Context

В системе Corpsite реализована событийная модель обработки задач:

task_events

task_event_recipients

task_event_deliveries

События возникают при переходах FSM (например: REPORT_SUBMITTED, APPROVED, REJECTED).

Изначально рассматривались два режима доставки событий в Telegram:

Per-user polling (/my-events)

Delivery-queue polling (/tasks/internal/pending-deliveries)

Необходимо было зафиксировать устойчивую долгосрочную архитектуру, исключающую:

дублирование источников истины

гонки курсоров

расхождения backend ↔ bot

повторную отправку сообщений

Decision

Принято архитектурное решение:

1️⃣ Backend — единственный источник истины

Истиной считаются данные таблицы:

public.task_event_deliveries


Статус доставки фиксируется только через backend:

PENDING

SENT

FAILED

Telegram-бот не является источником состояния.

2️⃣ Используется исключительно Delivery Queue mode

Бот работает только через:

GET /tasks/internal/pending-deliveries
POST /tasks/internal/ack-delivery


Per-user polling считается legacy-режимом и не используется в production.

3️⃣ Курсор — композитный

Используется композитный курсор:

(audit_id, user_id)


Файл хранения:

DATA_DIR/bot_deliveries_cursor_telegram.json


Формат:

{
  "cursor_audit_id": 98,
  "cursor_user_id": 1
}


Это гарантирует:

отсутствие зацикливания на одном audit_id

корректную обработку нескольких получателей

строгий порядок обработки

4️⃣ CursorStore (legacy)

CursorStore используется только для:

events_cursor.json


И сохраняет последний обработанный audit_id
для совместимости и аналитики.

Основной курсор — delivery composite cursor.

5️⃣ Бот — транспортный слой

Telegram-бот:

получает pending deliveries

отправляет сообщение

вызывает ack_delivery

двигает курсор

Бот:

не создает событий

не изменяет статус задач

не хранит состояние бизнес-логики

Consequences
Положительные

Строгая однонаправленная модель

Backend контролирует состояние

Возможна замена Telegram на другой канал (email, push)

Горизонтальное масштабирование ботов

Повторная отправка контролируется backend

Отрицательные

Повышенные требования к корректности internal API

Необходимость поддержки composite cursor

Verified Behavior (2026-02-13)

Проверено на задаче:

task_id = 325


Подтверждено:

создаются события REPORT_SUBMITTED, APPROVED

создаются записи в task_event_deliveries

telegram status = SENT

sent_at фиксируется backend

курсор двигается до (98, 1)

Long-term Principle

Backend управляет состоянием.
Бот — только доставляет.
Истина хранится в БД.