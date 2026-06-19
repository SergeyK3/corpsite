# ADR-039 Phase 3B — Training Normalization Schema (DDL Project)

## Статус

**Проектирование** (DDL review only; без сервисов и UI).

## Дата

2026-06-18

## Связанные документы

- [ADR-041 — Dual Personnel Registry Model](./ADR-041-dual-personnel-registry-model.md) — `employee_id` на staging **optional**; HR import не создаёт Employee автоматически
- [ADR-039 Phase 3A — Architectural Audit](./ADR-039-hr-professional-profile-normalization.md) *(если оформлен отдельно)*
- [ADR-037 — Employee Documents Registry](./ADR-037-employee-documents-registry.md)
- [ADR-038 Phase 2C — Training Documents Normalization](./ADR-038-Phase-2C-training-documents-normalization.md)

## Scope Phase 3B

| В scope | Вне scope |
|---------|-----------|
| `hr_import_normalized_records` | Promotion service |
| `training_hour_requirements` + seed | UI review / dashboard |
| Provenance columns on `employee_documents` | `employee_training_requirement_assignments` (Phase 3G) |
| Indexes, FK, UNIQUE, CHECK | Backfill из `document_candidates` |
| `source_record_key` dedup contract | Sync package changes |

**Alembic head (baseline):** `m6f7a8b9c0d1` (ADR-038 D.3 sync audit log)

**Planned revision:** `n7a8b9c0d1e2_adr039_phase_3b_training_normalization_schema.py`

---

## 1. ER Diagram

```mermaid
erDiagram
    hr_import_batches ||--o{ hr_import_rows : contains
    hr_import_batches ||--o{ hr_import_normalized_records : scopes
    hr_import_rows ||--o{ hr_import_normalized_records : generates
    employees ||--o{ hr_import_normalized_records : "optional match"
    document_types ||--o{ hr_import_normalized_records : "proposed type"
    medical_specialties ||--o{ hr_import_normalized_records : "optional"
    medical_specialty_groups ||--o{ training_hour_requirements : "optional category"
    hr_import_normalized_records ||--o| employee_documents : promotes_to
    employees ||--o{ employee_documents : has
    document_types ||--o{ employee_documents : classifies
    hr_import_batches ||--o{ employee_documents : "source_batch"
    hr_import_rows ||--o{ employee_documents : "source_row"
    users ||--o{ hr_import_normalized_records : "reviewed_by / promoted_by"

    hr_import_normalized_records {
        bigint normalized_record_id PK
        bigint batch_id FK
        bigint row_id FK
        bigint employee_id FK
        text record_kind
        text source_record_key UK_per_row
        text review_status
        bigint promoted_document_id FK
    }

    training_hour_requirements {
        bigint requirement_id PK
        text code UK
        int hours_required
        int window_years
        text date_basis
        bigint specialty_group_id FK
    }

    employee_documents {
        bigint document_id PK
        bigint source_batch_id FK
        bigint source_row_id FK
        bigint source_normalized_record_id FK
        text source_record_key UK_per_employee_active
        text parse_method
        date end_date
        text verification_status
    }
```

---

## 2. SQL Schema Review

### 2.1. `training_hour_requirements`

Справочник норм учёта часов. Заменяет hardcoded `DEFAULT_TRAINING_HOURS_REQUIRED = 144` в сервисном слое (Phase 3C).

