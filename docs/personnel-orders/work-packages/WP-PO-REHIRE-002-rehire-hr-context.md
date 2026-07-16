# WP-PO-REHIRE-002 — Rehire: hr_relationship_context FORMER_EMPLOYEE → EMPLOYED

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | REHIRE |
| Предшественник | WP-PO-REHIRE-001 |
| Связанные WP | Forward-flow hire apply; `_find_inactive_employee_for_person` |

---

## Problem

Rehire использует **employee_id path** (reuse inactive Employee row) — архитектурно корректно.

Однако после rehire Apply нет symmetric hook для `hr_relationship_context`:
`FORMER_EMPLOYEE → EMPLOYED`.

---

## Target behavior

После успешного Apply HIRE на inactive Employee (rehire path):

```text
hr_relationship_context: FORMER_EMPLOYEE → EMPLOYED
```

Same Person, same PPR, same Employee row reactivated.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Extend `sync_hr_context_after_hire` для FORMER_EMPLOYEE → EMPLOYED | Applicant-path rehire via person_id (blocked by design — correct) |
| HIRE apply via existing `employee_id` | New REHIRE event type (registry has REHIRE — mapping optional) |

---

## Architectural note

Rehire **не создаёт** новую PPR и **не использует** applicant-path (`person_id` without employee_id). Validation:

- `validate_hire_item_identity`: skips CANDIDATE check when `employee_id` present ✅
- `_find_inactive_employee_for_person`: reuses row ✅

---

## Acceptance criteria

1. Hire → Terminate → Rehire (employee_id HIRE): `hr_relationship_context = EMPLOYED`.
2. Employee count for person = 1; PPR count = 1.
3. person_* sections on PPR preserved across cycle.
