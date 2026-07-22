# ANALYSIS — Руководство админа Corpsite.docx

**Путь:** `docs-work/source-materials/system-admin/Руководство админа Corpsite.docx`  
**Дата в документе:** 15.02.2026 (+ фрагменты 01–03.2026)  
**Объём:** ~4911 слов, 49 PNG, 8 таблиц

---

## Структура документа (основные разделы)

| Раздел | Содержание |
|--------|------------|
| Цель проекта, сокращения | Tasks automation, DDL/UI/RBAC |
| Роль администратора | Справочники, логи, пароли, regular tasks |
| Интерфейс | Sidebar: шаблоны, задачи, роли, контакты, персонал |
| Шаблоны / догоняющий запуск | Regular tasks, cron, dry-run |
| Admin cabinet ADR-042 | Access, Enrollment, Security audit |
| **Защита и пароли** | JWT, pbkdf2 hashes, admin credentials |
| Импорт employees | SQL `\d`, staging tables |
| Онбординг | Создание сотрудника, роли, контакты, Telegram bind |
| UI debt notes | Дублирование Роли/Должности, Контакты |
| Regular tasks runbook | Cron, VPS, SQL checks |
| Position Cabinet / dualism | Architecture essay |
| (+ другие admin topics в хвосте документа) |

**Характер:** **admin runbook + UX audit + architecture notes**, частично годится как UG.

---

## Что можно сохранить

### Для `system-admin/`

- **Модель RBAC** (Role → Grant → Target, effective access).
- **Вкладки Admin:** Access Management, Enrollment, Security Audit — описание назначения.
- **Regular tasks:** шаблоны, cron, dry-run, догоняющий запуск (без VPS-specific secrets).
- **Онбординг сотрудника:** поиск → создать → должность → контакт → Telegram `/bind`.
- **Импорт персонала через Excel** — общий процесс.
- **49 скриншотов** — богатый визуальный материал после фильтрации и пересъёмки.

### Для `shared/`

- Сокращения DDL/UI/UX/RBAC (упрощённо).

### Для `docs/ops/` (не user-guides)

- Cron paths, SQL diagnostics, internal API tokens — **runbook**, не UG.

---

## Что устарело / КРИТИЧНО не публиковать

| Элемент | Риск |
|---------|------|
| **JWT access_token**, **pbkdf2 hashes**, пароли `Admin123!`, `Corp2026!` | 🔴 **Секреты — удалить из любого UG** |
| `login: admin`, `user_id: 289` | Pilot credentials |
| `http://localhost:3000/login` | Устаревший URL |
| «Кнопка Шаблоны не работает» | UX debt snapshot — проверить fix |
| Дублирование UI (Роли vs Должности) | Может быть частично исправлено |
| Имя бота `hospaccdevbot` | Dev bot |
| Длинные SQL `\d` dumps | Runbook only |

---

## Чего не хватает

- Чёткое разделение **System Admin vs HR Admin vs Security Auditor**.
- Актуальная карта `/admin/*` routes в Next.js UI.
- Version matrix «что изменилось с 02.2026».
- Безопасная редакция без секретов (redaction layer).
- Operational Orders / Personnel admin — отдельные главы или ссылки на hr UG.

---

## Скриншоты — пригодность

| Группа | ~кол-во | Оценка |
|--------|--------:|--------|
| Sidebar, tasks, templates | 10+ | ⚠️ Переснять; композиция полезна |
| Admin Access / Enrollment | 10+ | ✅ Высокая ценность для sysadmin UG |
| Personnel CRUD, contacts | 10+ | ⚠️ Сверить с текущим UI |
| UX «проблемы» slides | 5+ | 📝 Notes, не UG |
| Telegram bind | 3+ | ✅ Для shared/employee + sysadmin |

**Технически:** 49 PNG, ~3.4 MB — **лучший визуальный комплект** из всех source materials; требует **sanitization** (blur PII, crop secrets).

---

## Соответствие новой ролевой структуре

| Блок | Целевой каталог |
|------|-----------------|
| Access, Enrollment, Audit | `system-admin/` — **UG-SYS-001-admin-cabinet** |
| Regular tasks admin | `system-admin/` — **UG-SYS-002-regular-tasks** |
| Telegram onboarding | `shared/` + `employee/` (user) + `system-admin/` (setup) |
| SQL/cron/VPS | `docs/ops/` runbooks |
| Position Cabinet essay | architecture notes |
| HR import review | `hr/hr-specialist/` (не sysadmin) |

**Рекомендация:** **sanitized fork** → 2–3 sysadmin UG; исходный DOCX **не публиковать** из-за секретов.

---

## Вердикт

**Статус:** самый объёмный и полезный source, но **наибольший риск утечки** и смешения runbook/UG.  
**Первый шаг:** redaction pass, затем split на UG-SYS-* без переписывания смысла.