```sql
CREATE TABLE IF NOT EXISTS public.training_hour_requirements (
    requirement_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    hours_required      INTEGER NOT NULL,
    window_years        INTEGER NOT NULL DEFAULT 5,
    date_basis          TEXT NOT NULL DEFAULT 'issued_at',
    specialty_group_id  BIGINT NULL,
    include_superseded  BOOLEAN NOT NULL DEFAULT FALSE,
    effective_from      DATE NOT NULL,
    effective_to        DATE NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_training_hour_requirements_code
        UNIQUE (code),

    CONSTRAINT fk_training_hour_requirements_specialty_group
        FOREIGN KEY (specialty_group_id)
        REFERENCES public.medical_specialty_groups(group_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_training_hour_requirements_hours_positive
        CHECK (hours_required > 0),

    CONSTRAINT chk_training_hour_requirements_window_positive
        CHECK (window_years > 0),

    CONSTRAINT chk_training_hour_requirements_date_basis
        CHECK (date_basis IN ('issued_at', 'end_date')),

    CONSTRAINT chk_training_hour_requirements_effective_range
        CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

COMMENT ON TABLE public.training_hour_requirements IS
    'ADR-039: configurable training hour norms (e.g. 144h / 5y).';
COMMENT ON COLUMN public.training_hour_requirements.specialty_group_id IS
    'NULL = applies to all groups; DOCTOR/NURSE via medical_specialty_groups.code.';
COMMENT ON COLUMN public.training_hour_requirements.date_basis IS
    'Which employee_documents date column drives the rolling window.';
COMMENT ON COLUMN public.training_hour_requirements.include_superseded IS
    'Reserved; Phase 3C service defaults to FALSE (ACTIVE only).';
```

**Seed (upgrade only):**

```sql
INSERT INTO public.training_hour_requirements (
    code, name, hours_required, window_years, date_basis,
    specialty_group_id, effective_from, is_active, sort_order
)
SELECT
    'DEFAULT_144',
    'Норма НМО: 144 часа за 5 лет',
    144,
    5,
    'issued_at',
    NULL,
    DATE '2020-01-01',
    TRUE,
    10
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    hours_required = EXCLUDED.hours_required,
    window_years = EXCLUDED.window_years,
    date_basis = EXCLUDED.date_basis,
    is_active = EXCLUDED.is_active,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS ix_training_hour_requirements_active
    ON public.training_hour_requirements (is_active, sort_order)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS ix_training_hour_requirements_group
    ON public.training_hour_requirements (specialty_group_id)
    WHERE specialty_group_id IS NOT NULL;
```

---

### 2.2. `hr_import_normalized_records`

Staging-слой между import profile / parser и production `employee_documents`.

