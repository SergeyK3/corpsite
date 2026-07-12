# UDE-003 — Editorial Validation

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define validation performed by Editorial & Localization Core to assemble OfficialDraftPackage and gate promotion. **Distinct from** intake validation (I*) and **distinct from** full lifecycle validation (UDE-005).

---

## 2. Validation Layers

| Layer | Scope | Examples |
|---|---|---|
| **Structure** | Shell completeness | Title, preamble, formula, items region |
| **Editorial** | Block editorial rules | Effective present, no GENERATION_FAILED |
| **Ordering** | Section and item sequence | Monotonic numbering, BC002 |
| **Locale** | Per-locale completeness | Mandatory blocks per locale |
| **Generated/Effective** | Layer consistency | effective = override ?? generated |
| **Override consistency** | Orphan/stale overrides | STALE blocks flagged |
| **Mandatory sections** | Kind policy | Control block OO; basis when required |
| **Promotion readiness** | Aggregate gate | All blockers clear |

---

## 3. Check Catalog (E-series)

| ID | Layer | Name | Severity | Blocks promotion |
|---|---|---|---|---|
| E101 | structure | mandatory_sections_present | error | Yes |
| E102 | editorial | required_blocks_have_effective | error | Yes |
| E103 | locale | mandatory_locale_current | error | Yes |
| E104 | locale | review_required_cleared | error | Yes (waiver audited) |
| E105 | override | no_generation_failed | error | Yes |
| E106 | ordering | item_numbering_valid | error | Yes |
| E107 | ordering | section_order_valid | warning | No (unless waiver) |
| E108 | generated/effective | effective_derivation_valid | error | Yes |
| E109 | override | stale_override_acknowledged | warning | Yes if policy strict |
| E110 | mandatory | basis_present_when_required | error | Yes (PO policy) |
| E111 | mandatory | control_block_when_required | warning | OO policy |
| E112 | promotion | semantic_enrichment_complete | error | Yes |
| E113 | promotion | content_confirmation_satisfied | error | OO default |
| E114 | promotion | attachment_completeness | error | When required |
| E115 | promotion | open_clarifications_none | error | Yes |

### BC-series (localization — blocking subset)

| ID | Name | Severity |
|---|---|---|
| BC001 | item_count_match | error |
| BC002 | numbering_sequence | error |
| BC007 | date_values | error |
| BC010 | party_role_parity | error |
| BC013–BC016 | semantic_parity_assisted | error |
| BC019 | clause_completeness | error |
| BC020 | no_placeholders | error |
| BC023 | ru_change_after_kk | error |
| BC006, BC022, BC024 | various | warning |

---

## 4. Severity Model

| Severity | Promotion |
|---|---|
| **error** | Blocks OfficialDraftPackage assembly |
| **warning** | May proceed with audit; may block per policy |
| **info** | Logged only |

---

## 5. Validation vs Lifecycle

| Uses | Does not use |
|---|---|
| WorkspaceState OFFICIAL_DRAFT_READY | READY_FOR_SIGNATURE |
| PromotionReadiness | REGISTERED |
| Editorial ValidationResult | VOIDED |

Lifecycle READY gate (post-promotion) reuses BC + editorial checks — orchestrated by UDE-004.

---

## 6. Specialization Hooks

| Hook | PO | OO |
|---|---|---|
| E110 basis | basis_required per item type | Scenario-dependent |
| E111 control | N/A | Often required |
| E113 confirmation | Optional | Default required |
| Mandatory sections | title, preamble, item bodies | + control meta-item |

---

*Matrix: included in [`data/UDE-003-readiness.csv`](./data/UDE-003-readiness.csv)*  
*Diagram: [`diagrams/editorial-validation-flow.svg`](./diagrams/editorial-validation-flow.svg)*
