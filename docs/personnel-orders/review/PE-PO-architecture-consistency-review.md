# PE/PO Architecture Consistency Review

**Status:** Draft  
**Version:** 0.1  
**Scope:** PE-001, PE-002, PE-003, PO-001  
**Date:** 2026-07-09

---

# 1. Purpose

This document performs an architecture consistency review of the emerging Personnel Event / Personnel Orders documentation set.

Reviewed documents:

- PE-001 Personnel Event Engine Concept
- PE-002 Personnel State Model
- PE-003 Personnel Change Set Model
- PO-001 Personnel Orders Module Concept

The goal is to reduce duplication, define document boundaries, and establish a stable terminology baseline before continuing with PO-002 and data model design.

---

# 2. Document Roles

## PE-001 Personnel Event Engine Concept

Defines the architectural core:

- Personnel Event as primary business entity;
- Personnel Order as legal registration;
- Order Item as link between event and order;
- Order Document as file representation;
- Approval workflow as document lifecycle layer;
- related events such as leave, temporary assignment and allowance.

PE-001 is the top-level conceptual document.

---

## PE-002 Personnel State Model

Defines current employee state.

Personnel State is derived from Personnel Events and is used by:

- Employee Card;
- Position Cabinet;
- Personnel Orders;
- Reports;
- Analytics.

PE-002 should not describe order registration or document workflow.

---

## PE-003 Personnel Change Set Model

Defines the universal representation of change:

- field;
- old value;
- new value;
- effective period;
- source event.

PE-003 explains how Personnel Events transform Personnel State.

---

## PO-001 Personnel Orders Module Concept

Defines the Personnel Orders module as a consumer of PE-series concepts.

PO-001 should reference PE-001 / PE-002 / PE-003 instead of redefining the same model in detail.

---

# 3. Terminology Baseline

| Term | Definition |
|---|---|
| Employee | Person represented in the HR system. |
| Personnel State | Current calculated HR state of the employee. |
| Personnel Event | Business event that changes Personnel State. |
| Change Set | Structured set of atomic changes produced by a Personnel Event. |
| Personnel Order | Legal document registering one or more Personnel Events. |
| Order Item | Employee-level item inside an order; links order to Personnel Event. |
| Order Document | File representation of an order: DOCX, PDF, scan. |
| Approval Route | Workflow route for preparing and approving a draft order. |
| Visa / Approval | Approval action performed before signing. |
| Personnel Report | Reporting artifact; not a Personnel Order. |

---

# 4. Boundary Decisions

## Decision 1. Personnel Event is primary

The primary business entity is Personnel Event.

Personnel Orders and documents do not directly change employee state.

---

## Decision 2. Personnel State is derived

Personnel State is a calculated current snapshot based on Personnel Events.

Manual editing of Personnel State should be avoided except through controlled migration or administrative correction events.

---

## Decision 3. Change Set explains state transition

Every Personnel Event should produce a Change Set.

Change Set is the bridge between historical events and current state.

---

## Decision 4. Order Item is required

One Personnel Order may include multiple employees and multiple events.

Therefore, Order Item is mandatory as an intermediate entity.

---

## Decision 5. Reports are outside Personnel Orders

Personnel reports must not be stored inside the personnel orders archive.

They belong to a separate Personnel Reports area.

---

## Decision 6. Approval workflow belongs to document lifecycle

Visas, approvals, signatory and preparer fields belong to order/document workflow.

They are not Personnel Events themselves.

---

## Decision 7. Temporary assignment is a separate related event

Replacement, acting duties, temporary assignment and related allowance should be modeled as separate Personnel Events related to the initiating leave or business trip event.

This allows both one integrated order and multiple separate orders.

---

# 5. Recommended Documentation Structure

Current recommended placement:

```text
docs/
└── personnel-orders/
    └── architecture/
        PE-001-personnel-event-engine-concept.md
        PE-002-personnel-state-model.md
        PE-003-personnel-change-set-model.md
        PO-001-personnel-orders-module-concept.md
```

Future extraction to `docs/personnel-core/architecture/` should be considered only after another module besides Personnel Orders starts using PE-series concepts.

---

# 6. Required Updates to Existing Documents

## PE-001

Add explicit references:

- PE-002 for Personnel State details;
- PE-003 for Change Set details;
- PO-001 as first consumer of the model.

## PE-002

Clarify that Personnel State:

- stores current values only;
- is reconstructed from Personnel Events;
- should not contain document workflow fields.

## PE-003

Clarify that Change Set:

- is owned by Personnel Event;
- contains atomic changes;
- reconstructs Personnel State;
- should support typed values, not only text values.

## PO-001

Reduce duplication of PE-series concepts.

PO-001 should state:

> This module uses the Personnel Event Engine defined in PE-001.

Then describe only the Personnel Orders module-specific part:

- order registry;
- order numbering;
- order templates;
- bilingual document generation;
- approval route;
- signed PDF storage;
- integration with Personnel Events.

---

# 7. Proposed Next Documents

## PO-002 Personnel Orders Classification

Should define:

- classification of personnel events found in pilot archive;
- mapping from event classes to order templates;
- distinction between order type and personnel event type;
- handling of order cancellation/amendment;
- handling of reports outside order archive.

## PO-003 Personnel Orders Data Model

Should define:

- database entities;
- relationships;
- indexes;
- lifecycle statuses;
- migration strategy.

---

# 8. Open Questions

1. Should PE-series documents remain under `personnel-orders` until reused by another module?
2. Should Personnel State be materialized in DB or calculated on demand?
3. Should Change Set values be stored as JSON, normalized rows, or both?
4. Should temporary assignment always be generated from leave/business trip workflows or may it be created independently?
5. Should order cancellation be modeled only as document control, or also as a reversing Personnel Event?

---

# 9. Review Outcome

Architecture is internally consistent enough to proceed to PO-002.

Recommended immediate next step:

```text
PO-002-personnel-orders-classification.md
```

based on the pilot archive and the PE-series model.