```sql
CREATE TABLE IF NOT EXISTS public.hr_import_normalized_records (
    normalized_record_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Import lineage
    batch_id                    BIGINT NOT NULL,
    row_id                      BIGINT NOT NULL,
    employee_id                 BIGINT NULL,
    fragment_index              INTEGER NOT NULL DEFAULT 0,
    source_field                TEXT NOT NULL,
    source_text                 TEXT NOT NULL,

    -- Dedup key (computed by application; see §4)
    source_record_key           TEXT NOT NULL,

    -- Classification
    record_kind                 TEXT NOT NULL,
    document_type_id            BIGINT NULL,
    document_type_code          TEXT NULL,

    -- Normalized payload
    title                       TEXT NULL,
    provider                    TEXT NULL,
    hours                       INTEGER NULL,
    start_date                  DATE NULL,
    end_date                    DATE NULL,
    issue_date                  DATE NULL,
    expiry_date                 DATE NULL,
    document_number             TEXT NULL,
    specialty_text              TEXT NULL,
    medical_specialty_id        BIGINT NULL,
    file_url                    TEXT NULL,

    -- Parse metadata
    parse_method                TEXT NOT NULL DEFAULT 'regex_v1',
    confidence                  NUMERIC(5, 4) NULL,

    -- Review / promotion workflow
    review_status               TEXT NOT NULL DEFAULT 'pending',
    reviewed_at                 TIMESTAMPTZ NULL,
    reviewed_by                 BIGINT NULL,
    review_notes                TEXT NULL,
    promoted_document_id        BIGINT NULL,
    promoted_at                 TIMESTAMPTZ NULL,
    promoted_by                 BIGINT NULL,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Foreign keys
    CONSTRAINT fk_hinr_batch
        FOREIGN KEY (batch_id)
        REFERENCES public.hr_import_batches(batch_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_hinr_row
        FOREIGN KEY (row_id)
        REFERENCES public.hr_import_rows(row_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_hinr_employee
        FOREIGN KEY (employee_id)
        REFERENCES public.employees(employee_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hinr_document_type
        FOREIGN KEY (document_type_id)
        REFERENCES public.document_types(document_type_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hinr_medical_specialty
        FOREIGN KEY (medical_specialty_id)
        REFERENCES public.medical_specialties(medical_specialty_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hinr_reviewed_by
        FOREIGN KEY (reviewed_by)
        REFERENCES public.users(user_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hinr_promoted_by
        FOREIGN KEY (promoted_by)
        REFERENCES public.users(user_id)
        ON DELETE SET NULL,

    -- Note: fk_hinr_promoted_document added in step 3 after employee_documents columns exist

    -- Uniqueness (within import row)
    CONSTRAINT uq_hinr_row_source_record_key
        UNIQUE (row_id, source_record_key),

    -- Domain checks
    CONSTRAINT chk_hinr_record_kind
        CHECK (record_kind IN ('training', 'certificate', 'category', 'education')),

    CONSTRAINT chk_hinr_review_status
        CHECK (review_status IN (
            'pending', 'approved', 'rejected', 'promoted', 'superseded'
        )),

    CONSTRAINT chk_hinr_parse_method
        CHECK (parse_method IN (
            'regex_v1', 'manual_override', 'manual', 'ai_extraction', 'import_promoted'
        )),

    CONSTRAINT chk_hinr_hours_nonneg
        CHECK (hours IS NULL OR hours >= 0),

    CONSTRAINT chk_hinr_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),

    CONSTRAINT chk_hinr_fragment_index_nonneg
        CHECK (fragment_index >= 0),

    CONSTRAINT chk_hinr_source_field_nonempty
        CHECK (length(trim(source_field)) > 0),

    CONSTRAINT chk_hinr_source_record_key_nonempty
        CHECK (length(trim(source_record_key)) > 0),

    CONSTRAINT chk_hinr_date_order_start_end
        CHECK (
            start_date IS NULL OR end_date IS NULL OR start_date <= end_date
        ),

    CONSTRAINT chk_hinr_date_order_issue_expiry
        CHECK (
            issue_date IS NULL OR expiry_date IS NULL OR issue_date <= expiry_date
        ),

    CONSTRAINT chk_hinr_promoted_requires_document
        CHECK (
            review_status <> 'promoted' OR promoted_document_id IS NOT NULL
        ),

    CONSTRAINT chk_hinr_rejected_no_promotion
        CHECK (
            review_status <> 'rejected' OR promoted_document_id IS NULL
        )
);

COMMENT ON TABLE public.hr_import_normalized_records IS
    'ADR-039: parsed training/certificate/education records awaiting HR review and promotion.';
COMMENT ON COLUMN public.hr_import_normalized_records.source_record_key IS
    'Deterministic dedup key; UNIQUE per row_id; copied to employee_documents on promotion.';
COMMENT ON COLUMN public.hr_import_normalized_records.document_type_code IS
    'Staging fallback when document_type_id not yet resolved (parser proposed type code).';
COMMENT ON COLUMN public.hr_import_normalized_records.provider IS
    'Training organization / certificate issuer (maps to employee_documents.issued_by).';
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS ix_hinr_batch_id
    ON public.hr_import_normalized_records (batch_id);

CREATE INDEX IF NOT EXISTS ix_hinr_row_id
    ON public.hr_import_normalized_records (row_id);

CREATE INDEX IF NOT EXISTS ix_hinr_employee_id
    ON public.hr_import_normalized_records (employee_id)
    WHERE employee_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_hinr_batch_review_status
    ON public.hr_import_normalized_records (batch_id, review_status);

CREATE INDEX IF NOT EXISTS ix_hinr_employee_review_open
    ON public.hr_import_normalized_records (employee_id, review_status)
    WHERE employee_id IS NOT NULL
      AND review_status IN ('pending', 'approved')
      AND promoted_document_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_hinr_promoted_document
    ON public.hr_import_normalized_records (promoted_document_id)
    WHERE promoted_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_hinr_record_kind
    ON public.hr_import_normalized_records (record_kind);

CREATE INDEX IF NOT EXISTS ix_hinr_expiry_date
    ON public.hr_import_normalized_records (expiry_date)
    WHERE expiry_date IS NOT NULL
      AND review_status IN ('pending', 'approved', 'promoted');
```

