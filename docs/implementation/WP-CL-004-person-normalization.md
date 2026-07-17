--------------------------------------------------

Document Status

Document:
WP-CL-004-person-normalization

Title:
Control List Person Normalization — Person Candidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-004

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no PPR writes, no person matching, no DB persistence

--------------------------------------------------

# WP-CL-004 — Person Normalization

## 1. Цель

Преобразовать staging snapshot + mapping profile в **Person Candidate** — единый внутренний нормализованный формат import pipeline.

Без поиска совпадений с canonical Person и без записи в PPR.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| Person Candidate domain model | Person matching (WP-CL-005) |
| Value objects + normalizers | PPR / Employment DB writes |
| PersonNormalizationService | Candidate persistence table |
| Unit tests | API / frontend |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Staging (WP-CL-002) | Raw snapshot профилировщика | Нет |
| Mapping profile (WP-CL-003) | Versioned configuration | Нет |
| **Person Candidate (WP-CL-004)** | **Temporary normalized import model** | **Нет** |
| Canonical PPR Person | Operational person record after apply | Да |

**Person Candidate — не canonical Person.** Это промежуточный in-memory результат normalization pipeline для review / matching / apply на последующих этапах.

**Инварианты:**

- Temporary in-memory domain model; **без** ORM / SQLAlchemy и **без** записи в PPR.
- **Не содержит** `person_id`, `employee_id`, `candidate_id` и других ссылок на canonical PPR.
- **Не выполняет** person matching — сопоставление с Person только в WP-CL-005.
- Один `import_run` → **множество** Person Candidate (по data-строкам staging).

## 4. Person Candidate

Минимальные нормализуемые поля:

| Field | Value object | Normalizer |
|-------|--------------|------------|
| ФИО | `NormalizedFullName` | `normalize_full_name` |
| ИИН | `NormalizedIin` | `normalize_iin` |
| Дата рождения | `NormalizedBirthDate` | `normalize_birth_date` |
| Телефон | `NormalizedPhone` | `normalize_phone` |
| Пол | `NormalizedSex` | `normalize_sex` |
| Подразделение | `NormalizedPlainText` | plain string normalizer |
| Должность | `NormalizedPlainText` | plain string normalizer |

Каждое поле хранит `raw`, normalized value и `issues`.

Provenance на candidate:
- `import_run_id`, `profile_id`, `profile_code`, `profile_version`
- `source_row_id`, `source_sheet_name`, `source_excel_row_number`
- `personnel_category`, `employment_mode` — sheet context (не Person attribute)

## 5. Normalizers

| Module | Responsibility |
|--------|----------------|
| `normalization/strings.py` | trim, whitespace collapse, Unicode NFKC |
| `normalization/full_name.py` | FIO cleanup, title case, pattern issues |
| `normalization/iin.py` | 12-digit IIN, float/11-digit padding |
| `normalization/phone.py` | digits-only, 8→7 prefix |
| `normalization/dates.py` | text dates, Excel serial, datetime |
| `normalization/sex.py` | M/F mapping from RU tokens |

## 6. PersonNormalizationService

```text
StagingRunInput + MappingProfileSnapshot
  → PersonNormalizationService.normalize_run()
  → list[PersonCandidate]
```

Row-level flow:
1. Skip non-`data` rows.
2. Match profile sheet by `sheet_name`.
3. Read cell values by profile `column_index`.
4. Apply parser/semantic normalizers.
5. Collect `field_issues` (including required missing).

**No PPR database access.**

## 7. Артефакты

| Артефакт | Путь |
|----------|------|
| Person Candidate | `app/control_list_import/domain/person_candidate.py` |
| Staging inputs | `app/control_list_import/domain/staging_models.py` |
| Normalizers | `app/control_list_import/normalization/` |
| Service | `app/control_list_import/normalization/service.py` |
| Tests | `tests/test_wp_cl_004_person_normalization.py` |

## 8. Acceptance

- [x] Person Candidate domain model
- [x] Normalizers for FIO, IIN, phone, dates, strings, sex
- [x] Normalization service (staging + profile)
- [x] Unit tests pass
- [x] `git diff --check` clean

## 9. Следующий WP

WP-CL-005 — Person matching against canonical records.
