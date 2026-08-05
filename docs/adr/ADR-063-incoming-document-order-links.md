# ADR-063 — Incoming Document Links to Orders

## Status

**Accepted**

| Field | Value |
|-------|-------|
| Work Package | WP-II-001 |
| Parent | [incoming-information-register](../implementation/incoming-information-register.md) |
| Related | [ADR-062](./ADR-062-incoming-document-registration-number.md) |
| Date | 2026-08-04 |

---

## Context

Incoming Information records are the **origin** of managerial actions. One record may produce several outcomes; one operational or personnel order may cite several incoming records as basis.

The task requires typed many-to-many links without storing order numbers as plain text on the incoming record.

Existing order aggregates:

| Aggregate | Table | Module |
|-----------|-------|--------|
| Operational (production) order | `operational_order_documents` | `app/operational_orders/` |
| Personnel (HR) order | `personnel_orders` | personnel orders BC |

Scenario: **complaint or report → investigation → disciplinary personnel order**.

---

## Decision

### D1 — Separate typed link tables (not a generic polymorphic blob)

Two M2M tables with explicit FK integrity:

**`incoming_document_operational_order_links`**

- FK → `incoming_documents`
- FK → `operational_order_documents`
- `link_type_code` (FK to `incoming_document_link_types`)
- `comment`, audit columns

**`incoming_document_personnel_order_links`**

- FK → `incoming_documents`
- FK → `personnel_orders`
- same metadata shape

UNIQUE (`incoming_document_id`, target_id, `link_type_code`) on each table.

Rationale: FK enforcement and query performance outweigh a single `related_documents(target_kind, target_id)` table at MVP.

### D2 — Link type vocabulary

Seed table `incoming_document_link_types`:

| code | Typical use |
|------|-------------|
| `BASIS` | Incoming record is legal/factual basis for the order |
| `RESULT` | Order is an outcome of consideration |
| `DISCIPLINARY` | Disciplinary personnel order after complaint/report |
| `OTHER` | Free-form, requires comment |

Administrators deactivate types via `is_active`; used types are not physically deleted.

### D3 — Cardinality

- Incoming → many operational orders; operational order → many incoming records.
- Incoming → many personnel orders; personnel order → many incoming records.
- Cross-link between order types is not stored; each link table is independent.

### D4 — UI phasing

Foundation API exposes link attach/list/delete for **both** order kinds. UI v1 may show operational order picker only; personnel order picker is a follow-up UI task without schema change.

### D5 — No denormalized order numbers on `incoming_documents`

List/detail responses join target tables for display fields (number, date, status/title). Persist only FK + link metadata.

---

## Consequences

- Operational Orders module remains unchanged until optional reverse “basis” panel (additive read).
- Link mutations require the same access checks as the parent incoming document (including `RESTRICTED` rules).
- Tests must cover M2M in both directions and duplicate-link rejection.