**Cross-employee dedup (partial unique — open staging only):**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_hinr_employee_source_key_open
    ON public.hr_import_normalized_records (employee_id, source_record_key)
    WHERE employee_id IS NOT NULL
      AND review_status IN ('pending', 'approved')
      AND promoted_document_id IS NULL;
```

> **Note:** `employee_id IS NULL` rows (unmatched import) dedup only via `(row_id, source_record_key)`.
> After employee match, application must recompute key scope or merge duplicates before promotion.

> **ADR-041 — binding optional:** отсутствие `employee_id` на `hr_import_rows` / `hr_import_normalized_records` — **нормальное** состояние для HR analytics и canonical snapshot. Привязка к operational `employees` (Phase 3G: по ИИН / по ФИО) — опциональное улучшение match key, не обязательный результат импорта. Promotion в `employee_documents` по-прежнему требует `employee_id` (gate для operational documents).

---

### 2.3. `employee_documents` — provenance columns

Расширение production-реестра (ADR-037). Все новые колонки **NULLable** — backward compatible.

```sql
ALTER TABLE public.employee_documents
    ADD COLUMN IF NOT EXISTS source_batch_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS source_row_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS source_normalized_record_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS source_record_key TEXT NULL,
    ADD COLUMN IF NOT EXISTS source_text TEXT NULL,
    ADD COLUMN IF NOT EXISTS parse_method TEXT NULL,
    ADD COLUMN IF NOT EXISTS parse_confidence NUMERIC(5, 4) NULL,
    ADD COLUMN IF NOT EXISTS end_date DATE NULL,
    ADD COLUMN IF NOT EXISTS verification_status TEXT NULL;

-- Foreign keys (idempotent DO blocks in migration)
ALTER TABLE public.employee_documents
    ADD CONSTRAINT fk_employee_documents_source_batch
        FOREIGN KEY (source_batch_id)
        REFERENCES public.hr_import_batches(batch_id)
        ON DELETE SET NULL;

ALTER TABLE public.employee_documents
    ADD CONSTRAINT fk_employee_documents_source_row
        FOREIGN KEY (source_row_id)
        REFERENCES public.hr_import_rows(row_id)
        ON DELETE SET NULL;

ALTER TABLE public.employee_documents
    ADD CONSTRAINT fk_employee_documents_source_normalized_record
        FOREIGN KEY (source_normalized_record_id)
        REFERENCES public.hr_import_normalized_records(normalized_record_id)
        ON DELETE SET NULL;

-- Reverse FK (deferred step)
ALTER TABLE public.hr_import_normalized_records
    ADD CONSTRAINT fk_hinr_promoted_document
        FOREIGN KEY (promoted_document_id)
        REFERENCES public.employee_documents(document_id)
        ON DELETE SET NULL;

-- Checks
ALTER TABLE public.employee_documents
    ADD CONSTRAINT chk_employee_documents_parse_confidence_range
        CHECK (parse_confidence IS NULL OR (parse_confidence >= 0 AND parse_confidence <= 1));

