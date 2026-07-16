# WP-PO-VOID-HIRE-004 — Integration test: Applicant → Hire → Apply → Void

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | VOID HIRE (applicant-path) |
| Предшественник | WP-PO-VOID-HIRE-001, WP-PO-VOID-HIRE-002, WP-PO-VOID-HIRE-003 |
| Test file (target) | `tests/test_ppr_hire_from_applicant_void.py` |

---

## Purpose

End-to-end integration test, подтверждающий полную консистентность после void HIRE приказа, созданного для заявителя без pre-existing Employee.

---

## Scenario

```text
1. Create Person + PPR envelope (CANDIDATE)
2. Save intended employment (pre-order)
3. Create + register HIRE order (payload.person_id)
4. Apply
5. Assert post-apply invariants (existing tests)
6. Void order
7. Assert full rollback consistency
```

---

## Assertions (post-void)

| Object | Expected |
|--------|----------|
| Employee | `is_active = FALSE`; org/position → pre-apply |
| `operational_status` | not `active` (WP-003) |
| `hr_relationship_context` | `CANDIDATE` (WP-001) |
| `person_assignments` | no active primary assignment (WP-002) |
| PPR count | 1 (same envelope) |
| `employee_events` | HIRE → VOIDED |
| `intended_employment` API | readable for CANDIDATE again; not SoT for placement |
| PPR API | `intended_employment` may reappear; assignment sections hidden |

---

## Acceptance criteria

1. Test green on PostgreSQL CI.
2. Covers applicant-path specifically (not only pre-existing employee HIRE void from WP-PO-004D).
3. Documents expected void semantics for architectural review sign-off.
