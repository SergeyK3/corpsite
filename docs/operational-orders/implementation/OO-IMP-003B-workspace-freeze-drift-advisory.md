# OO-IMP-003B — Workspace Freeze, Fingerprint Drift Detection & Revision Advisory

**Status:** Implemented (local)  
**Revision:** `z0a1b2c3d4e5`  
**Down revision:** `y9z0a1b2c3d4`  
**Package:** `app/operational_orders/`  
**Ratification:** [OO-IMP-003A](../architecture/OO-IMP-003A-document-identity-ratification.md)

Completes the architectural contour around OO-IMP-003 per UDE-004/005: workspace ceases to be editorial source of truth after promotion; re-promote remains idempotent birth replay with optional drift advisory.

---

## Design summary

After successful promotion:

```text
EDITORIAL_PACKAGE_READY
  ↓ promote (birth event, once)
DOCUMENT_PROMOTED (read-only workspace)
  ↓ re-promote
existing Document + advisory (if fingerprint drift)
```

- **No Version 2** in this WP.
- **No Revision Command** — advisory only (`revision_recommended`).
- Workspace lifecycle stays independent from Document lifecycle.

---

## Freeze model

| Concept | Implementation |
|---|---|
| Frozen stage | `DOCUMENT_PROMOTED` on `operational_order_draft_workspaces.stage` |
| Frozen check | `is_workspace_frozen()` / `assert_workspace_not_frozen()` |
| Error | `OperationalOrderWorkspaceFrozenError` (`OO_WORKSPACE_FROZEN`, HTTP 409) |
| Repair path | `ensure_workspace_frozen_if_promoted()` backfills stage when document exists (pre-003B data) |

All mutating intake and editorial commands call freeze guard **before** business logic. Privileged users cannot bypass freeze.

### Blocked mutations (frozen workspace)

- Effective text edits, block add, intake validate (mutating), clarification resolve
- Translation assignment lifecycle
- Content confirmations (create/revoke)
- Bilingual reconciliations (create/invalidate)
- Editorial package ready

**READ** endpoints remain available.

---

## Drift detection model

`WorkspaceDriftDetector.detect_workspace_drift()` compares:

| Fingerprint | Source |
|---|---|
| `current_workspace_fingerprint` | Live workspace version + blocks + reconciliations |
| `promotion_workspace_fingerprint` | `operational_order_documents.created_from_workspace_fingerprint` |

Equal fingerprints → silent idempotent replay.  
Different fingerprints → `workspace_drift_detected` + `revision_recommended` (no new document, no Version 2).

---

## Advisory model

Re-promote response (`PromotionResultOut`, HTTP **200**):

| Field | Meaning |
|---|---|
| `idempotent_replay` | Existing document returned |
| `workspace_frozen` | Workspace is read-only |
| `workspace_drift_detected` | Live fingerprint ≠ promotion fingerprint |
| `revision_recommended` | Future Revision Command required to publish changes |
| `document_id` | Existing legal identity |
| `promotion_id` | Original birth event |
| `validation.issues` | OO314/OO315 always on replay; OO311/OO313 when drift |

No Revision entity, no new Workspace, no new Promotion record.

---

## Promotion replay

```text
POST /workspaces/{id}/promote (document already exists)
  ↓
ensure_workspace_frozen_if_promoted (repair)
  ↓
detect_workspace_drift
  ↓
append provenance: PROMOTION_REPLAY [+ WORKSPACE_DRIFT_DETECTED]
  ↓
append audit: PROMOTION_REPLAY [+ REVISION_ADVISORY_RETURNED]
  ↓
return existing document + advisories (HTTP 200)
```

First promotion still runs full OO-IMP-003 factory, then calls `freeze_workspace()`.

---

## Validation rules (OO311–OO315)

| Code | Severity | When |
|---|---|---|
| OO311 | WARNING | Workspace drift detected on replay |
| OO312 | ERROR | Mutating command on frozen workspace |
| OO313 | WARNING | Revision required (paired with OO311) |
| OO314 | INFO | Promotion replay |
| OO315 | INFO | Workspace already promoted |

OO301–OO310 unchanged (promotion preconditions).

---

## API changes

### `POST /api/operational-orders/workspaces/{workspace_id}/promote`

Response extended with advisory fields (see above). HTTP 200 for both first promotion and replay.

No separate drift inspection endpoint — drift is surfaced on replay per current API conventions.

### Mutating endpoints

Frozen workspace mutations return HTTP **409** with `OO_WORKSPACE_FROZEN`.

---

## Provenance (append-only)

New actions:

- `WORKSPACE_PROMOTED`
- `WORKSPACE_FROZEN`
- `PROMOTION_REPLAY`
- `WORKSPACE_DRIFT_DETECTED`

---

## Audit (append-only)

Draft workspace audit:

