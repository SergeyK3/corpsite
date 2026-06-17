# ADR-038-B. Sync Foundation (Phase B — Stage 0 Design)

Статус: Approved (B.1 implemented)  
Дата: 2026-06-17  
Родитель: [ADR-038](ADR-038-data-sync-and-hr-import-persistence.md)  
Предшествует: [ADR-038-A1](ADR-038-A1-import-integrity-hardening.md)

## Контекст

Phase A и Phase A.1 завершены:
- employee-level overrides переживают повторные импорты;
- provenance (`base_batch_id`, `base_row_id`, `base_imported_at`) и audit (`created_by`, `updated_by`) зафиксированы;
- integrity flags (`missing_from_latest_import`) доступны в API.

Phase B создаёт **механизм обмена** кадровыми данными между экземплярами Corpsite **без потери** provenance, audit и overrides.

**Scope Stage 0:** архитектурный дизайн и план.

**Scope Phase B (реализация):** export/import zip-пакета, валидация, dry-run preview (B.4). Полный Conflict Engine — Phase C.

**B.1 ✅ (2026-06-17):** `app/services/sync/` — package schema, writer, validator; `tests/test_adr038_phase_b1_sync_package_format.py`.

**B.2 ✅ (2026-06-17):** `app/services/sync/export_service.py`, `scripts/sync/export_hr_sync_package.py`; `tests/test_adr038_phase_b2_export_engine.py`.

**B.3 ✅ (2026-06-17):** `app/services/sync/import_service.py`, `scripts/sync/import_hr_sync_package.py`; `tests/test_adr038_phase_b3_import_engine.py`.

**B.4 ✅ (2026-06-17):** `app/services/sync/preview_service.py`, `scripts/sync/preview_hr_sync_package.py`; `tests/test_adr038_phase_b4_preview_engine.py`.

**C.1 ✅ (2026-06-17):** `app/services/sync/conflict_policy.py`; apply gate в import; [ADR-038-C.1](ADR-038-C-conflict-policy.md).

**D.1 ✅ (2026-06-17):** read-only Sync Admin UI `/admin/sync`; API `GET/POST /directory/personnel/sync/*`; [ADR-038-D.1](ADR-038-D-sync-admin-ui.md).

---

## 1. Имя и структура пакета

### Имя файла

```
corpsite_sync_{source_instance_id}_{YYYYMMDD_HHMMSS}.zip
```

Пример: `corpsite_sync_vps-pilot_20260617_143022.zip`

Алиас в документации: `sync-package.zip`.

### Структура каталога (v1)

```text
sync-package.zip
│
├── manifest.json              # обязательный — контракт пакета
├── metadata.json              # обязательный — контекст экспорта
├── checksums.json             # обязательный — SHA-256 по файлам
│
├── employees.jsonl            # обязательный — reference для employee_key
├── employee_import_profile_overrides.jsonl   # обязательный — цель Phase B
│
├── department_recoding.jsonl  # опциональный — перекодировка отделений
├── org_units.jsonl            # опциональный — справочник подразделений
│
├── hr_import_batches.jsonl    # опциональный — полный replay staging (Phase B+)
├── hr_import_rows.jsonl       # опциональный
├── hr_import_document_candidates.jsonl   # опциональный (Phase B+)
└── hr_import_ai_extraction_drafts.jsonl # опциональный (Phase B+)
```

**Примечание:** `departments.jsonl` (legacy `departments`) **не включается** в v1 — в Corpsite master для оргструктуры — `org_units` + `department_recoding` (ADR-014, ADR-038).

---

## 2. manifest.json

```json
{
  "package_version": "corpsite-sync-v1",
  "schema_version": "1.0",
  "source_instance_id": "vps-pilot",
  "source_organization": {
    "id": "org-pilot-1",
    "name": "City Hospital Pilot"
  },
  "exported_at": "2026-06-17T00:00:00+00:00",
  "export_scope": "hr_import_overrides",
  "required_files": [
    "checksums.json",
    "employee_import_profile_overrides.jsonl",
    "employees.jsonl",
    "metadata.json"
  ],
  "optional_files": [
    "department_recoding.jsonl",
    "hr_import_batches.jsonl",
    "hr_import_rows.jsonl",
    "org_units.jsonl"
  ],
  "record_counts": {
    "employees.jsonl": 37,
    "employee_import_profile_overrides.jsonl": 12
  },
  "min_reader_version": "1.0",
  "max_reader_version": "1.x"
}
```

