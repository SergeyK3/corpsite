# Выпуск первого этапа: общий язык кадрового раздела

Серверная ревизия подтверждена пользователем: `orgkk001 (head)`. Пакет добавляет только `orgkk001 → hrlang001`. Локальная рабочая БД с неизвестной ревизией в выпуске не используется. Этапы 2–3 отсутствуют.

`release.patch` содержит 13 production-файлов: настройку, API, миграцию и отображение названий. В пакет не включены словари RU/KZ, каталог/тексты шаблонов, генераторы, данные приказов, `.env`, соседние миграции, зависимости и локальная сборка `.next`. Изменения интерфейса накладываются патчем на серверную копию. Если серверный файл изменён в месте наложения патча, `git apply --check` остановится; не заменять файл локальной версией и не применять патч принудительно.

`check_release.py` только читает БД: сверяет ревизии и контрольные суммы всех `app/services/**/*.py`, двух frontend-файлов с текстами/названиями и всех таблиц `personnel_order*`/`employee_events`. `backup_database.py` делает pg_dump по серверному `.env`, используя установленный pg_dump либо штатный контейнер `corpsite-pg`; пароль не выводится и не передаётся в командной строке.

## 1. Передать пакет (PowerShell на своём компьютере)

Из корня локального проекта:

```powershell
scp .\runtime\corpsite-hr-language-stage1-20261006.zip .\runtime\corpsite-hr-language-stage1-20261006.zip.sha256 corpsite:/tmp/
```

Если профиль SSH называется иначе, заменить только `corpsite`. Команду выполняет пользователь; агент не подключается к серверу.

## 2. Распаковать и проверить (свой SSH-терминал)

Отключить Cursor Remote перед сборкой на VPS — это требование существующего `deploy_frontend.sh`. Дальнейшая сборка выполняется из серверного дерева с сохранёнными названиями.

```bash
set -euo pipefail
HR_LANGUAGE_PACKAGE=/tmp/corpsite-hr-language-stage1-20261006
HR_LANGUAGE_REPO=/opt/projects/corpsite/app
cd /tmp
sha256sum -c corpsite-hr-language-stage1-20261006.zip.sha256
cd "$HR_LANGUAGE_REPO"
.venv/bin/python -m zipfile -e /tmp/corpsite-hr-language-stage1-20261006.zip /tmp
cd "$HR_LANGUAGE_PACKAGE"
sha256sum -c SHA256SUMS
cd "$HR_LANGUAGE_REPO"
.venv/bin/python -m alembic current
.venv/bin/python -m alembic heads
git apply --check "$HR_LANGUAGE_PACKAGE/release.patch"
bash ./scripts/ops/check_cursor_remote.sh
docker inspect corpsite-pg >/dev/null
```

Ожидаются одна текущая ревизия и одна вершина `orgkk001`. После проверки патча выделить время на остановку backend/frontend для резервного копирования, миграции и сборки.

## 3. Резервная копия, установка, миграция

Продолжить в том же терминале:

```bash
mkdir -p "$HR_LANGUAGE_REPO/runtime"
HR_LANGUAGE_BACKUP=$(mktemp -d "$HR_LANGUAGE_REPO/runtime/hr-language-backup-XXXXXXXX")
printf '%s\n' "$HR_LANGUAGE_BACKUP"
sudo systemctl stop corpsite-backend corpsite-frontend

.venv/bin/python "$HR_LANGUAGE_PACKAGE/check_release.py" --repo "$HR_LANGUAGE_REPO" --phase before --state "$HR_LANGUAGE_BACKUP/protected-before.json"
tar --exclude='corpsite-ui/node_modules' --exclude='corpsite-ui/.next/cache' --exclude='*/__pycache__' -czf "$HR_LANGUAGE_BACKUP/source-env-build.tar.gz" .env app alembic scripts corpsite-ui
.venv/bin/python "$HR_LANGUAGE_PACKAGE/backup_database.py" --repo "$HR_LANGUAGE_REPO" --output "$HR_LANGUAGE_BACKUP/database.dump"
test -s "$HR_LANGUAGE_BACKUP/database.dump"
cd "$HR_LANGUAGE_BACKUP"
sha256sum -c database.dump.sha256
sha256sum source-env-build.tar.gz > source-env-build.tar.gz.sha256
cd "$HR_LANGUAGE_REPO"

git apply --check "$HR_LANGUAGE_PACKAGE/release.patch"
git apply "$HR_LANGUAGE_PACKAGE/release.patch"
test "$(.venv/bin/python -m alembic heads | awk 'NF {print $1}')" = hrlang001
.venv/bin/python -m alembic upgrade hrlang001
.venv/bin/python -m alembic current
.venv/bin/python "$HR_LANGUAGE_PACKAGE/check_release.py" --repo "$HR_LANGUAGE_REPO" --phase after --state "$HR_LANGUAGE_BACKUP/protected-before.json"
```

Последняя проверка должна сообщить `OK: hrlang001` и подтвердить неизменность серверных файлов и таблиц. Начальное значение настройки — `kk`. Любой ненулевой код завершения останавливает последовательность; сохранить путь резервной копии и текст ошибки. Не использовать stamp, не запускать дополнительные миграции и не затирать файлы шаблонов.

## 4. Перезапуск backend, сборка и запуск frontend

