# WP-ACCESS-003: административный сброс забытого пароля

## Реализовано

Основной интерфейс — «Кабинет системного администратора → Управление
доступом». Он доступен пользователю с эффективным `USER_ACCESS_ADMIN` и ищет
User непосредственно по login, имени или роли; связь с Employee для поиска и
сброса не требуется.

Фактические paths:

```text
GET  /directory/access/users?q={query}
POST /directory/access/users/{user_id}/password-reset
POST /directory/personnel/employees/{employee_id}/access/password-reset
POST /directory/access/users/{user_id}/activate?reason={reason}
```

Последний path сохранён для диагностического employee-based экрана. Основной
рабочий сценарий использует поиск User и reset по `user_id`.

Временный пароль возвращается только в непосредственном ответе и показывается
администратору один раз. В хранилище сохраняется только штатный hash; срок
временного пароля — 24 часа. Reset устанавливает `must_change_password=true`,
увеличивает `token_version` и очищает только блокировку с причиной
`brute_force`. Записывается безопасное security-audit событие без пароля.

Страница входа содержит «Забыли пароль?» с инструкцией обратиться к системному
администратору и сообщить login. Самостоятельная смена известного пароля
остаётся в `/profile`.

Активация существующей неактивной учётной записи требует
`USER_ACCESS_ADMIN` и обязательной причины. Она не изменяет login, Employee,
роль, password hash, grants или блокировки, а увеличивает `token_version`.
Обычный audit содержит действие `USER_ACTIVATED`; в существующем
security-audit vocabulary операция записана как `ACCESS_CHANGED` с безопасной
меткой `operation=USER_ACTIVATED`.

## Проверки

- Backend: `tests/test_wp_access_002_read_preview.py` и
  `tests/test_adr042_phase_b5_auth_policy.py` — passed в изолированной
  schema-only test-БД.
- Frontend: `AccessManagementClient.test.tsx` — 1 passed.
- `git diff --check` пройден.

Реальные пароли и production не изменялись.
