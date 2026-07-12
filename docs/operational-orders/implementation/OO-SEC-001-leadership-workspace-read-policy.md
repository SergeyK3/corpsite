# OO-SEC-001 — Leadership Workspace Read Policy

## Status

**Approved** — ready for commit. Not deployed to production.

## Scope

Grant **workspace preparation read** permission to approved leadership Platform Roles via existing ADR-042 RBAC (`access_grants.target_type = 'ROLE'`).

**Single permission:** `OPERATIONAL_ORDERS_INTAKE_READ`

**In scope:** ROLE-targeted `access_grants` for leadership allowlist; idempotent migration; classifier reference module; tests.

**Not in scope:** organization-wide official document read (see **OO-SEC-002**); UDE; OO domain model; lifecycle; auth projection semantics; frontend; Personnel Orders; task routing; position catalog; Platform Role renaming.

## Architecture (ratified 2026-07-13)

After additional product review, the following distinctions are **mandatory**:

| Contour | Purpose | OO-SEC-001 |
|---|---|---|
| **Leadership workspace read** | Read-only access to intake/editorial preparation contour for managers | **This WP** |
| **Organization-wide official read** | Read-only access to signed/registered/published orders for all active employees | **OO-SEC-002** (planned) |

**`OPERATIONAL_ORDERS_INTAKE_READ` is NOT organization-wide official read.**

- It must **not** be mass-granted to all employees.
- It opens the **preparation workspace** and **pre-publication document aggregate**, not a staff publication contour.
- All-employee official read requires a **separate permission**, a **publication boundary** in document lifecycle, and a **separate security contour** (OO-SEC-002).

## Problem

After OO-UI-001B, the «Производственные приказы» sidebar is correctly gated by `has_operational_orders_read`. Most organizational leaders lacked `OPERATIONAL_ORDERS_INTAKE_READ` and could not see the section or monitor preparation progress in their org scope.

## Solution

Idempotent Alembic migration `b2c3d4e5f6a7` inserts ROLE-targeted `access_grants` for each **approved** leadership `public.roles.code` that exists and is active at migration time.

Authority remains in `access_grants` — no runtime bypass in `platform_role_classification.py`.

## What `OPERATIONAL_ORDERS_INTAKE_READ` actually grants

### Backend semantics

Read-only access to **in-scope** draft workspaces and document aggregates. Gates section visibility via `has_operational_orders_read`. **No state mutations.**

Enforcement: `can_read_workspace()` → `can_read_document()` → `can_read_editorial()` → `can_read_signature_readiness()` (fallback chain).

### Data exposed (workspace preparation contour)

| Data category | Exposed? | Notes |
|---|---|---|
| Workspace list (summary) | Partial | Default list filtered to own workspaces; any in-scope workspace readable by ID |
| Submitted text | **Yes** | `blocks[].submitted_text`, `workspace_effective_text` |
| Clarifications | **Yes** | Full clarification records |
| Editorial package | **Yes** | Translation assignments, confirmations, reconciliations |
| Provenance / audit | **Yes** | Preparation provenance and workspace audit trail |
| Draft workspaces (pre-promotion) | **Yes** | Full draft aggregate |
| Pre-signature documents | **Yes** | `CREATED`, `READY_FOR_SIGNATURE` document aggregate and `official_text` snapshots |
| Signing readiness metadata | **Yes** | Via `can_read_document` fallback |

### Data NOT exposed (without additional permissions)

| Action | Required permission |
|---|---|
| Create workspace | `OPERATIONAL_ORDERS_INTAKE_CREATE` |
| Accept, edit blocks, validate intake, resolve clarifications | `OPERATIONAL_ORDERS_INTAKE_OPERATE` |
| Translation/editorial mutations | `OPERATIONAL_ORDERS_TRANSLATION_*`, `CONTENT_CONFIRM`, `RECONCILE`, `EDITORIAL_READY` |
| Promote | `OPERATIONAL_ORDERS_PROMOTE` |
| Assign signing authority | `OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY` |
| Mark ready for signature | `OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE` |
| Return from signature | `OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE` |

