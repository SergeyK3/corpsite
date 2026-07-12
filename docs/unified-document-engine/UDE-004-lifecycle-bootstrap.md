# UDE-004 — Lifecycle Bootstrap

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-004; UDE-001 DocumentLifecycleState

---

## 1. Purpose

Define how **Document Lifecycle** begins at Activation. Lifecycle at birth knows only **DRAFT** — READY, SIGNED, REGISTERED are future transitions owned by UDE-005 Lifecycle Core.

---

## 2. Bootstrap Rule

```text
Activation completes → DocumentLifecycleState := DRAFT
```

| Created at activation | NOT created at activation |
|---|---|
| DRAFT | READY_FOR_SIGNATURE |
| Lifecycle Audit stream | SIGNED, REGISTERED, VOIDED |
| Write-lock policy binding (DRAFT editable) | Archive flag (orthogonal; default active=false) |
| Editorial substate: none (lifecycle enum) | Execution lifecycle |

---

## 3. Lifecycle Independence

At bootstrap, three lifecycles are **initialized independently**:

| Lifecycle | State at activation |
|---|---|
| **Document** | DRAFT |
| **Localization** | Carried from package — CURRENT per mandatory locale (required for activation) |
| **Execution** | not_created |

Archive: `archived_at = null` (orthogonal).

---

## 4. Post-Activation Lifecycle Ownership

| Transition | Owner WP |
|---|---|
| DRAFT → READY_FOR_SIGNATURE | UDE-005 Lifecycle Core |
| READY → SIGNED | UDE-005 |
| SIGNED → REGISTERED | UDE-005 |
| VOIDED (CANCEL / ANNUL) | UDE-005 |
| Archive / restore | UDE-005 |
| Return-to-DRAFT | UDE-005 (PO-EDIT R2 compatible) |

Activation **only bootstraps** — does not implement transition guards beyond DRAFT entry.

---

## 5. Write Lock at Bootstrap

| State | Editorial writes | Structured writes |
|---|---|---|
| DRAFT (at birth) | Allowed | Allowed |
| READY+ | Forbidden (PO-EDIT R10) | Forbidden |

Write-lock policy attached at activation from shared LifecyclePolicy.

---

## 6. Localization Lifecycle at Bootstrap

Mandatory locales must be CURRENT at activation (precondition P103). Localization lifecycle **continues independently** after activation:

- DRAFT document + STALE locale → blocks READY (UDE-005), not activation
- At activation: locale states copied from package

---

## 7. PO Convergence Note

PO MVP creates document early (at order creation) — **before** UDE Workspace path. UDE-006 adapter may map:

- PO early creation → synthetic activation at first save
- OO path → full Workspace → Activation pipeline

Bootstrap semantics (DRAFT at birth) remain target for both.

---

*Matrix: [`data/UDE-004-lifecycle-bootstrap.csv`](./data/UDE-004-lifecycle-bootstrap.csv)*  
*Diagram: [`diagrams/lifecycle-bootstrap.svg`](./diagrams/lifecycle-bootstrap.svg)*
