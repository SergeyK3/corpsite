# WP-PO-LC-006 — Journal closed-document visibility

**Status:** Implemented  
**Scope:** Default journal filtering, `include_closed` API, checkbox rename

---

## Goal

Keep the personnel orders journal focused on active HR work while preserving full document history on demand.

Default journal shows active pipeline documents only. Closed documents (VOIDED and archived) are hidden until the user enables **«Показывать закрытые документы»**.

---

## API

Canonical query parameter:

```
GET /directory/personnel-orders?include_closed=true|false
```

Backward-compatible alias:

```
include_archived=true  →  equivalent to include_closed=true
```

No `archived_only` parameter in this WP.

---

## Filter matrix

| `include_closed` | `status` | Result |
|---|---|---|
| `false` | *(empty)* | `archived_at IS NULL AND status <> 'VOIDED'` |
| `false` | `VOIDED` | `archived_at IS NULL AND status = 'VOIDED'` |
| `false` | other | `archived_at IS NULL AND status = :status` |
| `true` | *(empty)* | no closed-document exclusion |
| `true` | `VOIDED` | `status = 'VOIDED'` (includes archived VOIDED) |
| `true` | other | `status = :status` |

Explicit `status=VOIDED` overrides default VOIDED hiding, but archive hiding remains while `include_closed=false`.

---

## Frontend

- Checkbox label: **«Показывать закрытые документы»**
- URL param emitted: `include_closed=true`
- Legacy bookmarks with `include_archived=true` are still parsed
- Existing status and archive badges distinguish VOIDED vs ARCHIVED

---

## Out of scope

- Physical deletion / `DELETE` endpoint — future dedicated WP
- `archived_only` filter
- Migrations, permissions, lifecycle/archive redesign

---

## Tests

- `tests/test_wp_po_lc_del_006_journal_closed_filter_api.py`
- `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.test.ts`
