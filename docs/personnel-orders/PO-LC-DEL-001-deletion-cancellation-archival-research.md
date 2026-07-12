# PO-LC-DEL-001 — Deletion, Cancellation, Archival and Void Research

**Статус:** Research / design only (код не изменялся)  
**WP:** WP-PO-LC-DEL-001  
**Дата:** 2026-07-12  
**Связь:** PO-LIFECYCLE-002, PO-004, WP-PO-004D, WP-PO-006, WP-PO-008

---

## 1. Executive summary

Проект **уже реализует** значительную часть политики удаления/аннулирования через единый статус `VOIDED` и сервис `personnel_orders_void_service`, но **не реализует** физическое удаление черновиков, архивирование и разграничение полномочий по стадиям lifecycle.

**Фактическая MVP-модель:**

```text
DRAFT → READY_FOR_SIGNATURE → SIGNED | REGISTERED → (apply) → linked employee_events
                                                              ↓
                                                    UX badge «Применён»
```

«Применён» — **не** `order.status`, а производное состояние (`linkedEventCount > 0`).

**Рекомендуемая целевая модель (подтверждена исследованием):**

| Стадия | Удаление | Отмена | Аннулирование | Архив | Исправление |
|--------|----------|--------|---------------|-------|-------------|
| DRAFT / READY | soft delete или cancel→VOIDED | да | н/п | н/п | редактирование (только DRAFT) |
| SIGNED / REGISTERED (не applied) | запрещено | н/п | void→VOIDED | н/п | void |
| Applied (events exist) | запрещено | запрещено | void + rollback (ограничено ADR-035) | да (после завершения) | **компенсирующий приказ** (предпочтительно) |
| VOIDED | запрещено | н/п | идемпотентно запрещено | да | корректирующий приказ |
| ARCHIVED (новый) | запрещено | н/п | н/п | — | restore |

**Hard delete:** только maintenance / non-production / recovery role; **не** через обычный UI.

**Следующий WP:** `WP-PO-LC-DEL-002 — lifecycle taxonomy, permissions and audit foundation`.

---

## 2. Current-state findings

### 2.1. Что уже есть в коде

| Возможность | Реализация | Файлы |
|-------------|------------|-------|
| Создание черновика | `POST /personnel-orders` → `DRAFT` | `personnel_orders_command_service.py` |
| Редактирование header/items | только `DRAFT` | `EDITABLE_ORDER_STATUSES = {DRAFT}` |
| К подписи | `DRAFT` → `READY_FOR_SIGNATURE` | `mark_personnel_order_ready_for_signature` |
| Регистрация | `DRAFT`/`READY` → `SIGNED`/`REGISTERED` | `register_personnel_order` |
| Применение | `SIGNED`/`REGISTERED` → `employee_events` | `personnel_orders_apply_service.py` |
| Отмена черновика | `DRAFT`/`READY` → `VOIDED` (без touch events) | `void_personnel_order`, ветка `CANCELABLE_ORDER_STATUSES` |
| Аннулирование | `SIGNED`/`REGISTERED` → `VOIDED` + cascade void events + rollback | `void_personnel_order`, ветка `VOIDABLE_ORDER_STATUSES` |
| Аннулирование пункта | `POST …/items/{id}/void` | `void_personnel_order_item` (API only, **нет UI**) |
| Watermark аннулирования | `VOIDED` → «АННУЛИРОВАН» | `personnelOrderPrintViewModel.ts` |
| Физическое DELETE | **нет API**; только test teardown SQL | `tests/test_wp_po_004d_*.py`, `scripts/local_demo/` |

### 2.2. Чего нет

