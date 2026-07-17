--------------------------------------------------

Document Status

Document:
WP-CL-010-other-ppr-fields-normalization

Title:
Control List Other PPR Fields Normalization — OtherPprCandidate Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-010

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**In-memory normalization only** — no canonical PPR writes, no dedup

--------------------------------------------------

# WP-CL-010 — Other PPR Fields Normalization

## 1. Цель

Нормализовать оставшиеся PPR-поля контрольного листа, не покрытые WP-CL-004…009, в **list[OtherPprCandidate]**.

## 2. Inventory semantic_field

### 2.1. Включено (WP-CL-010)

| semantic_field | PPR slice | Normalizer |
|----------------|-----------|------------|
| `person.citizenship` | Citizenship | Controlled aliases (KZ/RU) |
| `person.nationality_raw` | Nationality raw text | Plain text |
| `ppr.marital_status` | Marital status | Controlled aliases (married/single/…) |
| `ppr.military_summary` | Military attestation summary | Conservative attestation aliases |
| `ppr.disability_summary` | Disability / special status summary | yes/no/not_applicable aliases |
| `person.awards` | Awards | Plain text |
| `person.notes` | Notes | Plain text |
| `qualification.category` | Qualification category | Plain text |
| `qualification.degree` | Academic degree | Plain text |

### 2.2. Исключено (уже покрыто другими WP)

| semantic_field | Work package |
|----------------|--------------|
| `person.full_name`, `person.birth_date`, `person.iin`, `person.sex`, `person.phone` | WP-CL-004 |
| `employment.*` | WP-CL-006 |
| `contact.*` | WP-CL-007 |
| `education.records` | WP-CL-008 |
| `training.records` | WP-CL-009 |

### 2.3. Не включено

| Item | Reason |
|------|--------|
| Declaration / technical worksheets | Out of scope per ADR-057 |
| `person_relatives`, structured military attributes | Separate PPR section WPs; control list carries summary text only |
| Composite education/training cells | WP-CL-008/009 |

### 2.4. Profiler / header aliases

Новые aliases добавлены в `scripts/ops/control_list_import/header_aliases.py`:

- `гражданство` → `person.citizenship` (отделено от `person.nationality_raw`)
- `семейное положение` → `ppr.marital_status`
- `воинский учёт` → `ppr.military_summary`
- `инвалидность` → `ppr.disability_summary`

## 3. OtherPprCandidate

| Field | Description |
|-------|-------------|
| Provenance | `import_run_id`, `profile_*`, `source_row_id`, sheet/row/column |
| `semantic_field` | Interchange semantic field id |
| `raw_value` | Original cell text (preserved) |
| `normalized_value` | `NormalizedScalarValue` (`text` + optional controlled `code`) |
| `matched_person_id` | From person match when exact/probable |
| `field_issues` | Issue codes per field |
| `readiness_status` | Normalization readiness |

## 4. Conservative rules

- Unicode / whitespace normalization via WP-CL-004 string helpers.
- Technical-empty (`-`, `н/д`, …) → skip candidate (empty list for cell).
- Aliases only for citizenship, marital, military attestation, disability tri-state.
- Military parser **не** извлекает rank/VUS/commissariat — только attestation summary codes.
- Unsupported semantic_field with cell content → candidate + `other_ppr_unsupported_semantic_field`.
- Excluded fields → documented skip (`OTHER_PPR_EXCLUDED_FIELDS`).

## 5. Service

```text
StagingRowInput + MappingProfileSnapshot + PersonMatchResult
  → OtherPprNormalizationService.normalize_row()
  → list[OtherPprCandidate]
```

## 6. Tests

`tests/test_wp_cl_010_other_ppr_normalization.py`

## 7. Related

- [ADR-057 §5.9](../architecture/ADR-057-control-list-interchange-architecture.md)
- [WP-PR-026 — Military registration in PPR](../architecture/WP-PR-026-military-registration-in-ppr.md)
