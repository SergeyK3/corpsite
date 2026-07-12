# OO-SEC-002 — Organization-Wide Official Orders Read Policy

## Status

**Proposed** — planning/spec only. **Not implemented** in this review cycle.

## Problem

Product policy requires that **practically all active employees** can read **official** operational orders after signing/approval/publication. Only leaders and designated operators may access the preparation contour (intake, workspace, editorial, reconciliation, promotion, internal audit).

OO-SEC-001 correctly grants `OPERATIONAL_ORDERS_INTAKE_READ` to leadership for **workspace preparation read**. That permission is **unsuitable** for mass employee grants because it exposes draft workspaces, submitted text, editorial data, provenance, and pre-signature documents.

## Architectural gaps (current state)

| Gap | Current state | Required for OO-SEC-002 |
|---|---|---|
| **Publication boundary** | Document lifecycle stops at `READY_FOR_SIGNATURE`; `SIGNED` / `REGISTERED` exist in schema but have no transitions or services | Define official publication state (likely `REGISTERED` per UDE target) |
| **Official-read permission** | No `OPERATIONAL_ORDERS_OFFICIAL_READ` (or equivalent) in `access_roles` | New permission with narrow semantics |
| **API filtering** | `can_read_document()` treats `INTAKE_READ` and promoted documents equally; no publication-state filter | Separate read path filtering to published documents only |
| **Frontend view** | Single `/directory/operational-orders` contour gated by `has_operational_orders_read` | Distinct official-documents view for employees |
| **Mass grant subject** | No universal platform role for all employees | ORG_UNIT baseline or authenticated-active-employee projection |

**`READY_FOR_SIGNATURE` is NOT official publication.** Promotion creates an official **snapshot** (`official_text`) but the document remains in the internal signing pipeline.

## Target policy

### Eligible subjects

**All active enrolled employees** of the organization:

- authenticated (`users.is_active = true`);
- linked to an active employee shell with active assignment(s);
- **excluded:** terminated, blocked, inactive accounts, external users without enrollment, users without active assignments.

### Permitted read (official contour only)

After document reaches the **official publication boundary**:

- list of official orders;
- search;
- title, number, date;
- current official version;
- official PDF/HTML (when available);
- signing metadata;
- effective/action status;
- cancellation, supersession, or archive status;
- public attachments without separate restriction.

### Forbidden read (preparation contour)

Even with official-read permission, users must **not** access:

- intake workspaces;
- submitted text;
- effective text before publication;
- clarifications;
- translation assignments;
- editorial package;
- reconciliation records;
- promotion controls;
- readiness controls;
- internal preparation provenance/audit;
- draft and unsigned versions.

## Proposed permission

### `OPERATIONAL_ORDERS_OFFICIAL_READ` (proposed name)

| Property | Value |
|---|---|
| Code | `OPERATIONAL_ORDERS_OFFICIAL_READ` (subject to architecture approval) |
| Semantics | Read-only access to documents at or beyond official publication boundary |
| Workspace access | **None** |
| Document aggregate | Published documents only (filtered by lifecycle state) |
| State changes | **None** |
| Nav projection | New flag, e.g. `has_operational_orders_official_read` — **separate** from `has_operational_orders_read` |

### Alternative: extend existing permission

No existing permission has suitable semantics:

| Existing code | Why unsuitable |
|---|---|
| `OPERATIONAL_ORDERS_INTAKE_READ` | Opens full preparation contour |
| `OPERATIONAL_ORDERS_INTAKE_OPERATE` | Write + broader list |
| `OPERATIONAL_ORDERS_PROMOTE` | Write permission |
| `OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ` | Signing-prep; redundant with INTAKE_READ; no publication filter |

**Recommendation:** introduce `OPERATIONAL_ORDERS_OFFICIAL_READ` as a new `access_roles` code.

## Official publication boundary

### Proposed criterion

