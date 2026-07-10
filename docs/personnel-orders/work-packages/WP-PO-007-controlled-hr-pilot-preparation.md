# WP-PO-007 — Controlled HR Pilot Preparation

| Поле | Значение |
|------|----------|
| Статус | **Prepared** — ready for controlled HR pilot session |
| Дата | 2026-07-08 |
| Work Package | WP-PO-007 |
| Предшественник | [WP-PO-006](./WP-PO-006-closure-report.md) |
| HR quick guide | [WP-PO-007-hr-pilot-quick-guide.md](./WP-PO-007-hr-pilot-quick-guide.md) |
| Seed script | `scripts/local_demo/wp_po_007_pilot_seed.py` |

---

## Executive Summary

WP-PO-007 готовит **controlled HR pilot** модуля кадровых приказов:

1. Краткая инструкция для HR (отдельный quick guide).
2. Описание **4 P0-сценариев**: приём, перевод, увольнение, совмещение.
3. Каталог **тестовых сотрудников/приказов** + seed-скрипт.
4. Проверка журнала и вкладки «История» (API ✅, browser — см. §5).
5. Реестр **недостающих образцов отпусков** для Phase P1/P2.
6. **Gap-list** перед UI create/edit/apply/void.

**Backend/API:** validated (WP-PO-006, 26/26 tests).  
**Pilot seed:** `PILOT-2026-*` — 4 orders, employees `#142–145` (после последнего `--reset` seed).

---

## 1. Prerequisites

| Requirement | Command / note |
|-------------|----------------|
| PostgreSQL | running, `DATABASE_URL` configured |
| Alembic head | `p0q1r2s3t4u5` — `python -m alembic upgrade head` |
| Backend | `python -m uvicorn app.main:app --reload --port 8000` |
| Frontend | `npm run dev` in `corpsite-ui` → `http://localhost:3000` |
| Operator auth | user with `has_personnel_admin` (local: user_id **1** admin; **8** hr_head may be locked) |
| Pilot data | `python scripts/local_demo/wp_po_007_pilot_seed.py --operator-user-id 1 --reset` |

---

## 2. P0 scenarios — HR-facing description

Источник типов: [WP-PO-002 §7.1](./WP-PO-002-personnel-orders-architecture-scope-decision.md).

### 2.1. HIRE — Приём на работу

| | |
|--|--|
| **Когда** | Оформление нового сотрудника по подписанному приказу |
| **Пункт приказа** | `item_type_code=HIRE`, `effective_date`, org/position/rate |
| **После apply** | `employee_events.event_type=HIRE`, snapshot `employees` обновлён |
| **В истории** | Badge «Приём», ссылка на приказ |
| **Образец** | `ПРИЕМ.docx` |

### 2.2. TRANSFER — Перевод / смена должности

| | |
|--|--|
| **Когда** | Перевод в другое подразделение или смена должности |
| **Пункт** | `TRANSFER`, `to_position_id` / `to_org_unit_id` |
| **После apply** | `TRANSFER` или `POSITION_CHANGE` + snapshot |
| **Void rollback** | Восстановление `from_*` snapshot (проверено E2E WP-PO-006) |
| **Образец** | `Ауыстыру.docx` |

### 2.3. TERMINATION — Увольнение

| | |
|--|--|
| **Когда** | Расторжение трудового договора |
| **Пункт** | `TERMINATION`, `termination_reason`, `effective_date` |
| **После apply** | `TERMINATION`, `employees.is_active=false` |
| **Void rollback** | Reactivate employee (service logic) |
| **Образец** | `Еңбек шартын бұзу.docx` |
| **Pilot note** | Seed создаёт приказ в **REGISTERED** — apply выполняется на сессии пилота |

### 2.4. CONCURRENT_DUTY_START — Совмещение (доп. ставка)

| | |
|--|--|
| **Когда** | Назначение совмещаемой 0,5 ставки (ст. 111 ТК РК) |
| **Пункт** | `concurrent_position_id`, `concurrent_rate`, `total_rate` |
| **После apply** | `RATE_CHANGE` (+ metadata concurrent duty) |
| **Образец** | `Ауыстыру.docx`, сборник п.3 |
| **Pilot note** | Seed создаёт **DRAFT** — HR наблюдает register/apply/cancel через API |

### 2.5. CONCURRENT_DUTY_END (справочно)

| | |
|--|--|
| **Когда** | Снятие совмещения |
| **Образец** | `СТАВКА алу.docx` |
| **Pilot** | Не включён в seed; отдельный API-тест при необходимости |

---

## 3. Test catalog — employees & orders

### 3.1. Naming convention

| Entity | Pattern | Example |
|--------|---------|---------|
| Employee | `[PILOT-PO] {Фамилия} Пилот {сценарий}` | `[PILOT-PO] Петров Пилот Перевод` |
| Order number | `PILOT-2026-{TYPE}-{YYYYMMDD}` | `PILOT-2026-TR-20260708` |

### 3.2. Seed manifest (last run 2026-07-08)

