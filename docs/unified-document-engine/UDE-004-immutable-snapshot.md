# UDE-004 — Immutable Snapshot Model

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-009; UDE-002 SoT Stage 5

---

## 1. Snapshot Types

| Snapshot | When | Mutable? | Legal immutability |
|---|---|---|---|
| **Submitted Snapshot** | Intake | No | N/A — history |
| **Editorial Workspace Snapshot** | During workspace | Yes | No |
| **Official Draft Package** | OFFICIAL_DRAFT_READY | Frozen | No — pre-Document |
| **Initial Effective Baseline (v1)** | Activation | **Yes while DRAFT** | No |
| **Signed Immutable Snapshot** | SIGNED / REGISTERED | **No** | **Yes** (ADR-UDE-009) |

---

## 2. What Activation Creates

At Activation, the system creates **Initial Effective Baseline (Document Version 1)** — **not** the legally immutable signed snapshot.

### Included in Initial Effective Baseline v1

| Content | Source |
|---|---|
| Effective text per locale block | OfficialDraftPackage.locale_bundle |
| Generated text per block | Package (for regen/stale tracking) |
| Text provenance | Package |
| Semantic model | Package semantic_model_snapshot |
| Structure + items | Package |
| Metadata authorship | Package draft_metadata |
| Fingerprint references | Per block |

### NOT included

| Excluded | Reason |
|---|---|
| Raw submitted text | Workspace archive |
| Workspace intermediates | Superseded |
| Signatory frozen fields | Populated at SIGNED |
| Registration metadata | At REGISTERED |
| PDF bytes | Renderer output |

---

## 3. Mutability Rules

| Phase | Effective baseline |
|---|---|
| DRAFT (post-activation) | Editable via Editorial Core |
| READY_FOR_SIGNATURE | Read-only (write lock) |
| SIGNED | **Immutable snapshot created** — baseline frozen |
| REGISTERED | Snapshot unchanged; registration metadata added |

**Rule IS1:** Activation baseline may change in DRAFT — increments document version on material editorial/semantic commit (UDE-005).  
**Rule IS2:** Legally immutable snapshot only at SIGNED (ADR-UDE-009).  
**Rule IS3:** Signed snapshot = effective bilingual text + signatory metadata + registration metadata at sign/register.

---

## 4. Relation to Effective Text

```text
At Activation:
  Document.LocaleRepresentation.EffectiveText ← Package official effective

At SIGNED:
  SignedSnapshot.effective ← copy of EffectiveText at sign moment (frozen)
  Post-sign edits forbidden — amendment document required
```

---

## 5. Version Distinction

| Version kind | Scope |
|---|---|
| Draft versions | Workspace SubmittedDraftSnapshot versions |
| Editorial versions | Per-block derived_from chain |
| **Document Version 1** | First aggregate baseline at activation |
| Document Version N | Material changes in DRAFT (UDE-005) |
| **Signed Version** | Immutable — tied to SIGNED event |

---

*Diagram: [`diagrams/immutable-snapshot-model.svg`](./diagrams/immutable-snapshot-model.svg)*
