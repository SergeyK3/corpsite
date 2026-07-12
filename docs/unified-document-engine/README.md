# Unified Document Engine — Architecture Documentation

WP series defining the **Unified Document Engine (UDE)** shared architecture for Personnel Orders, Operational Orders, and future document families.

**Mode:** Architecture foundation only — no runtime changes in architecture WPs unless explicitly stated.

**Runtime status:** Production Personnel Orders and Operational Orders behavior **unchanged** through UDE-006.

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
| UDE-007 | Shared Runtime Contracts and PO Characterization Baseline | **Next — Planned** | [UDE-006-ude-007-initiation-package.md](./UDE-006-ude-007-initiation-package.md) |

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
                            → UDE-007 Contracts + Tests (next)
                                → UDE-008 Adapters
                                → OO-IMP-001..005
                                → PO-CONV-001 (optional)
```

---

## Next: UDE-007

**UDE-007 — Shared Runtime Contracts and PO Characterization Baseline**

- First WP permitted to write code
- Must not change Personnel Orders production behavior
- Full scope: [UDE-006-ude-007-initiation-package.md](./UDE-006-ude-007-initiation-package.md)

---

*Last updated: 2026-07-12*
