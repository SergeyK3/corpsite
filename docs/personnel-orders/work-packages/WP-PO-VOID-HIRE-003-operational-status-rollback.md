# WP-PO-VOID-HIRE-003 — Rollback operational_status on HIRE void

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | VOID HIRE (applicant-path) |
| Предшественник | Forward-flow «Заявитель → Работник» (**COMPLETE**) |
| Связанные WP | WP-PO-VOID-HIRE-001, WP-PO-VOID-HIRE-002, WP-PO-VOID-HIRE-004 |

---

## Problem

Apply HIRE устанавливает `employees.operational_status = 'active'` (если колонка существует).

`_rollback_hire_snapshot` восстанавливает `is_active`, org/position из `pre_apply_state`, но **не откатывает** `operational_status`.

**Следствие:** возможна inconsistency `is_active = FALSE` + `operational_status = 'active'`.

---

## Target behavior

При void HIRE (applicant-path, pre-apply bootstrap):

```text
operational_status → 'draft'  (или значение из pre_apply_state, если сохранено)
```

Согласованно с inactive Employee до повторного hire.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Extend `_rollback_hire_snapshot` / `_restore_employee_from_pre_apply_state` | operational_status для TRANSFER void |
| Capture `operational_status` в `pre_apply_state` metadata (если ещё не captured) | Enrollment workflow |

---

## Acceptance criteria

1. Applicant → HIRE → Apply → Void: `operational_status != 'active'` при `is_active = FALSE`.
2. Existing void tests для pre-existing employee path не регрессируют.
