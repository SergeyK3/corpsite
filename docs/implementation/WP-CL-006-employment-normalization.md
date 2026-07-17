--------------------------------------------------

Document Status

Document:
WP-CL-006-employment-normalization

Title:
Control List Employment Normalization — Employment Candidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-006

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no Employment/PPR writes, no org/position lookup

--------------------------------------------------

# WP-CL-006 — Employment Normalization

## 1. Цель

Преобразовать staging snapshot + mapping profile + person match result в **EmploymentCandidate** — временный нормализованный employment slice import pipeline.

Без записи в employees, assignments, positions, org units, PPR или Personnel Orders.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| EmploymentCandidate domain model | Position / OrgUnit lookup |
| Employment normalizers + service | PPR / Employment DB writes |
| Readiness status from person match | Apply / Personnel Orders |
| Unit tests | API / frontend |
| | Fuzzy matching |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Person Candidate + Match (WP-CL-004/005) | Person identity slice + match outcome | Нет |
| **Employment Candidate (WP-CL-006)** | **Temporary employment projection** | **Нет** |
| Canonical Employment / assignments | Operational workplace data after apply | Да |

**Employment Candidate — не canonical Employment и не current assignment.**

**Инварианты:**

- Temporary in-memory domain model; **без** ORM / SQLAlchemy и **без** DB persistence.
- **Не использует** `employee_id` как идентичность человека.
- `matched_person_id` только из `exact`/`probable` match с `recommended_person_id`.
- `ambiguous` / `invalid` / `not_found` создают candidate, но не достигают `normalization_ready`.
- `normalization_ready` **не авторизует** apply в Employment BC — только успешная нормализация import slice.
- `employment_mode` (`primary` / `concurrent`) из sheet snapshot; режимы **не смешиваются**.
- **Без** поиска Position / OrgUnit.

## 4. EmploymentCandidate

| Field | Description |
|-------|-------------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, `source_sheet_name`, `source_excel_row_number` |
| `matched_person_id` | Resolved Person id or `null` |
| `personnel_category` | Sheet snapshot |
| `employment_mode` | `primary` / `concurrent` / `unknown` |
| `department_name` | Normalized plain text |
| `position_title` | Normalized plain text |
| `rate` | Decimal (e.g. 1, 0.5) |
| `employment_start_date` | Parsed date |
| `field_issues` | Per semantic field issue codes |
| `readiness_status` | Normalization readiness (`normalization_ready` / review / unmatched / invalid match) |

### Readiness rules

`normalization_ready` означает только:

- Person сопоставлен и рекомендован (`exact`/`probable` + `recommended_person_id`);
- обязательные исходные employment-поля нормализованы без blocking issues.

**Не означает:** canonical Employment, resolved OrgUnit/Position, отсутствие конфликтов назначения или разрешение apply.

| Person match | Employment fields | readiness_status |
|--------------|--------------------|------------------|
| `exact` / `probable` + recommendation | no blocking issues | `normalization_ready` |
| `exact` / `probable` + recommendation | missing dept/position or invalid rate | `review_required` |
| `ambiguous` | any | `review_required` |
| `invalid` | any | `person_match_invalid` |
| `not_found` | any | `person_unmatched` |

## 5. Normalizers

| Module | Responsibility |
|--------|----------------|
| `employment_normalization/department.py` | Department plain text cleanup |
| `employment_normalization/position.py` | Position title cleanup |
| `employment_normalization/rate.py` | Decimal rate (`1`, `0.5`, `0,5`) |
| `employment_normalization/start_date.py` | Employment start date parsing |
| `employment_normalization/mode.py` | Sheet `employment_mode` validation |

## 6. EmploymentNormalizationService

```text
StagingRowInput + MappingProfileSnapshot + PersonMatchResult
  → EmploymentNormalizationService.normalize_row()
  → EmploymentCandidate
```

Batch flow binds `PersonMatchResult` by `source_row_id`.

**No Employment/PPR database access.**

## 7. Артефакты

| Артефакт | Путь |
|----------|------|
| Employment Candidate | `app/control_list_import/domain/employment_candidate.py` |
| Vocabulary extension | `app/control_list_import/domain/vocabulary.py` (`employment.rate`) |
| Normalizers | `app/control_list_import/employment_normalization/` |
| Service | `app/control_list_import/employment_normalization/service.py` |
| Tests | `tests/test_wp_cl_006_employment_normalization.py` |

## 8. Acceptance

- [x] EmploymentCandidate domain model + readiness status
- [x] Normalizers: department, position, rate, start date, employment_mode
- [x] EmploymentNormalizationService
- [x] Unit tests pass
- [x] ADR-057 updated

## 9. Следующий WP

WP-CL-007 — Контакты (или продолжение employment apply path в review/apply WP).
