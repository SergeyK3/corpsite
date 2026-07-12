# PO-LC-DEL-002 — Lifecycle Taxonomy, Permission Matrix and Audit Foundation

**Статус:** Implementation-ready specification (design only — код, миграции, тесты не изменялись)
**WP:** WP-PO-LC-DEL-002
**Дата:** 2026-07-12
**Предшественник:** [PO-LC-DEL-001](./PO-LC-DEL-001-deletion-cancellation-archival-research.md)
**Связь:** PO-LIFECYCLE-002, PO-004, ADR-035, ADR-033, ACCESS-001, ACCESS-002, ADR-053

---

## 1. Decision summary

| Тема | Решение | Обоснование |
|------|---------|-------------|
| **Cancel vs void** | Сохранить единый `status = VOIDED`; добавить `void_kind = CANCEL \| ANNUL` | Не ломает ADR-035, существующий `POST …/void`, тесты, watermark, фильтры `status=VOIDED` |
| **Archive** | Ортогональный флаг (`archived_at` / `archived_by`), **не** lifecycle status | Приказ может быть одновременно `REGISTERED`+archived или `VOIDED`+archived; юридическое состояние не смешивается с видимостью в журнале |
| **Applied state** | Вычисляемый признак `is_applied` из ledger `employee_events` | Нет отдельного `APPLIED` status; совместимо с PE Event Engine; нулевой риск рассинхронизации с кадровой историей |
| **Permissions** | Новые granular `access_roles.code` в стиле `PERSONNEL_ORDERS_*` (UPPER_SNAKE) | Проект не использует dot-notation grants; `HR_ENROLLMENT_MANAGER` остаётся baseline PD-5.2, но не заменяет lifecycle granularity |
| **Ownership** | `created_by` — authoritative owner v1; `owner_user_id` / `responsible_org_unit_id` — deferred | Минимальный безопасный старт; head scope через org subtree + `cancel.scope` |
| **Hard delete** | Запрещён в production API/UI; только `PERSONNEL_RECOVERY_ADMIN` + maintenance scripts | PO-LIFECYCLE-002 C4; sysadmin ≠ кадровое право |
| **Audit** | Append-only `personnel_order_lifecycle_audit` | Dedicated trail; order-level `void_*` поля остаются denormalized snapshot |
| **Applied correction** | Primary: compensating order; Secondary: governance void+rollback | ADR-035 void chain guard сохраняется |
| **Первый coding WP** | **WP-PO-LC-DEL-003** — audit schema + permission grants + read-only audit API | Foundation без изменения lifecycle semantics |

---

## 2. Canonical terminology

### 2.1. Пользовательские термины (RU UI)

| Термин (RU) | Business action | Технический код | Примечание |
|-------------|-----------------|-----------------|------------|
| **Отменить** | Cancel | `CANCEL` | До юридической регистрации; без кадрового эффекта |
| **Аннулировать** | Void / Annul | `ANNUL` | После `SIGNED`/`REGISTERED`; снимает юридическую силу |
| **Архивировать** | Archive | `ARCHIVE` | Скрытие из активного журнала; legal state не меняется |
| **Восстановить** | Restore | `RESTORE` | Снятие архивного флага |
| **Создать корректирующий приказ** | Compensating order | `COMPENSATE` | Для applied orders; primary correction path |
| **Исключительное аннулирование** | Governance void+rollback | `VOID_APPLIED` | Secondary path; void chain + elevated permission |
| **Удалить** (hard) | Hard delete | `HARD_DELETE` | **Не** в production UI |

### 2.2. Технические термины

| Термин | Определение |
|--------|-------------|
| `order.status` | Юридический lifecycle enum: `DRAFT` … `VOIDED` (без `ARCHIVED`, без `APPLIED`) |
| `void_kind` | Дискриминатор внутри `VOIDED`: `CANCEL` \| `ANNUL` |
| `is_applied` | `EXISTS(employee_events WHERE order_id = ? AND lifecycle_status = 'APPROVED')` |
| `is_archived` | `archived_at IS NOT NULL` |
| `linkedEventCount` | API/UI aggregate; источник — count APPROVED+VOIDED events по order |
| `void chain` | ADR-035 guard: запрет void, если есть более новые APPROVED events того же employee |

### 2.3. Business action matrix

| Business action | Technical transition | Допустимые исходные состояния | Создаёт rollback | Изменяет legal history |
| --------------- | -------------------- | ----------------------------- | ---------------: | ---------------------: |
| **Cancel** | `status → VOIDED`, `void_kind = CANCEL` | `DRAFT`, `READY_FOR_SIGNATURE` | нет | нет (нет events) |
| **Void / Annul** | `status → VOIDED`, `void_kind = ANNUL` | `SIGNED`, `REGISTERED` (any applied state) | да, если `is_applied` | да (events → VOIDED) |
| **Archive** | `archived_at := now()`, `archived_by := actor` | любой non-archived; типично `VOIDED`, applied+completed | нет | нет |
| **Restore** | `archived_at := NULL`, `archived_by := NULL` | `is_archived = true` | нет | нет |
| **Compensating order** | новый order + links + new events | applied source order | через новые events | да (append-only) |
| **Governance void applied** | void+rollback (существующий сервис) | `SIGNED`/`REGISTERED` + `is_applied` | да | да |
| **Hard delete** | physical DELETE | maintenance only; no events | нет | уничтожает запись |

---

## 3. Current-to-target mapping

