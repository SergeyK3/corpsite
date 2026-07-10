# WP-PO-008 — Personnel Orders Write UI (Phase 1)

| Field | Value |
|------|--------|
| Status | Implemented |
| Date | 2026-07-10 |
| Predecessor | WP-PO-006 / WP-PO-007 |
| Next | WP-PO-009 — Attachments |

## 1. Implemented scenarios

1. Create Draft without `order_number` / `order_date` (Paper First).
2. Edit header (number, date, type, comment) while DRAFT / READY.
3. Add / edit order items with type-specific payload.
4. Lifecycle: Ready → Register(`REGISTERED`) → Apply → Void (order-level).
5. Deep-link from employee History → `/directory/personnel/orders?order_id=…`.
6. Refresh journal after mutations.

## 2. Backend compatibility fix (required)

Nullable registration fields:

- Migration `r2s3t4u5v6w7`
- Create Draft allows `order_number=null`, `order_date=null`
- Register / Ready still require both via `_validate_registerable_order`
- No placeholder numbers (`Б/Н`, `DRAFT-001`, …)

## 3. APIs used

| Action | Endpoint |
|--------|----------|
| Create | `POST /directory/personnel-orders` |
| Update header | `PATCH /directory/personnel-orders/{id}` |
| Add/update item | `POST/PATCH …/items` |
| Ready | `POST …/ready-for-signature` |
| Register | `POST …/register` (`target_status=REGISTERED`) |
| Apply | `POST …/apply` |
| Void | `POST …/void` |

Not used in Phase 1: item-level void, localized-text upsert UI, attachments, prints.

## 4. Frontend surfaces

- `/directory/personnel/orders` — Create button, journal, drawer editor
- Import-card History — deep-link with `order_id`

## 5. Known limitations

- Localized text editor deferred
- Attachments / prints deferred (WP-PO-009)
- Item-level void deferred
- SIGNED path not emphasized in UI (Paper First uses REGISTERED)
- History deep-link on staff drawer (non import-card) still TODO
- Create Dialog does not show COMPOSITE

## 6. Tests

Backend:

- `tests/test_wp_po_008_nullable_order_registration_fields.py`
- Full WP-PO suite still green (30 passed at implementation time)

Frontend:

- `personnelOrdersApi.client.test.ts` (order_id deep-link)
- `personnelOrderPayload.test.ts`
- Existing table tests retained

## 7. TODO for WP-PO-009

1. Attachment upload / register API + UI
2. Signed scan required before REGISTERED (Paper First hardening)
3. Optional print metadata display improvements
