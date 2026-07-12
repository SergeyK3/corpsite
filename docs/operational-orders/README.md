# Operational Orders — Research, Architecture & Implementation

Исследовательская и архитектурная зона для корпуса **производственных приказов** (не кадровых).

**Implementation status:** OO-IMP-001–003B complete — document aggregate architecture ready for production (migration head `z0a1b2c3d4e5`).

---

## Implementation Program Status

| WP | Title | Status |
|---|---|---|
| **OO-IMP-001** | **Submitted-text Intake MVP** | **Complete (local)** |
| **OO-IMP-002** | **Content Confirmation and Translation Workflow** | **Complete (local)** |
| **OO-IMP-003** | **Official Draft Package and Document Aggregate** | **Complete (local)** |
| **OO-IMP-003A** | **Promotion Identity & Revision Architecture Review** | **Complete (ratified)** |
| **OO-IMP-003B** | **Workspace Freeze, Drift Detection & Revision Advisory** | **Complete** |
| **OO-IMP-003B-R1** | **Migration Backfill Safety Review** | **Complete** |

Records:
- [`implementation/OO-IMP-001-submitted-text-intake-mvp.md`](implementation/OO-IMP-001-submitted-text-intake-mvp.md)
- [`implementation/OO-IMP-002-content-confirmation-translation-workflow.md`](implementation/OO-IMP-002-content-confirmation-translation-workflow.md)
- [`implementation/OO-IMP-003-official-draft-package.md`](implementation/OO-IMP-003-official-draft-package.md)
- [`architecture/OO-IMP-003A-document-identity-ratification.md`](architecture/OO-IMP-003A-document-identity-ratification.md)
- [`implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md`](implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md)

Runtime package: `app/operational_orders/`  
API: `/api/operational-orders/draft-workspaces`, `/api/operational-orders/workspaces/{id}/promote`, `/api/operational-orders/documents`  
Migration head: `z0a1b2c3d4e5` (down: `y9z0a1b2c3d4`)

First native Shared UDE consumer — uses contracts/value objects only; persistence belongs to OO module.

---

## Research Program Status

| WP | Title | Status |
|---|---|---|
| OP-RES-001 | Corpus inventory and baseline | Done (2026-07-12) |
| OP-RES-002 | Structural pattern analysis | Done (2026-07-12) |
| OP-RES-003 | Operational order taxonomy | Done (2026-07-12) |
| OP-RES-004 | Control & execution model | Done (2026-07-12) |
| OP-RES-005 | Generation model | Done (2026-07-12) |
| OP-RES-005A | Bilingual drafting workflow | Done (2026-07-12) |
| **OP-RES-006** | **Unified Document Engine target architecture** | **Done (2026-07-12)** |
| **OP-RES-006A** | **Initiation, authorship, draft intake addendum** | **Done (2026-07-12)** |
| **UDE-000** | **Architecture ratification** | **Ratified with Minor Findings (2026-07-12)** |

### Architecture status

**Architecture Ratified with Minor Findings** — исследовательская программа **официально закрыта**. Реализация авторизована с **UDE-001**.

Ratification record: [`architecture/UDE-000-architecture-ratification-record.md`](architecture/UDE-000-architecture-ratification-record.md)

### Research program conclusion

Исследовательская программа OP-RES-001–006A подтвердила:

- Personnel Orders и Operational Orders — **специализации Unified Document Engine**, не независимые модули;
- общий document shell, Order Item как единица генерации, Execution Obligation как единица смысла;
- три независимых lifecycle (document, localization, execution);
- гибридный RU/KK workflow (semantic-first + RU-first editorial);
- **Content ownership ≠ Document processing ownership** *(006A)*;
- Operational Orders MVP — **Submitted-text Intake (Model C)** как P0 drafting path *(006A)*.

**Следующий WP:** **UDE-001 — Shared Terminology and Shared Contracts** (implementation phase).