| Аспект | Сейчас (MVP) | Целевая модель |
|--------|--------------|----------------|
| Cancel pre-reg | `POST …/void` → `VOIDED` | `POST …/cancel` (alias) или void с `void_kind=CANCEL` |
| Annul post-reg | тот же endpoint → `VOIDED` | `POST …/void` с `void_kind=ANNUL` |
| Applied badge | `linkedEventCount > 0` | без изменений (`is_applied` computed) |
| Archive | нет | `archived_at` flag + journal filter |
| Permissions | `require_personnel_admin_or_403` | granular `PERSONNEL_ORDERS_*` grants |
| Ownership | `created_by` stored, не enforced | enforced для `cancel.own` |
| Audit | `void_reason`, `voided_at`, `voided_by` на order | + `personnel_order_lifecycle_audit` |
| UI void label | «Аннулировать» для всех | stage-aware: «Отменить» / «Аннулировать» |
| Print watermark | все `VOIDED` → «АННУЛИРОВАН» | `CANCEL` → «ОТМЕНЁН» / «БАС ТАРТЫЛДЫ»; `ANNUL` → текущий watermark |
| Compensating links | нет | `reversal_of_order_id`, `replacement_order_id` (deferred WP) |

---

## 4. Lifecycle and applied-state model

### 4.1. Authoritative lifecycle state

```text
order.status ∈ { DRAFT, READY_FOR_SIGNATURE, SIGNED, REGISTERED, VOIDED }
```

Переходы status остаются как в PO-LC-DEL-001 §3.4. `VOIDED` — terminal для status (restore status не предусмотрен).

### 4.2. Applied-state model — **вычисляемый признак**

**Решение:** `is_applied` — **computed at query time**, не persisted flag, не отдельный lifecycle status.

```sql
-- Authoritative definition (read path)
is_applied := EXISTS (
  SELECT 1 FROM employee_events e
  WHERE e.order_id = :order_id
    AND e.lifecycle_status = 'APPROVED'
)
```

**Почему не persisted flag:**

| Вариант | Риск | Вердикт |
|---------|------|---------|
| Computed from ledger | Нет рассинхронизации; единый source of truth | **Recommended** |
| Persisted `is_applied` on order | Drift при partial item void, manual event fix, race apply | Reject |
| Status `APPLIED` | Ломает PO-004 mapping, register/void matrix, ADR-035 | Reject |
| Aggregate table | Дополнительная синхронизация без выгоды на MVP scale | Defer |

**API contract:** detail/list responses включают:

```json
{
  "linked_event_count": 3,
  "is_applied": true
}
```

`is_applied` вычисляется backend-ом; frontend **не** является authoritative.

**Совместимость с Personnel Event Engine:**

- Apply создаёт `employee_events` с `lifecycle_status = APPROVED` (PE-001).
- Void applied переводит events в `VOIDED` — `is_applied` становится `false` без изменения `order.status` path.
- Compensating order создаёт **новые** events; source order `status` не меняется.

### 4.3. Composite lifecycle view (status × applied × archived)

```text
                    ┌──────────────────────────────────────┐
                    │  status (legal)                       │
                    │  DRAFT → READY → SIGNED/REGISTERED   │
                    │           ↓ void_kind                 │
                    │         VOIDED (terminal)             │
                    └──────────────────────────────────────┘
                    ┌──────────────────────────────────────┐
                    │  is_applied (computed)                │
                    │  false until APPROVED events exist    │
                    └──────────────────────────────────────┘
                    ┌──────────────────────────────────────┐
                    │  is_archived (orthogonal flag)        │
                    │  independent of status & is_applied   │
                    └──────────────────────────────────────┘
```

---

## 5. Archive model

### 5.1. Сравнение вариантов

| Критерий | A: `ARCHIVED` status | B: orthogonal flag |
|----------|---------------------|-------------------|
| Юридическая семантика | Смешивает visibility с legal state | Разделены |
| `REGISTERED` + hidden | Невозможно без потери REGISTERED | `status=REGISTERED, archived_at≠null` |
| `VOIDED` + hidden | Требует `VOIDED→ARCHIVED` transition | `VOIDED` + flag |
| Фильтры журнала | `status NOT IN (ARCHIVED)` | `archived_at IS NULL` (default) |
| ADR-035 / void service | Новый terminal status | Без изменений void logic |
| Миграция | Backfill VOIDED→ARCHIVED рискован | Nullable columns only |

### 5.2. Рекомендация — **Вариант B (однозначно)**

```text
personnel_orders.archived_at   TIMESTAMPTZ NULL
personnel_orders.archived_by   BIGINT NULL → users
personnel_orders.archive_reason_code  TEXT NULL
personnel_orders.archive_reason_text  TEXT NULL
```

**Инварианты:**

- Archive **не** меняет `order.status`, `void_kind`, events.
- Restore **не** меняет `order.status`; только сбрасывает archive fields.
- Default journal list: `archived_at IS NULL` (configurable filter `include_archived=true`).
- Archived orders: read, print, search, audit — полный доступ в scope.

---

## 6. Permission taxonomy

### 6.1. Фактическая модель проекта

