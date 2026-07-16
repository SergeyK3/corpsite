# WP-PO-REHIRE-001 — Termination: hr_relationship_context EMPLOYED → FORMER_EMPLOYEE

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | REHIRE / Termination lifecycle |
| Предшественник | Forward-flow «Заявитель → Работник» (**COMPLETE**) |
| Связанные WP | WP-PO-004C `_apply_termination`; `ppr_candidate_service` |
| Связанные ADR | ADR-054 (`HR_RELATIONSHIP_FORMER_EMPLOYEE`) |

---

## Problem

Apply TERMINATION деактивирует Employee (`is_active = FALSE`), но **не обновляет** `personnel_record_metadata.hr_relationship_context`.

**Следствие:** после увольнения PPR остаётся `EMPLOYED` — UI и query layer не отражают статус «бывший сотрудник».

---

## Target behavior

После успешного Apply TERMINATION:

```text
hr_relationship_context: EMPLOYED → FORMER_EMPLOYEE
```

На той же PPR (`person_id` unchanged).

Symmetric to `sync_hr_context_after_hire`.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `sync_hr_context_after_termination` hook в apply pipeline | Void TERMINATION rollback of hr_context |
| Guard: only when current context is EMPLOYED | Termination without PPR envelope |

---

## Acceptance criteria

1. Hire → Terminate (Apply): `hr_relationship_context = FORMER_EMPLOYEE`.
2. Same PPR envelope; no new card.
3. PPR read API reflects FORMER_EMPLOYEE label in UI.
