# Architecture Governance — Corpsite

## Статус

**Active (baseline pending ARCH-001 approval)** — 2026-07-03

Метадокумент фиксирует правила принятия архитектурных решений в Corpsite и **Architecture Baseline** — обязательные принципы для новых ADR и проектных решений.

| Связанный документ | Роль |
|--------------------|------|
| [ARCH-001 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) | Источник baseline-принципов (Draft → Accepted) |
| [ADR-050 — Organization Position & Position Cabinet](../adr/ADR-050-organization-position-cabinet-model.md) | Implementation contract: Position + Cabinet (**Proposed**) |
| [ADR-051 — Cabinet Access Resolution](../adr/ADR-051-cabinet-access-resolution.md) | Implementation contract: access resolver (**Proposed**) |
| [docs/adr/](../adr/) | Каталог принятых ADR |

---

## Architecture Baseline

**С момента утверждения [ARCH-001](./ARCH-001-position-permission-model.md)** все новые ADR и архитектурные решения должны исходить из следующих принципов:

1. **Person не определяет полномочия.**
2. **Platform User** является исключительно **технической** сущностью аутентификации.
3. **Position** является **уникальной организационной штатной единицей**.
4. **Position Cabinet** является **цифровым представлением** Position.
5. **Полномочия** являются **следствием занятия должности** (Занятие должности / и.о.), а не атрибутом учётной записи.
6. **Рабочие процессы** связываются с **Position Cabinet**, если это допускается предметной областью.

### Правило несогласованности

Любое новое архитектурное решение, **противоречащее** этим принципам, требует явного **amendment ARCH-001** либо **нового ADR** с обоснованием отступления.

До утверждения ARCH-001 baseline носит **ориентирующий** характер: существующие ADR и as-is реализация остаются в силе, но новые решения **рекомендуется** проектировать в русле baseline.

---

## Применение baseline

| Ситуация | Действие |
|----------|----------|
| Новый ADR согласован с baseline | Стандартный процесс принятия ADR |
| Новый ADR частично расходится с baseline | Явно указать расхождение; amendment ARCH-001 или overriding ADR |
| Реализация as-is противоречит baseline | Зафиксировать как технический долг; миграция — отдельный ADR / roadmap |
| Business Policy (process policy) | Не требует amendment ARCH-001, если не меняет baseline-принципы (см. ARCH-001 §4.7.2) |

---

## История документа

| Дата | Изменение |
|------|-----------|
| 2026-07-03 | Первоначальная версия: Architecture Baseline на основе ARCH-001 v0.5 |
