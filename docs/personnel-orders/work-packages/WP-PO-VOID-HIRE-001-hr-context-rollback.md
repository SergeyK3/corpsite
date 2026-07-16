# WP-PO-VOID-HIRE-001 — Rollback hr_relationship_context (EMPLOYED → CANDIDATE)

| Поле | Значение |
|------|----------|
| Статус | **Planned** |
| Дата | 2026-07-16 |
| EPIC | VOID HIRE (applicant-path) |
| Предшественник | Forward-flow «Заявитель → Работник» (**COMPLETE**) |
| Связанные WP | WP-PO-004D (void service); WP-PO-VOID-HIRE-004 (integration test) |
| Связанные ADR | ADR-054, [ADR-054-NOTE-intended-employment-lifecycle](../../adr/ADR-054-NOTE-intended-employment-lifecycle.md) |

---

## Problem

После Apply приказа HIRE (applicant-path) `sync_hr_context_after_hire` переводит envelope:
`CANDIDATE → EMPLOYED`.

При VOID applied HIRE void-сервис откатывает Employee snapshot и помечает `employee_events` как VOIDED, но **не откатывает** `personnel_record_metadata.hr_relationship_context`.

**Следствие:** PPR остаётся в контексте EMPLOYED при деактивированном Employee — нарушение Employment Relationship и UI (баннер «Заявитель» не восстанавливается).

---

## Target behavior

При void единственного HIRE event (applicant-path, `had_prior_employment_events = false`):

```text
hr_relationship_context: EMPLOYED → CANDIDATE
```

На той же PPR (тот же `person_id`, без создания новой карточки).

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `sync_hr_context_after_hire_void` (или symmetric hook в void pipeline) | Void TRANSFER / TERMINATION |
| Guard: откат только если voided HIRE был первым approved employment event | Rehire path |
| Unit / integration tests | UI changes (автоматически следуют из hr_context) |

---

## Acceptance criteria

1. Applicant → HIRE → Apply → Void: `hr_relationship_context = CANDIDATE`.
2. PPR envelope count = 1 (та же карточка).
3. Повторный void того же приказа — idempotent (409 / no-op).
4. Void HIRE при наличии более новых approved events — blocked (existing void chain).

---

## Implementation notes

- Hook point: `personnel_orders_void_service._rollback_hire_snapshot` или post-void callback после cascade.
- Reuse: `ppr_candidate_service.update_hr_relationship_context_tx`.
- Не трогать `intended_*` columns (historical only per ADR-054-NOTE).
