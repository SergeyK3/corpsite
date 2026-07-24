# PIF-PHOTO — Хранение фото анкеты и встраивание в PDF

Краткая техническая заметка по runtime-хранению фото кандидатов в Personnel Intake.

| Поле | Значение |
|------|----------|
| **Статус** | Implemented (runtime) |
| **Обязательная настройка** | `PERSONNEL_PHOTO_STORAGE_ROOT` |
| **Связь с анкетой** | `draft.payload.personal.photo_file_id` |

---

## 1. Конфигурация корня

| Среда | Значение |
|-------|----------|
| Local (`.env.example`) | `runtime/personnel-intake/photos` (относительно корня репозитория) |
| Production (рекомендация) | постоянный каталог **вне** исходного кода и deploy-контура, например `/var/lib/corpsite/personnel-photos` |

Правила:

- Параметр **обязателен**: без него backend не сохраняет и не читает фото.
- Относительный путь резолвится от корня проекта; абсолютный используется как есть.
- Все операции загрузки / чтения / замены / удаления идут **только** через `app/personnel_intake/infrastructure/photo_storage.py` и этот корень — путь не собирается в других сервисах.
- При отсутствии каталога он создаётся; backend-пользователь должен иметь права записи (probe при первом обращении).
- Каталог не раздаётся публично (нет StaticFiles); в Git исключён (`runtime/personnel-intake/photos/`).

---

## 2. Каталог и имена файлов

```text
{PERSONNEL_PHOTO_STORAGE_ROOT}/{application_id}/{photo_file_id}.jpg
```

| Правило | Описание |
|---------|----------|
| Корень | Только `PERSONNEL_PHOTO_STORAGE_ROOT`. |
| Каталог заявки | `{application_id}` — целочисленный id обращения. |
| Физическое имя | `{photo_file_id}.jpg`, где `photo_file_id` — стабильный 32-символьный hex (`uuid4().hex`). |
| Запрет FIO в пути | Фамилия/имя **не** используются как путь или имя файла на диске. |
| Path confinement | Итоговый путь `resolve()` и проверка `is_relative_to(root)` — выход за configured root запрещён. |

Архивное (человекочитаемое) имя **только** для выгрузки / `Content-Disposition`:

- с табельным номером: `{Фамилия}_{Имя}_{ТабельныйНомер}.jpg`
- без табельного: `{Фамилия}_{Имя}_{application_id}.jpg`

Кириллица сохраняется; символы `\ / : * ? " < > |` и управляющие удаляются. Однофамильцы различаются суффиксом (табельный номер или `application_id`).

---

## 3. Процесс

```text
Загрузка / кадрирование (UI)
  → JPEG 600×800, ≤500 KB
  → серверная валидация (magic, Pillow, размер)
  → сохранение уникального файла под PERSONNEL_PHOTO_STORAGE_ROOT
  → запись photo_file_id в payload анкеты
  → чтение только через защищённый API
  → PDF: data URI JPEG строго в рамке 3×4 см
```

| Операция | Порядок |
|----------|---------|
| Замена | сохранить новый файл → обновить `photo_file_id` → удалить старый файл |
| Удаление | очистить `photo_file_id` в анкете → удалить файл |
| PDF без фото | заглушка «Место для фотографии 3×4» |
| PDF, фото недоступно/битое | заглушка; генерация документа не срывается |

---

## 4. Доступ и безопасность

| Контроль | Реализация |
|----------|------------|
| Нет публичной раздачи каталога | Файлы не монтируются как StaticFiles; путь на диске клиенту не отдаётся. |
| Public API | `PUT/GET/DELETE /intake/{token}/photo` — только по токену ссылки. |
| HR API | `PUT/GET/DELETE /directory/personnel-applications/{id}/intake/photo` — personnel admin. |
| Path traversal | `application_id` — int; `photo_file_id` — строго `[a-f0-9]{32}`; resolve + запрет выхода за root. |
| Права | Каталог должен быть writable для пользователя процесса backend. |
| Content-Type | ответ `image/jpeg` + `nosniff` + `Cache-Control: private, no-store`. |

---

## 5. Связь файла с анкетой

- Источник истины ссылки: JSON-черновик intake (`personnel_intake_drafts.payload`).
- Поле: `personal.photo_file_id`.
- Байты фото в БД не хранятся.
- GET резолвит: draft → `photo_file_id` → файл `{PERSONNEL_PHOTO_STORAGE_ROOT}/{application_id}/{photo_file_id}.jpg`.

---

## 6. Резервное копирование

| Что | Рекомендация |
|-----|--------------|
| Бэкап | Вместе с БД бэкапить каталог из `PERSONNEL_PHOTO_STORAGE_ROOT` (local: `runtime/personnel-intake/photos/`, prod: например `/var/lib/corpsite/personnel-photos`). |
| Восстановление | Без файлов ссылки в анкетах останутся, PDF покажет заглушку; без payload ссылка на файл потеряется. |
| Перенос | Сохранять структуру `{application_id}/{photo_file_id}.jpg`; архивные имена при переносе не требуются. |
| Git | Содержимое фото-каталога не коммитить. |

---

## 7. Код

| Слой | Модуль |
|------|--------|
| Storage (единственная сборка пути) | `app/personnel_intake/infrastructure/photo_storage.py` |
| Archive name | `app/personnel_intake/domain/photo_archive_name.py` |
| Validation | `app/personnel_intake/domain/photo_validation.py` |
| Service | `app/personnel_intake/application/photo_service.py` |
| PDF embed | `corpsite-ui/app/intake/_lib/intakePdfData.server.ts` |
