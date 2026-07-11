# PO-EDIT-001 — Personnel Order Editorial Document Model

**Статус:** Architecture Approved for Implementation  
**WP:** WP-PO-EDIT-001 (research + ratification complete; production persistence not started)  
**Связано:** [PO-PRINT-001](./PO-PRINT-001-print-form.md), [PO-PDF-001](./PO-PDF-001-official-pdf-engine.md), [PO-004](./PO-004-personnel-orders-lifecycle.md), [WP-PO-002](../work-packages/WP-PO-002-personnel-orders-architecture-scope-decision.md), [PO-LIFECYCLE-002](../PO-LIFECYCLE-002-delete-and-void-policy.md)

---

## 0. Decision summary / Ratification

**Status: Architecture Approved for Implementation**

Product decisions ratified before WP-PO-EDIT-002 persistence work:

| # | Topic | Decision |
|---|---|---|
| R1 | Lifecycle | `DRAFT` — structured + editorial edit. `READY_FOR_SIGNATURE` / `SIGNED` / `REGISTERED` / `VOIDED` — **read-only**. Fix READY only via **return-to-DRAFT**. Current MVP code allowing READY edits is **not** the target policy. |
| R2 | Return-to-DRAFT | Not required in EDIT-002; schema/API/editorial model must stay **compatible**. Implement in **WP-PO-EDIT-005**. Early UI editor = **DRAFT only**. |
| R3 | FIO morphology | Phase 1: auto proposal + manual override. **No** mandatory genitive/possessive profile fields. No 100% morphology claim. Optional FIO forms → EDIT-005 or separate WP. |
| R4 | Clause library | EDIT-002: generation contract + `generator_version` + generated snapshot + fingerprint. **No** DB admin library yet. **No** new legal wording in React components. Versioned DB library → **EDIT-004**. |
| R5 | Leave | Multi-period annual leave **out** of generic editorial persistence. Roadmap: **WP-PO-LEAVE-001**. Override may temporarily fix wording; does **not** replace structured leave SoT. |
| R6 | Legacy `localized_texts` | **Keep**; backward-compatible fallback; **do not** extend with new duties; staged deprecation (see R11). |
| R7 | Locales | Store editorial for `kk` + `ru`. `kk-ru` = render-time composition. Before READY: valid **effective** blocks for both locales (generated may be effective). Stale/failed required locale **blocks READY** or must be fixed. |
| R8 | READY required blocks | For each of `kk` and `ru`: **title**, **preamble**, and **body of every active item** are required. **Basis** required only when `basis_required=true` for the order/event/item type. Signature and acknowledgement are structured/rendered chrome — **not** in editorial persistence gate. |
| R9 | Regenerate | Updates `generated` snapshot + fingerprint only. Existing **override is kept**; marked **stale / review-required**. Clearing override is a separate confirmed command («Вернуть автоматически сформированный текст»). |
| R10 | Write lock in EDIT-002 | EDIT-002 forbids **both structured and editorial** writes for READY/SIGNED/REGISTERED/VOIDED. **DRAFT** is the only editable status. return-to-DRAFT remains EDIT-005. |
| R11 | localized_texts deprecation | EDIT-002: read fallback/mapping; new writes → editorial layer only. EDIT-003: editor uses new API. Legacy write API deprecated only after production migration verification. Table drop = separate cleanup WP (no fixed date). |
| R12 | WP-PO-LEAVE-001 | Preliminary scope ratified (in/out lists in §5.4 / roadmap). |

Spike remains **non-production**: no persistence, no editorial API, no editor UI wired.

---

## 1. Problem statement

После внедрения многоязычного HTML preview и официального PDF (Playwright) сравнение с реальными кадровыми приказами показало: **полностью детерминированного шаблонного текста недостаточно**.

В реальных приказах есть:

1. **Типовая преамбула** (статьи ТК, коллективный договор, формула «БҰЙЫРАМЫН» / «ПРИКАЗЫВАЮ»).
2. **Индивидуальный текст пунктов** (несколько периодов, дни, доп. дни, итог, даты отпуска, пособие, особенности контракта и т.д.).
3. **Основание по пункту** (личное заявление, служебная записка, представление, медзаключение, протокол и др.), часто с ФИО сотрудника.