Document status ∈ `{REGISTERED, ...}` (post-signing registration) **or** explicit `published_at` / `in_force_at` marker once lifecycle WP implements signing and registration.

### Interim dependency chain

```
OO-IMP-004 (READY_FOR_SIGNATURE)  ← current head
    ↓
OO-IMP-005+ Signing service (CREATED/READY → SIGNED)
    ↓
OO-IMP-006+ Registration service (SIGNED → REGISTERED)
    ↓
OO-SEC-002 Official read enforcement (REGISTERED+ only)
```

OO-SEC-002 **must not** ship before a ratified publication state exists. Do not use `READY_FOR_SIGNATURE` or promotion alone as the publication gate.

### Visibility rules for non-active documents

| Document state | Official-read visibility |
|---|---|
| `REGISTERED` (in force) | Visible |
| `VOIDED` / cancelled | Visible with cancelled status |
| Superseded by newer order | Visible with supersession link |
| Archived | Visible per archive policy (read-only, marked archived) |
| `CREATED` / `READY_FOR_SIGNATURE` / `SIGNED` (pre-registration) | **Not visible** via official-read contour |

## Grant provisioning strategy

### Recommended mechanism (short term, ADR-042)

**Root ORG_UNIT grant** at hospital level:

```
access_grants (
  access_role_id = OPERATIONAL_ORDERS_OFFICIAL_READ,
  target_type = 'ORG_UNIT',
  target_id = <root hospital org_unit_id>
)
```

Resolution: all users with **active assignments** in that unit (and subtree per scope rules) inherit the grant via `_collect_subject_ids`.

**Advantages:**

- O(1) grant rows, not O(users);
- follows existing ADR-042 POSITION/ORG_UNIT inheritance;
- naturally excludes users without active assignments.

**Exclusion enforcement:**

- `users.is_active = false` → cannot authenticate;
- inactive assignments → no ORG_UNIT subject collected;
- terminated employees → account lifecycle (deactivate / unlink), not grant resolver filtering;
- external users → no enrollment / no active assignment.

### Alternatives (evaluate during architecture review)

| Mechanism | Scale | Notes |
|---|---|---|
| Enumerate all `roles.code` with ROLE grants | O(~20–50) | Works if every enrolled user has a platform role, but couples to position-specific roles |
| ADR-053 permission template contour | O(positions) | Long-term baseline; not runtime-authoritative today |
| Authenticated-active-employee projection | O(1) rule | Requires auth projection change; evaluate vs explicit grant |
| Per-USER grants | O(users) | **Avoid** |

### Not recommended

- Mass `OPERATIONAL_ORDERS_INTAKE_READ` to all roles or all users;
- SQL `LIKE` on position names;
- Heuristic leadership classifier for security grants.

## API design (planned)

### New or restricted endpoints

| Endpoint | Behavior |
|---|---|
| `GET /api/operational-orders/official-documents` | List published documents only; requires `OPERATIONAL_ORDERS_OFFICIAL_READ` |
| `GET /api/operational-orders/official-documents/{id}` | Official summary + current version; no workspace/editorial data |
| `GET /api/operational-orders/official-documents/{id}/versions/{n}` | Official localized text only |

Existing preparation endpoints (`/draft-workspaces/*`, workspace detail, editorial sub-resources) remain gated by `OPERATIONAL_ORDERS_INTAKE_READ` / operate permissions.

### Enforcement helpers (planned)

```python
def can_read_official_document(user, document) -> bool:
    # 1. has OPERATIONAL_ORDERS_OFFICIAL_READ (or privileged)
    # 2. document.status in OFFICIAL_PUBLICATION_STATUSES
    # 3. document_in_user_scope (org-wide or hospital scope TBD)
```

Separate from `can_read_document()` used by preparation contour.

## Frontend design (planned)

| View | Gate | Audience |
|---|---|---|
| `/directory/operational-orders` (preparation) | `has_operational_orders_read` (INTAKE_READ family) | Leadership + operators |
| `/directory/operational-orders/official` (proposed) | `has_operational_orders_official_read` | All active employees |

