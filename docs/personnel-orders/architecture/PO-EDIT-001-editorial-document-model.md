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
| R6 | Legacy `localized_texts` | **Keep**; backward-compatible fallback; **do not** extend with new duties; document mapping → deprecation path. |
| R7 | Locales | Store editorial for `kk` + `ru`. `kk-ru` = render-time composition. Before READY: valid **effective** blocks for both locales (generated may be effective). Stale/failed required locale **blocks READY** or must be fixed. |

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

### 5.4 Leave / multi-period (R5)

Annual leave with multiple periods is **out of scope** for generic editorial persistence.

- Roadmap: **WP-PO-LEAVE-001 — Annual Leave Structured Item Model** (structured periods/days/payments as SoT).
- Until then: HR may use **item body override** to correct leave wording temporarily.
- Override **must not** be treated as structured leave SoT for apply/events.

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

## 8. Language strategy (R7)

| Mode | Storage | Render |
|---|---|---|
| `ru` | editorial rows `locale=ru` | ru effective texts |
| `kk` | editorial rows `locale=kk` | kk effective texts |
| `kk-ru` | **не** отдельная редакция | композиция kk + ru (как сейчас в print) |

**Before READY_FOR_SIGNATURE:**

- Valid **effective** blocks must exist for **both** `kk` and `ru` (required set: at least title + preamble + each active item body; basis per product rules).
- Manual edit of both languages is **not** required: `generated` may be the effective text.
- If a required locale is **missing**, **stale** (with unresolved override policy), or **failed** generation → **block READY** until fixed.

**kk authoritative** (WP-PO-002): UI shows both; official sense prefers kk when policies conflict.

Редактирование всегда **по locale**; preview `kk-ru` только читает оба effective.

---

## 9. Lifecycle — editability (R1, R2)

### Target policy (ratified)

| Status | Structured edit | Editorial edit |
|---|---|---|
| `DRAFT` | Yes | Yes |
| `READY_FOR_SIGNATURE` | **No** (read-only) | **No** (read-only) |
| `SIGNED` | No | No |
| `REGISTERED` | No | No |
| `VOIDED` | No | No |

Corrections while READY: only via **return-to-DRAFT**, then edit in DRAFT, then READY again.

### Compatibility note vs current MVP code

Today `_ensure_order_editable` still allows DRAFT **and** READY. That is **legacy MVP behavior**, not the target policy.

- EDIT-002 editorial write APIs: enforce **DRAFT only**.
- EDIT-002 structured write path: prefer aligning to DRAFT-only when touching editorial-related gates; full structured lock on READY may land with EDIT-005 together with return-to-DRAFT (avoid silent half-migration — document in EDIT-002 if structured READY edit remains temporarily).
- **return-to-DRAFT** endpoint: **EDIT-005** (not EDIT-002), but schema/API must not preclude it (no irreversible READY-only editorial columns).

Early UI editor (EDIT-003): **DRAFT only**.

PO-004 conceptual lifecycle is **not** silently rewritten; MVP enum remains `DRAFT…VOIDED`.

---

## 10. Stale-data handling

Когда меняются structured data после ручной правки:

```text
on structured change (item/header facts used by fingerprint):
  recompute fingerprint
  if override exists AND fingerprint != stored:
    mark block STALE
    do NOT auto-wipe override
  else:
    regenerate generated_* only
```

**Команды UI:**

| Command | Behavior |
|---|---|
| Сохранить правку | set `override`, clear stale or keep until regen |
| Вернуть автоматически сформированный | `override = null`; show `generated` |
| Перегенерировать | rewrite `generated_*` from templates+facts; **ask** if override exists: keep override / replace / cancel |
| Перегенерировать только блок | same, scoped to title/preamble/item body/basis |

Default: **не** молча затирать ручной текст.

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
PATCH  /personnel-orders/{id}/editorial/...          # DRAFT only
POST   /personnel-orders/{id}/editorial/.../regenerate
# item-level equivalents

# READY gate: validate kk+ru effective blocks; reject if stale/missing
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

## 16. Migration / backward compatibility