| Механизм | Где | Использование на PO routes |
|----------|-----|---------------------------|
| `access_grants` → `access_roles.code` | `admin_permissions.py`, `personnel_admin_guard.py` | `HR_ENROLLMENT_MANAGER`, `SYSADMIN_CABINET`, `ACCESS_ADMIN` |
| `require_personnel_admin_or_403` | `personnel_orders_routes.py` | Все write lifecycle endpoints |
| `has_hr_governance_permission` | `admin_permissions.py` | **Не подключён** к personnel-orders |
| ACCESS-001 PD-5.2 | `HR_ENROLLMENT_MANAGER` (candidate) | Baseline кадровое оформление |
| ACCESS-002 | Management subtree | Orthogonal; head scope для `cancel.scope` |

**Naming convention:** проект использует `access_roles.code` в **UPPER_SNAKE_CASE** (`HR_ENROLLMENT_MANAGER`), **не** dot-notation (`personnel.orders.cancel.own`). Спецификация вводит logical keys (dot) **и** implementation codes (UPPER_SNAKE) с 1:1 mapping.

### 6.2. Permission registry

| Logical key | `access_roles.code` | Назначение | PD domain |
|-------------|---------------------|------------|-----------|
| `personnel.orders.read` | *(existing baseline)* `HR_ENROLLMENT_MANAGER` | Read journal/detail | PD-5.2 |
| `personnel.orders.cancel.own` | `PERSONNEL_ORDERS_CANCEL_OWN` | Cancel own DRAFT/READY | PD-5.2 |
| `personnel.orders.cancel.scope` | `PERSONNEL_ORDERS_CANCEL_SCOPE` | Cancel subordinate scope DRAFT/READY | PD-5.2 + ACCESS-002 subtree |
| `personnel.orders.void` | `PERSONNEL_ORDERS_VOID` | Annul SIGNED/REGISTERED not-applied | PD-5.2 |
| `personnel.orders.void_applied` | `PERSONNEL_ORDERS_VOID_APPLIED` | Governance void+rollback applied | PD-5.3 / elevated |
| `personnel.orders.archive` | `PERSONNEL_ORDERS_ARCHIVE` | Archive completed/voided | PD-5.2 head |
| `personnel.orders.restore` | `PERSONNEL_ORDERS_RESTORE` | Restore from archive | PD-5.2 head |
| `personnel.orders.audit.read` | `PERSONNEL_ORDERS_AUDIT_READ` | Lifecycle audit trail | PD-5.3 |
| `personnel.orders.hard_delete` | `PERSONNEL_RECOVERY_ADMIN` | Maintenance hard delete | Recovery (PO-LIFECYCLE-002) |

**Не связывать с sysadmin:** `SYSADMIN_CABINET` / `ACCESS_ADMIN` дают **technical** bypass для break-glass, но **не** заменяют кадровые grants в нормальном enforcement path. Shadow mode: admin bypass логируется как elevated action.

### 6.3. Permission detail matrix

| Permission | Допустимые status | Applied restriction | Ownership | Org scope | Reason | Secondary approval | Technical admin |
|------------|-------------------|---------------------|-----------|-----------|--------|-------------------|-----------------|
| `CANCEL_OWN` | DRAFT, READY | `is_applied=false` (always for these statuses) | `created_by = actor` | n/a | optional; `other` → text required | no | **no** |
| `CANCEL_SCOPE` | DRAFT, READY | same | author in actor subtree | HR dept subtree | optional; `other` → text | no | **no** |
| `VOID` | SIGNED, REGISTERED | `is_applied=false` | any in HR scope | HR operational scope | **required** | no | **no** |
| `VOID_APPLIED` | SIGNED, REGISTERED | `is_applied=true` | governance | HR governance scope | **required** + code | **recommended** | **no** |
| `ARCHIVE` | any non-archived | typically VOIDED or applied+stable | any in scope | HR scope | optional; `other` → text | no | **no** |
| `RESTORE` | archived | any | any in scope | HR scope | optional | no | **no** |
| `AUDIT_READ` | any | any | read scope | HR scope + auditors | n/a | n/a | read-only OK for `SECURITY_AUDITOR` |
| `HARD_DELETE` | any | **no events** | n/a | n/a | **required** | **required** | **yes** (recovery only) |

### 6.4. Role → grant mapping (target, не runtime today)

| Organizational role | Grants (minimum) |
|---------------------|------------------|
| HR operator (кадровик) | `HR_ENROLLMENT_MANAGER` + `CANCEL_OWN` + read |
| HR head (руководитель ОК) | operator + `CANCEL_SCOPE` + `VOID` + `ARCHIVE` + `RESTORE` |
| HR governance (зам/контроль) | head + `VOID_APPLIED` + `AUDIT_READ` |
| Security auditor | `SECURITY_AUDITOR` + `AUDIT_READ` |
| Recovery admin | `PERSONNEL_RECOVERY_ADMIN` (isolated contour) |

Binding через ADR-053 `permission_template_contour_rule` после ACCESS-001 **Approved**; до cutover — explicit `access_grants` inserts.

---

## 7. Ownership and org scope

### 7.1. Authoritative owner (v1)

**Решение:** `created_by` — authoritative owner для ownership checks в WP-003/004.

| Вопрос | Ответ |
|--------|-------|
| 1. Можно ли использовать только `created_by`? | **Да** для v1 cancel.own |
| 2. Нужно ли `owner_user_id`? | **Defer** — вводить при transfer-of-responsibility WP |
| 3. Нужно ли `owner_position_id`? | **Defer** — полезно для Cabinet audit, не блокер v1 |
| 4. Нужен ли `responsible_org_unit_id`? | **Defer** — выводимый из author position / HR dept constant |
| 5. Как руководитель получает права на документы подчинённых? | `CANCEL_SCOPE` + ACCESS-002 subtree: author `created_by` ∈ managed subtree(actor) |
| 6. Исторические записи без ownership metadata? | `created_by` NOT NULL (FK RESTRICT) — всегда есть; при уволенном авторе ownership **не** передаётся автоматически |