ALTER TABLE public.employee_documents
    ADD CONSTRAINT chk_employee_documents_parse_method
        CHECK (parse_method IS NULL OR parse_method IN (
            'regex_v1', 'manual_override', 'manual', 'ai_extraction', 'import_promoted'
        ));

ALTER TABLE public.employee_documents
    ADD CONSTRAINT chk_employee_documents_verification_status
        CHECK (verification_status IS NULL OR verification_status IN (
            'UNVERIFIED', 'VERIFIED', 'REJECTED'
        ));

ALTER TABLE public.employee_documents
    ADD CONSTRAINT chk_employee_documents_end_date_order
        CHECK (
            issued_at IS NULL OR end_date IS NULL OR issued_at <= end_date
        );

ALTER TABLE public.employee_documents
    ADD CONSTRAINT chk_employee_documents_source_record_key_nonempty
        CHECK (source_record_key IS NULL OR length(trim(source_record_key)) > 0);
```

**Column mapping (staging → production):**

| `hr_import_normalized_records` | `employee_documents` |
|-------------------------------|----------------------|
| `issue_date` | `issued_at` |
| `end_date` | `end_date` |
| `expiry_date` | `valid_until` |
| `provider` | `issued_by` |
| `title` / `training_title` | `title` / `training_title` (by record_kind) |
| `document_number` | `document_number` |
| `hours` | `hours` |
| `file_url` | `file_url` |
| `source_record_key` | `source_record_key` |
| `source_text` | `source_text` |
| `parse_method` | `parse_method` |
| `confidence` | `parse_confidence` |
| `normalized_record_id` | `source_normalized_record_id` |
| `batch_id` / `row_id` | `source_batch_id` / `source_row_id` |

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS ix_employee_documents_source_batch
    ON public.employee_documents (source_batch_id)
    WHERE source_batch_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_employee_documents_source_row
    ON public.employee_documents (source_row_id)
    WHERE source_row_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_employee_documents_source_normalized_record
    ON public.employee_documents (source_normalized_record_id)
    WHERE source_normalized_record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_employee_documents_verification_status
    ON public.employee_documents (verification_status)
    WHERE verification_status IS NOT NULL
      AND lifecycle_status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS ix_employee_documents_end_date
    ON public.employee_documents (end_date)
    WHERE end_date IS NOT NULL
      AND lifecycle_status = 'ACTIVE';
```

**Production dedup (partial unique):**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_documents_employee_source_key_active
    ON public.employee_documents (employee_id, source_record_key)
    WHERE lifecycle_status = 'ACTIVE'
      AND source_record_key IS NOT NULL;