---

## UDE-000 Ratification Artifacts

| Artifact | Description |
|---|---|
| [`architecture/UDE-000-architecture-ratification-record.md`](architecture/UDE-000-architecture-ratification-record.md) | Official ratification record and decision |
| [`architecture/UDE-000-architecture-review-report.md`](architecture/UDE-000-architecture-review-report.md) | Consistency review (0 Critical) |
| [`architecture/UDE-000-terminology-freeze.md`](architecture/UDE-000-terminology-freeze.md) | Frozen glossary (34 terms) |
| [`architecture/UDE-000-architecture-readiness-checklist.md`](architecture/UDE-000-architecture-readiness-checklist.md) | 20/20 readiness checks |
| [`architecture/UDE-000-open-questions.md`](architecture/UDE-000-open-questions.md) | Categorized open questions |
| [`architecture/UDE-000-next-phase-initiation.md`](architecture/UDE-000-next-phase-initiation.md) | UDE-001 authorization |
| [`architecture/data/UDE-000-adr-status.csv`](architecture/data/UDE-000-adr-status.csv) | ADR-UDE-001–016 ratified |
| [`architecture/data/UDE-000-consistency-matrix.csv`](architecture/data/UDE-000-consistency-matrix.csv) | Cross-WP consistency |
| [`architecture/data/UDE-000-terminology-registry.csv`](architecture/data/UDE-000-terminology-registry.csv) | Term registry |
| [`architecture/data/UDE-000-readiness-checklist.csv`](architecture/data/UDE-000-readiness-checklist.csv) | Machine-readable checklist |

### UDE-000 Diagrams

| Diagram | Description |
|---|---|
| [`architecture/diagrams/unified-document-engine-overview.svg`](architecture/diagrams/unified-document-engine-overview.svg) | Ratified UDE overview |
| [`architecture/diagrams/unified-document-engine-boundaries.svg`](architecture/diagrams/unified-document-engine-boundaries.svg) | Final boundaries |
| [`architecture/diagrams/document-specialization-final.svg`](architecture/diagrams/document-specialization-final.svg) | PO / OO specialization |
| [`architecture/diagrams/implementation-roadmap-final.svg`](architecture/diagrams/implementation-roadmap-final.svg) | Authorized WP sequence |
| [`architecture/diagrams/research-to-implementation.svg`](architecture/diagrams/research-to-implementation.svg) | Research → implementation gate |

---

## OP-RES-006 Architecture Artifacts

| Artifact | Description |
|---|---|
| [`architecture/OP-RES-006-unified-document-engine-target-architecture.md`](architecture/OP-RES-006-unified-document-engine-target-architecture.md) | Full target architecture (42 sections, 35 mandatory Q&A) |
| [`architecture/OP-RES-006-architecture-executive-summary.md`](architecture/OP-RES-006-architecture-executive-summary.md) | Executive summary |
| [`architecture/OP-RES-006-personnel-orders-gap-analysis.md`](architecture/OP-RES-006-personnel-orders-gap-analysis.md) | PO → UDE gap analysis (read-only) |
| [`architecture/OP-RES-006-migration-roadmap.md`](architecture/OP-RES-006-migration-roadmap.md) | 6-phase incremental migration |
| [`architecture/OP-RES-006-adr-backlog.md`](architecture/OP-RES-006-adr-backlog.md) | ADR-UDE-001–016 (**ratified UDE-000**) |

### OP-RES-006 Data Matrices