| scenario | employee_id | order_id | order_number | state |
|----------|-------------|----------|--------------|-------|
| HIRE | 142 | 86 | `PILOT-2026-HIRE-20260708` | REGISTERED + applied |
| TRANSFER | 143 | 87 | `PILOT-2026-TR-20260708` | REGISTERED + applied |
| TERMINATION | 144 | 88 | `PILOT-2026-TERM-20260708` | REGISTERED (pending apply) |
| CONCURRENT_DUTY_START | 145 | 89 | `PILOT-2026-CON-20260708` | DRAFT |

> IDs пересоздаются при `--reset`. Актуальный manifest — stdout seed-скрипта.

### 3.3. Seed script

```powershell
cd D:\MyActivity\MyInfoBusiness\MyPythonApps\09 Corpsite
$env:PYTHONPATH="."
python scripts/local_demo/wp_po_007_pilot_seed.py --operator-user-id 1 --reset
```

| Flag | Purpose |
|------|---------|
| `--operator-user-id` | JWT user for API writes (local: **1** = admin) |
| `--reset` | Delete prior `[PILOT-PO]` employees and `PILOT-2026-*` orders |

### 3.4. History tab — import-card constraint

Вкладка **«История»** находится на `/directory/personnel/employees/{id}/import-card`.

| Employee group | Import-card | History tab |
|----------------|-------------|-------------|
| `[PILOT-PO]` seed employees | ❌ нет HR-import строки | Карточка: «не найдена строка HR-импорта» |
| Enrolled employees (e.g. `#138`) | ✅ | ✅ History tab работает |

**Pilot workaround для UI «История»:**

1. Использовать сотрудника с HR-import (например `#138`).
2. Техоператор создаёт/apply приказ через API на этого сотрудника.
3. HR открывает import-card → «История».

**API history** (без import-card) всегда доступен: `GET /directory/employees/{id}/events` — проверено для `#143` (order linkage ✅).

---

## 4. API validation (pilot data)

Post-seed checks (operator user_id=1):

```
GET /directory/personnel-orders?q=PILOT-2026  → 200, total=4
GET /directory/employees/143/events         → 200, order_number=PILOT-2026-TR-…
```

Order states in journal:

| order_number | status | employee_ids |
|--------------|--------|--------------|
| PILOT-2026-CON-… | DRAFT | [145] |
| PILOT-2026-TERM-… | REGISTERED | [144] |
| PILOT-2026-TR-… | REGISTERED | [143] |
| PILOT-2026-HIRE-… | REGISTERED | [142] |

---

## 5. Browser QA — journal & History tab

### 5.1. Procedure

1. `/dev-login` → `user_id=1` (admin, personnel admin).
2. `/directory/personnel/orders` — журнал, поиск `PILOT-2026`, drawer detail.
3. `/directory/personnel/employees/138/import-card` — вкладка **«История»** (enrolled employee).

### 5.2. Results (2026-07-08)

| Surface | URL | Result | Notes |
|---------|-----|--------|-------|
| Journal | `/directory/personnel/orders` | ⚠️ **Manual required** | MCP browser: `Failed to fetch` (isolated browser → no localhost:8000). Local manual QA expected OK if backend running. |
| History tab | `…/employees/138/import-card` → «История» | ⚠️ **Manual required** | Same network isolation in automation. Component: `EmployeePersonnelHistorySection`. |
| Unit tests | `PersonnelOrdersTable.test.tsx` | ✅ | Table render/empty/loading |
| API smoke | seed + list/detail/events | ✅ | See §4 |

**Manual sign-off checklist** (HR + ops on real browser):

- [ ] Journal loads, 4+ PILOT rows visible
- [ ] Row click opens drawer with items + events
- [ ] Filters: status, employee_id, search by order number
- [ ] Import-card → «История»: month groups, order link, «Журнал приказов»
- [ ] VOIDED badge after test void

---

## 6. Missing real order samples — leave types

Источник: [WP-PO-001 §3.2](./WP-PO-001-personnel-orders-domain-analysis.md).

### 6.1. Есть в папке образцов (7 файлов)

| File | Type | MVP |
|------|------|-----|
| `ПРИЕМ.docx` | HIRE | P0 ✅ |
| `Ауыстыру.docx` | TRANSFER + CONCURRENT | P0 ✅ |
| `Еңбек шартын бұзу.docx` | TERMINATION | P0 ✅ |
| `СТАВКА алу.docx` | CONCURRENT_DUTY_END | P0 ✅ |
| `Бала күтімінен жұмысқа шығу.docx` | RETURN_FROM_CHILDCARE | **P1** (не MVP) |
| `Біліктілік…docx` | QUALIFICATION | Out of MVP |
| `образцы приказов.docx` | сборник 8 шаблонов | mixed |

### 6.2. Недостающие образцы отпусков (collect before Phase P2)