- `WORKSPACE_FROZEN`
- `PROMOTION_REPLAY`
- `REVISION_ADVISORY_RETURNED`

Promotion audit: same three actions.

---

## Permissions

No new permissions. Re-promote uses existing `OPERATIONAL_ORDERS_PROMOTE` (allowed for `DOCUMENT_PROMOTED` stage).

---

## Migration

`z0a1b2c3d4e5_oo_imp_003b_workspace_freeze_drift.py`:

- Extends workspace stage CHECK with `DOCUMENT_PROMOTED`
- Extends provenance, draft audit, promotion audit CHECK constraints
- Backfills `DOCUMENT_PROMOTED` for workspaces with a **completed** promotion aggregate

---

## Migration Backfill Safety Review (OO-IMP-003B-R1)

### Current backfill criterion

Workspaces are set to `DOCUMENT_PROMOTED` when all of the following hold:

1. `operational_order_documents` row exists for the workspace
2. Linked `operational_order_promotions.status = 'COMPLETED'`
3. Bidirectional link: `promotions.document_id = documents.id` and `documents.promotion_id = promotions.id`
4. Version 1 snapshot exists: `operational_order_document_versions.version_number = 1`

```sql
UPDATE operational_order_draft_workspaces AS w
SET stage = 'DOCUMENT_PROMOTED'
WHERE stage <> 'DOCUMENT_PROMOTED'
  AND EXISTS (
      SELECT 1
      FROM operational_order_documents d
      INNER JOIN operational_order_promotions p
        ON p.id = d.promotion_id AND p.workspace_id = d.workspace_id
      INNER JOIN operational_order_document_versions v
        ON v.document_id = d.id AND v.version_number = 1
      WHERE d.workspace_id = w.workspace_id
        AND p.status = 'COMPLETED'
        AND p.document_id = d.id
  )
```

### Authoritative source of completed Promotion

**Document + Promotion (COMPLETED) + Version 1 snapshot**, with bidirectional `document_id`/`promotion_id` linkage.

- **Document** — legal identity (`DocumentId`) born by promotion
- **Promotion `COMPLETED`** — birth event finished (not merely `STARTED` or `FAILED`)
- **Version 1** — immutable snapshot materialized (guards partial aggregates)
- Promotion audit `PROMOTION_COMPLETED` is supporting evidence only, not the structural gate

### Scenario analysis

| Scenario | Backfill result | Expected | Correct? |
|---|---|---|---|
| **A** Document + completed Promotion + V1 | Frozen | Frozen | Yes |
| **B** Document without Promotion | Impossible (FK `documents.promotion_id NOT NULL`) | N/A | Yes |
| **C** Promotion without Document | Not frozen | Not frozen | Yes |
| **D** Partial / aborted promotion (STARTED, no document) | Not frozen | Not frozen | Yes |
| **D** Partial manual insert (document, promotion not COMPLETED) | Not frozen | Not frozen | Yes (R1 fix) |
| **E** Manual inconsistent rows | Frozen only when full completed aggregate present | Conservative freeze | Yes |

### Production safety (PromotionService only)

Official `PromotionService` commits document, version, localizations, and `promotions.status = COMPLETED` in a **single transaction**. Therefore every production document row from the service satisfies the tightened criterion. R1 does not change behaviour for valid service-created data.

### Damaged manual SQL data

- Document row with `STARTED` promotion → **not** frozen (pre-R1 document-only backfill would have over-frozen)
- `COMPLETED` promotion without `document_id` link → not frozen
- Document without Version 1 → not frozen

### Idempotency

- `upgrade` → `downgrade` → `upgrade`: backfill is idempotent (`WHERE stage <> 'DOCUMENT_PROMOTED'`); downgrade resets all `DOCUMENT_PROMOTED` → `EDITORIAL_PACKAGE_READY` (known stage-loss on downgrade); re-upgrade re-applies freeze from aggregate evidence only.

### R1 change

Initial 003B backfill used document existence only. R1 tightened to completed-promotion aggregate proof without changing promotion semantics, API, or runtime freeze logic.

---

## Tests

`tests/operational_orders/test_workspace_freeze.py`:

- Promotion freezes workspace
- Edit / translation / confirmation / reconciliation / clarification blocked
- Re-promote without drift (idempotent replay)
- Re-promote with drift (revision advisory)
- READ still works

Updated `test_promotion.py`: post-promotion edit returns 409.

---

## Deferred scope

- Revision Command, Version 2+, Business Intent
- Replacement / superseding documents
- Signing, registration, execution, PDF/HTML, frontend UI

---

## Readiness for OO-IMP-004

OO-IMP-003B closes workspace/document boundary debt from OO-IMP-003. Document aggregate and Version 1 snapshot remain stable. Next WP can introduce Revision Command without re-promote ambiguity.