| File | Description |
|---|---|
| [`architecture/data/OP-RES-006-core-vs-specialization-matrix.csv`](architecture/data/OP-RES-006-core-vs-specialization-matrix.csv) | Core vs specialization scope |
| [`architecture/data/OP-RES-006-component-responsibility-matrix.csv`](architecture/data/OP-RES-006-component-responsibility-matrix.csv) | Logical component responsibilities |
| [`architecture/data/OP-RES-006-lifecycle-interaction-matrix.csv`](architecture/data/OP-RES-006-lifecycle-interaction-matrix.csv) | Three lifecycle interactions |
| [`architecture/data/OP-RES-006-current-to-target-gap-matrix.csv`](architecture/data/OP-RES-006-current-to-target-gap-matrix.csv) | Personnel Orders gap classification |
| [`architecture/data/OP-RES-006-implementation-wp-roadmap.csv`](architecture/data/OP-RES-006-implementation-wp-roadmap.csv) | Future implementation WP sequence |

### OP-RES-006 Diagrams

| Diagram | Description |
|---|---|
| [`architecture/diagrams/unified-document-engine-context.svg`](architecture/diagrams/unified-document-engine-context.svg) | UDE context |
| [`architecture/diagrams/unified-document-engine-components.svg`](architecture/diagrams/unified-document-engine-components.svg) | Logical components |
| [`architecture/diagrams/document-aggregate-model.svg`](architecture/diagrams/document-aggregate-model.svg) | Document aggregate |
| [`architecture/diagrams/document-specialization-model.svg`](architecture/diagrams/document-specialization-model.svg) | Specialization model |
| [`architecture/diagrams/three-lifecycles-model.svg`](architecture/diagrams/three-lifecycles-model.svg) | Three lifecycles |
| [`architecture/diagrams/generation-localization-execution-boundaries.svg`](architecture/diagrams/generation-localization-execution-boundaries.svg) | Generation/localization/execution boundaries |
| [`architecture/diagrams/personnel-to-unified-migration.svg`](architecture/diagrams/personnel-to-unified-migration.svg) | Migration phases |
| [`architecture/diagrams/target-bounded-contexts.svg`](architecture/diagrams/target-bounded-contexts.svg) | Bounded contexts |
| [`architecture/diagrams/multilingual-document-architecture.svg`](architecture/diagrams/multilingual-document-architecture.svg) | Hybrid multilingual model |
| [`architecture/diagrams/implementation-roadmap.svg`](architecture/diagrams/implementation-roadmap.svg) | Implementation WP roadmap |

## OP-RES-006A Artifacts *(initiation, authorship, draft intake)*

| Artifact | Description |
|---|---|
| [`architecture/OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md`](architecture/OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md) | Full addendum (30 sections, 30 mandatory Q&A) |
| [`architecture/OP-RES-006A-organizational-interview-guide.md`](architecture/OP-RES-006A-organizational-interview-guide.md) | Interview guide for HR and dept heads |
| [`architecture/data/OP-RES-006A-role-responsibility-matrix.csv`](architecture/data/OP-RES-006A-role-responsibility-matrix.csv) | Process roles matrix |
| [`architecture/data/OP-RES-006A-drafting-path-matrix.csv`](architecture/data/OP-RES-006A-drafting-path-matrix.csv) | Three drafting paths (A/B/C) |
| [`architecture/data/OP-RES-006A-text-provenance-matrix.csv`](architecture/data/OP-RES-006A-text-provenance-matrix.csv) | Text layers and provenance |
| [`architecture/data/OP-RES-006A-intake-validation-matrix.csv`](architecture/data/OP-RES-006A-intake-validation-matrix.csv) | Intake checks I001–I026 |
| [`architecture/data/OP-RES-006A-op-res-006-impact-matrix.csv`](architecture/data/OP-RES-006A-op-res-006-impact-matrix.csv) | OP-RES-006 impact analysis |

### OP-RES-006A Diagrams

