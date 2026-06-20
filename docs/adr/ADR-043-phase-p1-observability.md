# ADR-043 Phase P1 — Lifecycle Observability Requirements

## Статус

**Prepared** (2026-06-20) — requirements only; **no Prometheus/Grafana implementation**.

## Objective

Define minimum observability for HR lifecycle pilot: what to log, what to query, what to review daily. Uses **existing** journals and reports — no new subsystems.

---

## Observability layers

```text
┌─────────────────────────────────────────────────────────┐
│  HR / SysAdmin UI  (C4.2 dashboards, tables, validation) │
├─────────────────────────────────────────────────────────┤
│  REST API          (/admin/personnel/* read + reports)  │
├─────────────────────────────────────────────────────────┤
│  Lifecycle journal (hr_personnel_lifecycle_runs)        │
├─────────────────────────────────────────────────────────┤
│  Domain tables     (events, overrides, enrollment)      │
├─────────────────────────────────────────────────────────┤
│  Application logs  (Python logger, systemd journal)     │
└─────────────────────────────────────────────────────────┘
```

---

## Required metrics (minimum set)

### 1. Lifecycle runs

| Metric | Source | Query / access |
|--------|--------|----------------|
| Run count by status | `hr_personnel_lifecycle_runs.status` | UI Runs tab; SQL below |
| Last run timestamp | `started_at`, `completed_at` | Lifecycle Dashboard |
| Run duration | `completed_at - started_at` or report `duration_ms` | Dashboard / run detail |
| Failed runs | `status = 'failed'` | Alert on any during pilot |

```sql
SELECT run_id, status, started_at, completed_at,
       events_created, persons_created, assignments_created,
       warnings_count, errors_count, actor_user_id
FROM hr_personnel_lifecycle_runs
ORDER BY run_id DESC LIMIT 20;
```

---

### 2. Events created / skipped / failed

| Metric | Source | Notes |
|--------|--------|-------|
| events_created | Run journal + diff report | Per lifecycle execute |
| events_existing (skipped) | Run journal | Idempotent re-runs |
| events failed / stuck | `hr_personnel_change_events.status = 'detected'` | Should → 0 after sync |

**C1 diff report** (`monthly_diff` / `personnel_events` in `PersonnelLifecycleReport`):

| Field (report) | Meaning |
|----------------|---------|
| `personnel_events.created` | New events materialized |
| `personnel_events.existing` | Already present (skip) |
| `personnel_events.by_type` | Breakdown by event_type |

**C2 sync report** (`person_sync` in report):

| Field | Meaning |
|-------|---------|
| `events_seen` | Loaded detected events |
| `events_applied` | Mutations applied |
| `events_skipped` | Non-mutating (notes, whitelist) |
| `events_failed` | Handler errors (retryable) |

```sql
SELECT status, COUNT(*) FROM hr_personnel_change_events
WHERE snapshot_id = :current GROUP BY status;
```

---

### 3. Persons created / updated

| Metric | Source |
|--------|--------|
| persons_created | Run journal; `person_sync.persons_created` |
| persons_updated | Run journal; sync report |

```sql
SELECT COUNT(*) FILTER (WHERE created_at > :pilot_start) AS new_persons
FROM persons;
```

---

### 4. Assignments created / closed

| Metric | Source |
|--------|--------|
| assignments_created | Run journal |
| assignments_closed | Run journal; `assignments_closed` column |
| assignments_updated | Run journal |

```sql
SELECT lifecycle_status, COUNT(*)
FROM person_assignments
GROUP BY lifecycle_status;
```

---

### 5. Override approvals / rejections

| Metric | Source |
|--------|--------|
| Overrides pending | `hr_review_overrides.status = pending_approval` |
| Approvals (period) | `hr_review_override_history.event_type = APPROVED` |
| Rejections | `event_type = REJECTED` |
| Revocations | `event_type = REVOKED` |

```sql
SELECT status, tier, COUNT(*)
FROM hr_review_overrides
GROUP BY status, tier;

SELECT event_type, COUNT(*)
FROM hr_review_override_history
WHERE event_at > :pilot_start
GROUP BY event_type;
```

---

### 6. Enrollment items created

| Metric | Source |
|--------|--------|
| enrollment_created | Run journal |
| enrollment_existing | Run journal (idempotent) |
| Queue depth | `enrollment_queue` by status |