### 7.2. Org scope resolution (v1 algorithm)

```text
actor_org_scope := resolve_hr_operational_scope(actor_user_id)
  -- v1: HR department subtree (contour 1,73,*) OR explicit grant scope JSON

order_in_scope :=
  EXISTS (
    SELECT 1 FROM personnel_order_items i
    JOIN employees e ON e.employee_id = i.employee_id
    WHERE i.order_id = :order_id
      AND e.org_unit_id IN actor_org_scope
  )
  OR (
    -- draft without items: author-based fallback
    NOT EXISTS (SELECT 1 FROM personnel_order_items WHERE order_id = :order_id)
    AND order.created_by IN subordinate_users(actor)
  )
```

**Принцип:** cross-org void/archive **запрещён** вне `actor_org_scope`.

### 7.3. Recommended ownership model (phased)

| Phase | Fields | Scope |
|-------|--------|-------|
| v1 (DEL-003/004) | `created_by` | cancel.own / cancel.scope |
| v2 (DEL-007+) | `owner_user_id`, `responsible_org_unit_id` | explicit reassignment |
| v3 (Cabinet) | `owner_position_id` | Cabinet-anchored ownership per ADR-050 |

---

## 8. Permission decision algorithm

Единый backend entry point: `assert_personnel_order_lifecycle_action(conn, *, action, order_id, actor_ctx, payload)`.

```text
1. RESOLVE ORDER
   - load order row (status, void_kind, archived_at, created_by)
   - compute is_applied from employee_events ledger
   - reject if order not found → 404

2. CHECK ARCHIVE ORTHOGONALITY
   - ARCHIVE: require archived_at IS NULL
   - RESTORE: require archived_at IS NOT NULL
   - CANCEL/VOID: archived orders → 409 ARCHIVED_ORDER_IMMUTABLE

3. CHECK LIFECYCLE STATE
   - map action → allowed status set (§2.3 matrix)
   - reject mismatch → 409 INVALID_LIFECYCLE_STATE

4. CHECK APPLIED STATE
   - VOID (standard): require is_applied = false
   - VOID_APPLIED: require is_applied = true
   - CANCEL: implicit false (pre-reg statuses)

5. CHECK PERMISSION GRANT
   - resolve actor access_roles via access_resolver_service
   - match action → required permission code(s)
   - reject → 403 PERMISSION_DENIED

6. CHECK OWNERSHIP / ORG SCOPE
   - CANCEL_OWN: created_by = actor.user_id
   - CANCEL_SCOPE / VOID / ARCHIVE: order_in_scope(actor)
   - VOID_APPLIED: governance scope (stricter)

7. CHECK ELEVATED GOVERNANCE (VOID_APPLIED only)
   - void chain guard (ADR-035) per employee in order
   - optional secondary_approval_token validation (future)

8. CHECK REASON
   - validate reason_code against taxonomy (§12)
   - if code = OTHER or action requires reason → reason_text non-empty

9. IDEMPOTENCY
   - if target state already reached → return 200 with unchanged detail (no duplicate audit)
   - void already VOIDED same void_kind → idempotent success

10. EXECUTE IN TRANSACTION
    - mutate order / events per action handler
    - insert personnel_order_lifecycle_audit row (append-only)

11. EMIT RESPONSE
    - return PersonnelOrderDetailResponse with computed is_applied
```

**Критично:** frontend visibility — hint only; steps 5–8 **всегда** на backend.

---

## 9. Cancel vs void compatibility decision

### 9.1. Сравнение вариантов

| Критерий | A: `VOIDED` + `void_kind` | B: `CANCELLED` status | C: migrate both statuses |
|----------|---------------------------|------------------------|--------------------------|
| ADR-035 void chain | Без изменений | Новый terminal | Breaking |
| `POST …/void` API | Расширить payload | Split endpoints | Dual maintenance |
| Tests WP-PO-004D | Minimal update | Rewrite expectations | Full migration |
| `status=VOIDED` filter | Сохраняется | Нужен `IN (VOIDED,CANCELLED)` | Breaking filters |
| Print watermark | `void_kind` drives label | Status drives label | Both |
| PO-EDIT write lock | `VOIDED` read-only | + `CANCELLED` | Enum expansion |
| DB CHECK constraint | + column, not enum | + enum value | + migration + backfill |

### 9.2. Решение — **Вариант A (подтверждён)**

```text
status = VOIDED          -- unchanged terminal
void_kind = CANCEL | ANNUL   -- new NOT NULL when status=VOIDED (after migration)
```

**Semantics:**

- `CANCEL`: pre-registration void; **no** employee_events touch; UI «Отменён».
- `ANNUL`: post-registration void; cascade void events + rollback; UI «Аннулирован».

### 9.3. Migration strategy