| Diagram | Description |
|---|---|
| [`architecture/diagrams/operational-order-initiation-flow.svg`](architecture/diagrams/operational-order-initiation-flow.svg) | Initiation chain |
| [`architecture/diagrams/content-author-vs-document-operator.svg`](architecture/diagrams/content-author-vs-document-operator.svg) | Author vs operator |
| [`architecture/diagrams/three-drafting-paths.svg`](architecture/diagrams/three-drafting-paths.svg) | Models A/B/C |
| [`architecture/diagrams/submitted-text-intake-flow.svg`](architecture/diagrams/submitted-text-intake-flow.svg) | Intake flow |
| [`architecture/diagrams/text-provenance-model.svg`](architecture/diagrams/text-provenance-model.svg) | Provenance model |
| [`architecture/diagrams/content-confirmation-flow.svg`](architecture/diagrams/content-confirmation-flow.svg) | Content confirmation |
| [`architecture/diagrams/intake-localization-approval-boundary.svg`](architecture/diagrams/intake-localization-approval-boundary.svg) | Intake/localization/approval boundaries |

---

## OP-RES-001 Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-001-corpus-passport.md`](research/OP-RES-001-corpus-passport.md) | Human-readable corpus passport |
| [`research/data/OP-RES-001-corpus-inventory-summary.csv`](research/data/OP-RES-001-corpus-inventory-summary.csv) | Aggregated metrics (Git-safe) |
| [`research/data/OP-RES-001-corpus-inventory.csv`](research/data/OP-RES-001-corpus-inventory.csv) | Full file-level registry (may contain PII in paths; local/ignored) |
| [`research/scripts/op_res_001_inventory.py`](research/scripts/op_res_001_inventory.py) | Reproducible inventory script |

## OP-RES-002 Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-002-structural-pattern-analysis.md`](research/OP-RES-002-structural-pattern-analysis.md) | Structural pattern analysis report |
| [`research/diagrams/operational-order-structure.svg`](research/diagrams/operational-order-structure.svg) | Canonical block sequence diagram |
| [`research/diagrams/operational-order-blocks.svg`](research/diagrams/operational-order-blocks.svg) | Document Engine block decomposition |
| [`research/diagrams/operational-order-structure.drawio`](research/diagrams/operational-order-structure.drawio) | Draw.io source |
| [`research/samples/anonymized-structure-skeleton.txt`](research/samples/anonymized-structure-skeleton.txt) | Anonymized structure skeleton |

## OP-RES-003 Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-003-operational-order-taxonomy.md`](research/OP-RES-003-operational-order-taxonomy.md) | Domain taxonomy report |
| [`research/data/OP-RES-003-order-taxonomy-summary.csv`](research/data/OP-RES-003-order-taxonomy-summary.csv) | Per-document taxonomy + aggregates |
| [`research/diagrams/operational-order-taxonomy.svg`](research/diagrams/operational-order-taxonomy.svg) | Taxonomy tree diagram |
| [`research/diagrams/operational-order-domain-map.svg`](research/diagrams/operational-order-domain-map.svg) | Preliminary domain map |
| [`research/diagrams/operational-order-intents.svg`](research/diagrams/operational-order-intents.svg) | Business intent frequencies |
| [`research/diagrams/operational-order-managed-objects.svg`](research/diagrams/operational-order-managed-objects.svg) | Managed object frequencies |

## OP-RES-004 Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-004-control-and-execution-model.md`](research/OP-RES-004-control-and-execution-model.md) | Control & execution model report |
| [`research/data/OP-RES-004-control-execution-matrix.csv`](research/data/OP-RES-004-control-execution-matrix.csv) | Scenario execution matrix (21 rows, anonymized) |
| [`research/data/OP-RES-004-corpus-probe-stats.txt`](research/data/OP-RES-004-corpus-probe-stats.txt) | Corpus probe aggregates |
| [`research/scripts/op_res_004_execution_probe.py`](research/scripts/op_res_004_execution_probe.py) | Read-only research script |
| [`research/samples/anonymized-execution-patterns.md`](research/samples/anonymized-execution-patterns.md) | Anonymized pattern library |
| [`research/diagrams/operational-order-execution-model.svg`](research/diagrams/operational-order-execution-model.svg) | Execution model diagram |
| [`research/diagrams/control-responsibility-model.svg`](research/diagrams/control-responsibility-model.svg) | Control vs responsibility |
| [`research/diagrams/execution-obligation-anatomy.svg`](research/diagrams/execution-obligation-anatomy.svg) | Obligation anatomy |
| [`research/diagrams/execution-lifecycle-concept.svg`](research/diagrams/execution-lifecycle-concept.svg) | Lifecycle concept |
| [`research/diagrams/commission-execution-model.svg`](research/diagrams/commission-execution-model.svg) | Commission model |

