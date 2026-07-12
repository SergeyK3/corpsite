# UDE-002 — Intake Validation

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: OP-RES-006A §11; I001–I026

---

## 1. Purpose

Define intake validation for Draft Intake — **without using Document lifecycle**. Validation governs acceptance into Draft Workspace and progression through Workspace stages.

---

## 2. Validation Does NOT Use Lifecycle

| Uses | Does not use |
|---|---|
| WorkspaceState (conceptual) | DocumentLifecycleState |
| IntakeValidationState | READY_FOR_SIGNATURE |
| Editorial Substate (derived) | REGISTERED, SIGNED, VOIDED |

Intake validation answers: **"May we open a Workspace?"** and **"May we advance Workspace stage?"** — not **"May we sign?"**

---

## 3. Validation Layers

| Layer | Scope | Examples |
|---|---|---|
| **Metadata** | Authorship, kind, units | I001–I006 |
| **Structure** | Shell detectability | I007–I013 |
| **Localization** | Language presence, parity | I019–I022 |
| **Semantic completeness** | Executors, deadlines, objects | I014–I018 |
| **Attachment completeness** | Required attachments | I013 |
| **Provenance completeness** | Submitter, author, origin | I023–I026 |
| **Content ownership** | Author ≠ operator ≠ submitter | I002, I024 |
| **Translation readiness** | KK quality, missing flags | I020–I022 |

---

## 4. Severity Model

| Severity | Effect | Symbol |
|---|---|---|
| **Blocking (error)** | Cannot accept intake or cannot advance stage | `blocker` |
| **Warning** | May proceed; logged; may need review | `warning` |
| **Clarification required** | Progression paused until resolved; not rejection | `clarification` |

**Clarification required** is neither error nor warning — it triggers ClarificationRequest without abandoning Workspace.

---

## 5. Intake Acceptance vs Workspace Progression

### 5.1 Intake Acceptance (Submitted → Workspace Created)

Minimum blockers must pass:

- I001–I004 (metadata)
- I007, I010 (structure minimum)
- I019–I020 (localization policy)
- I023–I024, I026 (provenance)
- I018 (no contradictions)

Warnings and clarifications may be **deferred** to Workspace editorial stage.

### 5.2 Workspace Stage Gates

| Target stage | Additional gates |
|---|---|
| EDITORIAL_PROCESSING | Acceptance passed |
| SEMANTIC_ENRICHMENT | Structure warnings resolved or waived |
| LOCALIZATION_PROCESSING | Semantic clarifications resolved or waived |
| CONTENT_CONFIRMATION | Mandatory locales present; translation reviewed |
| OFFICIAL_DRAFT_READY | All blockers clear; confirmations complete |
| DOCUMENT_PROMOTED | Official draft package validated (handoff to UDE-003/005) |

---

## 6. Check Catalog (Extended from I001–I026)

| ID | Layer | Name | Severity | Clarification? |
|---|---|---|---|---|
| I001 | metadata | initiator_declared | error | No |
| I002 | metadata | content_author_declared | error | No |
| I003 | metadata | submitting_unit_declared | error | No |
| I004 | metadata | document_kind_identified | error | Yes if ambiguous |
| I005 | metadata | signatory_hint_present | warning | Yes |
| I006 | metadata | basis_reference_present | warning | Yes |
| I007 | structural | title_present | error | No |
| I008 | structural | preamble_or_basis_detected | warning | Yes |
| I009 | structural | operative_formula_detected | warning | Yes |
| I010 | structural | numbered_items_present | error | No |
| I011 | structural | control_clause_detected | warning | Yes |
| I012 | structural | signature_block_hint | warning | Yes |
| I013 | structural | attachment_refs_valid | error | Yes |
| I014 | semantic | executors_identifiable | warning | Yes |
| I015 | semantic | deadlines_identifiable | warning | Yes |
| I016 | semantic | managed_objects_identifiable | warning | Yes |
| I017 | semantic | controller_identifiable | warning | Yes |
| I018 | semantic | internal_contradictions | error | No |
| I019 | localization | ru_present | error | No |
| I020 | localization | kk_present_or_declared_missing | error | No |
| I021 | localization | structural_parity_ru_kk | warning | Yes |
| I022 | localization | translation_quality_unknown | warning | Yes |
| I023 | provenance | submitter_recorded | error | No |
| I024 | provenance | content_author_recorded | error | No |
| I025 | provenance | translation_origin_recorded | warning | Yes |
| I026 | provenance | edit_chain_preserved | error | No |

### Workspace-only checks (W2xx — conceptual)

| ID | Layer | Name | Severity |
|---|---|---|---|
| W201 | semantic | enrichment_complete | warning→error at promotion |
| W202 | localization | mandatory_locale_current | error at OFFICIAL_DRAFT_READY |
| W203 | confirmation | content_confirmation_pending | blocker at promotion |
| W204 | clarification | open_clarifications | blocker at promotion |

---

## 7. Validation Result Shape

Uses UDE-001 **ValidationResult** contract:

```text
IntakeValidationResult
├── scope: intake | workspace_stage
├── findings[]: { code, severity, message, clarification_required }
├── blocking: boolean (derived)
└── waiver_allowed: boolean (policy hook; audited)
```

---

## 8. Specialization Hooks

| Hook | PO | OO |
|---|---|---|
| Kind-specific metadata | employee ref optional at intake | submitting_unit mandatory |
| Semantic checks | event type hints | obligation/controller hints |
| Localization | symmetric default | submitted_intake + missing-KK flag |

---

*Matrix: [`data/UDE-002-validation-matrix.csv`](./data/UDE-002-validation-matrix.csv)*  
*Diagram: [`diagrams/intake-validation-flow.svg`](./diagrams/intake-validation-flow.svg)*
