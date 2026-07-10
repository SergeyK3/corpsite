# PO-003 Personnel Orders Data Model

**Status:** Draft  
**Version:** 0.1  
**Depends on:** PE-001, PE-002, PE-003, PO-001, PO-002

---

# 1. Purpose

Define the conceptual and implementation-oriented data model for the Personnel Orders module in Corpsite.

The model is based on the architectural principle:

```text
Personnel Event
    → Change Set
    → Order Item
    → Personnel Order
    → Order Document
```

Personnel Event is the primary business entity.  
Personnel Order is the legal registration of one or more Personnel Events.  
Order Document is a file representation of the Personnel Order.

---

# 2. Core Entity Overview

```text
Employee
   │
   ├── PersonnelEvent
   │       └── PersonnelChangeSet
   │              └── PersonnelChange
   │
   └── OrderItem
            └── PersonnelOrder
                    ├── OrderDocument
                    ├── OrderApproval
                    └── OrderParticipant
```

---

# 3. Entity: personnel_events

Represents a business HR event that changes the employee's Personnel State.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| employee_id | uuid | FK to employee |
| event_type | text | HIRE, TERMINATION, TRANSFER, etc. |
| event_subtype | text | Optional detailed subtype |
| status | text | draft, approved, active, cancelled |
| effective_from | date | Start date |
| effective_to | date | Optional end date |
| parent_event_id | uuid | Optional FK to personnel_events |
| related_event_id | uuid | Optional FK to personnel_events |
| source_order_item_id | uuid | FK to order item |
| basis_text | text | Human-readable basis |
| created_by | uuid | User |
| created_at | timestamp | Audit |
| updated_at | timestamp | Audit |

## Notes

- Personnel Event must not depend on DOCX/PDF files.
- Personnel Event is the source for Personnel State reconstruction.
- Cancellation should be modeled either as status update or as separate reversal event; this remains an open design decision.

---

# 4. Entity: personnel_change_sets

Represents a set of changes produced by one Personnel Event.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| event_id | uuid | FK to personnel_events |
| summary | text | Optional |
| created_at | timestamp | Audit |

---

# 5. Entity: personnel_changes

Atomic change inside a Change Set.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| change_set_id | uuid | FK to personnel_change_sets |
| field_key | text | e.g. position_id, rate, surname |
| field_label | text | Display name |
| old_value_text | text | Human-readable previous value |
| new_value_text | text | Human-readable new value |
| old_value_json | jsonb | Typed previous value |
| new_value_json | jsonb | Typed new value |
| effective_from | date | Optional override |
| effective_to | date | Optional |
| created_at | timestamp | Audit |

## Design Note

Both text and JSON values are recommended:

- text values support audit, display and historical readability;
- JSON values support structured processing.

---

# 6. Entity: personnel_orders

Represents a registered or draft personnel order.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| order_number | text | Nullable while draft |
| order_date | date | Nullable while draft |
| order_type | text | HIRE_ORDER, LEAVE_ORDER, etc. |
| title_kz | text | Kazakh title |
| title_ru | text | Russian title |
| primary_language | text | Usually KZ |
| status | text | draft, prepared, approved, signed, registered, executed, archived, cancelled |
| registration_status | text | unregistered, registered |
| signed_by_position | text | Frozen text |
| signed_by_full_name | text | Frozen text |
| prepared_by_position | text | Frozen text |
| prepared_by_full_name | text | Frozen text |
| prepared_by_department | text | Frozen text |
| prepared_by_phone | text | Frozen text |
| created_by | uuid | User |
| created_at | timestamp | Audit |
| updated_at | timestamp | Audit |

## Notes

Signatory and preparer fields are stored as frozen text because the document must preserve historical reality even if employees or positions later change.

---

# 7. Entity: order_items

Represents an employee-level item inside a Personnel Order.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| order_id | uuid | FK to personnel_orders |
| event_id | uuid | FK to personnel_events |
| employee_id | uuid | FK to employee |
| item_number | integer | Order item sequence |
| item_text_kz | text | Generated or imported text |
| item_text_ru | text | Translation |
| effective_from | date | Usually equals event effective_from |
| effective_to | date | Optional |
| created_at | timestamp | Audit |