- Статуса `ARCHIVED`, `APPLIED`, `CANCELLED` (отдельно от `VOIDED`)
- API `DELETE /personnel-orders/{id}`
- Поля `deleted_at` / `archived_at`
- Ownership-проверок (`created_by`) на lifecycle endpoints
- Разделения operator / head / recovery admin на write lifecycle
- Dedicated audit log таблицы для lifecycle actions (void пишет только `void_reason`, `voided_at`, `voided_by` на order/item)
- UI «Удалить черновик» (вместо этого — «Аннулировать» для всех не-VOIDED статусов)
- UI void отдельного пункта
- Операции «Архивировать» / «Восстановить»
- Связи `replacement_order_id` / `reversal_order_id`

### 2.3. Расхождения документация ↔ код

| Тема | Документация | Код |
|------|--------------|-----|
| Статусы | PO-004: 8 стадий (Prepared, Approved, Executed, Archived) | 5 кодов: `DRAFT`…`VOIDED` |
| PO-003 data model | lowercase `draft`, `archived`, `cancelled` | UPPER_SNAKE MVP |
| PO-LIFECYCLE-002 header | «код не реализуется» | void **реализован** (WP-PO-004D) |
| Draft delete | Policy: DRAFT может быть удалён | Нет delete; void→`VOIDED` |
| Applied | PO-004 «Executed» | UX badge; `status` остаётся `REGISTERED`/`SIGNED` |
| Роли | Operator / head / recovery (§7) | Единый `require_personnel_admin_or_403` |
| Редактирование READY | WP-PO-008 упоминает edit while READY | Backend: только `DRAFT` editable |
| Annul vs cancel | Разные термины | Один код `VOIDED`; UI «Аннулировать» для всех |

---

## 3. Lifecycle inventory

### 3.1. Order statuses (фактические)

| Код | UI (RU) | Как попасть | Разрешённые действия |
|-----|---------|-------------|----------------------|
| `DRAFT` | Черновик | `POST /personnel-orders` | edit header/items, ready, register, void (cancel) |
| `READY_FOR_SIGNATURE` | На подписи | `POST …/ready-for-signature` | register, void (cancel); **не** edit |
| `SIGNED` | Подписан | register с `target_status=SIGNED` | apply, void (annul) |
| `REGISTERED` | Зарегистрирован | register (UI: `REGISTERED`) | apply, void (annul) |
| `VOIDED` | Аннулирован | void | read, print (watermark); terminal |

Источники: `app/db/models/personnel_orders.py`, `personnelOrderLabels.ts`, CHECK в migration `p0q1r2s3t4u5`.

### 3.2. Производные UX-состояния (не enum)

| Состояние | Условие | Метка UI |
|-----------|---------|----------|
| Applied | `events.length > 0` (linked `employee_events`) | «Применён» |
| Editable | `status === DRAFT` | формы enabled |
| Registerable | `DRAFT` \| `READY_FOR_SIGNATURE` | кнопка «Зарегистрировать» |
| Applyable | `SIGNED`/`REGISTERED` && !applied | кнопка «Применить» |

### 3.3. Item statuses

| Код | Значение |
|-----|----------|
| `ACTIVE` | рабочий пункт |
| `VOIDED` | аннулированный пункт |

### 3.4. Переходы (диаграмма)

```text
                    ┌─────────────────┐
                    │     CREATE      │
                    └────────┬────────┘
                             ▼
                         [DRAFT]──────edit header/items
                             │
              ready-for-signature
                             ▼
                  [READY_FOR_SIGNATURE]
                             │
                      register
                             ▼
              ┌──────────────┴──────────────┐
              ▼                             ▼
          [SIGNED]                    [REGISTERED]
              │                             │
              └──────────┬ apply ───────────┘
                         ▼
              employee_events (APPROVED)
              order.status unchanged
              UX: «Применён»

  DRAFT/READY ──void(cancel)──► [VOIDED]  (no event touch)
  SIGNED/REGISTERED ──void──► [VOIDED]    (events VOIDED + rollback)
```

### 3.5. Матрица действий по стадиям (фактическая)

