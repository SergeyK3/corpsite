# Unified Document Engine — Architecture Documentation

WP series defining the **Unified Document Engine (UDE)** shared architecture for Personnel Orders, Operational Orders, and future document families.

**Mode:** Architecture foundation only — no runtime changes in architecture WPs unless explicitly stated.

**Runtime status:** Production Personnel Orders behavior **unchanged** through UDE-012. Shared write runtime complete; PO write-path untouched. **Shared Runtime stack finished.**

---

## UDE-012 Summary

| Item | Detail |
|---|---|
| Package | `app/document_engine/write/` |
| Facade | `DocumentEngineWriteFacade` |
| Components | Commands, Command Policies, Write Orchestrator, Aggregate Factory, Domain Events |
| Models | DocumentAggregate, LifecycleMutationPlan, WriteEvaluation, etc. |
| Production PO changes | **None** |
| Record | [UDE-012-shared-write-runtime.md](./UDE-012-shared-write-runtime.md) |
| Next | **OO-IMP-001** — Operational Orders implementation |

---

## UDE-011 Summary

| Item | Detail |
|---|---|
| Package | `app/document_engine/lifecycle/` |
| Facade | `DocumentEngineLifecycleFacade` |
| Services | Activation, LifecycleEvaluation, Readiness, Promotion, Registration policies |
| Models | ActivationDecision, LifecycleEvaluation, PromotionReadiness, etc. |
| Production PO changes | **None** |
| Record | [UDE-011-shared-activation-and-lifecycle-runtime.md](./UDE-011-shared-activation-and-lifecycle-runtime.md) |

---

## UDE-010 Summary

| Item | Detail |
|---|---|
| Package | `app/document_engine/editorial/` |
| Facade | `DocumentEngineEditorialFacade` |
| Services | Editorial, Localization, Fingerprint, OverrideResolver, ReviewPolicy, OfficialDraftBuilder |
| Models | EditorialDocument, EditorialBlock, OfficialDraftSnapshot, ReviewState, etc. |
| Production PO changes | **None** |
| Record | [UDE-010-shared-editorial-runtime.md](./UDE-010-shared-editorial-runtime.md) |

---

## UDE-009 Summary

| Item | Detail |
|---|---|
| Packages | `app/document_engine/read_models/`, `app/document_engine/read_services/` |
| Facade | `DocumentEngineReadFacade` |
| Services | Document, Lifecycle, Localization, Audit, Print, Item read services |
| Read models | 6 shared runtime read models (not ORM, not API DTO) |
| Production PO changes | **None** |
| Record | [UDE-009-shared-read-services.md](./UDE-009-shared-read-services.md) |

---

## UDE-008 Summary

| Item | Detail |
|---|---|
| Package | `app/document_engine/adapters/personnel/` |
| Facade | `PersonnelReadAdapter` |
| Adapters | Document, Party, Lifecycle, Locale, Item, Audit, Print + CompatibilityHarness |
| First consumer | All 14 UDE-007 runtime contracts |
| Production PO changes | **None** |
| Record | [UDE-008-shared-read-adapters.md](./UDE-008-shared-read-adapters.md) |

---

## Work Packages