```sql
-- Phase 1: add nullable void_kind
ALTER TABLE personnel_orders ADD COLUMN void_kind TEXT NULL;
ALTER TABLE personnel_orders ADD CONSTRAINT chk_personnel_orders_void_kind CHECK (
  void_kind IS NULL OR void_kind IN ('CANCEL', 'ANNUL')
);

-- Phase 2: backfill heuristic (see §16)
UPDATE personnel_orders SET void_kind = 'CANCEL'
  WHERE status = 'VOIDED' AND <cancel inference>;
UPDATE personnel_orders SET void_kind = 'ANNUL'
  WHERE status = 'VOIDED' AND void_kind IS NULL;

-- Phase 3: enforce NOT NULL when VOIDED
ALTER TABLE personnel_orders ADD CONSTRAINT chk_personnel_orders_voided_kind CHECK (
  status <> 'VOIDED' OR void_kind IS NOT NULL
);
```

**API compatibility:**

- Сохранить `POST /personnel-orders/{id}/void` — для `SIGNED`/`REGISTERED` (sets `void_kind=ANNUL`).
- Добавить `POST /personnel-orders/{id}/cancel` — для `DRAFT`/`READY` (sets `void_kind=CANCEL`).
- Void endpoint на pre-reg statuses: **deprecated** → redirect internally to cancel (WP-006) с warning header `Deprecation: use /cancel`.

---

## 10. Applied-order correction policy

### 10.1. Dual path

```text
PRIMARY (default UX):
  Create compensating order
    - reversal_of_order_id → source order
    - replacement_order_id → optional correcting order
    - own order_number, order_date
    - new compensation events via apply
    - source order UNCHANGED (status, events preserved)

SECONDARY (governance only):
  VOID_APPLIED + existing void_personnel_order
    - PERSONNEL_ORDERS_VOID_APPLIED grant
    - mandatory reason_code + reason_text
    - ADR-035 void chain per employee
    - transaction: void events + rollback snapshot
    - idempotent on re-submit
    - audit row action = VOID_APPLIED
```

### 10.2. Compensating action by item type

| Item type | Рекомендуемое компенсирующее действие | Auto-reversal опасен? |
| --------- | --------------------------------------- | --------------------- |
| `HIRE` | `TERMINATION` или специальная отмена приёма | **High** — overlapping employment |
| `TRANSFER` | Обратный `TRANSFER` | Medium — rate/position drift |
| `TERMINATION` | `HIRE` / reinstatement order | **High** — legal reinstatement rules |
| `RATE_CHANGE` | Compensating rate restore | Medium |
| `CONCURRENT_DUTY_START` | `CONCURRENT_DUTY_END` | Low–Medium |
| `CONCURRENT_DUTY_END` | Повторное `CONCURRENT_DUTY_START` | Medium |
| `COMPOSITE` | Per-item decomposition | **High** — mixed effects |

**Governance void rollback** (`_rollback_snapshot_for_event`) остаётся fallback; не проектировать полную auto-reversal матрицу в этом WP.

### 10.3. Chain guard (unchanged)

Void applied blocked when newer APPROVED events exist for same employee (ADR-035). Compensating order **не** обходит chain — создаёт forward correction.

---

## 11. Audit schema

### 11.1. Entity: `personnel_order_lifecycle_audit`