```

> Manual CRUD documents without `source_record_key` are unaffected.
> Re-promotion of the same import fragment is blocked at DB level for ACTIVE docs.

---

## 3. Foreign Keys Summary

| Child table | Column | Parent | ON DELETE |
|-------------|--------|--------|-----------|
| `training_hour_requirements` | `specialty_group_id` | `medical_specialty_groups` | SET NULL |
| `hr_import_normalized_records` | `batch_id` | `hr_import_batches` | **CASCADE** |
| `hr_import_normalized_records` | `row_id` | `hr_import_rows` | **CASCADE** |
| `hr_import_normalized_records` | `employee_id` | `employees` | SET NULL |
| `hr_import_normalized_records` | `document_type_id` | `document_types` | SET NULL |
| `hr_import_normalized_records` | `medical_specialty_id` | `medical_specialties` | SET NULL |
| `hr_import_normalized_records` | `reviewed_by` | `users` | SET NULL |
| `hr_import_normalized_records` | `promoted_by` | `users` | SET NULL |
| `hr_import_normalized_records` | `promoted_document_id` | `employee_documents` | SET NULL |
| `employee_documents` | `source_batch_id` | `hr_import_batches` | SET NULL |
| `employee_documents` | `source_row_id` | `hr_import_rows` | SET NULL |
| `employee_documents` | `source_normalized_record_id` | `hr_import_normalized_records` | SET NULL |

**Circular FK resolution:** `hr_import_normalized_records.promoted_document_id` ↔ `employee_documents.source_normalized_record_id` — оба nullable; создаются в одной миграции после существования обеих таблиц/колонок.

---

## 4. `source_record_key` Dedup Strategy

### 4.1. Purpose

| Layer | Constraint | Prevents |
|-------|------------|----------|
| Staging per row | `UNIQUE (row_id, source_record_key)` | Duplicate parser output within one Excel row |
| Staging per employee (open) | `UNIQUE (employee_id, source_record_key) WHERE open` | Duplicate pending records across rows in same batch |
| Production | `UNIQUE (employee_id, source_record_key) WHERE ACTIVE` | Double promotion to live registry |

### 4.2. Key format

64-char lowercase hex SHA-256 truncated is acceptable; store full 64 chars for collision safety.

**Canonical input string** (UTF-8, `|` separator, empty fields as empty string):

```text
{scope}|{record_kind}|{norm_title}|{issue_date}|{end_date}|{hours}|{document_number}|{source_field}|{fragment_index}
```

**Scope:**

```text
scope = "emp:{employee_id}"   if employee_id IS NOT NULL
scope = "row:{row_id}"        otherwise
```

**Normalization helpers (application layer, Phase 3C):**

```python
def norm_title(s: str) -> str:
    # lower, strip, collapse whitespace, replace ё→е optional
    ...

def norm_date(d: date | None) -> str:
    return d.isoformat() if d else ""

def norm_hours(h: int | None) -> str:
    return str(h) if h is not None else ""
```

**Example:**

```text
Input fragment: row_id=501, employee_id=7, training, "ПК 72 ч", 2024-06-15, hours=72
Canonical: "emp:7|training|пк 72 ч|2024-06-15||72||education_training_raw|0"
source_record_key: sha256(canonical).hexdigest()  # 64 chars
```

### 4.3. Lifecycle rules

| Event | Action |
|-------|--------|
| Parse row → insert staging | Compute key; `ON CONFLICT (row_id, source_record_key) DO NOTHING` or upsert metadata |
| Employee matched on row | Recompute scope `row:*` → `emp:*`; resolve cross-row conflicts before approve |
| HR approve | `review_status = 'approved'` |
| Promote | Insert `employee_documents` with same key; set staging `promoted`, link IDs |
| Re-import same batch | New `row_id` → new keys unless content identical → open staging dedup catches via employee scope |
| Supersede production doc | `lifecycle_status = SUPERSEDED'` — unique slot freed; re-promotion allowed |

### 4.4. Explicit non-goals (Phase 3B)

- No fuzzy dedup (similar titles) — HR review only.
- No automatic merge of manual CRUD docs (no `source_record_key`).
- `hr_import_document_candidates` remains separate; backfill migration is Phase 3C.

---

## 5. Alembic Migration Plan

### 5.1. Single revision (recommended)

| Property | Value |
|----------|-------|
| File | `alembic/versions/n7a8b9c0d1e2_adr039_phase_3b_training_normalization_schema.py` |
| Revision | `n7a8b9c0d1e2` |
| `down_revision` | `m6f7a8b9c0d1` |
| Idempotent patterns | `IF NOT EXISTS`, `DO $$ ... IF NOT EXISTS (pg_constraint)` |

### 5.2. Upgrade step order

```
Step 1  CREATE TABLE training_hour_requirements (+ indexes, seed DEFAULT_144)
Step 2  CREATE TABLE hr_import_normalized_records (without fk_hinr_promoted_document)
Step 3  CREATE indexes on hr_import_normalized_records (including partial uniques)
Step 4  ALTER TABLE employee_documents ADD provenance columns (nullable)
Step 5  ADD FK employee_documents → hr_import_batches / hr_import_rows / hr_import_normalized_records
Step 6  ADD FK hr_import_normalized_records → employee_documents (promoted_document_id)
Step 7  ADD CHECK constraints on employee_documents new columns
Step 8  CREATE indexes on employee_documents (including uq_employee_documents_employee_source_key_active)
```

