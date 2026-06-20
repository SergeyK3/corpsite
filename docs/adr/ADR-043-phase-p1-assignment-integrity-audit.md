# ADR-043 Phase P1 — Assignment Integrity Audit

## Статус

**Prepared** (2026-06-20) — scenario catalog and integrity checklist for June pilot.

## Objective

Verify that personnel lifecycle correctly maintains **persons**, **person_assignments**, **employee_assignment_links**, **personnel events**, and **enrollment queue** across real HR change scenarios.

## Reference tests (automated baseline)

Local pytest coverage in `tests/test_adr043_phase_c2_person_assignment_sync.py`:

- `test_new_person_creates_person`
- `test_new_assignment_creates_assignment`
- `test_closed_assignment_closes_without_delete`
- `test_terminated_person_closes_active_assignments`
- `test_department_changed_updates_assignment`
- `test_position_changed_updates_assignment`
- `test_rate_changed_updates_assignment`
- `test_employee_link_updated_when_employee_exists`
- `test_no_employee_auto_created_without_enrollment`
- `test_dry_run_changes_nothing`
- `test_failed_event_remains_retryable`

Pilot manual scenarios below extend these with **June real data** samples.

---

## Scenario catalog

For each scenario: document **person_key**, **before/after snapshot IDs**, expected **event_type**, and verification queries.

### S1 — Перевод между отделениями (transfer)

| Item | Detail |
|------|--------|
| Trigger | Same person; `org_unit_id` / department changes; position may change |
| Event type | `DEPARTMENT_CHANGED` and/or `TRANSFER` (per C1 rules) |
| Person | Same `person_id`; status remains active |
| Assignment | Same assignment updated OR old closed + new opened (per sync rules) |
| Employee link | Updated if employee exists |

| # | Verification | Pass |
|---|--------------|------|
| S1.1 | Personnel event created with correct field_path | ☐ |
| S1.2 | Assignment reflects new department | ☐ |
| S1.3 | No duplicate active assignment same key | ☐ |
| S1.4 | Legacy `hr_change_events` not regressed (if parallel) | ☐ |

**Sample person_key:** _______________

---

### S2 — Смена должности (position change)

| Item | Detail |
|------|--------|
| Event type | `POSITION_CHANGED` |
| Assignment | `position` fields updated on active assignment |

| # | Verification | Pass |
|---|--------------|------|
| S2.1 | Event old/new values match snapshot diff | ☐ |
| S2.2 | Assignment position fields updated | ☐ |
| S2.3 | Employee operational record unchanged unless policy says otherwise | ☐ |

**Sample person_key:** _______________

---

### S3 — Смена ставки (rate change)

| Item | Detail |
|------|--------|
| Event type | `RATE_CHANGED` or field-level change |
| Assignment | `employment_rate` updated |

| # | Verification | Pass |
|---|--------------|------|
| S3.1 | Rate in assignment matches June snapshot | ☐ |
| S3.2 | Event effective values correct in drawer | ☐ |

**Sample person_key:** _______________

---

### S4 — Закрытие назначения (assignment close)

| Item | Detail |
|------|--------|
| Trigger | Row removed from roster or explicit close semantics |
| Event type | `CLOSED_ASSIGNMENT` / removal variant |
| Assignment | `lifecycle_status = closed`; not deleted |

| # | Verification | Pass |
|---|--------------|------|
| S4.1 | No hard DELETE on person_assignments | ☐ |
| S4.2 | closed_at / status set | ☐ |
| S4.3 | Person remains if still in registry | ☐ |

**Sample person_key:** _______________

---

### S5 — Повторный приём (rehire)

| Item | Detail |
|------|--------|
| Trigger | Person absent then reappears in June snapshot |
| Event type | `NEW_PERSON` or reactivation |
| Person | Same `person_key` — idempotent or new person_id per policy |

| # | Verification | Pass |
|---|--------------|------|
| S5.1 | No duplicate person rows for same IIN/key | ☐ |
| S5.2 | New active assignment created | ☐ |
| S5.3 | Enrollment queue item if no employee | ☐ |

**Sample person_key:** _______________

---

### S6 — Совместительство (concurrent assignments)

| Item | Detail |
|------|--------|
| Trigger | Same person; multiple `assignment_key` in snapshot |
| Expected | Multiple active assignments; distinct keys |

| # | Verification | Pass |
|---|--------------|------|
| S6.1 | COUNT active assignments ≥ 2 for person | ☐ |
| S6.2 | No duplicate (person_id, assignment_key) active pair | ☐ |
| S6.3 | Validation: `duplicate_active_assignments` = 0 | ☐ |

**Sample person_key:** _______________

---

### S7 — Увольнение (termination)

| Item | Detail |
|------|--------|
| Event type | `TERMINATED_PERSON` |
| Person | `person_status` → terminated/inactive |
| Assignments | All active → closed |