Employees without preparation permissions see only the official view. Leaders with `INTAKE_READ` may see both (tabbed or separate nav entries).

## Revoked employment behavior

When employment ends:

1. Deactivate user account (`users.is_active = false`) or unlink employee;
2. Active assignment ends → ORG_UNIT grant no longer resolves;
3. Official-read access revoked immediately on next auth resolution;
4. No retroactive audit of what was read (existing audit patterns apply).

## Confidentiality extension (future)

Base OO-SEC-002 policy covers **general** operational orders visible to all active employees.

Future **restricted orders** require classification/access scope:

| Restriction type | Example |
|---|---|
| Personal data | Orders naming specific individuals |
| Limited distribution | Internal investigations |
| Security | Security-sensitive directives |
| Medical confidentiality | Patient-related operational orders |
| Financial/procurement | Tender or contract restrictions |

### Extension point

Add optional `classification` / `access_scope` on document aggregate. Official-read resolver checks:

1. `OPERATIONAL_ORDERS_OFFICIAL_READ` (baseline), **and**
2. additional scope grant or classification rule for restricted documents.

Not in OO-SEC-002 MVP scope — document extension point only.

## Migration / provisioning plan

| Step | Action |
|---|---|
| 1 | Architecture review: approve permission name, publication state, grant mechanism |
| 2 | Register `OPERATIONAL_ORDERS_OFFICIAL_READ` in `access_roles` (Alembic seed) |
| 3 | Implement lifecycle transitions to publication state (dependency WP) |
| 4 | Add `can_read_official_document()` and API filtering |
| 5 | Add auth projection flag |
| 6 | Idempotent migration: ORG_UNIT grant at hospital root |
| 7 | Frontend official-documents view |
| 8 | Tests: positive (active employee), negative (no grant, pre-publication doc, terminated user) |
| 9 | Deploy: lifecycle WP first, then OO-SEC-002 migration, then frontend |

## Test plan (planned)

| Case | Expected |
|---|---|
| Active employee with ORG_UNIT grant | Can list/read `REGISTERED` documents |
| Active employee without grant | 403 on official endpoints |
| Leadership with INTAKE_READ only | Can read preparation contour; official read per grant |
| Pre-publication document (`CREATED`, `READY_FOR_SIGNATURE`) | 404 or 403 via official-read endpoints |
| Terminated / inactive user | No access (auth or resolver exclusion) |
| Voided / superseded / archived official document | Visible with correct status metadata |
| Restricted document (future) | Denied without scope grant |

## Deploy order

```
1. OO-IMP-005+ — Signing (SIGNED state)
2. OO-IMP-006+ — Registration (REGISTERED state, publication marker)
3. OO-SEC-002 — Permission, API, grants, frontend
4. OO-SEC-002A (optional) — Classification / restricted orders
```

## Relationship to OO-SEC-001

| WP | Contour | Permission |
|---|---|---|
| OO-SEC-001 | Leadership workspace read | `OPERATIONAL_ORDERS_INTAKE_READ` |
| OO-SEC-002 | Organization-wide official read | `OPERATIONAL_ORDERS_OFFICIAL_READ` (proposed) |

OO-SEC-001 and OO-SEC-002 are **orthogonal**. Leadership may hold both grants. Employees hold only official-read grant.

## Open questions for architecture review

1. Confirm publication state: `REGISTERED` only, or also `SIGNED`?
2. Hospital-wide ORG_UNIT grant vs per-department scope for official read?
3. Should official-read bypass org scope (hospital-wide visibility) or respect `submitting_org_unit_id`?
4. Separate nav entry vs unified section with role-based tabs?
5. PDF/HTML rendering WP dependency?
6. Timeline relative to signing/registration implementation WPs?

## Readiness

**Not ready for implementation.** Blocked on:

- ratified official publication state in document lifecycle;
- architecture approval of new permission code;
- signing and registration service implementation.