## Constraint

One order can contain many order items.  
One order item should normally reference one personnel event.

---

# 8. Entity: order_documents

Represents file versions of the Personnel Order.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| order_id | uuid | FK to personnel_orders |
| document_type | text | DOCX_KZ, PDF_KZ_SIGNED, DOCX_RU, PDF_RU, SCAN |
| language | text | KZ, RU |
| file_path | text | Storage path |
| file_name | text | Original file name |
| checksum | text | Integrity |
| is_signed | boolean | True for signed PDF |
| is_legal_copy | boolean | True for legal copy |
| created_at | timestamp | Audit |
| uploaded_by | uuid | User |

---

# 9. Entity: order_approvals

Represents visas and approvals collected before signing.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| order_id | uuid | FK to personnel_orders |
| order_item_id | uuid | Optional FK |
| event_id | uuid | Optional FK |
| approver_employee_id | uuid | Optional FK |
| approver_position | text | Frozen text |
| approver_full_name | text | Frozen text |
| approval_role | text | MANAGER, HR, LEGAL, FINANCE, DIRECTOR |
| status | text | pending, approved, rejected, skipped |
| approved_at | timestamp | Nullable |
| comment | text | Optional |
| sequence_number | integer | Route order |

## Notes

Approval workflow belongs to document lifecycle, not to the Personnel Event itself.

---

# 10. Entity: order_participants

Optional normalized representation of document participants.

## Fields

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| order_id | uuid | FK to personnel_orders |
| participant_role | text | SIGNATORY, PREPARER, APPROVER |
| employee_id | uuid | Optional FK |
| position_text | text | Frozen text |
| full_name_text | text | Frozen text |
| phone_text | text | Optional |
| department_text | text | Optional |

## Design Note

This table may be used later if document participant logic becomes more complex.  
For MVP, signatory/preparer fields in `personnel_orders` may be enough.

---

# 11. Related Events

Some events are related but remain independent.

Example:

```text
Leave Event
    ├── Temporary Assignment Event
    └── Allowance Event
```

Implementation options:

1. `parent_event_id`
2. `related_event_id`
3. separate `personnel_event_links` table

Recommended future table:

## personnel_event_links

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| source_event_id | uuid | FK |
| target_event_id | uuid | FK |
| relation_type | text | GENERATED, CAUSED_BY, REPLACES, CANCELS |
| created_at | timestamp | Audit |

---

# 12. Suggested Status Dictionaries

## Personnel Event Status

- draft
- approved
- active
- completed
- cancelled
- reversed

## Personnel Order Status

- draft
- prepared
- approval_in_progress
- approved
- signed
- registered
- executed
- archived
- cancelled

## Approval Status

- pending
- approved
- rejected
- skipped

---

# 13. Indexes

Recommended indexes:

```text
personnel_events(employee_id)
personnel_events(event_type)
personnel_events(effective_from)
personnel_events(status)

personnel_orders(order_number)
personnel_orders(order_date)
personnel_orders(order_type)
personnel_orders(status)

order_items(order_id)
order_items(event_id)
order_items(employee_id)

order_documents(order_id)
order_approvals(order_id)
order_approvals(approver_employee_id)
```

---

# 14. MVP Scope

For the first implementation, the minimum viable model should include:

- personnel_events
- personnel_change_sets
- personnel_changes
- personnel_orders
- order_items
- order_documents
- order_approvals

`order_participants` and `personnel_event_links` may be postponed unless required by implementation.

---

# 15. Open Questions

1. Should Personnel State be materialized in a table or calculated from events on demand?
2. Should cancellation of an order automatically create reversing Personnel Events?
3. Should Change Set values be stored as JSONB, normalized fields, or both?
4. Should approval routes be static templates or dynamically generated by event type?
5. Should one Order Item be allowed to reference multiple Personnel Events?

---

# Revision History

- v0.1 Initial draft based on PE-001, PE-002, PE-003 and PO-002.