### Why unsuitable for all employees

Mass grant of `OPERATIONAL_ORDERS_INTAKE_READ` would expose **every active employee** to:

- intake workspaces and submitted text before publication;
- editorial preparation data (translations, confirmations, reconciliations);
- internal provenance and audit of document preparation;
- unsigned / pre-signature document versions.

This violates the product policy: only leaders and designated operators may access the preparation contour.

## Target access matrix (context)

### A. All active employees — **not OO-SEC-001**

Read-only access to **official** orders after signing/registration/publication only. Requires OO-SEC-002 (separate permission + publication state).

### B. Leadership — **OO-SEC-001**

Approved leadership Platform Roles receive `OPERATIONAL_ORDERS_INTAKE_READ` (workspace preparation read).

**Do not receive automatically:** intake operate, translation, editorial, reconciliation, promote, mark ready, signing authority.

### C. Specialized operators — separate grants

Action permissions issued individually via `access_grants` per actual duty.

## Approved allowlist (`roles.code`)

| Code | Name (seed) | Category | Include | Rationale |
|---|---|---|---|---|
| `DIRECTOR` | Директор | Director | **YES** | Organization director |
| `DEP_MED` | Зам по лечебной работе | Deputy director | **YES** | Hospital deputy |
| `DEP_OUTPATIENT_AUDIT` | Зам по диспансеру и внутр экспертизе | Deputy director | **YES** | Hospital deputy |
| `DEP_ADMIN` | Зам по адм вопросам | Deputy director | **YES** | Hospital deputy |
| `DEP_STRATEGY` | Зам по стратегии | Deputy director | **YES** | Hospital deputy |
| `STAT_HEAD` | Руководитель отдела статистики | Department head | **YES** | Department leadership |
| `STAT_HEAD_DEPUTY` | зам рук-ля отдела статистики | Deputy head | **YES** | Deputy department leadership |
| `QM_HEAD` | Руководитель ОВЭиПД | Service head | **YES** | Service leadership |
| `HR_HEAD` | Руководитель отдела кадров | Department head | **YES** | Department leadership |
| `ACC_HEAD` | Главный бухгалтер | Service head | **YES** | Accounting service leadership |
| `ECON_HEAD` | Руководитель | Department head | **YES** | Economics department leadership |

Canonical source: `db/init/020_seed_roles_users_employees.sql`, `scripts/pilot/qm_roles_users_bootstrap.sql`.

## Excluded roles

| Code | Category | Include | Rationale |
|---|---|---|---|
| `STAT_EROB_INPUT` | Specialist | NO | Executor, not management |
| `STAT_EROB_OUTPUT` | Specialist | NO | Executor |
| `STAT_EROB_ANALYTICS` | Analyst | NO | Specialist |
| `QM_HOSP` | Expert | NO | Functional expert |
| `QM_AMB` | Expert | NO | Functional expert |
| `QM_COMPLAINT_REG` | Expert | NO | Functional expert |
| `QM_COMPLAINT_PAT` | Expert | NO | Functional expert |
| `QM_TRAINING_EXPERT` | Expert | NO | Training expert |
| `ECON_1` / `ECON_2` / `ECON_3` | Specialist | NO | Staff economists |
| `ADMIN` / `SYSTEM_ADMIN` | System | NO | Already `is_privileged` — redundant OO-SEC-001 grant |
| `LAB_HEAD` (hypothetical) | Unreviewed | NO | Fail-closed until explicit allowlist update |

Policy uses **`roles.code` only** — not `roles.name`, not `positions.name`.

## RBAC implementation

```
access_grants (target_type=ROLE, target_id=roles.role_id)
    ↓
list_active_access_role_codes(user_id)
    ↓
has_admin_permission(uid, OPERATIONAL_ORDERS_INTAKE_READ)
    ↓
/auth/me → has_operational_orders_read
    ↓
Sidebar «Производственные приказы» (OO-UI-001B, no frontend changes in OO-SEC-001)
```