`manifest.json` всегда присутствует в zip, но **не входит** в `required_files` (implicit).

### Поля

| Поле | Обязательное | Описание |
|---|---|---|
| `package_version` | да | Идентификатор формата пакета (`corpsite-sync-v1`) |
| `schema_version` | да | Semver схемы записей jsonl (`1.0`) |
| `source_instance_id` | да | Стабильный ID экземпляра (env/config) |
| `source_organization` | да | Объект `{id, name}` — организация-источник |
| `exported_at` | да | ISO 8601 **UTC** timestamp экспорта |
| `export_scope` | да | Набор сущностей (`hr_import_overrides`, …) |
| `required_files` | да | Список обязательных файлов (без `manifest.json`) |
| `optional_files` | да | Список опциональных файлов v1 |
| `record_counts` | да | Количество строк JSONL по имени файла |
| `min_reader_version` | да | Минимальная версия importer |
| `max_reader_version` | да | Верхняя граница совместимости (`1.x`) |

### metadata.json (B.1)

```json
{
  "generated_by": "corpsite",
  "generated_at": "2026-06-17T00:00:00+00:00",
  "environment": "server",
  "notes": null
}
```

| Поле | Обязательное | Описание |
|---|---|---|
| `generated_by` | да | Идентификатор генератора (`corpsite`) |
| `generated_at` | да | ISO 8601 **UTC** timestamp сборки пакета |
| `environment` | да | `server` \| `local` \| `staging` |
| `notes` | нет | Свободный текст или `null` |

**Расширение в B.2 (опциональные поля, не ломают B.1 validator):**

```json
{
  "exported_by_user_login": "admin",
  "exported_by_user_id": 1,
  "corpsite_git_sha": "070e91c",
  "alembic_revision": "l5e6f7a8b9c0",
  "export_mode": "full",
  "filters": {}
}
```

`exported_by_user_id` — **локальный** ID источника; на приёмнике не используется как FK.

---

## 3. Checksum policy

`checksums.json`:

```json
{
  "algorithm": "sha256",
  "files": {
    "manifest.json": "abc…",
    "metadata.json": "def…",
    "employees.jsonl": "…",
    "employee_import_profile_overrides.jsonl": "…"
  }
}
```

**Правила:**
1. SHA-256 от **raw bytes** каждого файла (UTF-8 для json/jsonl).
2. `checksums.json` **не включает** checksum самого себя.
3. Importer: reject пакет при mismatch (fail-closed).
4. Порядок проверки: manifest → checksums → содержимое jsonl.

---

## 4. Version compatibility

| Условие | Поведение importer |
|---|---|
| `schema_version` major > reader major | **Reject** |
| `schema_version` minor > reader minor | **Reject** (или warn + skip unknown fields — только если явно разрешено) |
| `package_version` неизвестен | **Reject** |
| `export_scope` не поддерживается | **Reject** |
| Optional file отсутствует | **OK** |
| Required file отсутствует | **Reject** |
| Unknown file в zip (не в known set) | **Warn** (пакет остаётся valid) |

Reader version задаётся константой в `app/services/sync/package_schema.py` (`READER_VERSION = "1.0"`).

---

## 5. Sync Package v1 — состав сущностей

