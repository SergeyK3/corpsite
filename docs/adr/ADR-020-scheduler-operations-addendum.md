# ADR-020 Addendum: Regular Tasks Scheduler — Operations (RTS)

## Статус
Принято (2026-07-02)

## Связь
Расширяет [ADR-020-regular-tasks-contract-v1.md](./ADR-020-regular-tasks-contract-v1.md) — контракт генератора и endpoint'ов без изменения бизнес-алгоритма.

Эксплуатация: [REGULAR_TASK_SCHEDULER_RUNBOOK.md](../ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md).

---

## Контекст

Operational audit выявил отсутствие persistent trigger для `POST /internal/regular-tasks/run` в deploy pipeline. При проектировании timer возник вопрос: должно ли время запуска вычисляться из `MAX(schedule_params.time)` активных шаблонов.

**Решение:** время scheduler — **эксплуатационная константа**; шаблоны ей соответствуют. Направление зависимости: **Infrastructure → Business**, не наоборот.

---

## RTS-1 — Daily invoke

**Scheduler запускается ровно один раз в сутки в 08:30 Asia/Almaty (UTC+5).**

- Механизм: `corpsite-regular-tasks.timer` → `scripts/ops/run_regular_tasks_cron.sh` → `POST /internal/regular-tasks/run`.
- На VPS с системными часами UTC: `OnCalendar=*-*-* 03:30:00`.
- Альтернатива host cron допустима при том же скрипте и том же времени; systemd timer — стандарт проекта (ADR-INFRA-005).

`schedule_params.time` в шаблоне — **time gate в due-день** (с какого локального момента шаблон считается создаваемым), а не расписание cron.

---

## RTS-2 — Соответствие шаблонов времени scheduler

Для всех **активных** шаблонов, у которых задан `schedule_params.time`:

**`time` ≤ 08:30** (локальное, UTC+5).

Если `time` не задан — time gate не применяется; due-день обрабатывается при единственном суточном запуске.

### Запрещено

Подбирать или менять время systemd timer / cron по агрегату `MAX(schedule_params.time)` из `regular_tasks`. Это делает инфраструктуру зависимой от бизнес-данных и ломает GitOps.

### Backlog (не реализовано)

Backend-валидация при create/update шаблона:

- env или константа `REGULAR_TASKS_SCHEDULER_DAILY_RUN_TIME=08:30`;
- если `schedule_params.time` > лимита → HTTP 422 с понятным сообщением;
- одноразовый ops SQL audit существующих шаблонов на VPS перед включением валидации.

---

## RTS-3 — Scheduler не восполняет пропуски

**Scheduler (`/internal/regular-tasks/run`) не выполняет backfill** пропущенных due-дней и отчётных периодов.

- Каждый invoke обрабатывает только **текущую** локальную дату (`today`) и шаблоны, due на этот день.
- Пропущенные периоды восстанавливаются через **catch-up** (`POST /internal/regular-tasks/catch-up` / UI `/admin/regular-tasks/catch-up`) — отдельный контракт, `run_kind=catch_up`.

**Scheduler ≠ catch-up.**

После длительного простоя:

1. Восстановить timer (устранить первопричину отсутствия automatic runs).
2. Выполнить catch-up для накопившихся пропущенных периодов (устранить последствия).

---

## RTS-4 — Infrastructure → Business

| Слой | Ответственность |
|------|-----------------|
| **Infrastructure** | Фиксированное время daily invoke (08:30 +05), unit-файлы в git, auth env |
| **Generator** | due-check, time gate, period resolve, dedupe, journal |
| **Business (`regular_tasks`)** | schedule_type, byweekday/bymonthday, time (≤ 08:30), offsets |

Время scheduler **задаётся инфраструктурой**, а не содержимым таблицы `regular_tasks`.

Изменение политики времени (например с 08:30 на 10:00) — решение ops/ADR + обновление timer и runbook, **не** следствие редактирования шаблона.

---

## Последствия

Плюсы:

- Предсказуемый deploy на всех средах.
- Ясное разделение scheduler vs catch-up.
- Админ понимает: panel «Автоматический запуск» отражает automatic `/run`, не catch-up.

Ограничения:

- Шаблон с `time` > 08:30 не сработает при единственном daily run (до введения RTS-2 validation — ops audit вручную).
- Смена RTS-1 требует ADR/runbook update, не только правки шаблона.

---

## Связанные артеfacts

| Artifact | Path |
|----------|------|
| systemd timer | `deploy/systemd/corpsite-regular-tasks.timer` |
| Invoke script | `scripts/ops/run_regular_tasks_cron.sh` |
| Runbook | `docs/ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md` |
| Audit script | `scripts/ops/ops_regular_tasks_scheduler_audit.py` |
