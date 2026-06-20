# ADR-043 Phase P1 — June Dataset Pilot Checklist

## Статус

**Prepared** (2026-06-20) — operational checklist for first HR lifecycle pilot.

## Objective

Verify the **full HR contour** on real **June 2026** control-list data:

```text
HR import → review → approved snapshot → effective cache → lifecycle run
  → person sync → enrollment queue → UI verification
```

## Roles

| Role | Responsibility |
|------|----------------|
| HR operator | Import, review, overrides, approve snapshots |
| HR enrollment manager | Enrollment queue decisions |
| SysAdmin | Lifecycle execute, grants, rollback |
| QA / support | Checklist execution, issue logging |

## Preconditions

- [ ] P1 Deployment Plan executed; `alembic current` = `y7z8a9b0c1d2`
- [ ] HR user has `HR_ENROLLMENT_MANAGER` grant (or sysadmin access)
- [ ] June source file available (`.xlsx` control list, `report_month=2026-06`)
- [ ] Previous approved snapshot exists (May or prior month) — record IDs below
- [ ] Pilot accounts tested: login, unit_id, directory access

### Record pilot IDs (fill before run)

| Item | Value |
|------|-------|
| June import batch_id | |
| Previous snapshot_id (May) | |
| June approved snapshot_id | |
| Lifecycle preview run_id | |
| Lifecycle execute run_id | |
| Pilot date | |
| Operator | |

---

## Phase 1 — HR Import

**Route:** `/directory/personnel/import` (or current import UI)

| # | Step | Expected | Pass |
|---|------|----------|------|
| 1.1 | Upload June `.xlsx` | Batch created; status `PARSED` or `IN_REVIEW` | ☐ |
| 1.2 | Review audit summary | Row counts match sheet manifest; duplicates flagged | ☐ |
| 1.3 | Resolve REVIEW_REQUIRED rows | `review_status=APPROVED` or rejected with reason | ☐ |
| 1.4 | Document candidates (if any) | Approved or skipped intentionally | ☐ |
| 1.5 | Apply batch | Status `APPLIED`; no fatal `error_message` | ☐ |

**SQL spot-check:**

```sql
SELECT batch_id, status, imported_at, applied_at, totals
FROM hr_import_batches
ORDER BY batch_id DESC LIMIT 3;
```

---

## Phase 2 — Review & Canonical Promotion

**Route:** normalized records / snapshot promotion UI (ADR-040 flow)

| # | Step | Expected | Pass |
|---|------|----------|------|
| 2.1 | Open diff vs previous canonical snapshot | NEW/CHANGED/REMOVED/CONFLICT visible | ☐ |
| 2.2 | Review CHANGED rows (dept, position, rate) | HR confirms or creates override | ☐ |
| 2.3 | Resolve CONFLICT rows | No unresolved conflicts before promotion | ☐ |
| 2.4 | Promote to approved snapshot | New `snapshot_id` for June; status approved | ☐ |
| 2.5 | Record snapshot pair | `previous_snapshot_id` → `snapshot_id` documented above | ☐ |

**SQL spot-check:**

```sql
SELECT snapshot_id, report_month, status, created_at
FROM hr_canonical_snapshots
ORDER BY snapshot_id DESC LIMIT 5;

SELECT COUNT(*) FROM hr_canonical_snapshot_entries
WHERE snapshot_id = :june_snapshot_id AND record_kind = 'roster';
```

---

## Phase 3 — Effective Snapshot (cache)

Can run via lifecycle preview (`refresh_cache: true`) or explicit cache step.

| # | Step | Expected | Pass |
|---|------|----------|------|
| 3.1 | Effective cache populated for both snapshots | Rows in `hr_snapshot_effective_entries` | ☐ |
| 3.2 | Active overrides reflected | `override_ids` / hash differ where overrides exist | ☐ |
| 3.3 | Spot-check 3 known persons | Effective payload matches override + canonical | ☐ |

**SQL spot-check:**

```sql
SELECT snapshot_id, COUNT(*) AS effective_rows
FROM hr_snapshot_effective_entries
WHERE snapshot_id IN (:prev, :june) AND record_kind = 'roster'
GROUP BY snapshot_id;
```

**UI:** Effective Person Viewer — load 3 `person_key` samples.

---

## Phase 4 — Lifecycle Preview (dry run)

**Route:** `/admin/system/personnel-lifecycle` → Monthly Lifecycle Run → **Preview**

| # | Step | Expected | Pass |
|---|------|----------|------|
| 4.1 | Enter snapshot pair | Validation accepts distinct IDs | ☐ |
| 4.2 | Flags: refresh_cache ✓, enqueue ✗, sync_persons ✗ | Preview completes | ☐ |
| 4.3 | Report: monthly_diff | Event counts plausible vs HR expectation | ☐ |
| 4.4 | Report: validation | No unexpected errors | ☐ |
| 4.5 | Report: warnings | Reviewed and accepted or ticketed | ☐ |
| 4.6 | Journal | No failed run row (dry_run may omit run_id) | ☐ |

