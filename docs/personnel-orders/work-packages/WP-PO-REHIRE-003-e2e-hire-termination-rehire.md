# WP-PO-REHIRE-003 — E2E: Hire → Termination → Rehire

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | REHIRE |
| Предшественник | WP-PO-REHIRE-001, WP-PO-REHIRE-002 |
| Test file (target) | `tests/test_ppr_hire_termination_rehire_e2e.py` |

---

## Purpose

End-to-end integration test полного employment lifecycle на одном Person / одной PPR / одном Employee row.

---

## Scenario

```text
1. Applicant → HIRE → Apply          (forward-flow)
2. Assert EMPLOYED + active Employee
3. TERMINATION order → Apply
4. Assert FORMER_EMPLOYEE + inactive Employee  (WP-REHIRE-001)
5. HIRE order with employee_id → Apply
6. Assert EMPLOYED + active Employee           (WP-REHIRE-002)
7. Assert invariants:
   - 1 Person, 1 PPR, 1 Employee
   - person_education/training sections unchanged (same person_id)
   - no duplicate employee_events for same order
```

---

## Assertions

| Checkpoint | Expected |
|------------|----------|
| After step 2 | 1 PPR, 1 Employee, hr_context=EMPLOYED |
| After step 4 | hr_context=FORMER_EMPLOYEE, is_active=FALSE |
| After step 6 | hr_context=EMPLOYED, is_active=TRUE, same employee_id |
| Cards | Single PPR URL by person_id throughout |

---

## Acceptance criteria

1. Test green on PostgreSQL.
2. Confirms architecture supports rehire without new card/PPR.
3. Serves as regression gate for WP-PO-REHIRE-001/002.
