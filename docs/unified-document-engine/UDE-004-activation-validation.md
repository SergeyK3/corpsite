# UDE-004 — Activation Validation

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Validation Layer Separation

| Layer | When | Owner | Examples |
|---|---|---|---|
| **Editorial Validation** | Before package assembly | UDE-003 | E101–E115, BC P0 |
| **Promotion / Activation Validation** | At activation command | UDE-004 | P101–P110 |
| **Lifecycle Validation** | At lifecycle transitions | UDE-005 | L101 READY gate, sign guards |

Editorial validation **must have passed** before OfficialDraftPackage exists. Activation validation **re-confirms** package integrity and activation policy — does not re-run full editorial suite.

---

## 2. Activation Validation (P-series)

| ID | Check | Severity | Blocks activation |
|---|---|---|---|
| P101 | official_draft_package_present | error | Yes |
| P102 | package_frozen_at_readiness | error | Yes |
| P103 | editorial_validation_clearance_attached | error | Yes |
| P104 | localization_mandatory_current | error | Yes |
| P105 | no_blocking_editorial_errors | error | Yes |
| P106 | promotion_readiness_flag_true | error | Yes |
| P107 | workspace_state_official_draft_ready | error | Yes |
| P108 | content_confirmation_satisfied | error | OO default; PO optional |
| P109 | workspace_not_already_promoted | error | Yes (idempotency) |
| P110 | document_kind_policy_allows_activation | error | Yes |
| P111 | package_integrity_checksum | error | Yes |
| P112 | specialization_preconditions | error | Per kind hook |

---

## 3. Relationship to E-series

| Rule | Description |
|---|---|
| AV1 | P103 requires E-series ValidationResult attached to package |
| AV2 | Activation does not re-execute BC checks — trusts package clearance + P111 integrity |
| AV3 | If package reopened for editorial edit → new package → new activation |

---

## 4. Specialization Hooks

| Hook | PO | OO |
|---|---|---|
| P108 confirmation | Optional / waived | Default required |
| P112 preconditions | employee refs valid | submitting_unit, control item |
| P110 kind | PersonnelOrder | OperationalOrder |

---

## 5. Failure Handling

| Outcome | Workspace | Document |
|---|---|---|
| P-series failure | Unchanged, OFFICIAL_DRAFT_READY | Not created |
| Partial failure (must not occur) | Rollback | Not created |
| Success | DOCUMENT_PROMOTED frozen | Created DRAFT |

Activation Audit: `PROMOTION_FAILED` with P-code findings.

---

*Diagram: [`diagrams/activation-validation-flow.svg`](./diagrams/activation-validation-flow.svg)*