```bash
sudo ./scripts/deploy_backend.sh
sudo ./scripts/deploy_frontend.sh
sudo systemctl is-active corpsite-backend corpsite-frontend
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error https://mmc.004.kz/api/health
.venv/bin/python -m alembic current
.venv/bin/python "$HR_LANGUAGE_PACKAGE/check_release.py" --repo "$HR_LANGUAGE_REPO" --phase after --state "$HR_LANGUAGE_BACKUP/protected-before.json"
```

`deploy_backend.sh` повторяет `upgrade head`; при единственной вершине `hrlang001` это не добавляет миграций. Выполнять его только после успешных проверок выше. `deploy_frontend.sh` выполняет npm ci, production-сборку из серверной копии, перезапуск и проверки страниц. Дополнительных зависимостей этот выпуск не добавляет.

## 5. Проверить права, чтение другим пользователем и сохранение после перезапуска

В браузере войти существующими учётными записями. В «Настройки» / «Баптаулар» кадрового раздела изначально должен быть выбран Қазақша. У HR_HEAD/ADMIN переключатель доступен, у HR_REG — отключён. Названия типов и шаблонов должны соответствовать общему языку, с fallback на имеющееся название. Редактор шаблона сохраняет отдельные поля RU/KK.

Для проверки API использовать JWT существующих сеансов HR_HEAD или ADMIN и HR_REG. Ввод скрыт и не сохраняет токены в истории shell; токены не присылать агенту:

```bash
read -rsp 'JWT HR_HEAD или ADMIN: ' HR_LANGUAGE_EDITOR_TOKEN
printf '\n'
read -rsp 'JWT HR_REG: ' HR_LANGUAGE_READER_TOKEN
printf '\n'

printf 'Authorization: Bearer %s\n' "$HR_LANGUAGE_EDITOR_TOKEN" | curl --fail-with-body --silent --show-error --header @- http://127.0.0.1:8000/personnel/settings | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); assert d == {"language":"kk","can_edit":True}, d; print("Default kk; editor allowed")'

printf 'Authorization: Bearer %s\n' "$HR_LANGUAGE_EDITOR_TOKEN" | curl --fail-with-body --silent --show-error --header @- --header 'Content-Type: application/json' --request PUT --data '{"language":"ru"}' http://127.0.0.1:8000/personnel/settings
printf '\n'
sudo ./scripts/deploy_backend.sh
printf 'Authorization: Bearer %s\n' "$HR_LANGUAGE_READER_TOKEN" | curl --fail-with-body --silent --show-error --header @- http://127.0.0.1:8000/personnel/settings | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); assert d == {"language":"ru","can_edit":False}, d; print("Persisted after restart; another user reads ru")'

HR_LANGUAGE_DENIED=$(printf 'Authorization: Bearer %s\n' "$HR_LANGUAGE_READER_TOKEN" | curl --silent --show-error --header @- --header 'Content-Type: application/json' --request PUT --data '{"language":"kk"}' --output "$HR_LANGUAGE_BACKUP/forbidden.json" --write-out '%{http_code}' http://127.0.0.1:8000/personnel/settings)
test "$HR_LANGUAGE_DENIED" = 403
printf 'API write denied: HTTP %s\n' "$HR_LANGUAGE_DENIED"

printf 'Authorization: Bearer %s\n' "$HR_LANGUAGE_EDITOR_TOKEN" | curl --fail-with-body --silent --show-error --header @- --header 'Content-Type: application/json' --request PUT --data '{"language":"kk"}' http://127.0.0.1:8000/personnel/settings
printf '\n'
unset HR_LANGUAGE_EDITOR_TOKEN HR_LANGUAGE_READER_TOKEN
.venv/bin/python "$HR_LANGUAGE_PACKAGE/check_release.py" --repo "$HR_LANGUAGE_REPO" --phase after --state "$HR_LANGUAGE_BACKUP/protected-before.json"
```

Повторить доступность изменения в браузере для обеих ролей HR_HEAD и ADMIN. После сохранения Русского второй пользователь обновляет кадровую страницу и видит русские названия. Не выполнять кадровые операции во время сравнения контрольных сумм: законное создание или изменение приказа изменит таблицы и вызовет остановку проверки.

Открыть создание приказа, выбрать язык документа Русский; переключить общий язык на Қазақша — выбранный язык документа должен остаться Русским. Черновик для этого сохранять не нужно. Проверить исходное архивное название в перечне: оно должно остаться записанным, меняется только подпись типа. Открыть шаблон и проверить серверные названия, не сохранять и не публиковать его. Вернуть общий язык Қазақша.

## Проверено при подготовке пакета

Патч применён к изолированной копии Git HEAD с дополнительными серверными названиями: они сохранились. Проверка snapshot выполнена на локальной PostgreSQL test-БД. Helper backup проверен через pg_dump без изменения БД. Ранее прошли 77 frontend-тестов, 9 API-тестов и приёмка на PostgreSQL с перезапуском, правами реальных пользователей и сравнением 16 таблиц. SSH при подготовке этого пакета не использовался.


## Завершение проверки в текущем локальном приложении

После отдельного разрешения пользователя и полной резервной копии создана только локальная таблица настройки по определению hrlang001. Команды Alembic и stamp не выполнялись; ревизия za0b1c2d3e4f не изменилась. Контрольные суммы всех 235 прежних таблиц public совпадают. В настоящем браузере через localhost:3000 и штатный API на порту 8000 проверены HR_HEAD и ADMIN: оба языка сохраняются после обновления страницы и читаются другим пользователем. HR_REG получает can_edit=false и HTTP 403 на PUT. Итоговый общий язык — kk. Сервер не изменялся.