| Сущность | v1 Export | Позже | Не экспортировать | Комментарий |
|---|---|---|---|---|
| **employees** | ✅ reference | — | — | Минимальный набор для `employee_key` |
| **employee_identities (IIN)** | ✅ embedded in employees | — | — | Business key |
| **employee_import_profile_overrides** | ✅ | — | — | **Primary payload Phase B** |
| **department_recoding** | ⚪ optional | — | — | HR mapping import → org_unit |
| **org_units** | ⚪ optional | — | — | `code` as business key (ADR-014) |
| **departments** (legacy) | ❌ | ❌ | ✅ | Deprecated; use org_units |
| **positions** | ⚪ optional | Phase B+ | — | Weak key (name); reference only |
| **hr_import_batches/rows** | ⚪ optional | Phase B+ | — | Full staging replay |
| **hr_import_document_candidates** | ❌ | Phase B+ | — | Phase C dependency |
| **employee_documents** | ❌ | Phase C+ | — | Operational HR records |
| **training** (as documents) | ❌ | Phase C+ | — | Part of employee_documents |
| **certificates** (as documents) | ❌ | Phase C+ | — | Part of override sections |
| **users** | ❌ | ❌ | ✅ | Auth/PII; ADR-014 never sync |
| **roles** | ❌ | ❌ | ✅ | Preserve prod role_id |
| **permissions** | ❌ | ❌ | ✅ | Environment-specific |

Legend: ✅ mandatory v1 · ⚪ optional v1 · ❌ excluded

---

## 6. Stable Keys — архитектурное заключение

### Принцип

**Surrogate ID (`employee_id`, `unit_id`, `position_id`, `batch_id`, `row_id`) не переносятся между организациями.**

Пакет использует **business keys** + **source metadata** для сопоставления на приёмнике.

### employees.jsonl (reference)

```json
{
  "employee_key": "iin:900101300123",
  "source_employee_id": 44,
  "full_name": "Иванов Иван Иванович",
  "iin": "900101300123",
  "org_unit_key": null,
  "position_key": null,
  "status": "active"
}
```

| Поле | Назначение |
|---|---|
| `employee_key` | **Primary sync key** — см. ниже |
| `source_employee_id` | Debug/provenance only; **ignored on import** |

**Формат `employee_key`:**

| Приоритет | Формат | Условие |
|---|---|---|
| 1 | `iin:{12digits}` | Valid IIN in `employee_identities` |
| 2 | `name:{normalized}` | No IIN; normalized full_name (lower, ё→е) |
| — | — | Ambiguous name on target → **skip override**, log conflict |

### org_units / departments

| Сущность | Business key | Surrogate | Import match |
|---|---|---|---|
| `org_units` | `code` (UNIQUE) | `unit_id` | Upsert by `code`; **preserve target unit_id** (ADR-014) |
| `department_recoding` | `import_department_name` (normalized) | `id` | Upsert by normalized import name |
| `departments` (legacy) | — | — | **Not synced** |
| `positions` | `name` (normalized) | `position_id` | Weak; match or create (Phase B+ only) |

### employee_import_profile_overrides

Foreign keys в пакете **только через `employee_key`**, не `employee_id`.

Provenance batch/row IDs источника — **metadata**, не FK на приёмнике.

---

## 7. employee_import_profile_overrides.jsonl — финальная схема

```json
{
  "employee_key": "iin:900101300123",
  "profile_override": {
    "notes": "уточнение HR",
    "certificates": [{"kind": "Сертификат", "topic": "…", "date": "2021-01-01"}]
  },
  "profile_status": "active",
  "profile_review_status": "pending",

  "created_at": "2026-06-01T10:00:00+00:00",
  "updated_at": "2026-06-15T12:30:00+00:00",
  "created_by_login": "hr.admin",
  "updated_by_login": "hr.admin",

  "base_imported_at": "2026-06-01T09:55:00+00:00",
  "base_source_file": "control_list_june_2026.xlsx",
  "base_source_batch_id": 293,
  "base_source_row_id": 1201,

  "source_employee_id": 44,
  "source_updated_by_user_id": 3
}
```

### Решения по полям

