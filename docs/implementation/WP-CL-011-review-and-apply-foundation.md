--------------------------------------------------

Document Status

Document:
WP-CL-011-review-and-apply-foundation

Title:
Control List Review Aggregate and Apply Planning Foundation

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-011

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory review aggregate and declarative apply plans only** — no canonical PPR/Employment writes

--------------------------------------------------

# WP-CL-011 — Review and Apply Foundation

## 1. Цель

Собрать результаты нормализации (WP-CL-004…010) и person matching (WP-CL-005) в единый **review aggregate** и определить безопасный **apply contract** в виде декларативного плана действий.

На этом этапе **не выполняется** фактическая запись в canonical PPR/Employment.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| Domain models: `ControlListReviewItem`, `ControlListReviewRun`, `ReviewStatus`, `ReviewDecision`, `BlockingIssueSummary`, `ApplyPlan`, `ApplyAction` | UI preview / review screens |
| `ReviewAssembler`: normalization bundle → review run | Candidate persistence tables |
| `ApplyPlanner`: declarative action plans | Apply execution / transactions |
| Idempotency keys for planned actions | Rollback engine (WP-CL-012) |
| Unit tests + ADR update | Automatic Person creation |

## 3. Архитектурная роль

```text
NormalizationRunBundle (WP-CL-004…010 + WP-CL-005 outputs)
  → ReviewAssembler
  → ControlListReviewRun / ControlListReviewItem
  → (operator) ReviewDecision
  → ApplyPlanner
  → ApplyPlan (immutable, declarative)
  → [future WP] ApplyExecutor
```

**Инварианты:**

- Review aggregate **не является** canonical data.
- `approve` **≠** `apply` — решение оператора не вызывает mutation.
- Apply plan **декларативный и immutable** — список intended actions с preconditions.
- Фактический mutation pipeline — **отдельный WP** (execution layer).
- Idempotency и rollback **обязательны** для execution layer (WP-CL-012).

## 4. Domain model

### 4.1. ControlListReviewItem

| Field group | Contents |
|-------------|----------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, sheet/row |
| Person | `PersonCandidate`, `PersonMatchResult` |
| Slices | Employment, Contact, Education[], Training[], OtherPpr[] |
| Issues | `blocking_issues`, `non_blocking_issues` |
| Readiness | `readiness_status` (`ReviewStatus`) |
| Decision | `decision` (`ReviewDecision`, default `pending`) |
| Plan | `apply_plan` (declarative preview from `ApplyPlanner`) |

**Cardinality:** 1 staging data row → 1 review item.

### 4.2. ReviewStatus matrix

| ReviewStatus | Meaning | Approval allowed |
|--------------|---------|------------------|
| `blocked` | Blocking issues present | No |
| `needs_review` | Non-blocking slice issues | Yes (with caution) |
| `ready` | No blocking/non-blocking issues | Yes |

### 4.3. ReviewDecision

| Value | Apply plan behaviour |
|-------|---------------------|
| `pending` | Empty / not executable |
| `approved` | Actions generated when no blocking issues |
| `rejected` | Single `skip` action, not executable |
| `needs_correction` | Not executable |

### 4.4. Blocking rules

| Condition | Blocking |
|-----------|----------|
| `person_match.status = ambiguous` | Yes |
| `person_match.status = invalid` | Yes |
| `person_match.status = not_found` | Yes (allows future explicit `create_person`, not auto-apply) |
| Missing person candidate / match | Yes |
| Person candidate blocking fields (`full_name`, `iin`) | Yes |
| Absent optional slices (employment, contacts, education, …) | **No** false blocking |
| Slice `normalization_ready` alone | **Does not** imply item ready |

### 4.5. ApplyActionType

| Action | Target aggregate | When planned |
|--------|------------------|--------------|
| `create_person` | `person` | `not_found` preview only (`is_ready=false`, pending plan) |
| `update_person_contact` | `person.contacts` | Contact candidate present |
| `resolve_assignment` | `employment.assignment` | EmploymentCandidate (primary **and** concurrent internal assignment) |
| `add_education` | `ppr.education` | Per education candidate |
| `add_training` | `ppr.training` | Per training candidate |
| `update_other_ppr_field` | `ppr.other_fields` | Per supported other PPR candidate |
| `skip` | `review_item` | Rejected items |

**Not generated in WP-CL-011:**

| Action | Reason |
|--------|--------|
| `create_external_employment` | Reserved for explicit external-employment biography sources (ADR-056). `employment_mode=concurrent` on Control List sheet denotes **internal** concurrent assignment in Employment BC, not `person_external_employment`. |

Each action carries: `preconditions`, `idempotency_key`, `is_ready`, optional `blocking_reason`.

### 4.6. Review decision rules

| Rule | Semantics |
|------|-----------|
| `blocked + approved` | **Forbidden** — `apply_review_decision` raises `ReviewDecisionError` |
| `approved` | Allowed only when `ready` or `needs_review` (no blocking issues) |
| `rejected` | Always non-executable `skip` plan |
| `pending` / `needs_correction` | Non-executable, no mutation actions |
| `approve ≠ apply` | Decision update replans only; no canonical writes |
| `plan.is_executable` | Means plan **could** be executed later — not that execution occurred |

### 4.7. Employment BC boundary

Per ADR-056:

- `employment_mode=primary` and `employment_mode=concurrent` on Control List sheets both map to **`resolve_assignment`** against Employment BC.
- Concurrent sheet context (e.g. «врачи совместители») means internal concurrent assignment at MMC — **not** external employment biography.
- `create_external_employment` remains vocabulary for a future explicit external-employment source; WP-CL-006 `EmploymentCandidate` must not produce it.

## 5. Services

| Module | Class | Responsibility |
|--------|-------|----------------|
| `review/assembler.py` | `ReviewAssembler` | Bundle → `ControlListReviewRun` |
| `review/apply_planner.py` | `ApplyPlanner` | Item + decision → `ApplyPlan` |
| `review/decisions.py` | `apply_review_decision` | Update decision + replan (no writes) |
| `review/normalization_bundle.py` | `NormalizationRunBundle` | Input keyed by `source_row_id` |

## 6. Tests

`tests/test_wp_cl_011_review_and_apply_foundation.py`

Coverage:

- Full review item assembly
- 1 source row → 1 item grouping
- Blocking issue aggregation
- `ambiguous` / `invalid` / `not_found` person match
- Approved item with executable plan
- Rejected item with skip only
- Mixed candidates (partial slice readiness)
- Empty optional sections
- Stable idempotency keys
- No DB/PPR/Employment writes in review layer
- Approve does not execute apply

## 7. Related

- [ADR-057 §5.10](../architecture/ADR-057-control-list-interchange-architecture.md)
- [WP-CL-004 … WP-CL-010](./WP-CL-010-other-ppr-fields-normalization.md)