## Migration

| Field | Value |
|---|---|
| Revision | `b2c3d4e5f6a7` |
| Down revision | `a1b2c3d4e5f6` |
| File | `alembic/versions/b2c3d4e5f6a7_oo_sec_001_leadership_oo_read_grants.py` |
| Reason marker | `OO-SEC-001: approved leadership workspace read policy` |

### Idempotency

`NOT EXISTS` guard on active `(access_role_id, target_type=ROLE, target_id)` — safe to re-run.

### One-time migration limitation

**Important:** Alembic migration grants only roles **existing in the database at upgrade time**. Platform Roles created later do **not** receive grants automatically. Each new leadership role requires:

1. Explicit allowlist update in `app/security/platform_role_classification.py`;
2. New migration or admin ROLE grant provisioning;
3. Tests and documentation update.

### Downgrade semantics

Downgrade deletes **only** grants matching **all** of:

- `access_roles.code = OPERATIONAL_ORDERS_INTAKE_READ`
- `target_type = ROLE`
- `roles.code` in approved allowlist
- `reason = OO-SEC-001: approved leadership workspace read policy`

Manually issued grants with different `reason` are preserved.

## Python classifier

`app/security/platform_role_classification.py`:

| Symbol | Purpose |
|---|---|
| `LEADERSHIP_PLATFORM_ROLE_CODES` | Approved allowlist (authority reference for migration) |
| `is_approved_leadership_workspace_read_role()` | Policy check for tests/docs |
| `looks_like_leadership_platform_role()` | Diagnostic only — **not** access authority |
| `find_potential_leadership_codes_missing_from_allowlist()` | Seed drift detection |

## Permissions NOT granted

Translation, editorial, promote, ready-for-signature, signing authority — unchanged.

## HR regression

`HR_HEAD` retains `HR_ENROLLMENT_MANAGER` (ADR-045) and additionally receives `OPERATIONAL_ORDERS_INTAKE_READ`. HR permission alone does not imply OO access.

## Confidentiality extension point

The baseline policy «all active employees read official orders» (OO-SEC-002) applies to **ordinary general operational orders** only.

Future restricted orders (personal data, limited-distribution service information, investigations, security, medical confidentiality, financial/procurement restrictions) will require a **classification/access scope** extension on the official-read contour. That mechanism is **out of scope** for OO-SEC-001 and OO-SEC-002 MVP; only the extension point is recorded here.

## Related work

| WP | Title | Relationship |
|---|---|---|
| **OO-SEC-002** | Organization-Wide Official Orders Read Policy | Next security contour — separate permission, publication boundary, active-employee grants |

## Test matrix

| Case | Expected |
|---|---|
| Approved leadership role + grant | `has_operational_orders_read == true` |
| `QM_HOSP` / `ECON_1` | `false` |
| `LAB_HEAD` (not in allowlist) | `false` (fail-closed) |
| `HR_HEAD` | HR admin + OO read |
| HR-only custom role | HR admin, no OO read |
| `SYSTEM_ADMIN` | privileged, no OO-SEC-001 grant row |
| Migration re-run | No duplicate active grants |

Tests: `tests/test_oo_sec_001_leadership_read_policy.py`

## Adding a new leadership Platform Role (future)

1. Add `roles.code` to org catalog (existing process).
2. Policy review — confirm leadership category.
3. Add code to `LEADERSHIP_PLATFORM_ROLE_CODES` in `platform_role_classification.py`.
4. Create idempotent migration (or admin grant) with `target_type=ROLE`.
5. Extend tests and this document.
6. Deploy `alembic upgrade head`.

Do **not** rely on SQL `LIKE` predicates for security grants.

## Readiness

Approved for commit. Implements **Leadership Workspace Read Policy** only. Organization-wide official read is **OO-SEC-002** (separate WP).
