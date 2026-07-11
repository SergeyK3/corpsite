# WP-PO-EDIT-002 — Migration draft → implemented reference

**Status:** Implemented in Alembic revision `s3t4u5v6w7x8`  
**WP:** WP-PO-EDIT-002

> **Physical storage refined from wide-row draft to normalized block-row model in WP-PO-EDIT-002. Architectural semantics R1–R12 remain unchanged.**

Ratified constraints (PO-EDIT-001 §0):

- Editorial **and structured** writes: **DRAFT only** (R10). READY/SIGNED/REGISTERED/VOIDED read-only.
- return-to-DRAFT in EDIT-005; rows must survive READY ↔ DRAFT.
- Store locales `kk` + `ru` only (`kk-ru` is render-time).
- READY gate: title + preamble + each active item body; basis only if `basis_required` (R8).
- Regenerate keeps override and marks stale/review-required; restore-generated is separate (R9).
- Stamp `generator_key` + `generator_version` + `source_fingerprint` on generate.
- Do **not** alter/drop `personnel_order_localized_texts` (R11).
- No leave multi-period structured tables (WP-PO-LEAVE-001 / R12).

## Final schema (normalized block-row)

```sql
-- personnel_order_editorial_blocks
-- Unique (order_id, locale, block_type)
-- block_type IN ('title', 'preamble', 'closing')
-- review_status IN ('CURRENT', 'STALE', 'REVIEW_REQUIRED', 'GENERATION_FAILED')

-- personnel_order_item_editorial_blocks
-- Unique (order_item_id, locale, block_type)
-- block_type IN ('body', 'basis')
-- + basis_required BOOLEAN

-- personnel_order_item_bases
-- Unique order_item_id (1:1)
-- basis_type, subject_employee_id, document_date, document_number, free_text, metadata JSONB
```

See Alembic: `alembic/versions/s3t4u5v6w7x8_wp_po_edit_002_editorial_persistence.py`  
Implementation notes: `docs/personnel-orders/implementation/PO-EDIT-002-editorial-persistence.md`

## Legacy mapping (runtime, not DDL)

On first `editorial/generate` for an order:

1. For each locale `kk`, `ru`: upsert editorial block rows.
2. If `personnel_order_localized_texts` has `title`/`preamble` → seed editorial (prefer generated if equal to generator output; else override).
3. Ignore `body_text` as item SoT.
4. Leave `personnel_order_localized_texts` unchanged (no DROP, no new columns).

## Historical note

Earlier drafts used a wide-row shape (`title_generated` / `title_override` columns on one row per locale). EDIT-002 intentionally replaced that with one row per `(scope, locale, block_type)` for per-block regenerate, stale, PATCH, and READY gate.
