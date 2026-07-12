# PO-EDIT-004 — Complete Bilingual Editorial Model

**Status:** Implemented (UI layer; reuses EDIT-002 persistence/API)  
**Term:** **Kazakh-first** — user starts with Kazakh text; Russian is available via locale tabs. Both locales are persisted.

---

## Phase 1 — Architecture review (existing)

### Editorial entities

| Entity | Table / type | Scope |
|---|---|---|
| Order editorial block | `personnel_order_editorial_blocks` | `title`, `preamble`, `closing` × `kk`/`ru` |
| Item editorial block | `personnel_order_item_editorial_blocks` | `body`, `basis` × `kk`/`ru` |
| Item basis facts | `personnel_order_item_bases` | locale-agnostic structured facts |
| API read model | `EditorialStateResponse` | grouped order + item blocks |
| Block projection | `EditorialBlockOut` | `generated_text`, `override_text`, `effective_text`, `revision`, `review_status` |

Unique keys: `(order_id, locale, block_type)` and `(order_item_id, locale, block_type)`.

### Persistence model (no schema change)

Each row is one locale × block type:

- **kk generated** → `generated_text` where `locale='kk'`
- **kk edited** → `override_text` where `locale='kk'`
- **ru generated** → `generated_text` where `locale='ru'`
- **ru edited** → `override_text` where `locale='ru'`

`effective_text = trim(override) || trim(generated)` (mapper + API).

### API contracts (unchanged)

| Method | Endpoint |
|---|---|
| GET | `/directory/personnel-orders/{id}/editorial` |
| POST | `/directory/personnel-orders/{id}/editorial/generate` |
| PATCH | `/directory/personnel-orders/{id}/editorial/blocks/{block_id}` |
| POST | `/directory/personnel-orders/{id}/editorial/blocks/{block_id}/reset-to-generated` |

Generate without scope creates/updates **both** `kk` and `ru`. Patch/reset target `block_id` (locale-agnostic).

### React state model

- `PersonnelOrderEditorialTextEditor` holds full `EditorialStateResponse`
- `activeLocale`: `kk` | `ru` (default `kk`, Kazakh-first)
- `buildEditorialDocumentSections(state, items, locale)` filters blocks for active tab
- `BlockEditor` is locale-agnostic (works on any block row)

### effective_text pipeline

1. Backend `mapper.effective_text(override, generated)`
2. Serialized on every `EditorialBlockOut`
3. UI `displayPersonnelOrderEditorialBlockText` mirrors priority for editing
4. Print `pickEffectiveByLocale` reads `effective_text` per kk/ru for HTML/PDF

### PrintViewModel mapping

`personnelOrderPrintViewModel.ts` → editorial `effective_text` for title, preamble, item body/basis; fallback to legacy localized texts and deterministic templates.

---

## Phase 2 — Bilingual model decision

**Decision: reuse existing block-row schema; no DB migration.**

The current schema already implements the conceptual model:

```
kk generated / kk edited / ru generated / ru edited
```

as separate rows with shared columns. Alternatives (four text columns per block, separate documents per locale) would duplicate the architecture without benefit.

`kk-ru` remains render-time composition only (print language mode).

---

## Phase 3 — Russian editorial UI

Implemented in `PersonnelOrderEditorialTextEditor.tsx`:

- Locale tabs: **Қазақша** | **Русский**
- Feature parity via shared `BlockEditor`: title, preamble, item body, basis, closing
- Full generate on first open when either locale missing (`hasRequiredEditorialLocales`)
- Manual generate regenerates both locales (READY gate compatible)

---

## Phase 4 — Ready Gate review

**No changes.** Existing `ready_gate.py` already validates for **each** of `kk` and `ru`:

- title + preamble required (non-empty effective)
- item body required
- item basis when `basis_required`
- blocks with `STALE`, `REVIEW_REQUIRED`, `GENERATION_FAILED` block READY

This naturally extends the bilingual model without architectural change.

---

## Phase 5 — Preview verification

Verified (existing, unchanged):

- HTML Preview: `buildPersonnelOrderPrintViewModel` + shared template
- PDF: same ViewModel via `loadPersonnelOrderPrintViewModelForPdf`
- Both use `effective_text` from editorial blocks per locale

**Known limitation (resolved in PO-DOC-001):** ~~closing blocks not in print~~ — now mapped.

---

## Phase 6 — Tests

| Area | Location |
|---|---|
| Locale tabs, ru save, bilingual auto-generate | `PersonnelOrderEditorialTextEditor.test.tsx` |
| Section building per locale, `hasRequiredEditorialLocales` | `personnelOrderEditorialUi.test.ts` |
| Backend ru/kk generate, override, reset, READY gate | `tests/test_wp_po_edit_002_editorial_api.py` (existing) |
| Print effective_text kk+ru | `personnelOrderPrint.test.ts` (existing) |

---

## Files modified

- `corpsite-ui/.../personnelOrderEditorialUi.ts`
- `corpsite-ui/.../personnelOrderEditorialUi.test.ts`
- `corpsite-ui/.../PersonnelOrderEditorialTextEditor.tsx`
- `corpsite-ui/.../PersonnelOrderEditorialTextEditor.test.tsx`
- `docs/.../PO-EDIT-004-bilingual-editorial.md` (this file)
- `docs/personnel-orders/README.md` (roadmap)

**Not modified:** `ready_gate.py`, `ALLOWED_LOCALES`, editorial backend, DB migrations.

---

## Remaining limitations

1. **Closing block** not in print ViewModel
2. **No per-locale editorial approval** — generation ≠ HR review (see Future work)
3. **Status labels** still English (`Generated` / `Edited` / `Requires review`)
4. **Editor does not reload** automatically when order items change in drawer
5. **Morphological FIO** in basis text — manual override only (EDIT-005+)

---

## Future work

Separate architectural question (not implemented):

> What counts as an editorially ready document?

- Automatic generation ≠ editorial review
- Block presence ≠ кадровик confirmation
- User may never open Russian tab under Kazakh-first UX
- May need explicit per-locale confirmation
- Possible Review Pending / Reviewed workflow

Track as **WP-PO-EDIT-005** or dedicated editorial-approval WP.

---

## Recommended next WP

| WP | Scope |
|---|---|
| **WP-PO-EDIT-005** | Editorial approval workflow; return-to-DRAFT polish; localized status labels |
| **WP-PO-EDIT-004b** | Map `closing` into print ViewModel |
| **WP-PO-EDIT-004** (clause library) | Renumber or merge with planned template library WP |

---

## Answer: schema vs EditorialDocument

**Full bilingual editorial model is achievable without DB schema changes.**

The existing `personnel_order_*_editorial_blocks` tables already store bilingual content as `(locale, block_type)` rows with `generated_text` + `override_text`. Extending storage (e.g. four columns per block) would break the established unique-key model and duplicate logic in generate, patch, ready gate, and print.

Architecturally correct path: **keep schema; extend UI and workflows on top of existing block rows.**
