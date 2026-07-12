# UDE-003 — Localization Core

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-006; OP-RES-005A; PO-EDIT-001 R7

---

## 1. Purpose

**Localization Core** is the shared logical component responsible for per-locale editorial state, bilingual consistency, and staleness propagation within Editorial & Localization Core.

It operates on Draft Workspace (pre-promotion) and Document Aggregate (post-promotion) through the same contracts.

---

## 2. Responsibility

| In scope | Out of scope |
|---|---|
| Locale lifecycle state (CURRENT, STALE, REVIEW_REQUIRED, UNKNOWN) | Machine translation engine |
| Translation state process stages | Task execution |
| Bilingual consistency checks (BC*) | Document lifecycle transitions |
| Locale completeness for promotion | PDF rendering |
| Staleness propagation RU→KK | HR apply logic |
| Mandatory locale policy | Draft Intake acceptance |
| Localization review tracking | Content author confirmation (Editorial Core coordinates) |

---

## 3. Locale Representation Architecture

```text
LocaleBundle (per Document or Workspace)
├── locale_code                       # ru | kk | ...
├── mandatory_for_promotion           # policy flag
├── localization_lifecycle_state      # aggregate per locale
├── translation_state               # generated→translated→reviewed→reconciled
├── drafting_path                   # SYMMETRIC | RU_FIRST | SUBMITTED_INTAKE
├── source_language                 # editorial primary
└── editorial_blocks[]              # per section/item × this locale
      ├── section_ref / item_ref
      ├── generated_text
      ├── override_text
      ├── effective_text
      ├── text_provenance
      ├── staleness_state
      └── editorial_completeness
```

### 3.1 Boundaries

| Boundary | Rule |
|---|---|
| Locale vs semantic | Semantic model is language-independent; locales are projections |
| Locale vs section | Each text-bearing section/item has N locale blocks (one per active locale) |
| Document-level locale aggregate | Derived from mandatory locale block states |
| Attachment locale | Attachments may have own language metadata |

### 3.2 Relation to semantic model

- Semantic change → invalidates generated in **all** locales (or affected items)
- Translation derives from source locale effective at derivation time
- BC checks verify semantic parity assisted — not free translation

---

## 4. Locale Lifecycle

| State | Meaning |
|---|---|
| **CURRENT** | Aligned with semantic fingerprint; no blocking staleness |
| **STALE** | Source changed after derivation; effective may be outdated |
| **REVIEW_REQUIRED** | Structural/terminology drift; human review needed |
| **UNKNOWN** | Legacy import; treat as REVIEW_REQUIRED until resolved |

Process stages (orthogonal): `generated` → `translated` → `reviewed` → `reconciled` → `waived`

---

## 5. Mandatory Locales

| Policy | Default |
|---|---|
| Org bilingual | ru + kk mandatory for promotion |
| Missing KK at intake | Explicit flag → translation workflow |
| Waiver | Audited; non-mandatory locale only |

---

## 6. Bilingual Consistency (summary)

Detail in main document §12. Checks BC001–BC025 from OP-RES-005A.

| Category | Examples |
|---|---|
| Blocking | BC001 item count, BC002 numbering, BC013–BC016 semantic parity (assisted), BC019 completeness, BC020 placeholders, BC023 ru_change_after_kk |
| Warning | BC006 block order, BC022 calque, BC024 structural drift |
| Informational | BC025 cross-file pair (research) |

---

## 7. Staleness Propagation

```text
RU effective change
  → KK TRANSLATED blocks: STALE (BC023)
  → KK GENERATED blocks: regenerate or REVIEW_REQUIRED
  → Document-level locale aggregate: blocks promotion if mandatory

Semantic item change
  → All locales for that item block: fingerprint mismatch
  → Overrides: STALE or REVIEW_REQUIRED
```

---

## 8. Localization Core vs Editorial Core

| Editorial Core | Localization Core |
|---|---|
| Structure, ordering, effective resolution | Per-locale state, BC checks |
| Regeneration orchestration | Staleness propagation |
| Manual override | Translation provenance |
| Section registry | Mandatory locale policy |

**Composition:** Editorial Core invokes Localization Core for locale mutations and validation; neither depends on specialization runtime.

---

*Matrix: [`data/UDE-003-localization-matrix.csv`](./data/UDE-003-localization-matrix.csv)*  
*Diagram: [`diagrams/localization-core.svg`](./diagrams/localization-core.svg)*
