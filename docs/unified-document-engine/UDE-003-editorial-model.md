# UDE-003 — Editorial Model

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-005; PO-EDIT-001 R1–R12

---

## 1. Text Layers

| Layer | Definition | Editorial reality? | History? | Promoted to Document? |
|---|---|---|---|---|
| **Submitted Text** | As received at intake | No — reference only | **Yes** — immutable | Provenance ref only |
| **Generated Text** | System output from semantic | Derived | Regenerable snapshot | Yes — as generated layer |
| **Manual Text** | Operator-authored without generation | Yes — when MANUALLY_AUTHORED | Audited | Yes — via override or effective |
| **Translated Text** | Locale derived from another | Yes — interim | Provenance chain | Yes — in effective chain |
| **Effective Text** | `override ?? generated` | **Yes — primary editorial reality** | Current authority pre-sign | **Yes — primary** |
| **Official Text** | Effective at OFFICIAL_DRAFT_READY | **Yes — promotion authority** | Frozen snapshot | **Yes — becomes Document effective** |

```text
Submitted (history) ──► Generated ──► Manual override ──► Effective ──► Official ──► Signed
                              ▲              │
                              └── regenerate ┘ (override preserved, stale)
```

---

## 2. Editorial Reality vs History

| Category | Layers | Rule |
|---|---|---|
| **Editorial reality** | Effective, Official (at readiness), workspace effective during edit | Drives promotion and signing prep |
| **Derived** | Generated | Regenerated from semantic; not sole authority |
| **Historical** | Submitted | Never deleted; never auto-promoted |
| **Process** | Translated, Manual | Becomes effective through explicit save + provenance |

---

## 3. Per-Block Editorial State

```text
EditorialBlock (conceptual — per locale × section/item)
├── submitted_text_ref          # optional link to immutable submitted
├── generated_text              # snapshot + generator_version + fingerprint
├── override_text               # nullable manual layer
├── effective_text              # computed: override ?? generated
├── is_manually_edited          # override present
├── staleness_state             # CURRENT | STALE | REVIEW_REQUIRED | UNKNOWN
├── text_provenance
└── editorial_completeness      # required for promotion?
```

---

## 4. Effective Text Semantics

```text
effective_text = override_text ?? generated_text
is_manually_edited = override_text is not null
```

| Case | Effective source |
|---|---|
| No override | generated_text |
| Override present | override_text |
| Override cleared (confirmed command) | generated_text |
| Submitted only (pre-generation) | workspace_effective (UDE-002 Stage 2) until generation runs |

**Rule EM1:** Never store single `edited_text` without generated snapshot (PO-EDIT-001).  
**Rule EM2:** Submitted text never becomes effective without explicit editorial acceptance.

---

## 5. Official Text

**Official Text** = Effective Text at the moment OfficialDraftPackage is frozen.

- Same bytes as effective per block at readiness
- Becomes Document LocaleRepresentation.EffectiveText at promotion
- After SIGNED → Signed Snapshot (immutable, ADR-UDE-009)

---

## 6. Manual vs Generated Interaction

| Action | Generated | Override | Effective | Staleness |
|---|---|---|---|---|
| Initial generate | Set | — | = generated | CURRENT |
| Manual edit | Unchanged | Set | = override | CURRENT if fingerprint match |
| Semantic change | Stale | Kept | = override | STALE or REVIEW_REQUIRED |
| Regenerate no override | Updated | — | = generated | CURRENT |
| Regenerate with override | Updated | Kept | = override | REVIEW_REQUIRED |
| Clear override | Current | Cleared | = generated | CURRENT |

---

## 7. Transfer at Promotion

| Layer | In Document after promotion |
|---|---|
| Submitted | Not copied as text; provenance.derived_from may reference |
| Generated | LocaleRepresentation.GeneratedText |
| Override | Encoded in effective chain + provenance MANUALLY_EDITED |
| Effective / Official | LocaleRepresentation.EffectiveText |
| Provenance | LocaleRepresentation.TextProvenance |

---

*Diagram: [`diagrams/generated-to-effective-flow.svg`](./diagrams/generated-to-effective-flow.svg)*
