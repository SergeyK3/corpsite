# WP-PO-EDIT-002 — Migration draft (NOT APPLIED)

Draft only. Do **not** run against production until WP-PO-EDIT-002.

Ratified constraints (PO-EDIT-001 §0):

- Editorial **and structured** writes: **DRAFT only** (R10). READY/SIGNED/REGISTERED/VOIDED read-only.
- return-to-DRAFT in EDIT-005; rows must survive READY ↔ DRAFT.
- Store locales `kk` + `ru` only (`kk-ru` is render-time).
- READY gate: title + preamble + each active item body; basis only if `basis_required` (R8).
- Regenerate keeps override and marks stale; restore-generated is separate (R9).
- Stamp `generator_version` + `source_fingerprint` on generate.
- `template_set_version` nullable reserved for EDIT-004.
- Do **not** alter/drop `personnel_order_localized_texts` here (R11).
- No leave multi-period structured tables (WP-PO-LEAVE-001 / R12).

```sql
-- personnel_order_editorial_blocks
CREATE TABLE IF NOT EXISTS personnel_order_editorial_blocks (
  editorial_block_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES personnel_orders(order_id) ON DELETE RESTRICT,
  locale VARCHAR(8) NOT NULL CHECK (locale IN ('kk', 'ru')),
  title_generated TEXT NULL,
  title_override TEXT NULL,
  preamble_generated TEXT NULL,
  preamble_override TEXT NULL,
  closing_generated TEXT NULL,
  closing_override TEXT NULL,
  source_fingerprint VARCHAR(128) NULL,
  generator_version VARCHAR(64) NULL,
  template_set_version INTEGER NULL,  -- reserved EDIT-004
  -- R9: when override present and generated refreshed → review_status = STALE / REVIEW_REQUIRED
  review_status VARCHAR(32) NULL,  -- NULL|OK|STALE|REVIEW_REQUIRED (exact enum in EDIT-002)
  generated_at TIMESTAMPTZ NULL,
  edited_at TIMESTAMPTZ NULL,
  edited_by BIGINT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  UNIQUE (order_id, locale)
);

CREATE INDEX IF NOT EXISTS ix_po_editorial_blocks_order
  ON personnel_order_editorial_blocks (order_id);

-- personnel_order_item_editorial_blocks
CREATE TABLE IF NOT EXISTS personnel_order_item_editorial_blocks (
  item_editorial_block_id BIGSERIAL PRIMARY KEY,
  order_item_id BIGINT NOT NULL REFERENCES personnel_order_items(item_id) ON DELETE RESTRICT,
  locale VARCHAR(8) NOT NULL CHECK (locale IN ('kk', 'ru')),
  body_generated TEXT NULL,
  body_override TEXT NULL,
  basis_generated TEXT NULL,
  basis_override TEXT NULL,
  source_fingerprint VARCHAR(128) NULL,
  generator_version VARCHAR(64) NULL,
  template_set_version INTEGER NULL,  -- reserved EDIT-004
  review_status VARCHAR(32) NULL,
  generated_at TIMESTAMPTZ NULL,
  edited_at TIMESTAMPTZ NULL,
  edited_by BIGINT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  UNIQUE (order_item_id, locale)
);

CREATE INDEX IF NOT EXISTS ix_po_item_editorial_blocks_item
  ON personnel_order_item_editorial_blocks (order_item_id);

-- Structured basis facts (optional in EDIT-002; may start as payload JSONB — decide in EDIT-002 impl)
CREATE TABLE IF NOT EXISTS personnel_order_item_bases (
  item_basis_id BIGSERIAL PRIMARY KEY,
  order_item_id BIGINT NOT NULL UNIQUE REFERENCES personnel_order_items(item_id) ON DELETE RESTRICT,
  basis_type VARCHAR(64) NOT NULL,
  subject_employee_id BIGINT NULL REFERENCES employees(employee_id),
  document_date DATE NULL,
  document_number VARCHAR(128) NULL,
  free_text TEXT NULL,
  attachment_id BIGINT NULL
);

-- NOTE: No return_to_draft table/column required.
-- Compatibility: editorial rows remain valid across DRAFT ↔ READY ↔ DRAFT
-- once EDIT-005 adds return-to-draft; do not bind mutability to READY.
```

## Legacy mapping (not DDL)

On first `editorial/generate` for an order:

1. For each locale `kk`, `ru`: upsert editorial row.
2. If `personnel_order_localized_texts` has `title`/`preamble` → seed editorial (prefer generated if equal to generator output; else override).
3. Ignore `body_text` as item SoT.
4. Leave `personnel_order_localized_texts` unchanged (no DROP, no new columns).
