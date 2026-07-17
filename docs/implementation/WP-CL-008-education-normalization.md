--------------------------------------------------

Document Status

Document:
WP-CL-008-education-normalization

Title:
Control List Education Normalization — Education Candidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-008

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no person_education writes, no dedup with canonical PPR

--------------------------------------------------

# WP-CL-008 — Education Normalization

## 1. Цель

Преобразовать staging snapshot + mapping profile + person match result в **list[EducationCandidate]** — временные нормализованные education slices import pipeline.

Без записи в `person_education` и без изменения canonical PPR.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| EducationCandidate domain model | PPR education apply |
| Composite cell parser + service | Dedup с existing person_education |
| Vocabulary (`education.records`, `records.education`) | API / frontend |
| Unit tests | DB persistence |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Person Candidate + Match (WP-CL-004/005) | Person identity slice + match outcome | Нет |
| **Education Candidate (WP-CL-008)** | **Temporary education projection** | **Нет** |
| Canonical person_education | Operational education data after apply | Да |

**Education Candidate — не canonical person_education record.**

**Инварианты:**

- Temporary in-memory domain model; **без** ORM / SQLAlchemy и **без** DB persistence.
- **Cardinality:** 1 staging row → **0..N** EducationCandidate.
- **Provenance:** каждый candidate сохраняет `source_column_*`, `source_fragment_index`, `raw_fragment`.
- **Не использует** `employee_id` как идентичность человека.
- `matched_person_id` только из `exact`/`probable` match с `recommended_person_id`.
- Пустая / technical-empty education cell → **пустой список**.
- Неполный фрагмент → candidate с issue, **не discard**.
- `normalization_ready` **не авторизует** запись в PPR.
- Split delimiters: newline, `;`, `|` — **не** каждая запятая.

## 4. EducationCandidate

| Field | Description |
|-------|-------------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, `source_sheet_name`, `source_excel_row_number`, `source_column_index`, `source_column_letter`, `source_fragment_index` |
| `raw_fragment` | Исходный текст фрагмента из ячейки |
| `matched_person_id` | Resolved Person id or `null` |
| `institution_name` | Normalized plain text |
| `qualification` | Parsed qualification label |
| `specialty` | Parsed specialty |
| `graduation_year` | Extracted year (1950–2100) |
| `education_level` | Parsed level keyword |
| `document_number` | Diploma / document number when present |
| `field_issues` | Per semantic field issue codes |
| `readiness_status` | Normalization readiness |

### Readiness rules

`normalization_ready` означает только:

- Person сопоставлен и рекомендован (`exact`/`probable` + `recommended_person_id`);
- education fragment разобран без blocking issues.

**Не означает:** canonical education record, dedup с PPR, apply authorization.

| Person match | Education fragment | readiness_status |
|--------------|-------------------|------------------|
| `exact` / `probable` + recommendation | parsed cleanly | `normalization_ready` |
| `exact` / `probable` + recommendation | incomplete / unparsed | `review_required` |
| `ambiguous` | any | `review_required` |
| `invalid` | any | `person_match_invalid` |
| `not_found` | any | `person_unmatched` |

## 5. Normalizers

| Module | Responsibility |
|--------|----------------|
| `education_normalization/records.py` | Composite cell split, fragment parsing, year/institution/specialty extraction |
| `education_normalization/service.py` | Staging row → list[EducationCandidate] |

## 6. EducationNormalizationService

```text
StagingRowInput + MappingProfileSnapshot + PersonMatchResult
  → EducationNormalizationService.normalize_row()
  → list[EducationCandidate]
```

Batch flow binds `PersonMatchResult` by `source_row_id`.

## 7. Issue codes

| Code | Meaning |
|------|---------|
| `education_fragment_incomplete` | No recognizable education signals in fragment |
| `education_fragment_unparsed` | Fragment present but institution/year/specialty not resolved |
| `education_graduation_year_out_of_range` | Year outside 1950–2100 |

## 8. Tests

`tests/test_wp_cl_008_education_normalization.py` — single/multi records, comma preservation, year extraction, incomplete fragments, empty/technical-empty, person match variants, provenance, no DB writes, normalization_ready ≠ apply-ready.

## 9. Related

- [ADR-057 §5.7](../architecture/ADR-057-control-list-interchange-architecture.md)
- [WP-CL-007 — Contacts Normalization](./WP-CL-007-contacts-normalization.md)