| Статус / состояние | Edit header | Edit items | Register | Apply | Void/Cancel | Delete | Archive | Restore |
|--------------------|:-----------:|:----------:|:--------:|:-----:|:-----------:|:------:|:-------:|:-------:|
| DRAFT | ✅ | ✅ | ✅ | ❌ | ✅ cancel | ❌ | ❌ | ❌ |
| READY_FOR_SIGNATURE | ❌ | ❌ | ✅ | ❌ | ✅ cancel | ❌ | ❌ | ❌ |
| SIGNED (not applied) | ❌ | ❌ | ❌ | ✅ | ✅ annul | ❌ | ❌ | ❌ |
| REGISTERED (not applied) | ❌ | ❌ | ❌ | ✅ | ✅ annul | ❌ | ❌ | ❌ |
| Applied (`events>0`) | ❌ | ❌ | ❌ | ❌ | ✅ annul* | ❌ | ❌ | ❌ |
| VOIDED | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

\* Annul applied: `void_personnel_order` выполняет rollback snapshot + void events, но блокируется **void chain** (ADR-035), если есть более новые APPROVED events.

**Причина:** void требует `void_reason` (обязательное поле в API/UI).

---

## 4. Data dependency analysis

### 4.1. Связанные сущности

| Сущность | Таблица | FK → order | ON DELETE | Nullable |
|----------|---------|------------|-----------|----------|
| Пункты | `personnel_order_items` | `order_id` | **RESTRICT** | — |
| Локализованные тексты | `personnel_order_localized_texts` | `order_id` | **RESTRICT** | — |
| Вложения | `personnel_order_attachments` | `order_id` | **RESTRICT** | — |
| Печати | `personnel_order_prints` | `order_id` | **RESTRICT** | — |
| Editorial blocks (order) | `personnel_order_editorial_blocks` | `order_id` | **RESTRICT** | — |
| Editorial blocks (item) | `personnel_order_item_editorial_blocks` | `order_item_id` | **RESTRICT** | — |
| Item bases | `personnel_order_item_bases` | `order_item_id` | **RESTRICT** | — |
| Employee events | `employee_events` | `order_id`, `order_item_id` | **RESTRICT** | nullable cols |

Дополнительно на header:
- `created_by` → `users` **RESTRICT**
- `voided_by` → `users` **SET NULL**
- `signed_by_employee_id` → `employees` **SET NULL**

### 4.2. Последствия физического DELETE order

**Заблокировано на уровне БД**, если существуют:
- items, localized_texts, attachments, prints, editorial blocks, employee_events

Тестовый teardown удаляет в порядке: `employee_events` → children → `personnel_orders`.

**Вывод:** production-safe путь — status-based lifecycle, не DELETE.

### 4.3. Apply — необратимые внешние последствия

`apply_personnel_order` (`personnel_orders_apply_service.py`):

| Тип пункта | Создаёт event | Меняет `employees` |
|------------|---------------|---------------------|
| HIRE | `HIRE` | org, position, rate, `is_active=TRUE` |
| TRANSFER | `TRANSFER` (+ optional RATE_CHANGE) | org, position, rate; может `users.unit_id` |
| TERMINATION | `TERMINATION` | `is_active=FALSE`, `date_to` |
| CONCURRENT_DUTY_* | `RATE_CHANGE` metadata | rate fields |

Apply **идемпотентен**: повторный apply → `PersonnelOrderAlreadyAppliedError`.

Void applied order **частично компенсирует** через `_rollback_snapshot_for_event` (HIRE/TRANSFER/TERMINATION/RATE_CHANGE), но:
- события не DELETE — `lifecycle_status` → `VOIDED`
- void chain guard блокирует, если есть более новые events
- не все сценарии покрыты E2E (GAP-PO-001 в WP-PO-006)

---

## 5. Deletion / cancellation / archive taxonomy

### A. Delete draft

**Целевое назначение:** убрать ошибочный черновик без юридического следа.

**Сейчас:** нет DELETE; `void` на `DRAFT`/`READY` переводит в `VOIDED`, запись остаётся в БД с `void_reason`.