Кадровику нужна возможность **отредактировать** сформированный текст до подписания, **не превращая** печатный текст в единственный источник истины для apply/events.

---

## 2. Real-order findings (vs current MVP)

| Реальный документ | Текущий MVP | Разрыв |
|---|---|---|
| Преамбула с нормативными ссылками | `localized_texts.preamble` есть в БД/API, UI нет; print читает если заполнено | Нет генерации типовой преамбулы + редактора |
| Индивидуальные формулировки пунктов | Только frontend templates (`personnelOrderPrintItemText`) | Нет per-item override; нет leave/multi-period |
| Основание на пункт с ФИО | Header `basis_summary` / `legal_basis_article`; item — почти нет | Нет structured basis + generated wording |
| kk + ru параллельно | Print composition `kk-ru`; storage rows `kk`/`ru` | Нет paired editorial UX |
| Ручная правка до подписи | Structured edit DRAFT/READY; тексты view-only | Editorial layer отсутствует |

**Вывод:** renderer-only подход годится для демо и типовых HIRE/TRANSFER, но не для production-качества текста приказа.

---

## 3. Bounded context

```text
┌─────────────────────────────────────────────────────────────┐
│ Structured HR layer (SoT for apply / employee_events)       │
│  PersonnelOrder + Items + payload + employees + periods …   │
└───────────────────────────┬─────────────────────────────────┘
                            │ generate
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Editorial document layer (SoT for print wording)            │
│  title / preamble / item body / item basis / closing        │
│  generated_* + override_* → effective_*                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ project
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Print projection                                            │
│  PersonnelOrderPrintViewModel → shared HTML → PDF           │
└─────────────────────────────────────────────────────────────┘
```

**Инварианты (WP-PO-002):**

- Apply читает **structured payload**, не free-text.
- Print/PDF — **проекция**; один ViewModel для HTML и PDF.
- После apply: void / correcting order, не «тихая» правка текста.

---

## 4. Structured vs editorial — что чем является

| Блок | Источник | Редактируемый? | Язык |
|---|---|---|---|
| Тип приказа, статусы, №, дата | Structured | Да (по lifecycle) | — |
| Сотрудник, должность, подразделение, ставки, даты, периоды, дни | Structured | Да | — |
| Нормативные ссылки (статьи ТК) | Template library (версионируемая) → preamble generated | Override преамбулы | kk/ru |
| Формула «ПРИКАЗЫВАЮ» | Print chrome (словарь) | Нет (системный) | kk/ru |
| Текст пункта | Item template + structured facts → `body_generated` | Да (`body_override`) | kk/ru |
| Основание пункта | Basis model → `basis_generated` | Да (`basis_override`) | kk/ru |
| Заголовок документа | Type title template / localized title | Да | kk/ru |
| Подпись (должность, ФИО) | Header historical fields | Да до lock; не rich-text | обычно одна строка |
| Ознакомление (строки) | Список сотрудников из пунктов | Структура нет; подписи пустые | chrome kk/ru |
| Watermark | Status | Нет | kk/ru |

---

## 5. Domain model (recommended)

### 5.1 Effective text semantics

```text
effective_text = override_text ?? generated_text
is_manually_edited = override_text is not null
is_stale = structured_fingerprint != fingerprint_at_generation
  AND is_manually_edited
```

Не хранить «единственный» `edited_text` без snapshot generated — иначе нельзя «вернуть авто» и детектировать stale.

### 5.2 Recommended storage: block-level tables (per locale)

**Отвергнуто как sole solution:** только `personnel_order_localized_texts.body_text` (order-level blob) — теряется per-item структура, сложно перегенерировать один пункт, HTML/PDF уже item-oriented.

**Отвергнуто:** JSON blob на order без нормализации — слабый audit, сложные partial updates, риск расхождения schema.

**Отвергнуто (на MVP):** полные immutable revisions на каждое нажатие — дорого; достаточно `revision` + audit metadata + optional history later.

**Рекомендация:**

#### A. Order-level editorial (`personnel_order_editorial_blocks`)