1. Existing orders: no editorial rows → print uses current generators (+ optional localized_texts title/preamble fallback).
2. First generate: create kk+ru snapshots; import legacy localized title/preamble per R6 mapping.
3. Do not extend `personnel_order_localized_texts` schema for editorial duties.
4. `body_text`: not item SoT.
5. ViewModel: prefer editorial effective; fallback chain as in §5.4/R6.
6. Leave multi-period: no new structured leave tables in EDIT-002 (WP-PO-LEAVE-001).

---

## 17. Open questions (remaining)

Ratified items removed from this list (see §0).

Still open / deferred detail (not blockers for EDIT-002 start):

1. Exact **required block set** for READY gate (minimum: title + preamble + each active item body; is item basis mandatory for all types?).
2. On regenerate with existing override: default UX = keep override / ask / replace? (architecture allows ask; product default TBD in EDIT-003).
3. Whether EDIT-002 also locks **structured** READY writes immediately, or only editorial writes until EDIT-005.
4. Deprecation calendar for `personnel_order_localized_texts` write API (after EDIT-003?).
5. Scope details of **WP-PO-LEAVE-001** (payload shape for periods/days/payments).

---

## 18. Phased implementation plan

| WP | Scope |
|---|---|
| **WP-PO-EDIT-001** | Architecture + ratification + non-prod spike (**done**) |
| **WP-PO-EDIT-002** | Persistence + generate API + ViewModel fallback wiring + READY locale gate (no return-to-draft; no editor UI; no DB clause admin) — see §18.1 |
| **WP-PO-EDIT-003** | Block editor UI (DRAFT only); stale/regenerate/restore |
| **WP-PO-EDIT-004** | Versioned DB clause/template library + legal review |
| **WP-PO-EDIT-005** | return-to-DRAFT; align structured READY lock; audit polish; optional FIO forms |
| **WP-PO-LEAVE-001** | Annual Leave Structured Item Model (separate) |
| Later | Immutable print snapshot (PO-PDF phase 2) |

### 18.1 Exact scope — WP-PO-EDIT-002

**In:**

- Alembic: editorial order/item tables + optional item basis facts; columns include `generator_version`, fingerprints, generated/override pairs.
- Server generators (shared module) producing kk/ru snapshots; stamp `generator_version`.
- API: generate / get / patch override / regenerate — **DRAFT only**.
- READY transition validation: both locales have valid effective required blocks; reject stale/missing.
- Print ViewModel: consume editorial effective when present; legacy fallback otherwise.
- Mapping from existing `localized_texts` on first generate.
- Tests: migration, API auth/status gates, ViewModel effective/fallback, READY gate, basis generate.

**Out:**

- return-to-DRAFT command (EDIT-005).
- Block editor UI (EDIT-003).
- DB clause admin library (EDIT-004).
- Employee FIO morphological profile fields (EDIT-005+).
- Leave multi-period structured model (LEAVE-001).
- Dropping `personnel_order_localized_texts`.

### 18.2 Recommended EDIT-002 test matrix

| Layer | Cases |
|---|---|
| Migration | tables/constraints/uniques; upgrade/downgrade smoke |
| API | 401/403; DRAFT ok; READY/SIGNED reject writes; generate creates kk+ru; patch override; clear override; regenerate |
| READY gate | missing locale → 422; stale required block → 422; both effective ok → allow |
| ViewModel | editorial override wins; generated used when no override; no editorial → legacy/generator fallback; HTML/PDF still share ViewModel |
| Basis | PERSONAL_APPLICATION ru/kk; nominative fallback; free_text OTHER |
| Compat | return-to-draft not present but READY remains read-only for editorial writes |

---

## 19. Risks

| Risk | Mitigation |
|---|---|
| Manual text diverges from apply payload | UI warnings; apply never reads overrides |
| Morphology errors in basis | Manual override; no 100% claim; FIO forms deferred |
| Dual storage (`localized_texts` + editorial) | Fallback + mapping; no new duties on legacy table |
| READY still editable in old structured code | Target policy R1; editorial DRAFT-only in EDIT-002; full lock in EDIT-005 |
| Template legal drift | generator_version now; DB library EDIT-004 |
| HTML injection | Plain text only + escape |
| Leave text via override mistaken for SoT | Document R5; LEAVE-001 |

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