**Рекомендация:** soft delete (`deleted_at`) **или** dedicated `CANCELLED` для pre-registration; hard delete только пустых test records.

### B. Cancel / withdraw

**Целевое назначение:** отозвать приказ до регистрации/применения.

**Сейчас:** реализовано как `void_personnel_order` для `CANCELABLE_ORDER_STATUSES` без touch `employee_events`.

**UI-проблема:** кнопка называется «Аннулировать» (юридический термин) даже для черновика.

### C. Annul / void

**Целевое назначение:** снять юридическую силу зарегистрированного приказа с сохранением истории.

**Сейчас:** `VOIDED` + `void_reason`/`voided_at`/`voided_by`; для applied — cascade void events + rollback.

**Сохраняется:** номер, дата, пункты, тексты, PDF, audit fields на order.

**Не сохраняется:** `replacement_order_id`, reason_code taxonomy, dedicated audit row.

### D. Archive

**Сейчас:** не реализовано.

**Целевое назначение:** скрыть из активного журнала, сохранить полный доступ по поиску.

**Рекомендация:** новый статус `ARCHIVED` **или** флаг `archived_at` + default list filter `status NOT IN (ARCHIVED)` и `deleted_at IS NULL`.

### E. Reverse applied order

**Сейчас:** частично через void (compensating rollback), не через отдельный «отменяющий приказ».

**Рекомендация:** для applied orders **предпочитать** новый корректирующий/компенсирующий приказ; void applied — только governance path с void chain checks.

---

## 6. Permission hierarchy

### 6.1. Существующая модель доступа

| Grant / role | Код | Используется на PO routes |
|--------------|-----|---------------------------|
| SYSADMIN / ACCESS_ADMIN | via `evaluate_admin_access` | да (full) |
| HR enrollment manager | `HR_ENROLLMENT_MANAGER` | да |
| HR governance | `has_hr_governance_permission` | **нет** на personnel-orders routes |

Все write lifecycle endpoints: `require_personnel_admin_or_403` (`personnel_orders_routes.py`).

**Нет проверок:**
- `created_by` (ownership)
- org scope на void/delete
- elevated approval для void applied

### 6.2. Рекомендуемая матрица (на базе существующих grants)

| Операция | HR operator (`HR_ENROLLMENT_MANAGER`) | HR head (+ future grant) | HR governance | Sysadmin (technical) | Recovery admin (new) |
|----------|---------------------------------------|--------------------------|-----------------|----------------------|----------------------|
| Delete own empty draft | ✅ (proposed) | ✅ | ✅ | ❌ | ✅ hard (exception) |
| Cancel own DRAFT/READY | ✅ (today: void) | ✅ subordinate | ✅ | ❌ | ✅ |
| Void REGISTERED not applied | ⚠️ today all HR admin | ✅ | ✅ | ❌ | ✅ |
| Void applied order | ❌ | ⚠️ with chain check | ✅ | ❌ | ✅ emergency |
| Archive | ❌ | ✅ | ✅ | ❌ | ✅ |
| Restore archive | ❌ | ✅ | ✅ | ❌ | ✅ |
| Hard delete | ❌ | ❌ | ❌ | ❌ | ✅ audited |

**Принцип:** sysadmin ≠ кадровое право аннулирования (подтверждает PO-LIFECYCLE-002 §7.4).

### 6.3. Предлагаемые permission keys (минимальное расширение)

Использовать существующую инфраструктуру `access_grants`:

- `HR_ENROLLMENT_MANAGER` — operator baseline (уже есть)
- `HR_GOVERNANCE` — void applied, archive, restore (guard уже есть: `require_hr_governance_api`, но не подключён к PO)
- `PERSONNEL_RECOVERY_ADMIN` (новый, concept из PO-LIFECYCLE-002) — hard delete

---

## 7. Org-scope and ownership rules

