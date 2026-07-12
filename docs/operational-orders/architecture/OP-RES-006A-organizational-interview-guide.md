# OP-RES-006A — Organizational Interview Guide

WP: **OP-RES-006A** (supporting artifact)  
Date: **2026-07-12**  
Audience: HR staff, department heads, translators, registry clerks  
Mode: Pre-ratification organizational validation (not legal review)

---

## Purpose

Validate assumptions in [OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md) before **UDE-000 Architecture Ratification**.

---

## Interview Protocol

| Step | Action |
|---|---|
| 1 | Interview HR document operators (2–3 sessions) |
| 2 | Interview production department heads (2–3 sessions) |
| 3 | Cross-check answers against corpus patterns (OP-RES-005A) |
| 4 | Record decisions as organizational policy notes (not ADR until confirmed) |
| 5 | Update OP-RES-006A open questions |

**Duration:** 30–45 minutes per session  
**Do not record:** PII from specific orders in Git artifacts

---

## Questions for HR

| # | Question | Why it matters |
|---|---|---|
| 1 | Кто обычно пишет первый текст производственного приказа? | Content author identification |
| 2 | Кто считается автором содержания в журнале? | Record creator ≠ content author |
| 3 | В каком виде текст передаётся в HR? | Intake channel design |
| 4 | Передаётся по email, Word, бумаге или иным способом? | Intake attachment model |
| 5 | Кто создаёт казахскую версию? | Translation responsibility |
| 6 | Кто проверяет перевод? | Localization reviewer role |
| 7 | Всегда ли требуется KK до согласования? | Mandatory locale policy |
| 8 | Может ли приказ быть согласован только на RU? | Waiver policy |
| 9 | Кто утверждает изменения HR в исходном тексте? | Content confirmation |
| 10 | Нужно ли автору повторно подтверждать документ после правок? | Confirmation triggers |
| 11 | Бывает ли, что HR полностью переписывает представленный текст? | Content vs form-only boundary |
| 12 | Какие категории приказов готовятся без текста подразделения? | Model A/D applicability |
| 13 | Что происходит, если KK не готов вовремя? | Missing KK workflow |
| 14 | Какая языковая версия основная при расхождении? | Authoritative locale policy |

---

## Questions for Department Heads

| # | Question | Why it matters |
|---|---|---|
| 15 | Кто отвечает за ошибки в исполнителях и сроках? | Content author responsibility |
| 16 | Кто считается инициатором в журнале приказов? | Business initiator vs author |
| 17 | Бывают ли совместные авторы? | Multi-author provenance |
| 18 | Кто отвечает за приложения? | Attachment ownership |
| 19 | Кто решает, нужен ли контрольный пункт? | Control enrichment by HR? |
| 20 | Кто определяет контролёра? | Controller assignment |

---

## Expected Outcomes

| Outcome | Action if confirmed | Action if denied |
|---|---|---|
| Dept head = content author | ADR-UDE-011 ratify | Revise role model |
| HR = document operator | ADR-UDE-015 ratify | Revise access model |
| Submitted-text intake primary | OO MVP intake-first | Revisit roadmap |
| KK mandatory before sign | BC019 + I020 block READY | Add waiver policy |
| Author must confirm HR edits | ADR-UDE-014 ratify | Form-only auto-approve |

---

## Recording Template (local, not Git)

```text
Interview ID: INT-OO-___
Date:
Role interviewed:
Q#: Answer summary
Policy implication:
Follow-up required: Y/N
```

---

## Related Artifacts

- [OP-RES-006A Addendum](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md)
- [Role matrix](./data/OP-RES-006A-role-responsibility-matrix.csv)
- [Intake validation matrix](./data/OP-RES-006A-intake-validation-matrix.csv)
