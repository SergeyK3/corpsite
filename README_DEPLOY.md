# Заметки По Развёртыванию Corpsite

Проект разрабатывается локально и разворачивается в закрытой корпоративной среде.
Для каждого обновления используй один и тот же, повторяемый сценарий развёртывания.

## Политика окружений

- Локальная разработка:
  - `APP_ENV=dev`
  - `NEXT_PUBLIC_APP_ENV=dev`
  - `ENABLE_DIRECTORY_DEBUG=1`
  - `ENABLE_LEGACY_X_USER_ID=1`
- Сервер / production:
  - `APP_ENV=prod`
  - `NEXT_PUBLIC_APP_ENV=prod`
  - `ENABLE_DIRECTORY_DEBUG=0`
  - `ENABLE_LEGACY_X_USER_ID=0`
  - `AUTH_JWT_SECRET` должен быть задан и не должен быть значением по умолчанию
  - `INTERNAL_API_TOKEN` должен быть задан, если бот всё ещё обращается к внутренним per-user endpoint'ам

`ENABLE_LEGACY_X_USER_ID=1` можно временно использовать на этапе миграции, если какой-то внутренний helper всё ещё отправляет `X-User-Id` без сервисного токена.
Считай это временным флагом совместимости, а не целевой production-настройкой.

Рекомендуемая production-схема для Telegram-бота:

- бот отправляет `X-User-Id`
- бот также отправляет `X-Internal-Api-Token`
- backend проверяет internal token перед тем, как доверять user id
- за основу конфигурации бота бери `corpsite-bot/.env.example`
- на VPS (bot и backend на одном хосте) задай:
  - `API_BASE_URL=http://127.0.0.1:8000`
  - `META_API_BASE_URL=http://127.0.0.1:8000`
  - не используй `https://mmc.004.kz/api` для бота — это browser/nginx prefix, не прямой uvicorn

## Database configuration

- Приложение (FastAPI), pytest и scripts подключаются к БД через `DATABASE_URL` из `.env`.
- Alembic использует **тот же** `DATABASE_URL` (загружается в `alembic/env.py` из корневого `.env`).
- Файл `alembic.ini` **не редактируется вручную** для смены БД и не должен содержать credentials.
- Перед `alembic upgrade head` достаточно проверить, что в `.env` задан корректный `DATABASE_URL` для целевой среды.

## Перед каждым развёртыванием

1. Сделай резервную копию базы данных.
2. Сохрани текущий серверный `.env`.
3. Проверь, что изменилось:
   - backend-код
   - frontend-код
   - миграции базы данных
4. Подтверди production-значения переменных:
   - `APP_ENV=prod`
   - `NEXT_PUBLIC_APP_ENV=prod`
   - `AUTH_JWT_SECRET` не равен значению по умолчанию
   - `INTERNAL_API_TOKEN` совпадает между backend и ботом
   - debug/dev-флаги выключены, если они не нужны специально

## Порядок развёртывания

1. При необходимости останови сервисы приложения.
2. Скопируй обновлённые файлы проекта на сервер.
3. Примени миграции БД до запуска новой версии backend.
4. Обнови backend-зависимости, если они изменились.
5. Собери или обнови frontend (`sudo ./scripts/deploy_frontend.sh` — см. `docs/deploy/frontend.md`).
6. Перезапусти backend через `sudo ./scripts/deploy_backend.sh` (см. `docs/deploy/VPS_STABILITY.md`).
   Скрипт автоматически выполняет health-check и **scheduler post-deploy smoke** после успешного `/health`.
7. Запусти backend и frontend (если не использовал deploy-скрипты выше).
8. Выполни smoke-check ниже.

### Post-deploy Scheduler Smoke

После каждого backend deploy `scripts/deploy_backend.sh` автоматически проверяет инфраструктуру regular-tasks scheduler (только диагностика, без создания задач):

1. `corpsite-regular-tasks.timer` установлен, enabled, active (waiting).
2. `systemctl list-timers` показывает следующий trigger.
3. `corpsite-regular-tasks.service` существует.
4. `scripts/ops/ops_regular_tasks_scheduler_audit.py --post-deploy-smoke` — exit 0 (`dry_run` probe + `GET /regular-tasks/scheduler-status`).
5. Deploy завершается с ошибкой, если smoke не прошёл.

Отключить только в аварийном случае: `CORPSITE_SKIP_SCHEDULER_SMOKE=1`.

Детали и ожидаемые результаты: `docs/deploy/VPS_STABILITY.md` § Post-deploy Scheduler Smoke, `docs/ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md`.

## Smoke-check после развёртывания

1. `GET /health` возвращает `{"status":"ok"}`.
2. При same-origin nginx также проверь `GET /api/health` → `{"status":"ok"}`.
3. Вход работает для реального тестового пользователя.
4. Страница задач открывается без ошибок.
5. Пилотный пользователь видит свои задачи.
6. Привилегированный пользователь может открыть экран периодов.
7. Тестовая задача проходит ожидаемый жизненный цикл по статусам.
8. В production не отображается debug-интерфейс.
9. `/directory/personnel` открывается как HTML (Next.js), а API-запросы идут на `/api/directory/...` и возвращают JSON.

### ADR-042 post-deploy smoke (personnel access / sysadmin cabinet)

После деплоя с миграциями ADR-042 (revisions `u3v4w5x6y7z8` … `w5x6y7z8a9b0`):

1. **Миграции:** `alembic upgrade head` → `alembic current` и `alembic heads` должны показать `w5x6y7z8a9b0`.
2. **Validation SQL:** `psql "$DATABASE_URL" -f docs/adr/ADR-042-phase-b2-validation.sql` — пустые check-queries = OK (drift #10 может требовать reconcile).
3. **Admin API** (JWT admin, `role_id=2` или privileged):
   - `GET /api/admin/access/roles` → 200
   - `GET /api/admin/access/guard-mode` → 200
   - `GET /api/admin/users` → 200
   - `GET /api/admin/security-audit` → 200
4. **UI:** `/admin/system` — 5 вкладок (Пользователи, Доступы, Enrollment, Назначения, Аудит); roles dropdown и target search работают.
5. **Feature flags** остаются OFF (defaults): `ADR042_ADMIN_GUARD_MODE=legacy`, `ADR042_TOKEN_VERSION_ENFORCEMENT=false`, `ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT=false`.

Детали: `docs/adr/ADR-042-phase-b2-migration-plan.md`, `docs/adr/ADR-042-phase-c1-sysadmin-ui.md`.

Same-origin routing (mmc.004.kz): см. `docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md`.

Frontend-only deploy (после `git pull` с изменениями UI): см. `docs/deploy/frontend.md`.

PowerShell helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_check.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -Login "test_user_login" `
  -Password "test_user_password"
```

Если `Login` и `Password` не переданы, скрипт проверяет только `/health`.

## Чеклист обновлений для пилота

Для первого пилота в одном подразделении:

1. Обновляй только то, что действительно нужно для пилотного сценария.
2. Избегай изменений схемы БД, если без них можно обойтись.
3. Держи хотя бы одного тестового пользователя на каждую роль.
4. Фиксируй каждый релиз в коротком журнале:
   - дата
   - что изменилось
   - что нужно проверить
   - примечание по откату

Операционный чеклист на первую рабочую неделю:

- см. `docs/PILOT_WEEK1_CHECKLIST.md`

## Минимальный откат

Если обновление прошло неудачно:

1. Верни предыдущую сборку backend/frontend.
2. Верни предыдущий `.env`, если он менялся.
3. Восстанови базу данных из резервной копии, если проблема вызвана миграцией или неудачным обновлением данных.