| Column | Purpose |
|---|---|
| `order_id`, `locale` (`kk`\|`ru`) | PK scope |
| `title_generated`, `title_override` | Заголовок |
| `preamble_generated`, `preamble_override` | Преамбула |
| `closing_generated`, `closing_override` | Заключительная часть (если нужна) |
| `source_fingerprint` | Hash structured inputs used at last generate |
| `generator_version` | Code/contract version of the generator (EDIT-002; not DB clause admin) |
| `template_set_version` | Nullable until EDIT-004 clause library; reserved for future |
| `generated_at`, `edited_at`, `edited_by` | Metadata |
| `revision` | Monotonic |

Unique `(order_id, locale)`.

#### B. Item-level editorial (`personnel_order_item_editorial_blocks`)

| Column | Purpose |
|---|---|
| `order_item_id`, `locale` | PK scope |
| `body_generated`, `body_override` | Текст пункта |
| `basis_generated`, `basis_override` | Основание пункта |
| `source_fingerprint` | Hash item structured inputs |
| `generator_version` | Same contract as order-level |
| `template_set_version` | Reserved for EDIT-004 |
| `generated_at`, `edited_at`, `edited_by` | |
| `revision` | |

#### C. Structured basis facts (`personnel_order_item_bases` or payload extension)

| Column / field | Purpose |
|---|---|
| `basis_type` | PERSONAL_APPLICATION, MEMO, … |
| `subject_employee_id` | Обычно = item.employee_id |
| `document_date`, `document_number` | Опционально |
| `free_text` | Структурированное доп. поле (не HTML) |
| `attachment_id` | Опциональная ссылка |

Generated wording строится из type + employee name + dates; override хранится в editorial block.

#### D. Compatibility with existing `personnel_order_localized_texts` (R6)

- **Keep** the table; do **not** delete in EDIT-002.
- **Do not** add new editorial responsibilities to it (no per-item body/basis, no fingerprint).
- **Fallback read path** (until editorial rows exist):
  1. If editorial block exists → `effective = override ?? generated`.
  2. Else if `localized_texts.title` / `preamble` present → use as display fallback (treat as override-like for title/preamble only).
  3. Else → live structured generators (current MVP).
- **Mapping on first generate (EDIT-002):** copy non-empty `title`/`preamble` into editorial `*_override` or seed `*_generated` (prefer seed generated + leave override null if text matches generator; if hand-authored unknown, seed as override).
- **`body_text`:** ignore as item SoT; optional later map to `closing_override` only if product confirms.
- **Deprecation path:** after editorial is SoT for print and UI no longer writes localized_texts → mark table read-only → remove write API → drop in a later WP (not EDIT-002).

### 5.3 Alternatives compared

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Fields on order/item only | Simple | Mixes SoT layers; weak per-locale | Reject as primary |
| Order-level JSON document | Flexible | Hard partial regen; weak constraints | Reject for MVP |
| Block tables + fingerprint | Clear effective_text; per-block regen | More tables/API | **Recommend** |
| Immutable revision every save | Strong audit | Heavy; UI complexity | Phase 2+ |

### 5.4 Leave / multi-period (R5, R12)

Annual leave with multiple periods is **out of scope** for generic editorial persistence.

Roadmap: **WP-PO-LEAVE-001 — Annual Leave Structured Item Model**.

**In (preliminary):**

- multiple work periods;
- days per period;
- additional leave days and reason;
- total days;
- actual leave dates;
- leave allowance clause;
- arithmetic validation;
- kk/ru generation;
- structured payload as SoT.

**Out (preliminary):**

- full leave balance engine;
- timesheet integration;
- payroll calculation;
- recalls/transfers;
- compensation workflows.

Until LEAVE-001: HR may use **item body override** to correct leave wording temporarily. Override **must not** be treated as structured leave SoT for apply/events.

---

## 6. Template / Clause Library (R4)

**EDIT-002:** do **not** ship a DB-backed clause admin.

Provide instead:

- **Generation contract** (stable function signatures / block kinds / locales).
- **`generator_version`** string/int stamped on each generated snapshot.
- **Generated snapshot** columns (`*_generated`) + **fingerprint**.
- Generators live in a **server-side / shared lib** module — **not** new legal wording inside React UI components.

**EDIT-004:** versioned DB clause/template library + legal review workflow.

Until EDIT-004, existing `personnelOrderPrintItemText` / locale dictionaries may remain as the interim generator implementation, but new statutory phrases must not be added ad hoc in React presentational components.