**API alternative:** `POST /admin/personnel/lifecycle/run-preview`

---

## Phase 5 — Lifecycle Execute

**Gate:** HR sign-off on preview + validation cards.

| # | Step | Expected | Pass |
|---|------|----------|------|
| 5.1 | Validation panel | `errors_count = 0` or documented exceptions | ☐ |
| 5.2 | Execute with enqueue ✓, sync_persons ✓ | `run_status = completed` | ☐ |
| 5.3 | Journal counters | `events_created`, `persons_created`, `assignments_created` logged | ☐ |
| 5.4 | Re-run preview | Idempotent: `events_existing` ↑, no duplicate persons | ☐ |

**SQL spot-check:**

```sql
SELECT run_id, status, events_created, persons_created, assignments_created,
       enrollment_created, warnings_count, errors_count
FROM hr_personnel_lifecycle_runs
ORDER BY run_id DESC LIMIT 3;
```

---

## Phase 6 — Person Sync Verification

| # | Step | Expected | Pass |
|---|------|----------|------|
| 6.1 | Personnel events table | NEW_PERSON, NEW_ASSIGNMENT, TERMINATED, FIELD_CHANGED as expected | ☐ |
| 6.2 | Event statuses | Applied events → `resolved`; stuck `detected` = 0 | ☐ |
| 6.3 | Persons registry | New June hires have `persons` rows | ☐ |
| 6.4 | Assignments | Active assignments match snapshot dept/position/rate | ☐ |
| 6.5 | Terminations | Assignments closed; person status updated | ☐ |
| 6.6 | Employee links | `employee_assignment_links` updated where employee exists | ☐ |
| 6.7 | No auto-employee | No new `employees` without enrollment apply | ☐ |

**SQL samples:**

```sql
-- Stuck events
SELECT COUNT(*) FROM hr_personnel_change_events
WHERE previous_snapshot_id = :prev AND snapshot_id = :june AND status = 'detected';

-- Sample person
SELECT p.person_id, p.person_key, p.person_status
FROM persons p
WHERE p.person_key = :sample_key;
```

---

## Phase 7 — Enrollment Queue

| # | Step | Expected | Pass |
|---|------|----------|------|
| 7.1 | Detect / lifecycle enqueue | Queue items created for new persons | ☐ |
| 7.2 | `/admin/system` → Enrollment tab | Items visible with `personnel_event_id` link | ☐ |
| 7.3 | Approve sample item | Status moves forward (not auto-employee) | ☐ |
| 7.4 | Apply sample item | Employee shell created per ADR-042 rules | ☐ |
| 7.5 | Reject path tested on test row | Rejected stays closed | ☐ |

---

## Phase 8 — UI Verification

| # | Screen | Check | Pass |
|---|--------|-------|------|
| 8.1 | Lifecycle Dashboard | Last run metrics match execute | ☐ |
| 8.2 | Lifecycle Runs table | Execute run row; detail summary JSON | ☐ |
| 8.3 | Personnel Events | Filters by snapshot, event_type, person_key | ☐ |
| 8.4 | Event drawer | old/new/effective values readable | ☐ |
| 8.5 | Overrides queue | Pending/active overrides listed | ☐ |
| 8.6 | Override drawer | Approve/reject workflow (Tier 1 sample) | ☐ |
| 8.7 | Effective Person | 3 spot-checks match SQL | ☐ |
| 8.8 | Validation cards | All green or documented warnings | ☐ |
| 8.9 | ADR-042 regression | Users, Access, Assignments, Audit tabs OK | ☐ |

---

## Phase 9 — Sign-off

| Criterion | Met | Notes |
|-----------|-----|-------|
| Full cycle completed without rollback | ☐ | |
| June snapshot is approved canonical source | ☐ | |
| No stuck `detected` events | ☐ | |
| Enrollment queue triaged | ☐ | |
| Integrity audit sample (P1.5) passed | ☐ | |
| Governance audit sample (P1.4) passed | ☐ | |
| UX feedback form distributed (P1.7) | ☐ | |

**Pilot owner signature:** _________________ **Date:** _________

---

## Issue log template

| ID | Phase | Severity | Description | Owner | Status |
|----|-------|----------|-------------|-------|--------|
| P1-001 | | blocker / major / minor | | | open |

---

## Related documents

- [P1 Deployment Plan](./ADR-043-phase-p1-deployment-plan.md)
- [P1 Assignment Integrity Audit](./ADR-043-phase-p1-assignment-integrity-audit.md)
- [P1 Governance Audit](./ADR-043-phase-p1-governance-audit.md)
- [P1 HR UX Review](./ADR-043-phase-p1-hr-ux-review.md)