| Поле | Экспорт | Import use | Обоснование |
|---|---|---|---|
| `employee_key` | ✅ required | Resolve → target `employee_id` | Stable cross-instance key |
| `profile_override` | ✅ | Upsert body | Core payload |
| `profile_status` | ✅ | Upsert | |
| `profile_review_status` | ✅ | Upsert | |
| `created_at` / `updated_at` | ✅ | Preserve if newer-wins (Phase C); B.3: source wins on first import | Audit timeline |
| `created_by_login` | ✅ | Display only | Users not synced; login for human audit |
| `updated_by_login` | ✅ | Display only | Same |
| `created_by` / `updated_by` (numeric) | ⚪ optional `source_*` | **Not** as FK | IDs local to source |
| `base_imported_at` | ✅ | Store as-is | Meaningful cross-instance |
| `base_source_file` | ✅ | Store as-is | Provenance for Conflict Engine |
| `base_source_batch_id` | ✅ as `base_source_*` | Store as metadata | **Not** remapped to target batch_id in B.3 |
| `base_source_row_id` | ✅ as `base_source_*` | Store as metadata | Same |
| Target `base_batch_id/row_id` | ❌ not in export | Recomputed on target at next save | Phase A.1 semantics |

**Phase B.3 import:** записать provenance metadata; `base_batch_id`/`base_row_id` на target остаются NULL до первого save Карты2 на приёмнике.

---

## 8. Конфликты синхронизации (основа Phase C)

Merge-модель Phase A: **section-level replace** (см. ADR-038). Conflict Engine Phase C опирается на `updated_at` + section scope.

### Сценарий A — источник изменил, приёмник не менял

| | |
|---|---|
| **Detect** | Target override absent OR target.updated_at < source.updated_at |
| **Phase B.3** | **Source wins** (replace) |
| **Phase C** | Auto-apply + audit log |

### Сценарий B — обе стороны меняли одну секцию

| | |
|---|---|
| **Detect** | Both have override; same section keys touched; both updated_at after last sync |
| **Phase B.3** | **Skip** + report in preview (no silent merge) |
| **Phase C** | REVIEW_REQUIRED; UI pick source/target/merge |

Example: both changed `certificates` → conflict; **newer-wins не применяется** по умолчанию (HR data).

### Сценарий C — источник: certificates; приёмник: training

| | |
|---|---|
| **Detect** | Disjoint section keys in profile_override |
| **Phase B.3** | **Merge keys** (union of sections); per-section replace |
| **Phase C** | Auto-merge if no key overlap |

### Сценарий D — сотрудник удалён, override остался

| | |
|---|---|
| **Export** | Override exported with `employee_key`; employee may be inactive/missing |
| **Import** | If `employee_key` not resolved → **orphan queue** (skip apply, report) |
| **Phase C** | Orphan override UI (ADR-038-A1 Вариант A) |

### Conflict record (Phase C preview model)

```json
{
  "employee_key": "iin:…",
  "conflict_type": "SECTION_OVERLAP",
  "sections": ["certificates"],
  "source_updated_at": "…",
  "target_updated_at": "…",
  "resolution": "REVIEW_REQUIRED"
}
```

---

## 9. Roadmap Phase B

### B.1 — Package Format ✅

| | |
|---|---|
| **Объём** | JSON schemas; zip builder/validator; constants (`schema_version`, `package_version`); unit tests fixtures |
| **Зависимости** | Phase A.1 schema |
| **Риски** | Schema drift vs ADR-038 original file list |
| **Done when** | Valid/invalid sample packages pass validator; documented in ADR |
| **Реализация** | `app/services/sync/package_schema.py`, `package_writer.py`, `package_validator.py`; `tests/test_adr038_phase_b1_sync_package_format.py` (8 tests) |

### B.2 — Export Engine ✅

| | |
|---|---|
| **Объём** | `scripts/sync/export_hr_sync_package.py` (or `app/services/sync/export_service.py`); CLI; writes zip |
| **Зависимости** | B.1 |
| **Риски** | PII in zip — ops rules (no GitHub, encrypted transfer) |
| **Done when** | Export from DB → zip; checksums verify; record_counts match |
| **Реализация** | `export_hr_sync_package()`; metadata B.2 fields (`alembic_revision`, `exported_by_user_login`); 10 tests |