### 5.3. Migration checklist

**Pre-deploy**

- [ ] Confirm Alembic head is `m6f7a8b9c0d1` on target environment
- [ ] Confirm `employee_documents`, `hr_import_batches`, `hr_import_rows` exist
- [ ] Confirm `document_types`, `medical_specialty_groups` seeded (ADR-037 1A)
- [ ] Review DDL on staging DB (`alembic upgrade n7a8b9c0d1e2`)
- [ ] Verify no existing column name conflicts (`end_date`, `verification_status`)

**Post-deploy validation**

- [ ] `\d training_hour_requirements` — seed row `DEFAULT_144` present
- [ ] `\d hr_import_normalized_records` — 25+ columns, 6+ CHECK constraints
- [ ] `\d employee_documents` — 9 new nullable columns
- [ ] Insert smoke test: staging row + manual promotion FK round-trip (SQL only)
- [ ] Confirm `uq_hinr_row_source_record_key` rejects duplicate insert
- [ ] Confirm `uq_employee_documents_employee_source_key_active` rejects duplicate ACTIVE promotion
- [ ] Run existing test suite — no regressions (schema-only change)
- [ ] `alembic downgrade -1` on staging → re-upgrade (rollback drill)

**Out of scope (Phase 3C+)**

- [ ] Population job: `build_import_profile` → `hr_import_normalized_records`
- [ ] Update `get_employee_training_hours_summary` to read `training_hour_requirements`
- [ ] Deprecate `hr_import_document_candidates` write path

---

## 6. Rollback Strategy

### 6.1. Downgrade order (reverse of upgrade)

```sql
-- Step 8↓
DROP INDEX IF EXISTS public.uq_employee_documents_employee_source_key_active;
DROP INDEX IF EXISTS public.ix_employee_documents_end_date;
DROP INDEX IF EXISTS public.ix_employee_documents_verification_status;
DROP INDEX IF EXISTS public.ix_employee_documents_source_normalized_record;
DROP INDEX IF EXISTS public.ix_employee_documents_source_row;
DROP INDEX IF EXISTS public.ix_employee_documents_source_batch;

-- Step 7↓ + Step 5↓ + Step 6↓
ALTER TABLE public.hr_import_normalized_records
    DROP CONSTRAINT IF EXISTS fk_hinr_promoted_document;

ALTER TABLE public.employee_documents
    DROP CONSTRAINT IF EXISTS chk_employee_documents_source_record_key_nonempty,
    DROP CONSTRAINT IF EXISTS chk_employee_documents_end_date_order,
    DROP CONSTRAINT IF EXISTS chk_employee_documents_verification_status,
    DROP CONSTRAINT IF EXISTS chk_employee_documents_parse_method,
    DROP CONSTRAINT IF EXISTS chk_employee_documents_parse_confidence_range,
    DROP CONSTRAINT IF EXISTS fk_employee_documents_source_normalized_record,
    DROP CONSTRAINT IF EXISTS fk_employee_documents_source_row,
    DROP CONSTRAINT IF EXISTS fk_employee_documents_source_batch;

-- Step 4↓
ALTER TABLE public.employee_documents
    DROP COLUMN IF EXISTS verification_status,
    DROP COLUMN IF EXISTS end_date,
    DROP COLUMN IF EXISTS parse_confidence,
    DROP COLUMN IF EXISTS parse_method,
    DROP COLUMN IF EXISTS source_text,
    DROP COLUMN IF EXISTS source_record_key,
    DROP COLUMN IF EXISTS source_normalized_record_id,
    DROP COLUMN IF EXISTS source_row_id,
    DROP COLUMN IF EXISTS source_batch_id;

-- Steps 3↓ 2↓
DROP TABLE IF EXISTS public.hr_import_normalized_records CASCADE;

-- Step 1↓
DROP INDEX IF EXISTS public.ix_training_hour_requirements_group;
DROP INDEX IF EXISTS public.ix_training_hour_requirements_active;
DROP TABLE IF EXISTS public.training_hour_requirements CASCADE;
```

