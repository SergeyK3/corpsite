# ADR-038 Phase 2C — Training Documents Normalization

## Статус

**Принят** (design + implementation scope).

## Дата

2026-06-16

## Связанные документы

- [ADR-038 — Employee Identity & HR Import Architecture](./ADR-038-employee-identity-hr-import-architecture.md) §6 Document Candidate Architecture
- [ADR-037 — Employee Documents Registry](./ADR-037-employee-documents-registry.md)

---

## Контекст

Phase 2B доставил analytics MVP поверх `hr_import_rows`: summary, risks, training/certification counters на сыром `training_raw` / `certification_raw`.

Две проблемы блокируют review workflow:

1. **Risk «Без ИИН»** считает все строки без ИИН, включая `DECLARATION`, `SUMMARY_ROW` и прочие служебные строки — завышает риск и смешивает сотрудников с техническими записями.
2. **training_raw / certification_raw** — неструктурированный текст в ячейке Excel; analytics показывает только факт наличия текста, без нормализованных document candidates для review.

Phase 2C исправляет классификацию рисков и вводит **staging document candidates** без автоматического создания `employee_documents`.

---

## Решение 1 — Employee vs technical row classification

### Определения

| Концепт | Условие |
|---------|---------|
| **Real employee row** | `classification ∉ {DECLARATION, SUMMARY_ROW}` и `sheet_type ≠ declaration` |
| **Missing IIN (employee risk)** | real employee row **и** пустой `iin` |
| **Technical no-IIN row** | **не** real employee row **и** пустой `iin` |

`PART_TIME`, `INVALID_IIN`, `DUPLICATE_IIN`, `NORMAL` — считаются real employee rows (это строки людей, не служебные итоги).

### Изменения analytics

| Метрика / risk | Было | Станет |
|----------------|------|--------|
| `missing_iin` (summary + risk) | все строки без ИИН | только real employee rows |
| `technical_no_iin_rows` (summary) | — | новый счётчик |
| risk `technical_no_iin` | — | «Служебные строки без ИИН» |
| `without_training`, `without_certification`, `unknown_department` | все строки | только real employee rows (согласованность employee-centric метрик) |

Фильтр `risk_type=missing_iin` в `/rows` использует ту же логику.

---

## Решение 2 — Расширение `hr_import_document_candidates`

### Решение: расширить существующую таблицу (не новая)

Phase 2A уже создала `hr_import_document_candidates` с минимальным набором полей (ADR-038 §6.2). Phase 2C **добавляет колонки** и сохраняет обратную совместимость:

| Legacy column (2A) | Phase 2C mapping |
|--------------------|------------------|
| `proposed_document_type` | → API `document_type` |
| `parsed_hours` | → API `hours` |
| `parsed_valid_until` | → API `valid_until` |
| `review_status` | → API `status` |
| — | `raw_text` (новое; ранее не было) |

### Новые колонки (migration)

```sql
ALTER TABLE hr_import_document_candidates ADD COLUMN IF NOT EXISTS
  batch_id              BIGINT NOT NULL REFERENCES hr_import_batches(batch_id) ON DELETE CASCADE,
  employee_identity_id  BIGINT NULL REFERENCES employee_identities(identity_id) ON DELETE SET NULL,
  full_name             TEXT NULL,
  iin                   TEXT NULL,          -- full IIN, internal only
  department            TEXT NULL,
  position              TEXT NULL,
  document_kind         TEXT NOT NULL DEFAULT 'training'
                        CHECK (document_kind IN ('training', 'certification')),
  title                 TEXT NULL,
  organization          TEXT NULL,
  parsed_issued_at      DATE NULL,
  specialty             TEXT NULL,
  category              TEXT NULL,
  certificate_number    TEXT NULL,
  raw_text              TEXT NOT NULL DEFAULT '',
  source_sheet          TEXT NULL,
  source_row            INT NULL,
  external_url          TEXT NULL,
  storage_type          TEXT NULL
                        CHECK (storage_type IS NULL OR storage_type IN ('url','google_drive','network_share','none')),
  storage_path          TEXT NULL,
  fragment_index        INT NOT NULL DEFAULT 0,
  parse_method          TEXT NULL DEFAULT 'regex_v1';
```

Индексы:

```text
ix_hr_import_doc_candidates_batch          ON (batch_id)
ix_hr_import_doc_candidates_batch_kind     ON (batch_id, document_kind)
ix_hr_import_doc_candidates_batch_status   ON (batch_id, review_status)
ix_hr_import_doc_candidates_iin            ON (batch_id, iin)  -- internal joins only
```

`batch_id` backfill: `UPDATE ... SET batch_id = r.batch_id FROM hr_import_rows r WHERE r.row_id = candidates.row_id`.

### IIN exposure policy

| Layer | IIN |
|-------|-----|
| DB `hr_import_document_candidates.iin` | full 12 digits (staging, privileged) |
| Authenticated API list/detail | full `iin` field |
| CLI preview (`import_hr_control_list.py`) | masked (non-authenticated debug output only) |

---

## Решение 3 — Parser pipeline

