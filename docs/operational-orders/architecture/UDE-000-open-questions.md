# UDE-000 — Open Questions

WP: **UDE-000** (supporting artifact)  
Date: **2026-07-12**  
Status: Categorized post-ratification backlog

---

## Summary

| Category | Count | Blocks architecture | Blocks UDE-001 | Blocks OO-IMP-001 |
|---|---:|---|---|---|
| Architecture | 0 open | — | — | — |
| Organizational | 8 | No | No | **Yes** (policy) |
| Legal | 3 | No | No | No |
| Implementation | 6 | No | Partial | Partial |

**Organizational interviews do not block architecture ratification or UDE-001.**  
**They are mandatory before OO-IMP-001.**

Interview guide: [OP-RES-006A-organizational-interview-guide.md](./OP-RES-006A-organizational-interview-guide.md)

---

## Architecture Questions

*All resolved at ratification.*

| ID | Question | Resolution |
|---|---|---|
| AQ-01 | Scenario-first vs intake-first conflict? | Coexisting paths; specialization-specific (F-001) |
| AQ-02 | Staged SoT vs semantic SoT? | Staged model T028; ADR-016 |
| AQ-03 | Document aggregate with intake? | Yes; submitted+provenance in aggregate early phase |
| AQ-04 | Microservices needed? | No; modular monolith ADR-010 |

---

## Organizational Questions

| ID | Question | Impact | Resolve by |
|---|---|---|---|
| OQ-01 | Who writes first draft of OO? | Content author model | Interview |
| OQ-02 | Is KK mandatory before approval? | READY gate; waiver policy | Interview |
| OQ-03 | Authoritative locale on RU/KK conflict? | Reconciliation rules | Interview |
| OQ-04 | Content confirmation always required? | ADR-014 policy | Interview |
| OQ-05 | Form-only vs content change classification? | Confirmation triggers | Interview + UDE-002 |
| OQ-06 | Who translates KK? | Translation workflow | Interview |
| OQ-07 | What if KK not ready in time? | Missing locale workflow | Interview |
| OQ-08 | Intake channel (email/Word/paper)? | Intake UX design | Interview + OO-IMP-001 |

---

## Legal Questions

| ID | Question | Impact | Resolve by |
|---|---|---|---|
| LQ-01 | Legal equivalence RU/KK final texts? | Signing validity | Separate legal WP (out of scope) |
| LQ-02 | RU-only approval permissible? | Locale policy | Legal + organizational |
| LQ-03 | Liability for executor/deadline errors | Content author vs HR | Organizational policy |

*Architecture does not assert legal conclusions.*

---

## Implementation Questions

| ID | Question | Impact | Resolve by |
|---|---|---|---|
| IQ-01 | PO employee_id → PartyReference migration? | UDE-006 scope | UDE-001 contracts |
| IQ-02 | Compensating order links? | Amendment workflow | Deferred PO-LC-DEL-002 |
| IQ-03 | Approval visa data model? | Optional workflow | Post OO-IMP-004 |
| IQ-04 | Immutable signed PDF storage? | PO-PDF-001 | Post MVP |
| IQ-05 | DOCX export priority? | Rendering roadmap | Post PDF stable |
| IQ-06 | Granular permission keys? | Access model | UDE-001 + security WP |

---

## Question Disposition Rules

| Gate | Open questions allowed |
|---|---|
| UDE-001 | Architecture closed; implementation design open |
| UDE-002 | Intake/provenance spec may use defaults pending OQ answers |
| OO-IMP-001 | **OQ-01–08 must have documented organizational policy or explicit defaults** |
| OO-IMP-002 | OQ-04, OQ-05 must be resolved for content confirmation |

---

## Defaults (if interviews delayed — not recommended)

| Topic | Interim default | Risk |
|---|---|---|
| KK mandatory | Yes; waiver by HR_HEAD only | Medium |
| Content confirmation | Required when HR changes executors/deadlines/control | Low |
| Authoritative locale | Bilingual package joint approval | Medium |
| Content author | Declared explicitly; never inferred from created_by | Low |

Defaults are **implementation fallbacks**, not ratified policy.