### 6.2. Rollback safety

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Rollback after promotion data exists | `source_*` columns on `employee_documents` lost | **Block downgrade** if `COUNT(*) WHERE source_normalized_record_id IS NOT NULL > 0` unless explicit `--force` ops script |
| Rollback with staging rows | Staging data lost (CASCADE) | Export staging CSV before downgrade in prod |
| Partial failed migration | Mixed state | Single transaction per `op.execute` batch; use Alembic transactional DDL (PostgreSQL) |
| Circular FK drop order | Drop `fk_hinr_promoted_document` before `fk_employee_documents_source_normalized_record` | Order enforced in downgrade() |

### 6.3. Production rollback policy

1. **Preferred:** forward-fix migration (`n7a8b9c0d1e3`) rather than downgrade after any promotion.
2. **Downgrade allowed only if:** zero rows in `hr_import_normalized_records` AND zero `employee_documents.source_normalized_record_id`.
3. Gate in `downgrade()`:

```python
def downgrade() -> None:
    conn = op.get_bind()
    promoted = conn.execute(text(
        "SELECT COUNT(*) FROM employee_documents WHERE source_normalized_record_id IS NOT NULL"
    )).scalar()
    if promoted and int(promoted) > 0:
        raise RuntimeError(
            "ADR-039 3B downgrade blocked: promoted documents exist. Use forward migration."
        )
    # ... proceed with DROP ...
```

---

## 7. Design Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Single `employee_documents` target, not parallel `TrainingRecord` table | ADR-037 already production-ready with `hours` |
| D2 | `provider` in staging, `issued_by` in production | Aligns with ADR-037 naming |
| D3 | `document_type_code` staging fallback | Parser emits codes before FK lookup |
| D4 | `review_status = 'superseded'` for re-import replacement | Keeps audit trail without DELETE |
| D5 | `verification_status` on production only | Staging uses `review_status`; verification after promotion |
| D6 | `training_hour_requirements.specialty_group_id` not free-text category | FK to existing `medical_specialty_groups` |
| D7 | Partial unique indexes over full UNIQUE | Allow SUPERSEDED / rejected duplicates in history |
| D8 | No backfill from `document_candidates` in 3B | Avoids data migration risk; Phase 3C job |

---

## 8. Open Items for Phase 3C (service layer)

1. Trigger or application code to maintain `updated_at` on `hr_import_normalized_records`.
2. Resolve `document_type_code` → `document_type_id` via seed lookup table mapping parser codes (`TRAINING_HOURS` → `CONTINUING_EDUCATION`).
3. Employee match hook: recompute `source_record_key` when `hr_import_rows.employee_id` set.
4. Integrate `training_hour_requirements` into `get_employee_training_hours_summary()` (replace constant 144).

---

## Appendix A — Skeleton `upgrade()` / `downgrade()`

```python
"""ADR-039 Phase 3B — training normalization schema (staging + requirements + provenance).

Revision ID: n7a8b9c0d1e2
Revises: m6f7a8b9c0d1
"""
from __future__ import annotations

from alembic import op

revision = "n7a8b9c0d1e2"
down_revision = "m6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: training_hour_requirements (+ seed)
    # Step 2: hr_import_normalized_records (no promoted_document FK yet)
    # Step 3: hinr indexes
    # Step 4–8: employee_documents columns, FKs, checks, indexes
    ...


def downgrade() -> None:
    # Promotion gate check
    # Reverse steps 8→1 (see §6.1)
    ...
```
