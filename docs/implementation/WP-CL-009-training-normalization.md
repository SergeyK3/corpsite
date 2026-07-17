--------------------------------------------------

Document Status

Document:
WP-CL-009-training-normalization

Title:
Control List Training Normalization — Training Candidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-009

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no person_training writes, no dedup with canonical PPR

--------------------------------------------------

# WP-CL-009 — Training Normalization

## 1. Цель

Преобразовать staging snapshot + mapping profile + person match result в **list[TrainingCandidate]** — временные нормализованные training slices import pipeline.

Без записи в `person_training` и без изменения canonical PPR.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| TrainingCandidate domain model | PPR training apply |
| Conservative composite parser + service | Dedup с existing person_training |
| Vocabulary (`training.records`, `records.training`) | API / frontend |
| Unit tests + golden fixtures | Fuzzy matching / auto-fix ambiguous data |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Person Candidate + Match (WP-CL-004/005) | Person identity slice + match outcome | Нет |
| **Training Candidate (WP-CL-009)** | **Temporary training projection** | **Нет** |
| Canonical person_training | Operational training data after apply | Да |

**Training Candidate — не canonical person_training record.**

**Инварианты:**

- Temporary in-memory domain model; **без** ORM / SQLAlchemy и **без** DB persistence.
- **Cardinality:** 1 staging row → **0..N** TrainingCandidate.
- **Provenance:** `source_column_*`, `source_fragment_index`, `raw_fragment`.
- **Fail-safe:** `raw_fragment` без потери текста; normalized values отдельно.
- **Conservative provider:** только явные метки (`организация:`, `провайдер:`, …).
- Title курса **не** принимается за provider.
- `matched_person_id` только из `exact`/`probable` match с `recommended_person_id`.
- `normalization_ready` **не авторизует** запись в PPR.

## 4. TrainingCandidate

| Field | Description |
|-------|-------------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, `source_sheet_name`, `source_excel_row_number`, `source_column_index`, `source_column_letter`, `source_fragment_index` |
| `raw_fragment` | Исходный текст фрагмента из ячейки |
| `matched_person_id` | Resolved Person id or `null` |
| `training_title` | Parsed course/title text |
| `provider_name` | Provider only when explicit label matched |
| `completion_date` | Parsed DMY date |
| `completion_year` | Extracted year |
| `certificate_number` | Certificate / document number |
| `duration_hours` | Parsed hours (including акад. час) |
| `training_type` | Keyword-derived type code |
| `field_issues` | Per semantic field issue codes |
| `readiness_status` | Normalization readiness |

### Readiness rules

| Person match | Training fragment | readiness_status |
|--------------|-------------------|------------------|
| `exact` / `probable` + recommendation | parsed cleanly | `normalization_ready` |
| `exact` / `probable` + recommendation | incomplete / unparsed | `review_required` |
| `ambiguous` | any | `review_required` |
| `invalid` | any | `person_match_invalid` |
| `not_found` | any | `person_unmatched` |

## 5. Normalizers

| Module | Responsibility |
|--------|----------------|
| `training_normalization/records.py` | Composite split, conservative parse, hours/date/cert/provider/title |
| `training_normalization/service.py` | Staging row → list[TrainingCandidate] |

## 6. Issue codes

| Code | Meaning |
|------|---------|
| `training_fragment_incomplete` | No recognizable training signals |
| `training_fragment_unparsed` | Partial signals without title/hours/cert |
| `training_completion_year_out_of_range` | Year outside 1950–2100 |
| `training_completion_date_invalid` | Invalid calendar date |
| `training_duration_hours_unrecognized` | Hours token not parsed |
| `training_duration_hours_out_of_range` | Non-positive hours |

## 7. Tests

`tests/test_wp_cl_009_training_normalization.py` — single/multi records, numbered lists, title≠provider, explicit provider, date/year/hours/cert, incomplete/unparsed, person match variants, provenance, golden Excel formats, no DB writes.

## 8. Related

- [ADR-057 §5.8](../architecture/ADR-057-control-list-interchange-architecture.md)
- [WP-CL-008 — Education Normalization](./WP-CL-008-education-normalization.md)
