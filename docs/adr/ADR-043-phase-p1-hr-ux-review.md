# ADR-043 Phase P1 — HR UX Review Template

## Статус

**Prepared** (2026-06-20) — feedback collection form for first pilot days.

## Purpose

Collect structured HR operator feedback after initial use of Personnel Lifecycle UI and related workflows. **No new features in P1** — input for post-pilot prioritization only.

## Instructions for HR reviewers

1. Use the system for **at least 2 working days** before completing.
2. One form per reviewer (HR operator, enrollment manager, sysadmin-as-HR).
3. Rate each section **1–5** (1 = unusable, 3 = acceptable, 5 = excellent).
4. Provide concrete examples in free text (screen, person_key, snapshot id).
5. Return completed form to pilot owner within **3 days** of lifecycle execute.

---

## Reviewer profile

| Field | Value |
|-------|-------|
| Name | |
| Role | HR operator / Enrollment manager / SysAdmin |
| Date | |
| Days of use | |
| June snapshot_id used | |
| Browser | |

---

## 1. Navigation

**Pages used:** `/admin/system/personnel-lifecycle`, `/admin/system`, `/directory/personnel/import`

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| N1 | Was Personnel Lifecycle easy to find in the menu? | | |
| N2 | Breadcrumb back to SysAdmin cabinet clear? | | |
| N3 | Tab names (Обзор / Runs / Events / Overrides) understandable? | | |
| N4 | HR-only access (without full admin menu) sufficient? | | |

**Free text:** What navigation step caused confusion?

---

## 2. Filters

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| F1 | Personnel Events filters sufficient (snapshot, type, status, keys, dates)? | | |
| F2 | Overrides filters sufficient (status, tier, domain, field_path)? | | |
| F3 | Filter response time acceptable? | | |
| F4 | Clear when filters are server-side vs page-local? | | |

**Free text:** Which filter is missing?

---

## 3. Search

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| S1 | Finding a person by `person_key` in Effective Person viewer? | | |
| S2 | Finding events by person_key filter? | | |
| S3 | Need for full-text / FIO search without exact key? | | |

**Free text:** Describe a search that failed.

---

## 4. Overrides

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| O1 | Overrides queue readable? | | |
| O2 | Detail drawer: canonical vs override vs effective clear? | | |
| O3 | Approve / Reject / Revoke workflow intuitive? | | |
| O4 | Tier 2 approval requirements understood? | | |
| O5 | Justification / evidence fields sufficient? | | |
| O6 | History / metadata readable? | | |

**Free text:** Override workflow pain points.

---

## 5. Personnel Events

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| E1 | Event table columns sufficient? | | |
| E2 | Event detail drawer: old/new/effective values helpful? | | |
| E3 | Event types understandable without training? | | |
| E4 | Resolved vs detected status clear? | | |

**Free text:** Which event type was hardest to interpret?

---

## 6. Lifecycle Runs

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| L1 | Dashboard (last run summary) useful? | | |
| L2 | Preview vs Execute distinction clear? | | |
| L3 | Execute confirmation dialog sufficient? | | |
| L4 | Report sections (effective cache, diff, sync, validation) readable? | | |
| L5 | Runs history table + detail drawer sufficient? | | |

**Free text:** What would you want in the run report summary?

---

## 7. Effective Person

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| P1 | Load by person_key workflow clear? | | |
| P2 | Canonical vs Effective JSON helpful for disputes? | | |
| P3 | Applied override IDs useful? | | |
| P4 | Need side-by-side diff instead of JSON? | | |

**Free text:** Example where viewer helped or failed.

---

## 8. Validation

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| V1 | Validation cards understandable (duplicates, orphans, stuck, cache)? | | |
| V2 | Severity (ok / warning / error) clear? | | |
| V3 | Ran validation before execute? | Yes / No | |
| V4 | Sample details in cards sufficient? | | |

**Free text:** Validation messages that were unclear.

---

## 9. Performance

| # | Question | Rating 1–5 | Comments |
|---|----------|------------|----------|
| R1 | Page load time acceptable? | | |
| R2 | Lifecycle Preview wait time acceptable? | | |
| R3 | Lifecycle Execute wait time acceptable? | | |
| R4 | Large event/override lists paginate well? | | |

**Approximate timings (optional):**

| Action | Seconds |
|--------|---------|
| Open Personnel Lifecycle | |
| Preview run | |
| Execute run | |
| Load events page | |

---

## 10. Missing Features

**Do not expect these in P1** — capture for future prioritization.

| # | Question | Response |
|---|----------|----------|
| M1 | What task forced you to use SQL/API instead of UI? | |
| M2 | Top 3 missing features (ranked) | 1. / 2. / 3. |
| M3 | Need export (Excel/CSV)? | Yes / No — what data? |
| M4 | Need bulk override actions? | Yes / No |
| M5 | Need charts / dashboards? | Yes / No |
| M6 | Need notifications (email/TG) on lifecycle complete? | Yes / No |

---

## Overall

| Question | Rating 1–5 |
|----------|------------|
| Overall usability for June pilot | |
| Confidence to run monthly cycle without dev help | |
| Would recommend to other HR units? | |

**Top 3 blockers (must fix before wider rollout):**

1.
2.
3.

**Top 3 improvements (nice to have):**

1.
2.
3.

---

## Sign-off

| Role | Name | Date |
|------|------|------|
| Reviewer | | |
| Pilot owner (received) | | |

---

## Aggregated summary (for pilot owner — fill after collecting forms)

| Section | Avg rating | Top issue |
|---------|------------|-----------|
| Navigation | | |
| Filters | | |
| Search | | |
| Overrides | | |
| Personnel Events | | |
| Lifecycle Runs | | |
| Effective Person | | |
| Validation | | |
| Performance | | |

**Decision:** Proceed to wider pilot / Hold for fixes / Escalate to ADR-044 planning

---

## Related documents

- [ADR-043 Phase C4.2 UI](./ADR-043-phase-c4-2-personnel-lifecycle-ui.md)
- [P1 Pilot Checklist](./ADR-043-phase-p1-pilot-checklist.md)
- [P1 Observability](./ADR-043-phase-p1-observability.md)
