# UDE-005 — Lifecycle Validation

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define **L-series Lifecycle Validation** — third layer after Editorial (E*) and Promotion (P*).

```text
E* (UDE-003) → P* (UDE-004) → L* (UDE-005)
```

---

## 2. Validation Flow

```text
Lifecycle Command received
    → L001 valid state
    → L002 allowed transition
    → L003 authority
    → L004 not archived
    → L013 version current
    → L014 no concurrent transition
    → transition-specific L005–L012, L016–L020
    → specialization L021–L025
    → L015 idempotency resolution
    → commit or reject
```

Diagram: [`diagrams/lifecycle-validation-flow.svg`](./diagrams/lifecycle-validation-flow.svg)

---

## 3. Non-Waivable Blockers (shared)

| ID | Rule |
|---|---|
| L001 | valid_current_state |
| L002 | allowed_transition |
| L003 | actor_authority_present |
| L004 | document_not_archived |
| L010 | void_reason_present |
| L011 | void_kind_applicable |
| L013 | document_version_current |
| L014 | no_concurrent_transition |
| L016 | not_already_signed |
| L017 | not_already_registered |
| L018 | registration_number_conflict |

---

## 4. Waivable Blockers

| ID | Rule | Typical waiver |
|---|---|---|
| L005 | no_blocking_localization_state | Head waiver for REVIEW_REQUIRED |
| L006 | no_blocking_editorial_validation | Policy waiver with audit |
| L012 | attachments_consistent | Kind policy |
| L021 | content_confirmation_satisfied | OO author waiver |
| L023 | control_obligations_complete | OO commission waiver |

---

## 5. Warnings

Warnings do not block unless specialization elevates to error.

---

## 6. Specialization Checks

| ID | Specialization | Transition |
|---|---|---|
| L021 | OO content confirmation | MarkReady |
| L022 | PO employee readiness | MarkReady |
| L023 | OO control obligations | MarkReady |
| L024 | PO void chain | AnnulDocument |
| L025 | OO projection readiness | RegisterDocument |

---

## 7. Localization States Blocking READY

| Localization state | Blocks MarkReady |
|---|---|
| STALE | **Yes** (non-waivable default) |
| REVIEW_REQUIRED | **Yes** (waivable with audit) |
| CURRENT | No |
| GENERATION_FAILED | Yes (via L006/E*) |

---

*Catalog: [`data/UDE-005-validation-rules.csv`](./data/UDE-005-validation-rules.csv)*