| # | Verification | Pass |
|---|--------------|------|
| S7.1 | All assignments closed | ☐ |
| S7.2 | Employee link preserved but assignment inactive | ☐ |
| S7.3 | No new enrollment for terminated person | ☐ |

**Sample person_key:** _______________

---

## Cross-entity integrity checklist

Run after lifecycle execute on June pair.

### Persons

```sql
SELECT person_status, COUNT(*)
FROM persons
GROUP BY person_status;
```

| # | Check | Pass |
|---|-------|------|
| I1 | Every active person has ≥ 0 assignments (warn if 0) | ☐ |
| I2 | No person_id NULL in active assignments | ☐ |
| I3 | person_key unique among active persons | ☐ |

### Person assignments

```sql
SELECT lifecycle_status, COUNT(*)
FROM person_assignments
GROUP BY lifecycle_status;

-- Duplicate active check
SELECT person_id, lower(assignment_key), COUNT(*)
FROM person_assignments
WHERE lifecycle_status = 'active'
GROUP BY 1, 2 HAVING COUNT(*) > 1;
```

| # | Check | Pass |
|---|-------|------|
| I4 | Zero duplicate active (person_id, assignment_key) | ☐ |
| I5 | Closed assignments retain history | ☐ |
| I6 | Primary assignment flag consistent (if used) | ☐ |

### Employee assignment links

```sql
SELECT COUNT(*) AS orphan_links
FROM employee_assignment_links eal
LEFT JOIN person_assignments pa ON pa.assignment_id = eal.assignment_id
WHERE pa.assignment_id IS NULL;

SELECT COUNT(*) AS persons_without_employee
FROM persons p
WHERE p.person_status = 'active'
  AND NOT EXISTS (
    SELECT 1 FROM employee_assignment_links eal
    JOIN employees e ON e.employee_id = eal.employee_id
    WHERE e.person_id = p.person_id
  );
-- Expected: many (enrollment pending) — document count
```

| # | Check | Pass |
|---|-------|------|
| I7 | No orphan links to missing assignments | ☐ |
| I8 | Links point to correct employee_id for enrolled staff | ☐ |
| I9 | No employee auto-created outside enrollment apply | ☐ |

### Personnel events

```sql
SELECT event_type, status, COUNT(*)
FROM hr_personnel_change_events
WHERE snapshot_id = :june
GROUP BY 1, 2
ORDER BY 1, 2;
```

| # | Check | Pass |
|---|-------|------|
| I10 | Zero stuck `detected` after successful sync | ☐ |
| I11 | Failed events documented with retry plan | ☐ |
| I12 | Event person_key matches persons.person_key | ☐ |

### Enrollment queue

```sql
SELECT queue_status, COUNT(*)
FROM enrollment_queue
GROUP BY queue_status;
```

| # | Check | Pass |
|---|-------|------|
| I13 | New persons have PENDING items (if policy) | ☐ |
| I14 | `personnel_event_id` populated on new items | ☐ |
| I15 | Rejected items not reopened without new event | ☐ |

---

## Reconciliation with ADR-042 Assignments tab

| # | Check | Pass |
|---|-------|------|
| R1 | Drift report reviewed for pilot persons | ☐ |
| R2 | Bulk reconcile dry-run before apply | ☐ |
| R3 | No unexpected employee ↔ assignment drift after lifecycle | ☐ |

---

## Idempotency check

| # | Step | Expected | Pass |
|---|------|----------|------|
| ID1 | Re-run lifecycle preview same pair | No duplicate persons/assignments | ☐ |
| ID2 | Re-run execute (if safe) or sync dry_run | Counters stable | ☐ |

---

## Failure handling

| Symptom | Action |
|---------|--------|
| Event stuck in `detected` | Inspect `person_sync` errors in run summary; retry sync |
| Duplicate assignment | Stop; run validation; manual close duplicate |
| Person without assignment | Document; HR decision enroll or terminate |
| Orphan assignment | Critical — P1 deployment rollback consideration |

---

## Sign-off

| Scenario | Tested | Issues |
|----------|--------|--------|
| S1 Transfer | ☐ | |
| S2 Position | ☐ | |
| S3 Rate | ☐ | |
| S4 Close | ☐ | |
| S5 Rehire | ☐ | |
| S6 Concurrent | ☐ | |
| S7 Termination | ☐ | |

**Integrity owner:** _________________ **Date:** _________

---

## Related documents

- [P1 Pilot Checklist](./ADR-043-phase-p1-pilot-checklist.md)
- [ADR-043 Phase C2](./ADR-043-phase-c2-person-assignment-sync.md)
- [ADR-042 Assignments reconciliation](../adr/ADR-042-phase-b3-service-layer.md)
