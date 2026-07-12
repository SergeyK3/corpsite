# UDE-004 — Publication Boundary

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define when an activated Document becomes **visible and operable** in the system — distinct from Workspace (pre-activation) and from REGISTERED (legal journal entry).

---

## 2. Publication States

| State | When | Visibility |
|---|---|---|
| **Pre-activation** | Workspace only | Not in document journal |
| **PublicationReady** | Activation success | Document discoverable |
| **JournalEligible** | Activation success | Appears in default journal list (DRAFT) |
| **Registered** | REGISTERED transition | Official number assigned |

---

## 3. What Becomes Available at Activation

| Capability | At activation | Notes |
|---|---|---|
| DocumentId lookup | **Yes** | Primary key |
| Open document detail | **Yes** | DRAFT editable |
| Journal list (default) | **Yes** | Unless filtered by status |
| Edit (DRAFT) | **Yes** | Editorial + structured |
| Lifecycle transitions | **Yes** | Via UDE-005 — READY etc. |
| Official registration number | **No** (default) | At REGISTERED |
| PDF official export | **Preview** | Non-immutable preview OK |
| Execution projection | **No** | At REGISTERED |
| Archive hide | **No** | archive_at null |

---

## 4. Registration Number Policy

| Policy | Kind |
|---|---|
| **Deferred (default)** | Number null at activation; assigned at REGISTERED |
| **Provisional** | Optional kind policy — draft number at activation (audited) |
| **Paper-first** | Number may pre-exist — specialization hook P112 |

OO/PO convergence: PO may have early number — adapter in UDE-006.

---

## 5. Registry Entry

At activation, Document Kind Registry records:

- DocumentId
- DocumentKind
- organization ref
- created_at
- lifecycle_state = DRAFT
- workspace_origin_ref (WorkspaceId)

Enables specialization policies and journal queries.

---

## 6. Publication Boundary vs Activation Boundary

```text
Editorial World          │  Predmetny World
─────────────────────────┼──────────────────────────
Draft Workspace          │  Document Aggregate
OfficialDraftPackage     │  DocumentId + DRAFT
                         │  PublicationReady
                         │  Journal visible
                         │  Lifecycle eligible
```

---

*Diagram: [`diagrams/publication-boundary.svg`](./diagrams/publication-boundary.svg)*
