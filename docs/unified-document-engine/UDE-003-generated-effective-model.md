# UDE-003 — Generated ↔ Effective Model

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Lifecycle Chain

```text
Semantic Model
    ↓ generate
Generated Text
    ↓ optional manual edit
Manual Override
    ↓ resolve
Effective Text
    ↓ freeze at readiness
Official Text
    ↓ sign
Signed Snapshot
```

---

## 2. When Generated Becomes Stale

| Trigger | Generated stale? | Override behavior |
|---|---|---|
| Semantic fingerprint unchanged | No — CURRENT | Unchanged |
| Semantic input changed | New generate produces new generated | Override kept → REVIEW_REQUIRED |
| Scenario/registry version changed | Regenerate scope affected blocks | Override kept per block |
| Item added/removed | New items generated; removed items archived | Overrides on surviving items kept |
| Party/deadline changed | Item-level fingerprint change | Block-level STALE |
| Translation source (RU) changed | KK generated N/A; TRANSLATED blocks STALE | KK override kept |

**Generated itself** is replaced on regenerate — not marked stale. **Staleness applies to the editorial block state** when override exists and fingerprint diverges.

---

## 3. When Effective Rebuilds

| Event | Effective result |
|---|---|
| Save override | effective = override |
| Clear override (confirmed) | effective = generated |
| Regenerate, no override | effective = new generated |
| Regenerate, override kept | effective = override (unchanged wording) |
| Accept workspace effective (intake path) | effective promoted from workspace_effective after validation |
| Official package freeze | effective = official (immutable in package) |

Effective **does not auto-update** when override is STALE — operator must reconcile (regenerate, edit, or clear).

---

## 4. After Regeneration

```text
Regenerate command(scope: item | section | document)
  1. Compute new generated_text from semantic + registry version
  2. Update fingerprint_at_generation
  3. If override absent:
       effective ← generated; staleness ← CURRENT
  4. If override present:
       effective ← override (unchanged)
       staleness ← REVIEW_REQUIRED (fingerprint mismatch)
  5. Emit EditorialAuditEvent: REGENERATED
  6. Propagate locale staleness to derived TRANSLATED blocks (BC023)
```

---

## 5. Fingerprint Model

| Property | Purpose |
|---|---|
| source_fingerprint | Hash of semantic inputs affecting block |
| generator_version | Registry/template version |
| fingerprint_at_generation | Snapshot when generated last run |

```text
is_stale = (override present) AND (source_fingerprint != fingerprint_at_generation)
review_required = is_stale after regenerate with override kept
```

Aligned with PO-EDIT-001 §5.1 and PO-EDIT-002 review_status.

---

## 6. Scope of Regeneration

| Scope | Default | Use |
|---|---|---|
| **Item block** | Yes | Single item body/basis |
| **Section block** | Yes | Title, preamble |
| **Document-level** | Optional | Full regen — explicit command |
| **Post-sign** | **Forbidden** | ADR-UDE-009 |

---

## 7. Idempotency

Same semantic input + same generator_version + same registry → same generated_text.

---

*See also: [UDE-003-editorial-model.md](./UDE-003-editorial-model.md), PO-EDIT-001 R9*