### 7.1. Текущее состояние

- `personnel_orders.created_by` хранится, но **не используется** для авторизации lifecycle
- Journal list filter: `org_unit_id` — через employees в пунктах (`personnel_orders_query_service.py`), не через owner
- Нет поля `owner_unit_id` на приказе
- Нет проверки подчинённости при void

### 7.2. Рекомендации

| Правило | Предложение |
|---------|-------------|
| Кадровик удаляет черновик | только если `created_by = actor` **или** head scope |
| Руководитель удаляет черновик подчинённого | если actor в HR head scope автора (org/position grant) |
| Cross-org | запрет void/archive вне org scope актора |
| Приказ без owner | `created_by` обязателен (NOT NULL); при смене должности автора ownership не меняется |
| Просмотр архива | read в пределах org scope + personnel read grant |

---

## 8. Audit requirements

### 8.1. Сейчас

| Операция | Audit |
|----------|-------|
| Void order/item | `void_reason`, `voided_at`, `voided_by` на order/item |
| Editorial changes | `write_security_event` / `write_editorial_audit` |
| Register ready gate fail | `write_security_event` |
| Void lifecycle | **нет** dedicated security audit row |

### 8.2. Предлагаемые обязательные поля (новая таблица `personnel_order_lifecycle_audit`)

| Поле | Обязательность |
|------|----------------|
| `order_id` | всегда |
| `action` | `DRAFT_DELETE`, `CANCEL`, `VOID`, `ARCHIVE`, `RESTORE`, `HARD_DELETE` |
| `previous_status` | всегда |
| `new_status` | всегда |
| `actor_user_id` | всегда |
| `actor_position_id` | optional |
| `actor_org_scope` | JSON optional |
| `timestamp` | always |
| `reason_code` | enum для classified reasons |
| `reason_text` | free text |
| `related_order_id` | replacement/reversal link |
| `correlation_id` | request id |
| `state_digest` | hash/snapshot JSON |

### 8.3. Политики

- **Обратимость:** archive/restore — да; void applied — компенсирующий, не «undo»; hard delete — нет
- **Просмотр audit:** HR governance + security auditor (`SECURITY_AUDITOR` grant exists)
- **Редактирование причины после void:** запретить (append-only audit)
- **Двухэтапный approval:** для void applied и hard delete — рекомендуется

---

## 9. Soft delete vs hard delete options

### Вариант A — только status lifecycle

`DRAFT → VOIDED` (как сейчас для cancel).

**Плюсы:** минимальные изменения.  
**Минусы:** журнал засоряется voided drafts; `order_number` UNIQUE блокирует повторное использование номера.

### Вариант B — soft delete

`deleted_at`, `deleted_by`, `deletion_reason`, `restored_at`.

**Плюсы:** чистый активный список; draft recovery.  
**Минусы:** новые поля, фильтры, UI.

### Вариант C — hybrid (рекомендуется)

| Стадия | Механизм |
|--------|----------|
| DRAFT пустой/с пунктами | soft delete **или** cancel→VOIDED |
| READY | cancel→VOIDED (не delete) |
| REGISTERED+ | void only |
| Applied | compensating order primary; void governance |
| Завершённые | archive |
| Hard delete | recovery admin + no events + no number conflict |

### Hard delete policy (однозначно)

| Где | Допустимость |
|-----|--------------|
| Production UI | **Запрещён** |
| Production API | **Запрещён** для обычных ролей |
| Maintenance script | Допустим для test/pilot seed (`wp_po_007_pilot_seed.py`) |
| Recovery role | Допустим с audit + pre-checks (no `employee_events`) |
| Документ с `order_number` | **Не удалять** в production; номер остаётся в UNIQUE index |
| Повторное использование номера | Только если запись физически удалена **или** политика разрешает reuse voided numbers (отдельное решение) |

**Рекомендация:** voided/cancelled orders **сохраняют** `order_number`; reuse номера — отдельный governance WP.