| WP | Title | Status | Main document |
|---|---|---|---|
| UDE-000 | Architecture Ratification | Complete | [`../operational-orders/architecture/`](../operational-orders/architecture/) |
| UDE-001 | Shared Terminology and Contracts | Complete | [UDE-001-shared-terminology-and-contracts.md](./UDE-001-shared-terminology-and-contracts.md) |
| UDE-002 | Draft Intake and Text Provenance | Complete | [UDE-002-draft-intake-and-text-provenance.md](./UDE-002-draft-intake-and-text-provenance.md) |
| UDE-003 | Shared Editorial and Localization Core | Complete | [UDE-003-shared-editorial-and-localization-core.md](./UDE-003-shared-editorial-and-localization-core.md) |
| UDE-004 | Document Activation and Promotion | Complete | [UDE-004-document-activation-and-promotion.md](./UDE-004-document-activation-and-promotion.md) |
| UDE-005 | Shared Lifecycle Core and Orchestration | Complete | [UDE-005-shared-lifecycle-core-and-orchestration.md](./UDE-005-shared-lifecycle-core-and-orchestration.md) |
| **UDE-006** | **Personnel Orders Compatibility and Extraction Plan** | **Complete** | [UDE-006-personnel-orders-compatibility-and-extraction-plan.md](./UDE-006-personnel-orders-compatibility-and-extraction-plan.md) |
| **UDE-007** | **Shared Runtime Contracts and PO Characterization Baseline** | **Complete (local)** | [UDE-007-shared-runtime-contracts-and-characterization-baseline.md](./UDE-007-shared-runtime-contracts-and-characterization-baseline.md) |
| **UDE-008** | **Shared Read-only Adapters for Personnel Orders** | **Complete (local)** | [UDE-008-shared-read-adapters.md](./UDE-008-shared-read-adapters.md) |
| **UDE-009** | **Shared Read Services and Document Read Model** | **Complete (local)** | [UDE-009-shared-read-services.md](./UDE-009-shared-read-services.md) |
| **UDE-010** | **Shared Editorial & Localization Runtime** | **Complete (local)** | [UDE-010-shared-editorial-runtime.md](./UDE-010-shared-editorial-runtime.md) |
| **UDE-011** | **Shared Activation & Lifecycle Runtime** | **Complete (local)** | [UDE-011-shared-activation-and-lifecycle-runtime.md](./UDE-011-shared-activation-and-lifecycle-runtime.md) |
| **UDE-012** | **Shared Write Runtime and Document Aggregate Foundation** | **Complete (local)** | [UDE-012-shared-write-runtime.md](./UDE-012-shared-write-runtime.md) |
| — | **OO-IMP-001 Operational Orders Intake (first UDE consumer)** | **Complete (local)** | [`../operational-orders/implementation/OO-IMP-001-submitted-text-intake-mvp.md`](../operational-orders/implementation/OO-IMP-001-submitted-text-intake-mvp.md) |
| — | **OO-IMP-003 Document Aggregate & Promotion** | **Complete (local)** | [`../operational-orders/implementation/OO-IMP-003-official-draft-package.md`](../operational-orders/implementation/OO-IMP-003-official-draft-package.md) |
| — | **OO-IMP-003B Workspace Freeze & Drift Advisory** | **Complete (local)** | [`../operational-orders/implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md`](../operational-orders/implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md) |

---

## UDE-006 Conclusion

| Finding | Detail |
|---|---|
| Compatibility authority | [UDE-006-current-personnel-orders-baseline.md](./UDE-006-current-personnel-orders-baseline.md) |
| Data migration | **Not required** — read-time adapters |
| Strategy | Contracts → read adapters → OO native → optional PO convergence |
| Dual model | **Accepted** controlled period (PO legacy + OO shared) |
| F-003 resolved | employee_id authoritative; PartyReference via adapter |
| OO independence | **Confirmed** — does not wait for PO refactor |
| **Next WP** | **UDE-007** — first code WP; **no production behavior change** |

---

## UDE-006 Artifacts

| Type | Path |
|---|---|
| Main | [UDE-006-personnel-orders-compatibility-and-extraction-plan.md](./UDE-006-personnel-orders-compatibility-and-extraction-plan.md) |
| Baseline | [UDE-006-current-personnel-orders-baseline.md](./UDE-006-current-personnel-orders-baseline.md) |
| Mapping | [UDE-006-current-to-target-mapping.md](./UDE-006-current-to-target-mapping.md) |
| Adapters | [UDE-006-compatibility-adapter-model.md](./UDE-006-compatibility-adapter-model.md) |
| Migration | [UDE-006-data-and-lifecycle-migration-strategy.md](./UDE-006-data-and-lifecycle-migration-strategy.md) |
| Testing | [UDE-006-characterization-and-compatibility-testing.md](./UDE-006-characterization-and-compatibility-testing.md) |
| Roadmap | [UDE-006-implementation-roadmap.md](./UDE-006-implementation-roadmap.md) |
| ADRs | [UDE-006-adr-addendum.md](./UDE-006-adr-addendum.md) |
| UDE-007 package | [UDE-006-ude-007-initiation-package.md](./UDE-006-ude-007-initiation-package.md) |
| Data matrices | [`data/UDE-006-*.csv`](./data/) |
| Diagrams | [`diagrams/`](./diagrams/) (10 migration diagrams) |