Google-перевод ≠ юридический источник.

---

## 7. Basis model

### Types (initial)

- `PERSONAL_APPLICATION`
- `MEMO`
- `MANAGEMENT_SUBMISSION`
- `MEDICAL_CONCLUSION`
- `COMMISSION_PROTOCOL`
- `COURT_ACT`
- `OTHER`

### Generated wording examples

**ru / PERSONAL_APPLICATION:**  
`Основание: личное заявление {{employee_name_genitive}}.`

**kk / PERSONAL_APPLICATION:**  
`Негіз: {{employee_name_possessive}} жеке өтініші.`

### Morphology (ФИО) — R3

Автосклонение **не гарантируется** на 100%.

**Phase 1 / EDIT-002–003:**

1. Auto-generated proposal (nominative FIO fallback when no morphological form).
2. Manual `basis_override` (and body override) — primary correction path.
3. UI hint: «Предложено автоматически — проверьте формулировку».

**Not in phase 1:** mandatory `fio_genitive_ru` / `fio_possessive_kk` on employee profile.

**EDIT-005 or separate WP:** optional FIO forms if product still needs them.

Spike: `personnelOrderBasisGenerate.ts` — templates without false morphology claims.

---

## 8. Language strategy (R7, R8)

| Mode | Storage | Render |
|---|---|---|
| `ru` | editorial rows `locale=ru` | ru effective texts |
| `kk` | editorial rows `locale=kk` | kk effective texts |
| `kk-ru` | **не** отдельная редакция | композиция kk + ru (как сейчас в print) |

### READY required editorial blocks (R8)

For **each** locale `kk` and `ru`, before `READY_FOR_SIGNATURE`:

| Block | Required? |
|---|---|
| `title` | **Yes** (non-empty effective) |
| `preamble` | **Yes** (non-empty effective) |
| each active item `body` | **Yes** (non-empty effective) |
| item `basis` | **Only if** `basis_required=true` for that order type / event type / item type |
| signature | **No** — structured/rendered; not editorial gate |
| acknowledgement | **No** — structured/rendered; not editorial gate |

- Manual edit of both languages is **not** required: `generated` may be the effective text.
- Missing required effective text, failed generation, or **unresolved stale** required block → **block READY**.

**kk authoritative** (WP-PO-002): UI shows both; official sense prefers kk when policies conflict.

Редактирование всегда **по locale**; preview `kk-ru` только читает оба effective.

---

## 9. Lifecycle — editability (R1, R2, R10)

### Target policy (ratified)

| Status | Structured write | Editorial write |
|---|---|---|
| `DRAFT` | Yes | Yes |
| `READY_FOR_SIGNATURE` | **No** | **No** |
| `SIGNED` | No | No |
| `REGISTERED` | No | No |
| `VOIDED` | No | No |

Corrections while READY: only via **return-to-DRAFT** (EDIT-005), then edit in DRAFT, then READY again.

### EDIT-002 enforcement (R10)

- **Both** structured and editorial write APIs must reject READY/SIGNED/REGISTERED/VOIDED (**DRAFT only**).
- This replaces the legacy MVP `_ensure_order_editable` allowance of READY as soon as EDIT-002 lands for those endpoints.
- **return-to-DRAFT** endpoint remains **EDIT-005**; schema must stay compatible (editorial rows survive READY ↔ DRAFT).

Early UI editor (EDIT-003): **DRAFT only**.

PO-004 conceptual lifecycle is **not** silently rewritten; MVP enum remains `DRAFT…VOIDED`.

---

## 10. Stale-data handling & regenerate (R9)

```text
on regenerate (or structured change that triggers regen of generated_*):
  rewrite generated_* from templates + facts
  update source_fingerprint (+ generator_version)
  if override exists:
    KEEP override
    mark block STALE / review-required
  else:
    effective = generated (clean)
```

**Команды:**

| Command | Behavior |
|---|---|
| Сохранить правку | set `override`; clear or set review flags per UX |
| **Перегенерировать** | update `generated` + fingerprint; **do not** delete/replace override; if override present → **stale/review-required** |
| **Вернуть автоматически сформированный текст** | separate command with **confirmation**; clears `override` (`null`); effective becomes `generated` |
| Перегенерировать только блок | same regenerate semantics, scoped |