### Модуль

`app/services/hr_import_document_parser.py` — pure functions, без DB.

### Fragment splitting

Один `training_raw` / `certification_raw` → 0..N fragments:

1. Split по `\n`, `;`, numbered list (`1.`, `2)`, `1)`).
2. Trim, skip empty.
3. Каждый fragment → отдельный candidate с `fragment_index`.

### Training fragment extraction (`document_kind=training`)

| Field | Heuristics (regex_v1) |
|-------|----------------------|
| `parsed_issued_at` | year `\b(19\|20)\d{2}\b` → `YYYY-01-01`; или `DD.MM.YYYY` |
| `parsed_valid_until` | `до DD.MM.YYYY`, `действ. до`, `срок до` |
| `parsed_hours` | `(\d+(?:[.,]\d+)?)\s*(?:ч(?:ас(?:ов)?)?\.?)` |
| `proposed_document_type` | keywords: `ПК`, `повышение квалифика`, `семинар`, `конференц`, `мастер-класс` |
| `title` | fragment minus extracted metadata |
| `organization` | `(?:в\|на\|ОО\|ГК\|НМО)\s+…` (best-effort) |
| `confidence_score` | 0.3 base + bonuses for date/hours/type |

### Certification fragment extraction (`document_kind=certification`)

| Field | Heuristics |
|-------|------------|
| `category` | `высш`, `перва`, `втор`, `сертификат` |
| `certificate_number` | `№\s*[\d/-]+`, `номер\s*[\d/-]+` |
| `parsed_valid_until` | date patterns |
| `proposed_document_type` | `SPECIALIST_CERT` / `QUALIFICATION_CATEGORY` |
| `title` | raw fragment or category label |

### Persistence trigger

После `_persist_rows()` в `import_control_list()`:

```text
parse_and_persist_document_candidates(conn, batch_id)
```

- DELETE existing candidates for batch (idempotent rebuild).
- INSERT one row per fragment.
- Copy employee snapshot: `full_name`, `department`, `position`, `source_sheet`, `source_row`.
- Resolve `employee_id` / `employee_identity_id` from `hr_import_rows.employee_id` + IIN lookup in `employee_identities` (best-effort, nullable).
- **Never** INSERT into `employee_documents`.

---

## Решение 4 — API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/directory/personnel/import/batches/{id}/document-candidates` | paginated list + filters |
| GET | `/directory/personnel/import/batches/{id}/document-candidates/summary` | counts by kind/status |
| GET | `/directory/personnel/import/batches/{id}/document-candidates/employees/{key}` | specialist card + history |

Query filters: `document_kind`, `status`, `department`, `q_name`, `has_hours`, `has_valid_until`.

Specialist key: `row_id` or grouping by `full_name+iin` for unmatched employees.

---

## Решение 5 — UI

Новая страница: `/directory/personnel/import/{batchId}/training`

| Block | Content |
|-------|---------|
| Summary cards | total candidates, training / certification split, pending review |
| Filters | kind, department, status, search by name |
| Table | employee, department, title, hours, issued_at, valid_until, status, raw_text preview |
| Detail drawer | full raw_text, external_url / Google Drive link field (read from candidate), link to source row |
| Navigation | link from analytics dashboard + sub-nav within batch context |

`external_url` / `storage_type=google_drive` — поля для ссылки на обменный диск (заполняются при apply/review в Phase 3; Phase 2C показывает placeholder + parsed data).

---

## Ограничения (explicit non-goals)

- ❌ Auto-create `employee_documents`
- ❌ Auto-match employee beyond existing `hr_import_rows.employee_id` / IIN identity lookup
- ❌ LLM parsing (future `parse_method=llm_assisted`)
- ❌ File upload to storage

---

## Test plan

| Test | Assertion |
|------|-----------|
| `test_missing_iin_excludes_declaration_and_summary` | DECLARATION/SUMMARY_ROW not in `missing_iin`; counted in `technical_no_iin` |
| `test_document_candidates_from_training_raw` | import sample → candidates with `document_kind=training` |
| `test_parser_hours_and_dates` | unit tests on parser: hours, year, DD.MM.YYYY |
| `test_candidates_api_returns_full_iin` | Authenticated API returns full `iin`, not `iin_masked` |
| `test_no_employee_documents_created` | after import + candidate build, `employee_documents` count unchanged |

---

## Migration path

```text
Phase 2A table (minimal)
    ↓ alembic upgrade (Phase 2C migration)
Extended candidates + backfill batch_id
    ↓ import_control_list hook
Auto-populated candidates per batch
    ↓ UI /directory/.../training
HR review staging (Phase 3: approve → employee_documents)
```

---

## Diff summary vs ADR-038 §6.2

| ADR-038 planned | Phase 2C actual |
|-----------------|-----------------|
| `batch_id` | ✅ added via ALTER |
| `fragment_index` | ✅ added |
| `raw_fragment` | named `raw_text` |
| `proposed_title` | named `title` |
| Employee snapshot fields | ✅ denormalized for review UX |
| `external_url` / storage | ✅ columns added, UI read-only in 2C |
