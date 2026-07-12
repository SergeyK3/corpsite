# OP-RES-006 — Executive Summary: Unified Document Engine Target Architecture

WP: **OP-RES-006**  
Date: **2026-07-12**  
Updated: **OP-RES-006A** (2026-07-12)  
Mode: **Architecture research and specification only** (no runtime changes)

---

## Research Program Conclusion

Исследовательская программа OP-RES-001–005A подтвердила главный вывод:

**Personnel Orders и Operational Orders — специализации единого Unified Document Engine**, а не независимые документные модули.

| Evidence base | Value |
|---|---|
| Corpus files | 193 (183 DOCX deep analysis) |
| Numbered items | 1 926 |
| Domains / scenarios | 8 / 21 |
| P0 scenario coverage | ~59% |
| Item type families | 14 |
| Intra-doc bilingual | 135 / 183 DOCX |

---

## Target Architecture (confirmed)

```text
Unified Document Engine
│
├── Document Core (identity · structure · lifecycle · audit)
├── Editorial Core (semantic model · generated · effective · override)
├── Draft Intake *(006A)* (submitted text · provenance · content confirmation)
├── Localization (RU/KK · provenance · hybrid workflow · staleness)
├── Generation (scenario · registries · validation)
├── Specializations
│     ├── Personnel Orders → Employee Events
│     └── Operational Orders → Execution/Control Obligations
├── Rendering (HTML · PDF · future DOCX)
└── Execution Boundary → Execution Projection (downstream only)
```

**Рекомендуемая модель специализации:** composition + policy/registry + plugin-like modules — **не** наследование классов.

---

## Key Architectural Decisions (pending ratification)

| ADR | Decision |
|---|---|
| ADR-UDE-001 | One Document Core, multiple specializations |
| ADR-UDE-003 | Order Item ≠ Execution Obligation |
| ADR-UDE-004 | Three independent lifecycles |
| ADR-UDE-005 | Generated text ≠ effective text |
| ADR-UDE-006 | Hybrid multilingual (semantic-first + RU-first editorial) |
| ADR-UDE-008 | Execution Projection is downstream boundary |
| ADR-UDE-010 | Incremental migration — no big-bang rewrite |
| ADR-UDE-011 *(006A)* | Content Author ≠ Record Creator |
| ADR-UDE-012 *(006A)* | Submitted-text Intake as first-class path |
| ADR-UDE-015 *(006A)* | HR as Document Operator, not default Content Owner |

---

## OP-RES-006A Key Finding

**Content ownership ≠ Document processing ownership.**

Operational Orders MVP should start with **Model C — Submitted-text Intake**, not scenario-first generation alone.

See: [OP-RES-006A Addendum](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md)

## Personnel Orders Foundation (read-only gap analysis)

Personnel Orders MVP уже реализует значительную часть целевой архитектуры:

| Reusable now (Class A) | Gap for OO (Class E) |
|---|---|
| Editorial blocks (generated/override/effective) | Scenario-first generation |
| Fingerprint + staleness | Execution/Control obligations |
| Lifecycle audit + archive | 14 item type registry |
| void_kind CANCEL/ANNUL | Control meta-item |
| Print ViewModel + Playwright PDF | Execution projection adapter |

**Operational Orders можно добавить без полного рефакторинга Personnel Orders** — через общий shell и параллельную специализацию (Phase 4).

---

## Migration Strategy (6 phases)

0. Architecture Ratification (OP-RES-006)  
1. Common Document Contracts (no PO behavior change)  
2. Shared Editorial Core  
3. Shared Lifecycle and Audit  
4. Operational Orders MVP (**intake-first**, Model C; scenario generation parallel)  
5. Execution Projection  
6. Controlled Personnel Orders Convergence  

Rollback boundary: каждая фаза доказывает совместимость с production PO MVP.

---

## Mandatory Answers (short form)

| # | Question | Answer |
|---|---|---|
| 1 | Ядро UDE? | Document Core + Editorial + Localization + Generation + Lifecycle + Rendering |
| 2 | Общая сущность PO/OO? | Document shell + Order Item + locale editorial model |
| 3 | Специализация? | Scenario taxonomy, item registries, obligation semantics, apply/projection |
| 4 | Document = aggregate root? | **Да** |
| 5 | Единица генерации? | **Order Item** |
| 6 | Единица управленческого смысла? | **Execution Obligation** |
| 35 | Первый WP? | **UDE-000 — Architecture Ratification** (OP-RES-006 + 006A) |

Полные ответы: OP-RES-006 §Mandatory Questions; OP-RES-006A §Mandatory Questions (30 additional).

---

## Artifacts

| Document | Purpose |
|---|---|
| [Target Architecture](./OP-RES-006-unified-document-engine-target-architecture.md) | Full specification (42 sections) |
| [Gap Analysis](./OP-RES-006-personnel-orders-gap-analysis.md) | PO → UDE classification |
| [Migration Roadmap](./OP-RES-006-migration-roadmap.md) | Phased transition plan |
| [ADR Backlog](./OP-RES-006-adr-backlog.md) | Decisions to ratify (UDE-001–016) |
| [006A Addendum](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md) | Initiation, authorship, draft intake |
| [006A Interview Guide](./OP-RES-006A-organizational-interview-guide.md) | Pre-implementation interviews |
| [`data/`](./data/) | Matrices (core vs specialization, components, lifecycles, gaps, WP roadmap) |
| [`diagrams/`](./diagrams/) | Conceptual architecture diagrams |

---

## Next Recommended WP

**UDE-000 — Architecture Ratification**

- Ratify OP-RES-006 **and OP-RES-006A** + ADR backlog (UDE-001–016)  
- Freeze terminology (content author, document operator, submitted text)  
- Obtain stakeholder sign-off before any implementation WP  
- Schedule organizational interviews before OO-IMP-001 (not blocking UDE-000)
