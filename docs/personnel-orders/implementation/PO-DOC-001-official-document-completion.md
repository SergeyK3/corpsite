# PO-DOC-001 — Official Personnel Order Document Completion

**Status:** Implemented  
**Scope:** Print/PDF document completeness; no editorial model or persistence changes.

---

## Phase 1 — Document audit (findings)

| Element | HTML Preview | PDF | Issue before fix |
|---|---|---|---|
| Title | ✅ | ✅ | — |
| Preamble | ✅ | ✅ | Duplicated «ПРИКАЗЫВАЮ» when editorial preamble included verb |
| Order verb | ✅ | ✅ | Always rendered even when embedded in preamble |
| Item body | ✅ | ✅ | — |
| Order-level basis | ✅ | ✅ | — |
| **Closing** | ❌ | ❌ | Editorial block stored but not in ViewModel/HTML |
| Signature | ✅ | ✅ | — |
| Acknowledgement | ✅ | ✅ | — |
| Watermark | ✅ | ✅ | — |
| Bilingual kk-ru | ✅ | ✅ | — |
| Item numbering | ✅ | ✅ | — |
| Page breaks | partial | partial | Signature/ack could orphan; no closing tail group |

**Architecture:** HTML and PDF already shared `buildPersonnelOrderPrintDocumentHtml` + `buildPersonnelOrderPrintViewModel`. No duplicated markup — only duplicated data-loading (client vs server), unchanged.

---

## Phase 2 — Closing mapping

**Decision:** Closing is part of the official document when non-empty.

Implemented:

1. `PersonnelOrderPrintViewModel.closing: LocalizedText | null` from editorial `order_blocks` (`effective_text` per kk/ru).
2. `renderClosing()` in shared HTML — after basis, before signature.
3. Default generator text (backend, not schema):
   - **ru:** «Контроль за исполнением приказа оставляю за собой.»
   - **kk:** «Бұйрықты орындалу бақылауын өзімде қалдырамын.»

Empty closing → section omitted (same rule as empty preamble).

---

## Phase 3 — Print consistency

- Single ViewModel + single HTML template unchanged in architecture.
- Closing added to both preview and PDF paths automatically.
- Section order: header → items → basis → **closing** → signature → acknowledgement.

---

## Phase 4 — Long document / layout

- `orphans` / `widows` on item body paragraphs.
- `.personnel-order-print-tail` wraps signature + acknowledgement with `break-inside: avoid`.
- Closing block uses `break-inside: avoid`.
- Multi-item numbering test (12 items) added.

---

## Phase 5 — HR review fixes

| Fix | Rationale |
|---|---|
| Closing in print | Standard personnel order responsibility clause |
| No duplicate order verb | Official text reads correctly when preamble is generated |
| Default closing text | Document no longer ends abruptly after basis |

Not changed (out of scope): per-item basis inline, org name KK loading, digital seal, place of issue from order data.

---

## Phase 6 — Tests

| Test file | Added |
|---|---|
| `personnelOrderPrint.test.ts` | closing VM, HTML closing, preamble dedup, 12-item numbering |
| `PersonnelOrderPrintDocument.test.tsx` | closing render, no duplicate ПРИКАЗЫВАЮ |
| `test_wp_po_edit_002_generators.py` | default closing text |

---

## Files modified

- `corpsite-ui/.../personnelOrderPrintViewModel.ts`
- `corpsite-ui/.../personnelOrderPrintDocumentHtml.ts`
- `corpsite-ui/.../personnelOrderPrintDocumentCss.ts`
- `corpsite-ui/.../personnelOrderPrint.test.ts`
- `corpsite-ui/.../PersonnelOrderPrintDocument.test.tsx`
- `app/services/personnel_orders_editorial/generators.py`
- `tests/test_wp_po_edit_002_generators.py`
- `docs/.../PO-DOC-001-official-document-completion.md` (this file)

**Not modified:** `ready_gate.py`, editorial persistence, React editor.

---

## Remaining limitations

1. Per-item basis only in aggregate «Основание» section, not under each пункт.
2. `organizationNameKk` not loaded from tenant (KK org falls back to RU).
3. Place of issue hardcoded (Астана).
4. Legacy `localized_texts.body_text` not used.
5. No digital signature / stamp (PO-SIGN-001).
6. Browser HTML print lacks `@page` margins (PDF is authoritative).

---

## Recommended next WP

**WP-PO-DOC-002** — Editorial approval workflow (EDIT-005) + org name KK + place of issue from order metadata + optional per-item basis inline for composite orders.

---

## Audit checklist (post-fix)

| Check | Result |
|---|---|
| Closing in ViewModel | ✅ |
| Closing in HTML/PDF | ✅ |
| Same template HTML + PDF | ✅ |
| Preamble verb dedup | ✅ |
| Default closing generated | ✅ |
| READY gate unchanged | ✅ |
| Bilingual effective_text | ✅ |
