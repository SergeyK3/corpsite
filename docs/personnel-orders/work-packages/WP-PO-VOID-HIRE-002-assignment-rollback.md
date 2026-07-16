# WP-PO-VOID-HIRE-002 — Rollback person_assignments on HIRE void

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | VOID HIRE (applicant-path) |
| Предшественник | Forward-flow «Заявитель → Работник» (**COMPLETE**) |
| Связанные WP | WP-PO-VOID-HIRE-001; WP-PO-VOID-HIRE-004 |
| Зависит от | Apply создаёт assignment с `assignment_key = hire:order:{order_id}:item:{item_id}` |

---

## Problem

`_apply_hire` вызывает `ensure_person_assignment_for_hire`, создавая активный `person_assignments` row.

Void HIRE откатывает Employee, но **не деактивирует и не удаляет** связанный Assignment.

**Следствие:** после void остаётся активное назначение, противоречащее inactive Employee — нарушение Source of Truth для операционного контура.

---

## Target behavior

При void applied HIRE (applicant-path):

```text
person_assignments WHERE assignment_key = hire:order:{order_id}:item:{item_id}
  → lifecycle_status = 'voided' OR active_flag = FALSE
```

(конкретная семантика — по ADR-043 / person_assignments lifecycle; минимум — deactivate)

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Rollback assignment, созданного Apply HIRE | Assignment reconciliation bulk jobs |
| Idempotent void (повторный void не меняет assignment повторно) | Void TRANSFER-side effects |

---

## Acceptance criteria

1. Applicant → HIRE → Apply → Void: нет активного primary assignment для person.
2. Assignment row может сохраняться как historical (voided), но не участвует в operational read.
3. Повторный Apply того же voided order — blocked (existing apply guard).