---

## 10. Applied-order reversal analysis

### 10.1. Текущий механизм void applied

1. Void chain check (ADR-035)
2. `_rollback_snapshot_for_event` по типу event
3. Events → `lifecycle_status = VOIDED`

### 10.2. Безопасная модель по типам

| Тип | Void rollback (сейчас) | Рекомендуемый primary fix |
|-----|------------------------|---------------------------|
| HIRE | deactivate or restore from snapshot | TERMINATION / correcting order |
| TRANSFER | restore from_org/from_position/from_rate | reverse TRANSFER order |
| TERMINATION | `is_active=TRUE`, clear `date_to` | HIRE / reinstatement order |
| RATE_CHANGE | restore from_rate | compensating rate order |
| CONCURRENT_DUTY_START | partial in service | CONCURRENT_DUTY_END order |
| CONCURRENT_DUTY_END | partial | CONCURRENT_DUTY_START order |

### 10.3. Рекомендация

```text
Applied order:
  PRIMARY  → новый компенсирующий приказ (links: original_order_id, reversal_order_id)
  SECONDARY → void + rollback (governance only, void chain, dual approval)
  FORBIDDEN → DELETE, silent undo
```

---

## 11. Recommended target model

Подтверждённый принцип (с уточнениями под фактический код):

```text
DRAFT:
  → soft delete ИЛИ cancel (VOIDED) в пределах ownership/role
  → edit только в DRAFT

READY_FOR_SIGNATURE:
  → cancel (VOIDED), не edit

REGISTERED / SIGNED (not applied):
  → void (annul), не delete

APPLIED (linked events):
  → не delete
  → void только governance + chain check
  → предпочтительно compensating order

VOIDED:
  → read-only history, printable with watermark
  → archivable

ARCHIVED (new):
  → hidden from default list
  → restore by HR head/governance

HARD DELETE:
  → recovery admin, no events, audited, non-UI
```

---

## 12. Proposed API changes (future WPs)

| Endpoint | Назначение | WP |
|----------|------------|-----|
| `DELETE /personnel-orders/{id}` | soft delete draft | DEL-003 |
| `POST …/cancel` | semantic cancel pre-registration (alias void today) | DEL-003 |
| `POST …/archive` | archive | DEL-004 |
| `POST …/restore` | unarchive | DEL-004 |
| `POST …/void` | keep; add governance gate for applied | DEL-005 |
| `GET …/audit` | lifecycle audit trail | DEL-002 |
| `POST …/compensate` | link reversal order | DEL-006 |

---

## 13. Proposed DB changes (future WPs)

Минимальный набор:

```sql
-- Option: status extension
ALTER ... CHECK (status IN (..., 'ARCHIVED'));

-- Option: soft delete columns
deleted_at TIMESTAMPTZ,
deleted_by BIGINT REFERENCES users(user_id),
deletion_reason TEXT,

-- Archive
archived_at TIMESTAMPTZ,
archived_by BIGINT REFERENCES users(user_id),

-- Links
replacement_order_id BIGINT REFERENCES personnel_orders(order_id),
reversal_of_order_id BIGINT REFERENCES personnel_orders(order_id),

-- Audit table
personnel_order_lifecycle_audit (...)
```

**Не менять** `ON DELETE RESTRICT` на child tables.

---

## 14. Proposed UI actions

| Действие | Где | Кому | UX |
|----------|-----|------|-----|
| **Удалить черновик** | drawer DRAFT | author / head | confirm + optional reason; warn if items exist |
| **Отменить** | drawer DRAFT/READY | author / head | заменить label «Аннулировать» для pre-reg |
| **Аннулировать** | drawer SIGNED/REGISTERED/+applied | governance for applied | modal + обязательная причина (есть) + warning consequences |
| **Архивировать** | drawer VOIDED / old applied | head | reason optional |
| **Восстановить** | archive view | governance | confirm |
| **Создать отменяющий приказ** | drawer applied | operator | prefill link to original |