---

## Dependency Chain

```text
UDE-000 Ratification
    → UDE-001 Terminology & Contracts
        → UDE-002 Draft Intake
            → UDE-003 Editorial & Localization
                → UDE-004 Activation & Promotion
                    → UDE-005 Lifecycle Core
                        → UDE-006 PO Compatibility Plan  ← complete
                            → UDE-007 Contracts + Tests  ← complete (local)
                                → UDE-008 Read Adapters  ← complete (local)
                                    → UDE-009 Read Services  ← complete (local)
                                        → UDE-010 Editorial Runtime  ← complete (local)
                                            → UDE-011 Lifecycle Runtime  ← complete (local)
                                                → UDE-012 Write Runtime  ← complete (local)
                                                    → OO-IMP-001 (next)
                                → OO-IMP-001..005
                                → PO-CONV-001 (optional)
```

---

## Shared Runtime Complete

UDE-007 through UDE-012 deliver the full Shared Runtime stack:

| Layer | Facade |
|---|---|
| Contracts (UDE-007) | `app.document_engine` |
| Read Adapters (UDE-008) | `PersonnelReadAdapter` |
| Read Services (UDE-009) | `DocumentEngineReadFacade` |
| Editorial (UDE-010) | `DocumentEngineEditorialFacade` |
| Lifecycle (UDE-011) | `DocumentEngineLifecycleFacade` |
| Write (UDE-012) | `DocumentEngineWriteFacade` |
| **OO Intake (OO-IMP-001)** | **First native consumer — contracts only; no write facade** |
| **OO Editorial (OO-IMP-002)** | **Translation, confirmation, reconciliation; still no Document Aggregate** |

## OO-IMP-001 Complete

**OO-IMP-001 — Submitted-text Intake MVP**

- First Operational Orders production WP
- First native Shared UDE consumer (`LocaleCode`, `TextSourceType`, `ValidationResult`, `PartyReference`, `DraftingPath`)
- OO-scoped persistence and API — not in Shared Runtime
- `DocumentEngineWriteFacade` **not** invoked at intake stage
- Personnel Orders behavior unchanged

## OO-IMP-002 Complete

**OO-IMP-002 — Content Confirmation and Translation Workflow**

- Translation assignment lifecycle (RU-only / KK-only paths)
- Per-block content confirmation with fingerprint binding
- Bilingual reconciliation and `EDITORIAL_PACKAGE_READY` gate
- Uses UDE `ValidationResult` for OO201–OO213 rule codes
- Still no `DocumentId` / Document Aggregate / write facade
- Personnel Orders behavior unchanged

Record: [`../operational-orders/implementation/OO-IMP-002-content-confirmation-translation-workflow.md`](../operational-orders/implementation/OO-IMP-002-content-confirmation-translation-workflow.md)

## OO-IMP-003 / 003B Complete

**OO-IMP-003** introduced `DocumentId`, Version 1 snapshot, and idempotent promotion birth event (UDE-004 alignment).

**OO-IMP-003B** closes ratified gaps from OO-IMP-003A:

- Workspace freezes to `DOCUMENT_PROMOTED` after promotion (UDE-004 workspace post-promotion model)
- Mutating workspace commands blocked with `OO_WORKSPACE_FROZEN`
- Re-promote compares workspace fingerprint vs promotion snapshot; returns revision advisory on drift (HTTP 200)
- No Version 2, no Revision Command in this WP

Records:
- [`../operational-orders/implementation/OO-IMP-003-official-draft-package.md`](../operational-orders/implementation/OO-IMP-003-official-draft-package.md)
- [`../operational-orders/architecture/OO-IMP-003A-document-identity-ratification.md`](../operational-orders/architecture/OO-IMP-003A-document-identity-ratification.md)
- [`../operational-orders/implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md`](../operational-orders/implementation/OO-IMP-003B-workspace-freeze-drift-advisory.md)

Personnel Orders behavior unchanged.

---

## Next WP

**OO-IMP-004** — Revision Command and Version 2+ (separate from re-promote; builds on frozen workspace + drift advisory model).

---

*Last updated: 2026-07-12*
