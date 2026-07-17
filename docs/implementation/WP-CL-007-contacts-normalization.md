--------------------------------------------------

Document Status

Document:
WP-CL-007-contacts-normalization

Title:
Control List Contacts Normalization — Contact Candidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-007

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no PPR contact writes, no merge/update of canonical contacts

--------------------------------------------------

# WP-CL-007 — Contacts Normalization

## 1. Цель

Преобразовать staging snapshot + mapping profile + person match result в **ContactCandidate** — временный нормализованный contact slice import pipeline.

Без записи в Person/PPR и без изменения canonical contact data.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| ContactCandidate domain model | PPR contact merge/update |
| Contact normalizers + service | Apply / canonical contact writes |
| Vocabulary extension (`contact.*`) | API / frontend |
| Unit tests | Duplicate detection policy |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Person Candidate + Match (WP-CL-004/005) | Person identity slice + match outcome | Нет |
| **Contact Candidate (WP-CL-007)** | **Temporary contact projection** | **Нет** |
| Canonical Person contacts | Operational contact data after apply | Да |

**Contact Candidate — не canonical Person contact record.**

**Инварианты:**

- Temporary in-memory domain model; **без** ORM / SQLAlchemy и **без** DB persistence.
- **Не использует** `employee_id` как идентичность человека.
- `matched_person_id` только из `exact`/`probable` match с `recommended_person_id`.
- Полностью пустые контакты → **skip** (no candidate).
- `normalization_ready` **не авторизует** запись/merge в PPR.
- Телефон — переиспользование WP-CL-004 `normalize_phone` (без дублирования).

## 4. ContactCandidate

| Field | Description |
|-------|-------------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, `source_sheet_name`, `source_excel_row_number` |
| `matched_person_id` | Resolved Person id or `null` |
| `phone` | `NormalizedPhone` (WP-CL-004) |
| `email` | `NormalizedEmail` |
| `residence_address` | Normalized address plain text |
| `registration_address` | Normalized address plain text |
| `field_issues` | Per semantic field issue codes |
| `readiness_status` | Normalization readiness |

### Readiness rules

| Person match | Contact fields | readiness_status |
|--------------|----------------|------------------|
| `exact` / `probable` + recommendation | no blocking issues | `normalization_ready` |
| `exact` / `probable` + recommendation | invalid phone/email | `review_required` |
| `ambiguous` | any | `review_required` |
| `invalid` | any | `person_match_invalid` |
| `not_found` | any | `person_unmatched` |

## 5. Normalizers

| Module | Responsibility |
|--------|----------------|
| WP-CL-004 `normalization/phone.py` | Phone digits normalization (reused) |
| `contact_normalization/email.py` | Email format + lowercase |
| `contact_normalization/address.py` | Address cleanup, technical empty detection |

## 6. ContactNormalizationService

```text
StagingRowInput + MappingProfileSnapshot + PersonMatchResult
  → ContactNormalizationService.normalize_row()
  → ContactCandidate | None
```

Returns `None` when all contact values are empty or technical-empty.

**No PPR / contact database access.**

## 7. Vocabulary

| semantic_field | parser_code |
|----------------|-------------|
| `contact.phone` | `contact.phone` (also accepts `identity.phone` parser) |
| `contact.email` | `contact.email` |
| `contact.residence_address` | `contact.address` |
| `contact.registration_address` | `contact.address` |

## 8. Артефакты

| Артефакт | Путь |
|----------|------|
| Contact Candidate | `app/control_list_import/domain/contact_candidate.py` |
| Vocabulary extension | `app/control_list_import/domain/vocabulary.py` |
| Normalizers | `app/control_list_import/contact_normalization/` |
| Service | `app/control_list_import/contact_normalization/service.py` |
| Tests | `tests/test_wp_cl_007_contacts_normalization.py` |

## 9. Acceptance

- [x] ContactCandidate domain model + readiness status
- [x] Normalizers: phone (reuse), email, address
- [x] ContactNormalizationService with empty skip
- [x] Unit tests pass
- [x] ADR-057 updated

## 10. Следующий WP

WP-CL-008 — Образование.