### B.3 — Import Engine ✅

| | |
|---|---|
| **Объём** | Import CLI; checksum verify; employee_key resolve; upsert overrides; skip orphans/ambiguous |
| **Зависимости** | B.1, B.2 |
| **Риски** | Wrong employee_key match; partial apply |
| **Done when** | Dry-run + `--apply`; overrides on target match source; provenance metadata stored |
| **Реализация** | `import_hr_sync_package()`; `resolve_employee_key()`; provenance в `_sync_provenance`; 10 tests |

### B.4 — Preview Engine ✅

| | |
|---|---|
| **Объём** | Read-only diff: new/update/skip/conflict/orphan counts; JSON report; no DB writes |
| **Зависимости** | B.1, B.3 (`resolve_employee_key`, package parsing) |
| **Риски** | Duplication with Phase C — keep preview minimal |
| **Done when** | `preview_hr_sync_package()` prints actionable report; section diff included |
| **Реализация** | `preview_hr_sync_package()`; `SyncPreviewItem` / `SyncPreviewResult`; CLI `--json`; 10 tests |

#### Classification model (B.4)

| status | action | Условие |
|---|---|---|
| `orphan` | `skip` | `employee_key` не найден на target |
| `ambiguous` | `skip` | `employee_key` → 2+ `employee_id` |
| `new` | `insert` | сотрудник найден, override на target отсутствует |
| `identical` | `skip` | `profile_override` полностью совпадает |
| `update` | `update` | override отличается; target не новее incoming |
| `conflict` | `review_required` | override отличается; `target.updated_at > incoming.updated_at` |

#### Conflict heuristic (B.4)

Минимальное правило до Phase C:

```text
if target.updated_at > incoming.updated_at and profile_override differs:
    status = conflict
    action = review_required
```

#### Section diff

Editable sections: `education`, `training`, `categories`, `certificates`, `degree`, `awards`, `notes`.

Сравнение JSON — stable (`sort_keys=True`); section отсутствует с одной стороны → `changed`.

#### Read-only guarantee

`preview_hr_sync_package()` не выполняет INSERT/UPDATE/DELETE.

#### Limitations (B.4)

- Нет UI, approval workflow, auto-apply после preview
- ~~`conflict` не блокирует B.3 `--apply`~~ → исправлено в [C.1](ADR-038-C-conflict-policy.md) (apply gate)
- `_sync_provenance` на target исключается из сравнения `profile_override`

**Explicitly out of Phase B:** UI, scheduled jobs, bidirectional sync, full Conflict Engine UI (Phase C).

---

## 10. Связь с ADR-014

| ADR-014 rule | Phase B alignment |
|---|---|
| Employees delta only | v1: overrides only touch existing employees; no employee create in B.3 |
| Preserve prod unit_id | org_units matched by `code` |
| Never sync users/auth | audit via `*_login` strings only |
| Dry-run mandatory | B.4 preview + B.3 `--dry-run` default |

---

## 11. Готовность к реализации

- **B.1 ✅** — package format, writer, validator, tests.
- **B.2 ✅** — DB export engine, CLI, post-export validation.
- **B.3 ✅** — import engine, dry-run/apply, employee_key resolver, orphan/ambiguous skip.
- **B.4 ✅** — preview/diff engine, section classification, read-only guarantee.
- **C.1 ✅** — conflict policy, apply gate, section merge on import.
- **D.1 ✅** — read-only Sync Admin UI (export, upload, preview); см. [ADR-038-D.1](ADR-038-D-sync-admin-ui.md).
- **Следующий шаг: Phase D.2** — Apply UI с apply gate; затем **C.2** — conflict resolution workflow, audit log.

---

## Ссылки

- [ADR-038](ADR-038-data-sync-and-hr-import-persistence.md)
- [ADR-038-A1](ADR-038-A1-import-integrity-hardening.md)
- [ADR-014](ADR-014-data-sync-policy.md)
- [ADR-038 employee identity](ADR-038-employee-identity-hr-import-architecture.md)