Default: **never** silently wipe manual text on regenerate.

---

## 11. Security

- Хранить **plain text** (абзацы `\n`), не HTML.
- Renderer: `escapePersonnelOrderPrintHtml` (уже есть) для всех effective texts.
- Запрет script/style; sanitize на API (strip control chars, max length).
- RBAC: те же `personnel_admin` / editable status gates.
- Audit: `order_id`, `item_id`, `locale`, `block_kind`, `action`, `user_id`, `revision` — **без** полного текста, ИИН, cookies.

---

## 12. Print / PDF compatibility

```text
structured + editorial effective
  → buildPersonnelOrderPrintViewModel (extended)
  → buildPersonnelOrderPrintDocumentHtml
  → HTML preview / PDF
```

- Один shared HTML renderer — без дублирования.
- Fallback для старых приказов без editorial rows: текущая генерация из structured (как сейчас).
- Watermark / languages / auth PDF route — без изменений контракта.

---

## 13. API sketch

### EDIT-002 (in scope)

```text
POST   /personnel-orders/{id}/editorial/generate
GET    /personnel-orders/{id}/editorial?locale=kk|ru
PATCH  /personnel-orders/{id}/editorial/...                 # set override; DRAFT only
POST   /personnel-orders/{id}/editorial/.../regenerate      # R9: keep override → stale
POST   /personnel-orders/{id}/editorial/.../restore-generated  # R9: confirm; clear override
# item-level equivalents

# Structured + editorial writes: DRAFT only (R10)
# READY gate: R8 required blocks for kk+ru; reject missing/unresolved stale
```

### EDIT-005 (reserved; keep compatible)

```text
POST   /personnel-orders/{id}/return-to-draft
```

Do not implement return-to-draft in EDIT-002; do not design editorial schema that assumes READY is editable.

---

## 14. UI sketch (block editor, not Word)

Early phases (EDIT-003): editor available **only for DRAFT**. READY/SIGNED/… — view + print/PDF only.

```text
Приказ #125-К                    [ru] [kk]   [Preview] [PDF]
────────────────────────────────────────────────────────────
Заголовок          [изменён вручную]  [Вернуть авто] [Перегенерировать]
…
```

- Plain multiline editor; **без** WYSIWYG на этапе 1.
- Индикаторы: вручную / stale.
- Preview ru/kk/kk-ru через существующие routes.

---

## 15. Audit model (MVP)

Log events: `editorial.generate`, `editorial.override_set`, `editorial.override_clear`, `editorial.regenerate`, `editorial.stale_detected`.

Fields: ids, locale, block_kind, result, duration — **не** body text.

---

## 16. Migration / backward compatibility (R6, R11)

1. Existing orders: no editorial rows → print uses current generators (+ optional localized_texts title/preamble fallback).
2. First generate: create kk+ru snapshots; import legacy localized title/preamble per §5.2 D.
3. Do not extend `personnel_order_localized_texts` schema for editorial duties.
4. **New editorial writes** go only to the new editorial layer (EDIT-002+).
5. **EDIT-003:** editor UI uses the new editorial API only.
6. **Legacy write API** (`PUT …/localized-texts/{locale}`): deprecate only **after** production migration verification (not automatic in EDIT-002).
7. **Table drop:** separate cleanup WP; **no fixed date** in this ratification.
8. `body_text`: not item SoT.
9. Leave multi-period: no new structured leave tables in EDIT-002 (WP-PO-LEAVE-001).

---

## 17. Open questions (remaining technical details)

Product decisions R1–R12 are closed. Remaining items are implementation details for EDIT-002 (not architecture blockers):

1. **Catalog of `basis_required`:** which `order_type_code` / `item_type_code` combinations set `basis_required=true` (initial matrix in EDIT-002 code/config).
2. **Stale representation:** boolean column vs `review_status` enum (`OK` / `STALE` / `REVIEW_REQUIRED`) on editorial cells.
3. **Fingerprint algorithm:** exact canonical serialization of structured inputs (field order, null handling).
4. **Item basis storage:** dedicated `personnel_order_item_bases` table vs JSONB on item payload for EDIT-002 MVP.

---

## 18. Phased implementation plan

