# ADR-042 Phase B2 — Migration Plan (Implemented)

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase B1 — DB Schema Design](./ADR-042-phase-b1-schema-design.md)
- [ADR-042 Phase A — Architecture](./ADR-042-phase-a-personnel-access-enrollment-architecture.md)
- [Validation SQL](./ADR-042-phase-b2-validation.sql)

---

## Alembic revisions

| Revision | File | Scope |
|----------|------|-------|
| `u3v4w5x6y7z8` | `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` | DDL + `access_roles` seed |
| `v4w5x6y7z8a9` | `alembic/versions/v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py` | Idempotent legacy backfill |
| `w5x6y7z8a9b0` | `alembic/versions/w5x6y7z8a9b0_adr042_phase_b5_access_roles_seed.py` | B5 seed: `SECURITY_AUDITOR` role |

**Chain:** `t2u3v4w5x6y7` → `u3v4w5x6y7z8` → `v4w5x6y7z8a9` → `w5x6y7z8a9b0` (head)

---

## Новые таблицы

1. `persons`
2. `person_assignments`
3. `employee_assignment_links`
4. `enrollment_queue`
5. `enrollment_history`
6. `access_roles`
7. `access_grants`
8. `security_audit_log`

---

## Расширенные таблицы

### `employees` (ADD columns)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `person_id` | BIGINT FK → persons | YES | NULL |
| `operational_status` | TEXT | NO | `'active'` |
| `enrolled_at` | TIMESTAMPTZ | YES | NULL |
| `enrolled_by_user_id` | BIGINT FK → users | YES | NULL |
| `enrollment_source` | TEXT | NO | `'migration'` |
| `updated_at` | TIMESTAMPTZ | YES | NULL |

Legacy columns **не изменены**: `full_name`, `org_unit_id`, `position_id`, `employment_rate`, `date_from`, `date_to`, `is_active`, `department_id`.

### `users` (ADD columns)

| Column | Type | Default |
|--------|------|---------|
| `must_change_password` | BOOLEAN | FALSE |
| `password_changed_at` | TIMESTAMPTZ | NULL |
| `temp_password_expires_at` | TIMESTAMPTZ | NULL |
| `failed_login_count` | INTEGER | 0 |
| `locked_at` | TIMESTAMPTZ | NULL |
| `locked_until` | TIMESTAMPTZ | NULL |
| `locked_reason` | TEXT | NULL |
| `last_login_at` | TIMESTAMPTZ | NULL |
| `last_failed_login_at` | TIMESTAMPTZ | NULL |
| `token_version` | INTEGER | 1 |

---

## Access roles seed (idempotent)

| code | access_level | level_rank |
|------|--------------|------------|
| ACCESS_NONE | NONE | 0 |
| ACCESS_OBSERVER | OBSERVER | 10 |
| ACCESS_MANAGER | MANAGER | 20 |
| ACCESS_ADMIN | ADMIN | 30 |
| SYSADMIN_CABINET | ADMIN | 30 |
| HR_ENROLLMENT_MANAGER | MANAGER | 20 |

Revision `w5x6y7z8a9b0` (Phase B5) adds:

| code | access_level | level_rank |
|------|--------------|------------|
| SECURITY_AUDITOR | OBSERVER | 10 |

`ON CONFLICT (code) DO UPDATE` — повторный upgrade безопасен.

---

## Backfill rules (revision `v4w5x6y7z8a9`)

```text
employees → persons (IIN dedup, then match_key)
         → employees.person_id
         → person_assignments (primary, source=migration)
         → employee_assignment_links
```

| Field | Source / fallback |
|-------|-------------------|
| IIN | `employee_identities` (IIN, valid_to IS NULL) |
| match_key | `iin:{12}` or `name:{normalized full_name}` |
| org_unit_id | `employees.org_unit_id` → fallback first active org_unit |
| position_id | `employees.position_id` → fallback first position |
| rate | `COALESCE(employment_rate, 1.0)` clamped to (0, 1.5] |
| start_date | `COALESCE(date_from, CURRENT_DATE)` |
| employment_type | `'primary'` (поля нет в legacy employees) |
| enrolled_by | first active `users.user_id` |

**Idempotency:** повторный upgrade backfill не создаёт дубли persons/assignments/links.

**Skip condition:** если нет active users — backfill пропускается (NOTICE).

---

## Запуск

```bash
alembic upgrade head
```

### Validation SQL

```bash
psql "$DATABASE_URL" -f docs/adr/ADR-042-phase-b2-validation.sql
```

Пустой результат в каждом check-query = OK.

### Tests

```bash
pytest tests/test_adr042_phase_b2_schema.py -v
```

---

## Rollback

```bash
# Откат только backfill (сохраняет DDL)
alembic downgrade u3v4w5x6y7z8

# Полный откат Phase B2
alembic downgrade t2u3v4w5x6y7
```

| Downgrade step | Effect |
|----------------|--------|
| `v4w5x6y7z8a9` → `u3v4w5x6y7z8` | Удаляет migration persons/assignments/links; clears `employees.person_id` |
| `u3v4w5x6y7z8` → `t2u3v4w5x6y7` | DROP новых таблиц; DROP новых columns на employees/users |

**Post-backfill rollback:** runtime продолжает работать на legacy `employees` columns.

---

## Known limitations (B2)

1. **No runtime dual-write** — изменения assignments не синхронизируют `employees` snapshot автоматически.
2. **No enrollment detector** — `enrollment_queue` пуст до B3 job/API.
3. **No access evaluator** — grants не применяются в middleware.
4. **No JWT token_version check** — колонка добавлена, логика в B3.
5. **Backfill fallback org/position** — employees без org_unit/position получают первый справочный ID (validation #10 может показать drift если fallback использован).
6. **EXCLUDE overlap constraint** — не добавлен; контроль в service layer (B3).
7. **`employee_identities`** — не мигрирован на `persons`; dual-read в B3.

---

## Out of scope (осталось на B3)

- Enrollment queue detector (hr_change_events → queue)
- Enrollment approve/reject API
- Access grant API + effective access resolver
- Auth policy (lockout, must_change_password, token_version in JWT)
- Security audit writer integration
- Sysadmin Cabinet UI
- Dual-write service flag `PERSON_ASSIGNMENTS_DUAL_WRITE`
- ORM models for new tables

---

## Risks before B3

| Risk | Mitigation |
|------|------------|
| Snapshot drift employees ↔ primary assignment | Validation SQL #10; dual-write in B3 |
| Fallback org/position in backfill | Review validation output; manual correction |
| Empty backfill if no users | Ensure ≥1 active user before migrate on fresh DB |
| access_roles vs task roles confusion | Namespace `/admin/access/*` in B3 |
| Partial unique index person dedup edge cases | Manual merge tool (B3/C) |