```sql
SELECT queue_status, COUNT(*)
FROM enrollment_queue
GROUP BY queue_status;
```

---

### 7. Validation warnings

| Metric | Source |
|--------|--------|
| warnings_count | Validation API / run report |
| errors_count | Validation API / run report |
| Per-check counts | `checks[].code`, `count`, `severity` |

**Check codes to monitor:**

| Code | Severity if > 0 |
|------|-----------------|
| `duplicate_active_overrides` | error |
| `duplicate_active_assignments` | error |
| `active_assignment_without_person` | error |
| `personnel_events_stuck_detected` | warning |
| `outdated_effective_cache` | warning |
| `persons_without_active_assignment` | warning |

---

## Journal schema reference (`hr_personnel_lifecycle_runs`)

Columns already persisted (C3 migration):

| Column | Observability use |
|--------|-------------------|
| `run_id` | Correlation id |
| `previous_snapshot_id`, `snapshot_id` | Snapshot pair |
| `status` | running / completed / failed |
| `dry_run` | Preview vs execute |
| `effective_entries_processed` | Cache stage |
| `events_created`, `events_existing` | Event pipeline |
| `enrollment_created`, `enrollment_existing` | Enrollment stage |
| `persons_created`, `persons_updated` | Sync stage |
| `assignments_created`, `assignments_updated`, `assignments_closed` | Sync stage |
| `warnings_count`, `errors_count` | Aggregate health |
| `summary` (JSONB) | Full stage reports |

---

## Application logs

| Logger | Module | What to capture |
|--------|--------|-----------------|
| `app.services.hr_personnel_lifecycle_service` | C3 | Stage failures, `PersonnelLifecycleError.stage` |
| `app.services.hr_person_assignment_sync_service` | C2 | Per-event apply/skip/fail |
| `app.services.hr_review_override_service` | B3 | Transition errors |
| FastAPI access | uvicorn | 4xx/5xx on `/admin/personnel/*` |

**systemd:**

```bash
journalctl -u corpsite-backend -f --since "1 hour ago" | grep -iE 'lifecycle|personnel|override'
```

---

## Security audit cross-reference

Override and access changes may appear in `security_audit_log` (ADR-042):

```sql
SELECT event_type, actor_user_id, created_at, metadata
FROM security_audit_log
WHERE event_type IN ('ACCESS_CHANGED', 'ACCESS_GRANTED', 'ACCESS_REVOKED')
   OR metadata->>'action' LIKE '%override%'
ORDER BY audit_id DESC LIMIT 50;
```

---

## Pilot monitoring cadence

| When | Action |
|------|--------|
| **Pre-execute** | Validation API; preview report review |
| **Post-execute** | Run journal row; stuck events = 0 |
| **Daily** | Overrides pending count; enrollment queue depth |
| **Weekly** | Validation full check; assignment duplicate query |

---

## Alert thresholds (pilot — manual)

| Condition | Action |
|-----------|--------|
| Any `failed` lifecycle run | Stop; investigate before re-run |
| `errors_count > 0` on execute | HR + dev review |
| Stuck `detected` events > 0 after sync | Run integrity audit S* scenarios |
| `duplicate_active_assignments` > 0 | Block next execute |
| Pending overrides > 20 | HR triage session |

---

## Future (out of P1 scope)

Not implemented in P1 — document for ADR-044+ consideration only:

- Prometheus exporters
- Grafana dashboards
- Automated paging
- Structured JSON log shipping
- Run duration SLOs

---

## API endpoints for observability (read-only)

| Endpoint | Use |
|----------|-----|
| `GET /admin/personnel/lifecycle/runs` | Run history |
| `GET /admin/personnel/lifecycle/runs/{id}` | Run detail + summary JSON |
| `GET /admin/personnel/lifecycle/validation` | Health checks |
| `GET /admin/personnel/events` | Event pipeline |
| `GET /admin/personnel/overrides` | Override queue |
| `GET /admin/enrollment/queue` | Enrollment (ADR-042) |
| `GET /admin/security-audit` | Access/audit trail |

---

## Related documents

- [P1 Pilot Checklist](./ADR-043-phase-p1-pilot-checklist.md)
- [P1 Production Gap Audit](./ADR-043-phase-p1-production-gap-audit.md)
- [ADR-043 Phase C3](./ADR-043-phase-c3-lifecycle-orchestrator.md)
