# Personnel Intake Framework (PIF) — Documentation Index

Индекс проектной документации **Personnel Intake Framework (PIF)** — программы электронного приёма кадровых данных новых сотрудников.

| Поле | Значение |
|------|----------|
| **Контур** | Кадровые процессы → Intake |
| **Статус программы** | **Initiated** (Architecture) — 2026-07-08 |
| **Predecessor** | [PMF Pilot Freeze](../personnel-migration/PMF-PILOT-FREEZE.md) |
| **Канонический формат** | **Markdown** (`.md`) |

---

## Документы

| Code | Document | Description |
|------|----------|-------------|
| PIF-001 | [PIF-001-personnel-intake-framework.md](./PIF-001-personnel-intake-framework.md) | Fundamental architecture — problem, pipeline, canonical model, PMF position |
| PIF-002 | [PIF-002-electronic-personal-sheet.md](./PIF-002-electronic-personal-sheet.md) | Electronic Personal Sheet concept (not UI design) |
| PIF-003 | [PIF-003-dynamic-form-model.md](./PIF-003-dynamic-form-model.md) | Dynamic form architecture (Section → Generated Form) |
| PIF-004 | [PIF-004-data-ownership.md](./PIF-004-data-ownership.md) | Candidate / HR ownership and commit policy |
| PIF-2A | [PIF-2A-electronic-intake-ux-specification.md](./PIF-2A-electronic-intake-ux-specification.md) | **Candidate UX specification** — screen-by-screen анкета |
| PIF-2B | [demo/](./demo/) | **Clickable HTML demo prototype** (local browser) |
| PIF-PHOTO | [PIF-PHOTO-storage.md](./PIF-PHOTO-storage.md) | Runtime photo storage, archive names, PDF embed, backup |
| PIF-ROADMAP | [PIF-roadmap.md](./PIF-roadmap.md) | Work package sequence PIF-1 → Pilot |

---

## Связанные документы

| Document | Relationship |
|----------|--------------|
| [PMF-PILOT-FREEZE](../personnel-migration/PMF-PILOT-FREEZE.md) | PMF frozen; PIF is active successor program |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Target Personal File aggregate |
| [ADR-047 Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md) | Official form analysis; layer separation |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person creation at intake commit |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | Sibling program — legacy control sheet migration |

---

## Roadmap (summary)

```text
PIF-1 Architecture → PIF-2 Data Model → PIF-3 Invitation → PIF-4 Electronic Form
  → PIF-5 HR Review → PIF-6 Commit → PIF-7 Generated Documents → Pilot
```

Recommended first engineering WP: **PIF-2 — Canonical Personnel Data Model** (see [PIF-roadmap §7](./PIF-roadmap.md#7-recommended-first-engineering-work-package)).