**Не использовать** одну красную кнопку «Удалить» для всех стадий.

Текущий `PersonnelOrderVoidDialog`: единый «Аннулировать» + причина — требует stage-aware labels и warnings.

---

## 15. Test strategy

### Backend unit
- permission matrix per action/status
- ownership: own vs foreign draft
- void chain violation
- rollback per event type
- idempotent void/archive

### API integration
- delete draft with/without items
- register protection
- apply protection (no delete)
- archive/restore roundtrip
- direct API bypass without grant

### DB constraint
- DELETE order with events → RESTRICT
- UNIQUE order_number after void

### Frontend
- stage-aware button visibility
- void dialog copy per status
- stale UI after concurrent void

### E2E
- create → cancel draft
- register → void not applied
- apply → compensating order flow (future)
- archive → search → restore

---

## 16. Risks and open questions

| Risk | Severity |
|------|----------|
| UI «Аннулировать» на черновике вводит в заблуждение | Medium |
| Любой HR admin может void applied (no governance split) | High |
| Void applied без compensating order — риск partial rollback | High |
| `order_number` UNIQUE + VOIDED drafts блокируют reuse | Medium |
| Нет lifecycle audit table | Medium |
| Item void API без UI | Low |
| READY locked but UI doc says editable | Low |

**Open questions:**
1. Нужен ли отдельный статус `CANCELLED` vs `VOIDED` для pre-registration?
2. Разрешать ли reuse `order_number` после void?
3. Archive как status или как `archived_at` flag?
4. Подключать ли `require_hr_governance_api` к void applied?
5. Нужен ли dual approval для void applied?

---

## 17. Recommended implementation sequence

```text
WP-PO-LC-DEL-002 — lifecycle taxonomy, permission matrix, audit schema (foundation)
WP-PO-LC-DEL-003 — draft soft delete / semantic cancel + ownership
WP-PO-LC-DEL-004 — archive and restore + journal filters
WP-PO-LC-DEL-005 — registered/applied void hardening + governance gates
WP-PO-LC-DEL-006 — compensating/reversal order links
WP-PO-LC-DEL-007 — stage-aware UI, audit viewer, test hardening
```

**Начать с:** `WP-PO-LC-DEL-002` — без foundation нельзя безопасно добавить delete/archive UI.

---

## Appendix A — Key source files

| Area | Path |
|------|------|
| Models | `app/db/models/personnel_orders.py` |
| Command | `app/services/personnel_orders_command_service.py` |
| Apply | `app/services/personnel_orders_apply_service.py` |
| Void | `app/services/personnel_orders_void_service.py` |
| Routes | `app/directory/personnel_orders_routes.py` |
| Permissions | `app/security/personnel_admin_guard.py`, `admin_permissions.py` |
| UI lifecycle | `corpsite-ui/.../PersonnelOrderLifecycleActions.tsx` |
| UI void dialog | `corpsite-ui/.../PersonnelOrderVoidDialog.tsx` |
| Labels/helpers | `corpsite-ui/.../personnelOrderLabels.ts` |
| Policy doc | `docs/personnel-orders/PO-LIFECYCLE-002-delete-and-void-policy.md` |
| Void tests | `tests/test_wp_po_004d_personnel_orders_void_api.py` |

---

## Appendix B — Permission × lifecycle matrix (target)

| Статус | Редактировать | Удалить draft | Отменить | Аннулировать | Архивировать | Восстановить | Причина |
|--------|:-------------:|:-------------:|:--------:|:------------:|:------------:|:------------:|:-------:|
| DRAFT | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | optional |
| READY | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | optional |
| SIGNED/REG (no apply) | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | required |
| Applied | ❌ | ❌ | ❌ | ✅* | ✅ | ❌ | required |
| VOIDED | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | optional |
| ARCHIVED | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | optional |

\* Applied void: governance + void chain.
