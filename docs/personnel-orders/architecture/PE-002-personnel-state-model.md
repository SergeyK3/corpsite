# PE-002 Personnel State Model

**Status:** Draft  
**Version:** 0.1

## Purpose

Define the conceptual model of the current personnel state maintained by Corpsite.

Personnel State is **not entered manually**. It is calculated from the sequence of Personnel Events.

---

# 1. Concept

```
Personnel Events
        │
        ▼
Personnel State
        │
        ├── Employee Card
        ├── Position Cabinet
        ├── Personnel Orders
        ├── Reports
        └── Analytics
```

Personnel State represents the current HR snapshot of an employee.

---

# 2. State Domains

## Employment State

- employment_status
- hire_date
- termination_date
- contract_type

Statuses:
- Candidate
- Active
- On Leave
- Childcare Leave
- Business Trip
- Suspended
- Terminated

---

## Organization State

- organization
- department_group
- department
- manager

---

## Position State

- position
- role
- appointment_date
- position_status

---

## Workload State

- base_rate
- additional_rate
- total_rate
- employment_mode
- work_schedule

---

## Compensation State

- salary_reference
- allowance_type
- allowance_percent
- allowance_amount
- effective_period

---

## Leave / Absence State

- absence_type
- absence_from
- absence_to
- expected_return

Types:
- Annual Leave
- Partial Leave
- Unpaid Leave
- Maternity Leave
- Childcare Leave
- Sick Leave
- Business Trip

---

## Acting / Replacement State

- acting_employee
- replaced_employee
- acting_position
- acting_from
- acting_to
- allowance

This state is produced by related Personnel Events.

---

## Qualification State

- qualification_category
- academic_degree
- seniority_group
- certification

---

## Education State

- education_level
- institution
- specialty
- diploma
- graduation_year

---

## Personal Data State

- surname
- first_name
- middle_name
- IIN
- contacts

---

## Legal State

- last_order
- last_order_date
- source_event
- state_valid_from
- state_valid_to

---

# 3. Design Principles

1. Personnel State is derived from Personnel Events.
2. State stores current values only.
3. History belongs to Personnel Events.
4. Documents never change the state directly.
5. Every change must be traceable to an originating Personnel Event.

---

# Revision History

- v0.1 Initial draft.
