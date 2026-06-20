# ADR-044 B1 — Identity Reconciliation Dry-Run API

## Status

**Implemented** (2026-06-20) — read-only preview; no execute mode, no data writes.

## Overview

ADR-044 B1 exposes R1a **dry-run analysis**: scan persons, resolve IIN via P1→P5 precedence, classify candidates, run validation gates G1–G10.

**Not included:** execute mode, `UPDATE persons`, `INSERT employee_identities`, reconciliation DDL.

---

## Endpoints

Base path: `/admin/personnel`  
Auth: personnel admin (SYSADMIN/ACCESS_ADMIN or `HR_ENROLLMENT_MANAGER` grant).

### GET `/identity/reconciliation/r1a/preview`

Query params:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `snapshot_id` | int | No | Canonical snapshot; defaults to active `HR_CONTROL_LIST` snapshot |

### POST `/identity/reconciliation/r1a/preview`

Body (JSON):

```json
{
  "snapshot_id": 42
}
```

`snapshot_id` optional — same default as GET.

---

## Response contract

```json
{
  "phase": "R1a",
  "dry_run": true,
  "snapshot_id": 12,
  "generated_at": "2026-06-20T12:00:00+00:00",
  "blocking": false,
  "execute_allowed": true,
  "summary": {
    "candidates_total": 87,
    "by_outcome": {
      "APPLY": 64,
      "SKIP_INCOMPLETE": 3,
      "SKIP_ALREADY_FILLED": 20
    },
    "persons_total": 87,
    "persons_with_iin_before": 20,
    "persons_iin_coverage_before_pct": 22.99,
    "apply_count": 64,
    "projected_persons_with_iin_after": 84,
    "projected_iin_coverage_after_pct": 96.55,
    "resolvable_gap_after_r1a": 3,
    "identity_incomplete_count": 3,
    "would_insert_employee_identity_count": 58
  },
  "gates": [
    {
      "gate_id": "G5",
      "severity": "CRITICAL",
      "blocks_execute": false,
      "count": 0,
      "passed": true,
      "message": "active snapshot_id=12",
      "violations": []
    }
  ],
  "apply_preview": [],
  "conflicts": [],
  "incomplete": [],
  "already_filled": [],
  "employee_identity_gaps": [],
  "candidates": [],
  "warnings": [],
  "errors": []
}
```

### Field semantics

| Field | Meaning |
|-------|---------|
| `blocking` | Any gate has `blocks_execute=true` and `count>0` |
| `execute_allowed` | Inverse of `blocking` (execute not implemented in B1) |
| `apply_preview` | Candidates with `outcome=APPLY` |
| `employee_identity_gaps` | APPLY rows where `would_insert_employee_identity=true` |
| `candidates` | Full per-person classification |

### Candidate object

| Field | Description |
|-------|-------------|
| `person_id` | Target person |
| `match_key` | Current `persons.match_key` (**unchanged in dry-run**) |
| `canonical_person_key` | ADR-040 key used for P1/P2 lookup (`emp:{id}` etc.) |
| `resolved_iin` | 12-digit IIN from precedence chain |
| `source` | Winning source: `P1_override` … `P5_change_event` |
| `outcome` | `APPLY`, `SKIP_*` |
| `would_update_person_iin` | Always `false` in DB; `true` in preview for APPLY |
| `would_insert_employee_identity` | Preview flag for missing EI row |

---

## IIN precedence (P1 → P5)

```text
P1  hr_review_overrides     identity.iin, active, scope PERSON:{canonical_person_key}
P2  hr_snapshot_effective_entries   effective_payload.iin
P3  hr_canonical_snapshot_entries   iin column / payload
P4  employee_identities     IIN, valid_to IS NULL
P5  hr_change_events        latest iin column
```

P1 scope uses **canonical `person_key`**, not legacy `persons.match_key`.

---

## Validation gates G1–G10

| Gate | Severity | Blocks batch? |
|------|----------|---------------|
| G1 Duplicate active IIN (existing) | CRITICAL | Yes |
| G2 Apply would duplicate IIN | CRITICAL | Per person |
| G3 Invalid resolved IIN | CRITICAL | Per person |
| G4 Multiple persons → same canonical IIN | CRITICAL | Yes |
| G5 No active snapshot | CRITICAL | Yes |
| G6 Existing persons.iin ≠ resolved | HIGH | Per person |
| G7 Orphan employees | MEDIUM | Warn |
| G8 Employee without canonical row | LOW | Warn |
| G9 EI mismatch | HIGH | Per person |
| G10 IDENTITY_INCOMPLETE count | INFO | Warn |

---

## Example: Әбітаев case (dry-run excerpt)

```json
{
  "person_id": 115,
  "full_name": "Әбітаев Ерхан Сайлаубекұлы",
  "match_key": "name:әбітаев ерхан сайлаубекұлы",
  "canonical_person_key": "emp:26",
  "employee_id": 26,
  "resolved_iin": "800115300290",
  "source": "P3_canonical_entry",
  "outcome": "APPLY",
  "would_update_person_iin": true,
  "would_insert_employee_identity": true,
  "message": "eligible for R1a materialization"
}
```

After R1a execute (B2, not B1): `persons.iin` filled; `match_key` **unchanged**.

---

## CLI (B2)

Not in B1. Future: `scripts/run_identity_reconciliation_r1a.py --dry-run`.

---

## Service module

`app/services/identity_reconciliation_service.py`

| Function | Purpose |
|----------|---------|
| `build_reconciliation_candidates()` | Scan + classify all persons |
| `classify_candidate()` | Single-person classification |
| `build_reconciliation_report()` | Full report + gates + metrics |
| `run_r1a_dry_run()` | Entry point |
| `run_validation_gates()` | G1–G10 |

---

## Example curl

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/admin/personnel/identity/reconciliation/r1a/preview" \
  | jq '.summary, .gates[] | select(.passed == false)'
```
