# PE-001 Personnel Event Engine Concept

**Status:** Draft  
**Version:** 0.1

## Purpose

Define the conceptual personnel domain model for Corpsite in which the primary business entity is the **Personnel Event**, while personnel orders serve as the legal registration of one or more personnel events.

This document is an architectural dependency for **PO-001 Personnel Orders Module Concept** and may later become the foundation for additional HR modules.

---

# 1. Architectural Principle

```
Employee
    │
    ▼
Personnel State
    │
    ▼
Personnel Event
    │
    ▼
Change Set
    │
    ▼
Order Item
    │
    ▼
Personnel Order
    │
    ▼
Order Documents
```

The Personnel Event changes the employee's state.
The Personnel Order legally records one or more Personnel Events.

---

# 2. Core Entities

## Employee

Represents the employee and stores the current personnel state.

## Personnel State

Snapshot of the employee's current HR status:

- Organization
- Department
- Position
- Employment type
- FTE / Rate
- Qualification
- Education
- Seniority group
- Employment status

Personnel State is derived from the sequence of Personnel Events.

## Personnel Event

Primary business entity.

### Suggested attributes

- EventID
- EmployeeID
- EventType
- EventSubtype
- EffectiveFrom
- EffectiveTo
- Status
- ParentEventID
- RelatedEventID
- SourceOrderItemID

---

# 3. Change Set

Each Personnel Event contains one or more changes.

| Attribute | Previous | New |
|-----------|----------|-----|
| Department | | |
| Position | | |
| FTE / Rate | | |
| Qualification | | |
| Salary Allowance | | |
| Surname | | |

This model allows one event to modify any combination of employee attributes.

---

# 4. Personnel Order

A Personnel Order is the legal wrapper for one or more Personnel Events.

## Main attributes

- Order Number
- Order Date
- Order Type
- Registration Status

### Signatory

- Position
- Full name

### Prepared by

- Position
- Full name
- Department
- Work phone

---

# 5. Order Item

Each Order Item describes one Personnel Event affecting one employee.

---

# 6. Order Documents

Supported representations:

- DOCX (Kazakh)
- PDF (signed original)
- DOCX (Russian)
- PDF (Russian)
- Scan

---

# 7. Approval Workflow

Personnel Event
→ Draft Order
→ Approval Route
→ Signing
→ Registration
→ Execution
→ Archive

Approval record:

- Approver
- Position
- Approval Role
- Status
- Date
- Comment

---

# 8. Personnel Event Classes

## Employment

- Hire
- Termination

## Position

- Transfer
- Appointment

## Work Conditions

- Rate change
- Concurrent assignment
- Secondary employment
- Allowance

## Leave

- Annual leave
- Partial leave
- Unpaid leave
- Maternity leave
- Childcare leave
- Business trip
- Return from leave

## Qualification

- Qualification category
- Academic degree
- Education update
- Seniority group change

## Personal Data

- Personal data change

## Order Control

- Order amendment
- Order cancellation

---

# 9. Related Personnel Events

Some events naturally generate related events.

Example:

```
Leave Event
      │
      ├── Temporary Assignment Event
      │
      └── Allowance Event
```

or

```
Business Trip
      │
      ├── Temporary Assignment Event
      │
      └── Allowance Event
```

Temporary Assignment Event includes:

- Replaced employee
- Acting employee
- Period
- Acting type
- Allowance (optional)

This allows one integrated order or several independent orders without changing the domain model.

---

# 10. Architectural Conclusions

1. Personnel Event is the primary HR business entity.
2. Personnel State is reconstructed from Personnel Events.
3. Personnel Orders legally register Personnel Events.
4. Documents are representations of Personnel Orders.
5. Approval workflow belongs to document lifecycle, not to Personnel Event.
6. Temporary assignment, acting duties and allowances are independent but related Personnel Events.

---

# 11. Relationship with Other Modules

Current dependency:

```
PE-001 Personnel Event Engine
        │
        └── PO-001 Personnel Orders
```

Future planned reuse:

- Personnel Intake
- Personnel Migration
- Position Cabinet
- Leave Management
- Business Trips
- Qualification & Education
- Personnel Reports

---

# Revision History

- v0.1 — Initial conceptual model based on analysis of the pilot personnel orders archive.