## OP-RES-005 Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-005-generation-model.md`](research/OP-RES-005-generation-model.md) | Generation model report |
| [`research/data/OP-RES-005-item-type-registry.csv`](research/data/OP-RES-005-item-type-registry.csv) | 14 semantic item families |
| [`research/data/OP-RES-005-scenario-generation-matrix.csv`](research/data/OP-RES-005-scenario-generation-matrix.csv) | 21 scenario blueprints |
| [`research/data/OP-RES-005-validation-rules.csv`](research/data/OP-RES-005-validation-rules.csv) | Validation rules V001–W010 |
| [`research/scripts/op_res_005_generation_probe.py`](research/scripts/op_res_005_generation_probe.py) | Read-only research script |
| [`research/samples/OP-RES-005-anonymized-generation-patterns.md`](research/samples/OP-RES-005-anonymized-generation-patterns.md) | Anonymized generation patterns |
| [`research/samples/OP-RES-005-p0-generation-blueprints.md`](research/samples/OP-RES-005-p0-generation-blueprints.md) | P0 scenario blueprints |
| [`research/diagrams/operational-order-generation-pipeline.svg`](research/diagrams/operational-order-generation-pipeline.svg) | Generation pipeline |
| [`research/diagrams/generation-model-concept.svg`](research/diagrams/generation-model-concept.svg) | Generation model concept |
| [`research/diagrams/order-item-generation-anatomy.svg`](research/diagrams/order-item-generation-anatomy.svg) | Order item anatomy |
| [`research/diagrams/multilingual-generation-model.svg`](research/diagrams/multilingual-generation-model.svg) | Multilingual generation |
| [`research/diagrams/generation-execution-boundary.svg`](research/diagrams/generation-execution-boundary.svg) | Generation vs execution |
| [`research/diagrams/scenario-blueprint-model.svg`](research/diagrams/scenario-blueprint-model.svg) | Scenario blueprint |

## OP-RES-005A Artifacts

| Artifact | Description |
|---|---|
| [`research/OP-RES-005A-bilingual-drafting-workflow.md`](research/OP-RES-005A-bilingual-drafting-workflow.md) | Bilingual workflow validation |
| [`research/data/OP-RES-005A-language-pair-summary.csv`](research/data/OP-RES-005A-language-pair-summary.csv) | Language pair summary |
| [`research/data/OP-RES-005A-workflow-evidence-summary.csv`](research/data/OP-RES-005A-workflow-evidence-summary.csv) | Workflow evidence |
| [`research/data/OP-RES-005A-refined-pair-counts.txt`](research/data/OP-RES-005A-refined-pair-counts.txt) | Refined pair counts |
| [`research/scripts/op_res_005a_bilingual_probe.py`](research/scripts/op_res_005a_bilingual_probe.py) | Bilingual probe script |
| [`research/scripts/op_res_005a_pair_refine.py`](research/scripts/op_res_005a_pair_refine.py) | Pair refine script |

---

## Source (external, read-only)

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы\
```

См. также: [`docs/personnel-orders/inventories/ORDER-SAMPLES-INVENTORY-REPORT.md`](../personnel-orders/inventories/ORDER-SAMPLES-INVENTORY-REPORT.md)

Personnel Orders (read-only reference for OP-RES-006): [`docs/personnel-orders/architecture/`](../personnel-orders/architecture/)