```sql
CREATE TABLE personnel_order_lifecycle_audit (
    audit_id            BIGSERIAL PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES personnel_orders(order_id) ON DELETE RESTRICT,
    action              TEXT NOT NULL,
    previous_status     TEXT NULL,
    new_status          TEXT NULL,
    previous_void_kind  TEXT NULL,
    new_void_kind       TEXT NULL,
    previous_archived_at TIMESTAMPTZ NULL,
    new_archived_at     TIMESTAMPTZ NULL,
    actor_user_id       BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    actor_position_id   BIGINT NULL,
    actor_org_unit_id   BIGINT NULL,
    reason_code         TEXT NULL,
    reason_text         TEXT NULL,
    related_order_id    BIGINT NULL REFERENCES personnel_orders(order_id) ON DELETE RESTRICT,
    request_id          TEXT NULL,
    idempotency_key     TEXT NULL,
    metadata_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**`action` enum:** `CANCEL`, `ANNUL`, `ARCHIVE`, `RESTORE`, `VOID_APPLIED`, `HARD_DELETE`, `COMPENSATE_LINK` (future).

### 11.2. Snapshot policy

| Уровень | Содержимое | Когда |
|---------|------------|-------|
| Lifecycle metadata only | status, void_kind, archived_at, reason | **Default** — все actions |
| Event correlation | `metadata_json.event_ids[]`, `rollback_digest` | ANNUL, VOID_APPLIED |
| Full JSON snapshot | header + items hash | HARD_DELETE only |
| Hash/digest | `sha256(canonical_json)` | HARD_DELETE, optional VOID_APPLIED |

**Не** дублировать полный order JSON на каждый cancel — достаточно lifecycle metadata.

### 11.3. Policies

| Policy | Rule |
|--------|------|
| Append-only | INSERT only; UPDATE/DELETE forbidden (DB trigger or role) |
| FK strategy | `ON DELETE RESTRICT` — audit переживает soft references |
| Retention | Indefinite (legal); archive old partitions — ops WP |
| Visibility | `AUDIT_READ` + `SECURITY_AUDITOR` |
| Indexes | `(order_id, created_at DESC)`, `(actor_user_id, created_at DESC)`, `(action)`, unique partial `(idempotency_key) WHERE idempotency_key IS NOT NULL` |
| Idempotency | Client sends `Idempotency-Key` header → unique constraint prevents duplicate rows |
| Employee event correlation | `metadata_json.affected_event_ids` on void paths |

---

## 12. Reason taxonomy

### 12.1. Cancel (draft / ready)

| `reason_code` | Label (RU) |
|---------------|------------|
| `DUPLICATE` | Дубликат |
| `CREATED_BY_MISTAKE` | Создан по ошибке |
| `NO_LONGER_REQUIRED` | Больше не требуется |
| `REPLACED_BEFORE_REGISTRATION` | Заменён до регистрации |
| `TEST_RECORD` | Тестовая запись |
| `OTHER` | Другое |

### 12.2. Void registered order

| `reason_code` | Label (RU) |
|---------------|------------|
| `REGISTRATION_ERROR` | Ошибка регистрации |
| `INCORRECT_EMPLOYEE` | Неверный сотрудник |
| `INCORRECT_TERMS` | Неверные условия |
| `LEGAL_BASIS_INVALID` | Недействительное основание |
| `REPLACED_BY_ORDER` | Заменён другим приказом |
| `GOVERNANCE_DECISION` | Решение руководства |
| `OTHER` | Другое |

### 12.3. Archive

| `reason_code` | Label (RU) |
|---------------|------------|
| `LIFECYCLE_COMPLETED` | Жизненный цикл завершён |
| `VOIDED_RECORD` | Аннулированная запись |
| `MIGRATED_LEGACY` | Мигрировано из legacy |
| `DUPLICATE_REFERENCE` | Дублирующая ссылка |
| `OTHER` | Другое |

### 12.4. Free-text rules

| Condition | `reason_text` |
|-----------|---------------|
| `reason_code = OTHER` | **Обязателен** (non-empty trim) |
| `ANNUL`, `VOID_APPLIED` | **Обязателен** всегда (даже с classified code) |
| `CANCEL` with non-OTHER code | Optional |
| `ARCHIVE`, `RESTORE` | Optional unless `OTHER` |

---

## 13. API proposal

### 13.1. Endpoints

| Method | Path | Action | Replaces |
|--------|------|--------|----------|
| `POST` | `/directory/personnel-orders/{id}/cancel` | Cancel pre-reg | void on DRAFT/READY (deprecated) |
| `POST` | `/directory/personnel-orders/{id}/void` | Annul post-reg | existing endpoint (extended) |
| `POST` | `/directory/personnel-orders/{id}/archive` | Archive | new |
| `POST` | `/directory/personnel-orders/{id}/restore` | Restore | new |
| `GET` | `/directory/personnel-orders/{id}/lifecycle-audit` | Audit list | new |
| — | `DELETE …` | — | **not proposed** |

Base path follows existing router prefix `/directory`.

### 13.2. `POST …/cancel`

**Permission:** `PERSONNEL_ORDERS_CANCEL_OWN` or `PERSONNEL_ORDERS_CANCEL_SCOPE`

**Preconditions:** `status ∈ {DRAFT, READY_FOR_SIGNATURE}`, `archived_at IS NULL`, `is_applied = false`

**Request:**

```json
{
  "reason_code": "CREATED_BY_MISTAKE",
  "reason_text": null,
  "idempotency_key": "optional-uuid"
}
```

**Response:** `200 PersonnelOrderDetailResponse` with `status=VOIDED`, `void_kind=CANCEL`

**Errors:**

| Code | HTTP | When |
|------|------|------|
| `PERMISSION_DENIED` | 403 | no grant / ownership |
| `INVALID_LIFECYCLE_STATE` | 409 | wrong status |
| `ARCHIVED_ORDER_IMMUTABLE` | 409 | archived |
| `VALIDATION_ERROR` | 422 | bad reason |

**Idempotency:** already `VOIDED` + `void_kind=CANCEL` → 200 no-op.

### 13.3. `POST …/void` (extended, backward compatible)

**Permission:** `PERSONNEL_ORDERS_VOID` or `PERSONNEL_ORDERS_VOID_APPLIED` (if `is_applied`)

**Preconditions:** `status ∈ {SIGNED, REGISTERED}`, `archived_at IS NULL`

**Request:**

```json
{
  "void_reason": "текст",
  "reason_code": "REGISTRATION_ERROR",
  "idempotency_key": "optional-uuid"
}
```

`void_reason` retained for backward compatibility (= `reason_text` canonical going forward).

**Response:** `200 PersonnelOrderDetailResponse` with `void_kind=ANNUL`

**Errors:** + `VOID_CHAIN_VIOLATION` (409) from ADR-035

**Idempotency:** already `VOIDED` + `void_kind=ANNUL` → 200

### 13.4. `POST …/archive`

**Permission:** `PERSONNEL_ORDERS_ARCHIVE`

**Preconditions:** `archived_at IS NULL`

**Request:**

```json
{
  "reason_code": "VOIDED_RECORD",
  "reason_text": null
}
```

**Response:** `200` with `archived_at` set; `status` unchanged

### 13.5. `POST …/restore`

**Permission:** `PERSONNEL_ORDERS_RESTORE`

**Preconditions:** `archived_at IS NOT NULL`

**Request:** `{}` or optional reason

**Response:** `200` with `archived_at = null`

### 13.6. `GET …/lifecycle-audit`

**Permission:** `PERSONNEL_ORDERS_AUDIT_READ`

**Query:** `?limit=50&offset=0`

**Response:**

```json
{
  "items": [{ "audit_id": 1, "action": "ANNUL", "created_at": "...", "actor_user_id": 5, "reason_code": "..." }],
  "total": 1
}
```

### 13.7. List filter extensions

```
GET /directory/personnel-orders?status=VOIDED&void_kind=ANNUL
GET /directory/personnel-orders?include_archived=false   -- default
GET /directory/personnel-orders?archived_only=true
```

---

## 14. DB change proposal

### 14.1. Minimal foundation (WP-003 + WP-005)

**`personnel_orders` columns:**

```text
void_kind              TEXT NULL → NOT NULL when VOIDED
archived_at            TIMESTAMPTZ NULL
archived_by            BIGINT NULL → users(user_id)
archive_reason_code    TEXT NULL
archive_reason_text    TEXT NULL
```

**New table:** `personnel_order_lifecycle_audit` (§11)

**New `access_roles` rows:** `PERSONNEL_ORDERS_*` codes (§6.2)

**No change:** `ORDER_STATUSES` enum in code (still 5 values)

### 14.2. Extended (WP-007+)

```text
owner_user_id          BIGINT NULL → users
owner_position_id      BIGINT NULL → positions/catalog
responsible_org_unit_id BIGINT NULL → org_units
reversal_of_order_id   BIGINT NULL → personnel_orders
replacement_order_id   BIGINT NULL → personnel_orders
```

### 14.3. Phasing

| WP | DB scope |
|----|----------|
| DEL-003 | audit table + permission role seeds + `void_kind` nullable |
| DEL-004 | ownership enforcement (no new columns) |
| DEL-005 | archive columns |
| DEL-006 | void_kind backfill + NOT NULL constraint + cancel route |
| DEL-007 | reversal/replacement FK columns |

---

## 15. UI action matrix

| Состояние | Applied | Permission | Действие (кнопка) | Severity | Confirm |
|-----------|--------:|------------|-------------------|----------|---------|
| DRAFT own | no | `CANCEL_OWN` | **Отменить черновик** | `neutral` / secondary | simple confirm |
| DRAFT subordinate | no | `CANCEL_SCOPE` | **Отменить** | `warning` | confirm + optional reason |
| READY | no | `CANCEL_SCOPE` | **Отменить** | `warning` | confirm |
| SIGNED/REG | no | `VOID` | **Аннулировать** | `danger` | modal + required reason |
| SIGNED/REG | yes | `VOID_APPLIED` | **Исключительное аннулирование** | `danger` | modal + warning consequences + chain info |
| SIGNED/REG | yes | *(read)* | **Создать корректирующий приказ** | `primary` | navigation, not destructive |
| VOIDED | any | `ARCHIVE` | **Архивировать** | `neutral` | optional reason |
| archived | any | `RESTORE` | **Восстановить из архива** | `neutral` | confirm |

### 15.1. UI rules

- **Запрет универсальной «Удалить»** — нет кнопки Delete на production drawer.
- **Applied badge:** `PersonnelOrderAppliedBadge` when `is_applied`; tooltip «Кадровые события созданы».
- **Archived badge:** «В архиве» when `archived_at`; hidden from default list.
- **Void dialog:** stage-aware copy — cancel vs annul; void_applied shows rollback warning.
- **Print:** `void_kind=CANCEL` → watermark «ОТМЕНЁН»; `ANNUL` → «АННУЛИРОВАН» (existing).
- **Permissions:** UI hides buttons; backend enforces (§8).

---

## 16. Backward compatibility

### 16.1. `VOIDED` without `void_kind`

**Backfill heuristic:**

```text
IF status = VOIDED AND void_kind IS NULL:
  IF EXISTS employee_events(order_id) → ANNUL
  ELIF status_before_void IN (SIGNED, REGISTERED) → ANNUL  -- from audit if available
  ELIF order_number IS NOT NULL AND order_date IS NOT NULL
       AND voided_at > created_at + interval '1 minute' → ANNUL  -- likely registered
  ELSE → CANCEL
