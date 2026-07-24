# PIF-003 — Dynamic Form Model

## Status

**Target architecture (partially adopted)** — architecture initiated 2026-07-08.

This document describes the **target** metadata-driven FormDefinition model. **Production** implements a **static React wizard** driven by `INTAKE_STEPS` in `corpsite-ui` — not a FormDefinition interpreter.

| Field | Value |
|-------|-------|
| Parent | [PIF-001](./PIF-001-personnel-intake-framework.md) |
| Consumer | [PIF-002 — Electronic Personal Sheet](./PIF-002-electronic-personal-sheet.md) |
| Canonical domains | [PIF-001 §3.2](./PIF-001-personnel-intake-framework.md) |
| Production form | Static React components + `INTAKE_STEPS` (9 steps) |
| Target form engine | Declarative FormDefinition (this document) — **not yet implemented** |

### Current production vs target

| Aspect | Target (PIF-003) | Production (2026-07-24) |
|--------|------------------|-------------------------|
| Form structure | Versioned FormDefinition metadata | Hardcoded `INTAKE_STEPS` + React section components |
| Validation | Shared rule catalog from metadata | Per-section TS validation + backend date checks |
| Dictionaries | Dictionary refs in FormDefinition | TS dictionaries (`intakePersonalDictionary`, military, …) |
| HR review renderer | Same FormDefinition + extensions | Same static editor as candidate (mode flags) |
| PDF field map | FormDefinition.canonical_path → template | Dedicated PDF view model (`intakePdfViewModel`) |

**Migration path:** extract stable `canonical_path` and validation rules from production into FormDefinition v1 (PIF-2 deliverable) without blocking current pilot.

---

## 1. Problem

Жёстко запрограммированная форма «Личного листка» создаёт (и **создаёт сегодня в production**, пока FormDefinition не внедрён):

- дублирование логики между intake, HR review, PDF export;
- невозможность адаптировать разделы без деплоя frontend;
- расхождение validation rules между UI и commit;
- сложность двуязычности (RU/KZ) при каждом новом поле.

**Решение:** metadata-driven form model — единый источник структуры формы, из которого генерируются candidate UI, HR review UI и validation schema.

---

## 2. Conceptual pipeline

```text
Section
  ↓
Field
  ↓
Validation
  ↓
Dictionary
  ↓
Visibility Rule
  ↓
Localization
  ↓
Generated Form
```

Каждый уровень — декларативный артеfact. Runtime **интерпретирует** metadata и рендерит форму.

---

## 3. Layer definitions

### 3.1. Section

**Section** — логическая группа полей, соответствующая EPS section (S1–S12) или каноническому домену.

| Property | Description |
|----------|-------------|
| `section_code` | Stable identifier (e.g. `identity`, `education`, `employment_history`) |
| `domain_code` | Link to canonical domain D1–D15 |
| `order` | Display sequence |
| `cardinality` | `single` (one block) or `repeatable` (table rows, e.g. education entries) |
| `intake_modes` | Which intake programs include this section (`new_hire`, `rehire`, …) |
| `required_policy` | `always` / `configurable` / `never` |

```text
Section: education
  domain: D6
  cardinality: repeatable
  min_rows: 1
  max_rows: 10
```

### 3.2. Field

**Field** — atomic data element within a section.

| Property | Description |
|----------|-------------|
| `field_code` | Stable key mapped to canonical attribute |
| `data_type` | `string`, `date`, `iin`, `phone`, `email`, `file`, `enum`, `text`, `year`, … |
| `canonical_path` | Target path in draft/canonical model (e.g. `education[].institution_name`) |
| `widget_hint` | Rendering hint: `text`, `textarea`, `select`, `date_picker`, `file_upload`, `table_cell` |
| `required` | Boolean or rule reference |
| `default_value` | Optional |
| `read_only_after_submit` | Candidate cannot edit after submit unless revision |

**Field ≠ column in paper form.** Field maps to **canonical attribute**, not to «графа 8 строка 3».

### 3.3. Validation

**Validation** — declarative rules attached to field, section, or form.

| Rule type | Example |
|-----------|---------|
| `required` | Field must have value on submit |
| `format` | IIN checksum, phone pattern, email RFC |
| `range` | `birth_date` not in future; `graduation_year` ≥ 1950 |
| `cross_field` | `end_date` ≥ `start_date` |
| `cross_section` | If `citizenship != KZ` then `residence_permit` required |
| `dictionary` | Value must exist in reference dictionary |
| `file` | Max size, mime whitelist |

Validation runs at:

1. **Field blur** (soft, UX);
2. **Section save** (draft);
3. **Submit** (hard gate);
4. **HR Review** (re-validate before commit);
5. **Commit** (server-side authoritative).

**Single rule catalog** — same definitions drive client hints and server enforcement.

### 3.4. Dictionary

**Dictionary** — reference data for enums and autocomplete.

| Property | Description |
|----------|-------------|
| `dictionary_code` | e.g. `country`, `nationality`, `language`, `education_level` |
| `source` | `static`, `db_table`, `external_api` |
| `localized_labels` | RU + KZ labels per entry |
| `version` | For cache invalidation |

Examples:

- `sex`: static (`M`, `F`)
- `country`: ISO 3166 with KZ/RU labels
- `institution`: optional autocomplete (future)

Dictionaries decouple form from hardcoded `<select>` options.

### 3.5. Visibility Rule

**Visibility Rule** — conditional show/hide/require of fields or sections.

