# ADR-064 — Incoming Document Party Addressing Model

## Status

**Accepted**

| Field | Value |
|-------|-------|
| Work Package | WP-II-001 |
| Parent | [incoming-information-register](../implementation/incoming-information-register.md) |
| Date | 2026-08-04 |
| Amended | 2026-08-05 (WP-II-005R7 — RESTRICTED access model) |

---

## Context

Incoming Information is a **registration record**, not necessarily a file. Sources include paper, email, phone, verbal instruction, and internal messages. Attachments are optional related files.

Each record must capture:

- **From whom** — person, employee, org unit, or external text;
- **To whom addressed** — user, employee, org unit, position, or free text.

Corpsite already has `persons`, `employees`, `org_units`, `positions`, `users`. Reuse these references; do not duplicate master data.

Registration org unit and responsible org unit are **separate** from party addressing (see implementation spec §3 user clarification).

---

## Decision

### D1 — Polymorphic sender (`sender_kind` + nullable FKs)

| `sender_kind` | Required fields |
|---------------|-----------------|
| `EXTERNAL_TEXT` | `sender_text` NOT NULL |
| `PERSON` | `sender_person_id` |
| `EMPLOYEE` | `sender_employee_id` |
| `ORG_UNIT` | `sender_org_unit_id` |

CHECK constraint ensures kind matches populated FK; `sender_text` cleared when not `EXTERNAL_TEXT`.

### D2 — Polymorphic addressee (`addressee_kind` + nullable FKs)

| `addressee_kind` | Required fields |
|------------------|-----------------|
| `TEXT` | `addressee_text` NOT NULL |
| `USER` | `addressee_user_id` |
| `EMPLOYEE` | `addressee_employee_id` |
| `ORG_UNIT` | `addressee_org_unit_id` |
| `POSITION` | `addressee_position_id` |

### D3 — Default `responsible_org_unit_id`

At registration:

1. If addressee is `ORG_UNIT` → that unit.
2. If addressee is `USER` and user has `unit_id` → that unit.
3. If addressee is `EMPLOYEE` → employee `org_unit_id`.
4. Otherwise → `registration_org_unit_id`.

`registration_org_unit_id` is immutable history of where the record was registered. Transfer by competence updates `responsible_org_unit_id` only (future lifecycle WP).

### D4 — Access level interaction (`RESTRICTED`)

For `access_level = RESTRICTED`, org-scope read is **insufficient**. **Protected content**
(document body, audit trail, attachments, and other sensitive fields) is readable only by:

1. **Document participants:**
   - registrar (`created_by_user_id`);
   - addressee user / employee linked to current user;
   - active assignees (`incoming_document_assignments`);
   - controller (`controller_user_id`).

2. Users with an **explicit** `INCOMING_INFO_RESTRICTED_BYPASS` grant.

`INCOMING_INFO_RESTRICTED_BYPASS` is a separate permission from `INCOMING_INFO_CONTROL`
and `INCOMING_INFO_ADMIN`. It **may** be included in approved role permission packages
(for example director or module administrator profiles), but possession of those roles
or packages **without** this grant does **not** imply bypass.

**Administrative management vs protected content read**

- `INCOMING_INFO_ADMIN` supports module administration on records the user may already
  access under NORMAL rules and general RBAC; it does **not** automatically grant
  read access to RESTRICTED protected content.
- Platform privileged status (`is_privileged`, including `SYSTEM_ADMIN` / `role_id = 2`
  and directory env allowlists) does **not** bypass RESTRICTED for Incoming Information.
- A generic **director** or deputy catalog role, without participant status or
  `INCOMING_INFO_RESTRICTED_BYPASS`, does **not** bypass RESTRICTED.

Addressee `ORG_UNIT` / `POSITION` alone does not grant org-wide visibility under
`RESTRICTED`; resolution/assignment must name participants.

**Aggregated management reporting (future work)**

Management dashboards and aggregate KPIs may expose **de-identified / aggregated**
counts and status breakdowns without `INCOMING_INFO_RESTRICTED_BYPASS`, provided
they do **not** reveal protected texts, attachment metadata/content, or other
sensitive fields of individual RESTRICTED records. No such reporting API is part
of WP-II backend scope.

**Audit (future work)**

Reading a RESTRICTED document by a non-participant via `INCOMING_INFO_RESTRICTED_BYPASS`
SHOULD be auditable (who, which document, when). WP-II ships document lifecycle audit
only; dedicated bypass-read audit is deferred.

### D5 — Attachments optional

`incoming_document_attachments` is 0..N. Absence of attachment does not invalidate registration (verbal/phone channel).

---

## Consequences

- Validation lives in registration service + CHECK constraints.
- List filters may search `sender_text` / `addressee_text` and joined master names.
- Future transfer operation must update `responsible_org_unit_id` and audit prior value.
- RESTRICTED protected-content rule is implemented in WP-II-003/004 (`can_restricted_bypass`,
  participant checks); see [implementation spec §wp_ii_004](../implementation/incoming-information-register.md).
- Aggregate reporting and bypass-read audit remain **future work** (see D4).