| WP | Scope |
|---|---|
| **WP-PO-EDIT-001** | Architecture + ratification + non-prod spike (**done**) |
| **WP-PO-EDIT-002** | Persistence; generate/regenerate/restore-generated APIs; **DRAFT-only structured+editorial writes**; READY required-block gate; ViewModel fallback — see §18.1 |
| **WP-PO-EDIT-003** | Block editor UI (DRAFT only); stale/review UX |
| **WP-PO-EDIT-004** | Versioned DB clause/template library + legal review |
| **WP-PO-EDIT-005** | return-to-DRAFT; audit polish; optional FIO forms |
| **WP-PO-LEAVE-001** | Annual Leave Structured Item Model (R12 in/out) |
| Later | localized_texts cleanup WP; immutable print snapshot (PO-PDF phase 2) |

### 18.1 Exact scope — WP-PO-EDIT-002

**In:**

- Alembic: editorial order/item tables (+ optional item bases); `generator_version`, fingerprints, generated/override; stale/review flag support.
- Server generators (shared module) for kk/ru; stamp `generator_version`.
- API: generate / get / patch override / regenerate / clear-override (restore generated) — **DRAFT only**.
- **Structured write lock:** READY/SIGNED/REGISTERED/VOIDED reject mutations (align `_ensure_order_editable` to DRAFT-only).
- READY gate: R8 required blocks for kk+ru; reject missing/unresolved stale.
- Print ViewModel: editorial effective when present; legacy fallback otherwise.
- Mapping from existing `localized_texts` on first generate (read-only legacy thereafter for new writes).
- Tests: migration, API auth/status gates (structured+editorial), ViewModel, READY gate, regenerate-keeps-override, restore-clears-override, basis generate.

**Out:**

- return-to-DRAFT command (EDIT-005).
- Block editor UI (EDIT-003).
- DB clause admin library (EDIT-004).
- Employee FIO morphological profile fields (EDIT-005+).
- Leave multi-period structured model (LEAVE-001).
- Deprecating/dropping `personnel_order_localized_texts` write API/table (post-verification cleanup WP).

### 18.2 Recommended EDIT-002 test matrix

| Layer | Cases |
|---|---|
| Migration | tables/constraints/uniques; upgrade/downgrade smoke |
| API writes | 401/403; DRAFT ok; READY/SIGNED/REGISTERED/VOIDED reject **structured and editorial** writes |
| Generate / regenerate | creates kk+ru; regenerate updates generated+fingerprint; override preserved + stale |
| Restore generated | confirmed clear override; effective = generated |
| READY gate | missing title/preamble/item body → 422; basis missing only if `basis_required`; unresolved stale → 422; clean effective → allow |
| ViewModel | override wins; generated when no override; no editorial → legacy/generator fallback; HTML/PDF share ViewModel |
| Basis | PERSONAL_APPLICATION ru/kk; nominative fallback; free_text OTHER |

---

## 19. Risks

| Risk | Mitigation |
|---|---|
| Manual text diverges from apply payload | UI warnings; apply never reads overrides |
| Morphology errors in basis | Manual override; no 100% claim; FIO forms deferred |
| Dual storage (`localized_texts` + editorial) | Fallback + mapping; no new duties on legacy table |
| READY still editable in old structured code | **R10:** EDIT-002 locks structured+editorial to DRAFT only |
| Template legal drift | generator_version now; DB library EDIT-004 |
| HTML injection | Plain text only + escape |
| Leave text via override mistaken for SoT | Document R5/R12; LEAVE-001 |
| Regenerate wiping manual text | **R9:** keep override; mark stale; separate restore command |
---

## 20. Spike artifacts (non-production)

| Path | Role |
|---|---|
| `corpsite-ui/.../personnelOrderEditorialTypes.ts` | DTO / effective_text types |
| `corpsite-ui/.../personnelOrderBasisGenerate.ts` | Basis wording generator |
| `corpsite-ui/.../personnelOrderBasisGenerate.test.ts` | Unit tests |
| `docs/.../PO-EDIT-001-editorial-document-model.md` | This document |
| `docs/.../PO-EDIT-001-migration-draft.sql.md` | Draft SQL only |

**Confirmed non-production:** no alembic applied; no editorial routes; no editor UI; spike not imported by print/PDF/drawer production paths.