| Condition type | Example |
|----------------|---------|
| `field_equals` | Show `previous_names` if `name_changed == true` |
| `field_not_empty` | Show `diploma_number` when `education_level >= bachelor` |
| `intake_mode` | Hide `family` section for `intern` mode |
| `locale` | Show KZ-specific fields |
| `hr_only` | Field visible only in HR review, not candidate form |

Rules evaluated at render time and at validation time.

```text
IF citizenship != 'KZ'
  THEN show section: residence_permit
  AND require field: permit_number
```

### 3.6. Localization

**Localization** — parallel presentation layer over stable field codes.

| Element | Localized |
|---------|-----------|
| Section title | ✅ |
| Field label | ✅ |
| Placeholder | ✅ |
| Help text | ✅ |
| Validation message template | ✅ |
| Enum display labels | ✅ (via Dictionary) |
| **Stored value** | ❌ (canonical value language-neutral or locale-tagged) |

Structure:

```text
LocalizationBundle (locale: ru | kz)
  section_code + field_code → label, hint, error_template
```

Form generator picks bundle by candidate locale preference.

### 3.7. Generated Form

**Generated Form** — runtime artifact assembled from all layers.

```text
FormDefinition (versioned)
  ├── sections[] (ordered, filtered by intake_mode + visibility)
  │     ├── fields[] (with validation refs, dictionary refs)
  │     └── visibility_rules[]
  ├── validation_catalog[]
  ├── dictionary_refs[]
  └── localization_bundles[]
        ↓ FormRenderer (future)
  Candidate UI | HR Review UI | Validation Engine | PDF field map
```

| Output | Generator input |
|--------|-----------------|
| Candidate form JSON schema | FormDefinition + locale + visibility context |
| HR review diff view | FormDefinition + draft values + canonical labels |
| Server validation plan | FormDefinition (authoritative) |
| PDF field mapping | FormDefinition.canonical_path → template slot |

---

## 4. FormDefinition versioning

| Concept | Policy |
|---------|--------|
| Version | Semantic: `form_def_id` + `version` |
| Case binding | Intake case locked to FormDefinition version at invitation |
| Upgrade | New cases use latest; in-flight cases keep original version |
| Migration | Draft values mapped forward on version bump (explicit migration rules) |

Prevents breaking in-progress intake when form metadata changes.

---

## 5. Architecture diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                  FORM DEFINITION STORE                       │
│  (declarative metadata — not hardcoded React components)     │
├─────────────────────────────────────────────────────────────┤
│  Sections │ Fields │ Validations │ Dictionaries │ Rules     │
│  Localization bundles (RU / KZ)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Form      │  │ Validation │  │  PDF /     │
    │  Renderer  │  │  Engine    │  │  Export    │
    │  (client)  │  │  (server)  │  │  Mapper    │
    └────────────┘  └────────────┘  └────────────┘
           │               │
           └───────┬───────┘
                   ▼
            Intake Draft Values
         (canonical_path keyed)
```

---

## 6. Mapping to canonical data model

Form fields **do not** map 1:1 to DB columns at definition time. Mapping is:

```text
field.canonical_path  →  draft JSON path  →  (at commit)  →  person_* table / section
```

Example:

| field_code | canonical_path | Commit target (PIF-2) |
|------------|----------------|------------------------|
| `iin` | `identity.iin` | `persons.iin` |
| `institution_name` | `education[].institution_name` | `person_education.institution_name` |
| `phone` | `contact.phone` | `contacts.phone` or person contact section |

This indirection allows:

- same canonical field in EPS, HR correction UI, and PDF;
- form restructuring without schema rename.

---

## 7. Intake modes and form profiles

**Form Profile** — subset of FormDefinition for a hire scenario.

| Profile | Sections included |
|---------|-------------------|
| `new_hire_full` | S1–S12 (default pilot) |
| `new_hire_minimal` | S1, S3, S4, S6, S9, S12 |
| `rehire` | S1, S3 (verify), S9 delta |
| `intern` | Reduced S6, no S10 |

Profile selected at Invitation; drives Visibility Rules.

---

## 8. HR Review rendering

Same FormDefinition powers HR view with extensions:

| Extension | Purpose |
|-----------|---------|
| `hr_editable: true` | HR may override candidate value |
| `show_provenance` | Display «entered by candidate» vs «corrected by HR» |
| `show_validation_warnings` | Soft issues HR may accept with comment |
| `section_approval` | Per-section approve flag before commit |

---

## 9. Design principles

| # | Principle |
|---|-----------|
| 1 | **Schema-first, not screen-first** — canonical path before widget |
| 2 | **Server authoritative validation** — client validation is UX only |
| 3 | **Version immutability per case** — no silent form changes mid-intake |
| 4 | **Reuse across surfaces** — one definition, many renderers |
| 5 | **Progressive complexity** — static dictionaries first; external APIs later |

---

## 10. Non-goals

- React component implementation.
- FormDefinition storage format (JSON file vs DB table) — PIF-2.
- Visual form builder UI for HR admins — future.
- WYSIWYG PDF template designer — PIF-7.

---

## 11. Related documents

| Document | Role |
|----------|------|
| [PIF-001](./PIF-001-personnel-intake-framework.md) | Canonical domains |
| [PIF-002](./PIF-002-electronic-personal-sheet.md) | EPS sections and lifecycle |
| [PIF-004](./PIF-004-data-ownership.md) | Who may edit which fields |
| [PIF-roadmap](./PIF-roadmap.md) | PIF-4 implementation sequence |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Target section tables |