| code (draft) | RU | Priority | Status |
|--------------|-----|----------|--------|
| `ANNUAL_LEAVE` | Ежегодный оплачиваемый отпуск | **High** | ❌ нет образца |
| `UNPAID_LEAVE` | Отпуск без сохранения ЗП | Medium | ❌ |
| `MATERNITY_LEAVE` | Декретный отпуск | Medium | ❌ |
| `CHILDCARE_LEAVE_START` | Отпуск по уходу (начало) | Medium | ❌ (есть только **выход**) |
| `LEAVE_RECALL` | Отзыв из отпуска | Low | ❌ |
| `SICK_LEAVE` | Больничный / временная нетрудоспособность | Medium | ❌ |

### 6.3. Action for HR document owner

1. Запросить у канцелярии/кадров **3 приоритетных** образца: annual leave, childcare start, unpaid leave.
2. Сохранить в `order_samples/` с именем `{TYPE}_{YYYY-MM}.docx`.
3. Обновить WP-PO-001 §3.2 и taxonomy перед WP-PO-008 (leave types).

---

## 7. Gap-list before UI create/edit (WP-PO-008+)

### 7.1. UI gaps (blocking self-service HR)

| ID | Gap | Severity | Target WP |
|----|-----|----------|-----------|
| **GAP-UI-001** | Нет кнопки «Создать приказ» | **Blocker** | WP-PO-008A |
| **GAP-UI-002** | Нет формы добавления/редактирования пунктов | **Blocker** | WP-PO-008A |
| **GAP-UI-003** | Нет действий Register / Apply / Void в drawer | **Blocker** | WP-PO-008B |
| **GAP-UI-004** | `personnelOrdersApi.client.ts` — только `list` + `get` (no write helpers) | Blocker | WP-PO-008A |
| **GAP-UI-005** | History tab: ссылка на приказ → журнал с `employee_id`, без deep-link на drawer | Low | WP-PO-008C |
| **GAP-UI-006** | History tab только на import-card; нет на `/directory/staff` drawer | Medium | WP-PO-008C |
| **GAP-UI-007** | `[PILOT-PO]` seed employees без import-card — HR не видит «Историю» в UI | Medium | enroll or staff drawer history |

### 7.2. API / domain gaps (non-blocking pilot read)

| ID | Gap | Severity | Notes |
|----|-----|----------|-------|
| GAP-PO-001 | No E2E for TERMINATION / CONCURRENT_DUTY_END | Low | WP-PO-006 partial |
| GAP-PO-004 | Order stays `REGISTERED` after apply (no `APPLIED` status) | Info | By design MVP |
| GAP-PO-003 | No DOCX/PDF generation UI | Expected | Phase 2 |

### 7.3. Environment gaps

| ID | Gap | Notes |
|----|-----|-------|
| GAP-ENV-001 | `hr_head@corp.local` (user 8) — **Account locked** in local DB | Use admin or unlock before HR pilot |
| GAP-ENV-002 | Alembic production head in old runbook (`b5e2…`) vs PO migration | Update ops runbook to `p0q1r2s3t4u5` |

---

## 8. Pilot session agenda (recommended)

| Time | Activity | Owner |
|------|----------|-------|
| 0–5 min | Prerequisites, seed manifest | Ops |
| 5–15 min | Journal walkthrough (4 PILOT orders, filters, drawer) | HR |
| 15–25 min | History tab on enrolled employee `#138` | HR |
| 25–35 min | Live apply `PILOT-2026-TERM` + refresh history | Ops + HR |
| 35–40 min | Live void + rollback demo on TRANSFER order | Ops + HR |
| 40–45 min | Gap review, leave samples request | HR lead |

---

## 9. Acceptance criteria — WP-PO-007

| # | Criterion | Status |
|---|-----------|--------|
| 1 | HR quick guide published | ✅ |
| 2 | P0 scenarios documented (4 types) | ✅ |
| 3 | Test employees/orders defined + seed script | ✅ |
| 4 | Journal + History browser check documented | ✅ (manual sign-off pending) |
| 5 | Missing leave samples catalogued | ✅ |
| 6 | Gap-list before UI write | ✅ |
| 7 | Link from WP-PO-006 closure | ✅ |

**Decision:** WP-PO-007 **Prepared**. Proceed to controlled HR pilot session; **WP-PO-008** — UI write workflow.

---

## Appendix A — API write reference (ops only)

| Step | Method | Path |
|------|--------|------|
| Create | POST | `/directory/personnel-orders` |
| Add item | POST | `/directory/personnel-orders/{id}/items` |
| Register | POST | `/directory/personnel-orders/{id}/register` |
| Apply | POST | `/directory/personnel-orders/{id}/apply` |
| Void | POST | `/directory/personnel-orders/{id}/void` |

RBAC: `require_personnel_admin_or_403`.

---

## Appendix B — Related files

| Layer | Path |
|-------|------|
| Seed | `scripts/local_demo/wp_po_007_pilot_seed.py` |
| Journal UI | `corpsite-ui/app/directory/personnel/orders/` |
| History UI | `corpsite-ui/app/directory/personnel/_components/EmployeePersonnelHistorySection.tsx` |
| E2E tests | `tests/test_wp_po_006_e2e_validation.py` |
| Closure | `docs/personnel-orders/WP-PO-006-closure-report.md` |