```

| Heuristic branch | Reliability |
|------------------|-------------|
| Has APPROVED/VOIDED events | **High** |
| `signed_by_*` populated | **Medium** |
| `order_number` assigned pre-void | **Medium** |
| DRAFT voided same session | **High** → CANCEL |
| Legacy voided READY without number | **Medium** → CANCEL |

**Fallback:** manual review queue for `void_kind IS NULL` after backfill (should be 0 rows).

### 16.2. Other compat

| Artifact | Behavior |
|----------|----------|
| `void_reason` on order | Preserved; mapped to `reason_text` in audit |
| Records with employee events | `void_kind=ANNUL`; void chain rules apply |
| No ownership metadata | `created_by` always present |
| Frontend `status=VOIDED` filter | Unchanged; optional `void_kind` filter added |
| PDF watermark | Uses `void_kind` when present; fallback «АННУЛИРОВАН» |
| API clients using `POST …/void` on drafts | Continue working until DEP-006; deprecation header |
| Tests WP-PO-004D | Add `void_kind` assertions; no status enum change |

---

## 17. Implementation sequence

```text
WP-PO-LC-DEL-003 — audit schema, permission grants, audit read API
WP-PO-LC-DEL-004 — cancel command + ownership enforcement
WP-PO-LC-DEL-005 — archive / restore + journal filters
WP-PO-LC-DEL-006 — void_kind backfill + cancel/void API split + UX labels
WP-PO-LC-DEL-007 — compensating order links + governance void hardening
WP-PO-LC-DEL-008 — lifecycle UI polish + audit viewer
```

### WP-PO-LC-DEL-003 — Audit schema and permission grants

| Field | Value |
|-------|-------|
| **Scope** | Migration: `personnel_order_lifecycle_audit`; seed `PERSONNEL_ORDERS_*` roles; `GET lifecycle-audit`; hook void service to write audit rows (no semantic change) |
| **Prerequisites** | This spec approved |
| **DB** | New audit table; `void_kind` nullable column |
| **API** | Read-only audit endpoint |
| **UI** | None |
| **Risks** | Grant seed in non-prod only first; audit volume |
| **DoD** | Audit row on every void; permissions queryable; tests for append-only |

### WP-PO-LC-DEL-004 — Cancel command and ownership

| Field | Value |
|-------|-------|
| **Scope** | `POST …/cancel`; `assert_personnel_order_lifecycle_action`; `CANCEL_OWN`/`CANCEL_SCOPE` enforcement |
| **Prerequisites** | DEL-003 |
| **DB** | None beyond 003 |
| **API** | New cancel endpoint |
| **UI** | Optional label fix |
| **Risks** | Scope resolver accuracy |
| **DoD** | Own vs foreign draft tested; 403 without grant |

### WP-PO-LC-DEL-005 — Archive and restore

| Field | Value |
|-------|-------|
| **Scope** | Archive columns; `POST archive/restore`; list filters `include_archived` |
| **Prerequisites** | DEL-003 |
| **DB** | `archived_*` columns |
| **API** | archive, restore |
| **UI** | Archive badge (minimal) |
| **Risks** | Default filter hides records — UX communication |
| **DoD** | Roundtrip archive→restore; archived excluded from default list |

### WP-PO-LC-DEL-006 — Split cancel/void semantics

| Field | Value |
|-------|-------|
| **Scope** | `void_kind` backfill migration; void sets ANNUL; cancel sets CANCEL; print watermark split; deprecate void-on-draft |
| **Prerequisites** | DEL-004, DEL-005 |
| **DB** | void_kind NOT NULL constraint |
| **API** | void hardening; governance gate stub for applied |
| **UI** | Stage-aware buttons and dialogs |
| **Risks** | Backfill misclassification — run validation report |
| **DoD** | Zero NULL void_kind; UI labels correct per stage |

### WP-PO-LC-DEL-007 — Compensating order links

| Field | Value |
|-------|-------|
| **Scope** | `reversal_of_order_id`, `replacement_order_id`; `VOID_APPLIED` permission; void chain UI messaging |
| **Prerequisites** | DEL-006 |
| **DB** | FK columns |
| **API** | Link fields on create; void_applied gate |
| **UI** | «Создать корректирующий приказ» CTA |
| **Risks** | TERMINATION/HIRE auto-reversal |
| **DoD** | Compensating order link persisted; void_applied requires elevated grant |

### WP-PO-LC-DEL-008 — Lifecycle UI and audit viewer

| Field | Value |
|-------|-------|
| **Scope** | Audit viewer tab; archive view; permission-aware action bar; E2E tests |
| **Prerequisites** | DEL-003…007 |
| **UI** | Full matrix §15 |
| **DoD** | E2E cancel/annul/archive; audit visible to governance |

---

## 18. Open questions

| # | Question | Proposed default | Decision owner |
|---|----------|------------------|----------------|
| 1 | Reuse `order_number` after CANCEL? | **No** — preserve UNIQUE integrity | HR policy WP |
| 2 | Dual approval for VOID_APPLIED? | Recommended; implement as phase 2 | Governance |
| 3 | Soft delete (`deleted_at`) for empty DRAFT? | Defer; CANCEL sufficient for v1 | Architecture |
| 4 | Item-level void UI? | Separate WP; API exists | Product |
| 5 | `SECURITY_AUDITOR` read-only on orders? | Audit endpoint only, not mutation | Security |
| 6 | HR head contour binding `(1,73,86)` | Pending ACCESS-001 WP-B4 | Ops |

---

## 19. Ratification checklist

- [ ] HR policy owner: cancel/annul terminology approved
- [ ] Architecture: `void_kind` + orthogonal archive approved
- [ ] Security: permission codes + no sysadmin HR bypass approved
- [ ] PE owner: computed `is_applied` compatible with Event Engine
- [ ] Ops: `PERSONNEL_ORDERS_*` grant seed plan approved
- [ ] UI/UX: stage-aware action matrix approved
- [ ] Backfill heuristic validated on staging copy
- [ ] PO-LIFECYCLE-002 alignment confirmed (hard delete policy)
- [ ] ADR-035 void chain preserved in VOID_APPLIED path

---

## Appendix A — Source files

| Area | Path |
|------|------|
| Void service | `app/services/personnel_orders_void_service.py` |
| Routes | `app/directory/personnel_orders_routes.py` |
| Models | `app/db/models/personnel_orders.py` |
| Permissions | `app/security/admin_permissions.py`, `personnel_admin_guard.py` |
| UI lifecycle | `corpsite-ui/.../PersonnelOrderLifecycleActions.tsx` |
| UI labels | `corpsite-ui/.../personnelOrderLabels.ts` |
| Print watermark | `corpsite-ui/.../personnelOrderPrintViewModel.ts` |
| Research | `docs/personnel-orders/PO-LC-DEL-001-deletion-cancellation-archival-research.md` |
| Policy | `docs/personnel-orders/PO-LIFECYCLE-002-delete-and-void-policy.md` |
| Void chain ADR | `docs/adr/ADR-035-hr-transfer-approval-and-event-voiding.md` |
