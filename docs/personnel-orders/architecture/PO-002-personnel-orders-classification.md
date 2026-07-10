# PO-002 Personnel Orders Classification

**Status:** Draft  
**Version:** 0.1

## Purpose

Define the canonical classification of personnel orders and personnel events for Corpsite based on analysis of the pilot archive.

---

# 1. Principles

The classification is built around **Personnel Events**.  
A Personnel Order is the legal document that registers one or more Personnel Events.

One order may contain multiple employees and multiple event types.

---

# 2. Personnel Event Classification

| Group | Event Type | Notes |
|---|---|---|
| Employment | Hire | Employment begins |
| Employment | Termination | Employment ends |
| Position | Transfer | Change of position/department |
| Position | Appointment | Appointment to a position |
| Work Conditions | Rate Change | FTE change |
| Work Conditions | Concurrent Assignment | Internal combination |
| Work Conditions | Secondary Employment | Additional employment |
| Work Conditions | Allowance | Additional payment |
| Leave | Annual Leave | Paid leave |
| Leave | Partial Leave | Part of annual leave |
| Leave | Unpaid Leave | Leave without pay |
| Leave | Maternity Leave | Pregnancy leave |
| Leave | Childcare Leave | Childcare leave |
| Leave | Return from Leave | Return to work |
| Leave | Business Trip | Long-term business trip |
| Qualification | Qualification Category | Category assignment/change |
| Qualification | Academic Degree | PhD, MSc etc. |
| Qualification | Education Update | Education data update |
| Qualification | Seniority Group | Seniority recalculation |
| Personal Data | Personal Data Change | Name, identity data |
| Temporary Assignment | Acting Duties | Temporary replacement |
| Temporary Assignment | Replacement | Acting for absent employee |
| Order Control | Order Amendment | Amendment |
| Order Control | Order Cancellation | Cancellation |

---

# 3. Mapping to Order Templates

| Personnel Event | Typical Order |
|---|---|
| Hire | Hiring Order |
| Termination | Termination Order |
| Transfer | Transfer Order |
| Annual Leave | Leave Order |
| Acting Duties | Acting Assignment Order or combined leave order |
| Allowance | Allowance Order or combined order |
| Qualification Category | Qualification Order |

---

# 4. Combined Orders

The system shall support:

- one order → one event;
- one order → many events;
- one order → many employees.

Example:

1. Grant annual leave.
2. Assign acting duties.
3. Apply allowance.

All three are separate Personnel Events linked to one Personnel Order.

---

# 5. Pilot Archive Findings

Identified major groups:

- Hire
- Termination
- Transfer
- Position/Work condition changes
- Leave-related events
- Qualification events
- Personal data changes
- Temporary assignments
- Order control events

Personnel reports shall be stored outside the Personnel Orders archive.

---

# 6. Coding Recommendation

Internal system identifiers should be stable English codes:

- HIRE
- TERMINATION
- TRANSFER
- APPOINTMENT
- RATE_CHANGE
- ACTING_ASSIGNMENT
- ALLOWANCE
- ANNUAL_LEAVE
- RETURN_FROM_LEAVE
- QUALIFICATION_CATEGORY
- ACADEMIC_DEGREE
- PERSONAL_DATA_CHANGE
- ORDER_CANCELLATION

User interface may display localized names in Russian or Kazakh.

---

# 7. Revision History

- v0.1 Initial draft.
