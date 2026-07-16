# Personnel Orders — Hire Lifecycle Backlog Index

| Поле | Значение |
|------|----------|
| Статус | **Active backlog** |
| Дата | 2026-07-16 |
| Контекст | Architectural Review «Заявитель → Работник» — forward-flow **COMPLETE** |
| Родитель | [WP-PO-004C](../implementation/) Apply; [WP-UI-PPR-HIRE-FROM-PERSON](../../../docs-work/WP-UI-PPR-HIRE-FROM-PERSON-v1-pre-commit-report.md) |
| ADR | [ADR-054-NOTE-intended-employment-lifecycle](../../adr/ADR-054-NOTE-intended-employment-lifecycle.md) |

---

## Forward-flow (COMPLETE)

```text
PPR (CANDIDATE)
  → intended employment (pre-order)
  → HIRE order
  → Apply
  → Employee + Assignment
  → PPR (EMPLOYED)
```

**Статус:** реализован и готов к commit. VOID HIRE и REHIRE сознательно вынесены в отдельные work packages ниже.

---

## EPIC: VOID HIRE (applicant-path)

| WP | Название | Статус |
|----|----------|--------|
| [WP-PO-VOID-HIRE-001](./WP-PO-VOID-HIRE-001-hr-context-rollback.md) | Rollback `hr_relationship_context`: EMPLOYED → CANDIDATE | Planned |
| [WP-PO-VOID-HIRE-002](./WP-PO-VOID-HIRE-002-assignment-rollback.md) | Rollback `person_assignments` | Planned |
| [WP-PO-VOID-HIRE-003](./WP-PO-VOID-HIRE-003-operational-status-rollback.md) | Rollback `operational_status` | Planned |
| [WP-PO-VOID-HIRE-004](./WP-PO-VOID-HIRE-004-integration-test-applicant-hire-void.md) | Integration test: Applicant → Hire → Apply → Void | Planned |

**Зависимости:** WP-001…003 должны быть реализованы до или вместе с WP-004.

---

## EPIC: REHIRE / TERMINATION lifecycle sync

| WP | Название | Статус |
|----|----------|--------|
| [WP-PO-REHIRE-001](./WP-PO-REHIRE-001-termination-hr-context.md) | Termination: EMPLOYED → FORMER_EMPLOYEE | Planned |
| [WP-PO-REHIRE-002](./WP-PO-REHIRE-002-rehire-hr-context.md) | Rehire: FORMER_EMPLOYEE → EMPLOYED | Planned |
| [WP-PO-REHIRE-003](./WP-PO-REHIRE-003-e2e-hire-termination-rehire.md) | E2E: Hire → Termination → Rehire | Planned |

**Зависимости:** WP-PO-REHIRE-001 → WP-PO-REHIRE-002 → WP-PO-REHIRE-003.

---

## Следующие EPIC (вне этого backlog)

| EPIC | Описание |
|------|----------|
| **EPIC-4** | Новые person_* секции PPR (родственники, документы, языки, …) |
| **R8–R10** | PPR evaluation, UI migration, Import/PMF cutover ([WP-PR-012](../../architecture/WP-PR-012-ppr-implementation-roadmap.md)) |
