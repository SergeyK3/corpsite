# UDE-006 — Personnel Orders Compatibility and Shared Core Extraction Plan

WP: **UDE-006** — Personnel Orders Compatibility and Shared Core Extraction Plan  
Date: **2026-07-12**  
Status: **Architecture and Migration Planning — Complete**  
Prerequisites: UDE-000 ✓ · UDE-001 ✓ · UDE-002 ✓ · UDE-003 ✓ · UDE-004 ✓ · UDE-005 ✓  
Mode: **No runtime changes** — planning only

**Runtime unchanged:** No modifications to production code, PO, OO, API, UI, DB, PDF, or HTML.

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-006-current-personnel-orders-baseline.md](./UDE-006-current-personnel-orders-baseline.md) | Production behavior authority |
| [UDE-006-current-to-target-mapping.md](./UDE-006-current-to-target-mapping.md) | PO → UDE mapping |
| [UDE-006-compatibility-adapter-model.md](./UDE-006-compatibility-adapter-model.md) | 15 conceptual adapters |
| [UDE-006-data-and-lifecycle-migration-strategy.md](./UDE-006-data-and-lifecycle-migration-strategy.md) | No-migration default |
| [UDE-006-characterization-and-compatibility-testing.md](./UDE-006-characterization-and-compatibility-testing.md) | Test strategy + harness |
| [UDE-006-implementation-roadmap.md](./UDE-006-implementation-roadmap.md) | Phases A–F + OO path |
| [UDE-006-adr-addendum.md](./UDE-006-adr-addendum.md) | ADR-UDE-017–024 |
| [UDE-006-ude-007-initiation-package.md](./UDE-006-ude-007-initiation-package.md) | First code WP scope |
| [`data/`](./data/) | 10 compatibility matrices |
| [`diagrams/`](./diagrams/) | 10 migration diagrams |

---

## 1. Purpose

UDE-006 answers:

> **How to move from working Personnel Orders to Shared UDE Core without big-bang rewrite, without changing current behavior, and without blocking Operational Orders?**

**Principle:** Preserve behavior first → Extract contracts second → Add adapters third → Implement OO on shared core fourth → Converge PO only after proof.

---

## 2. Scope

### In scope

- PO production baseline (read-only)
- Current-to-target mapping
- Compatibility guarantees (24)
- Adoption strategy
- Compatibility adapter model
- Synthetic activation, locale, lifecycle, snapshot, rendering compatibility
- Authority, items, F-003 resolution, employee event boundary
- Journal, API, data migration strategy
- Dual model period
- Extraction units and phases A–F
- Characterization tests, harness, rollback, flags, observability
- OO independence proof
- Implementation roadmap
- UDE-007 initiation package
- ADR addendum
- Risk analysis and readiness

### Out of scope

- Any code, refactor, migration, API/UI change
- PO or OO behavior change
- Commit, push, deploy

---

## 3. Inputs and Ratified Decisions

From UDE-005: five lifecycle states, void_kind, archive orthogonality, L-series, signed snapshot at SIGNED, PO gap classification A–E.

From UDE-006 planning:

- **No immediate PO data migration**
- **No historical audit fabrication** (ADR-UDE-021)
- **Legacy effective text = authority** (ADR-UDE-019)
- **Dual model period acceptable** (ADR-UDE-018)
- **OO independent of PO convergence** (ADR-UDE-022)

---

## 4. Current Personnel Orders Baseline

**Compatibility authority:** [UDE-006-current-personnel-orders-baseline.md](./UDE-006-current-personnel-orders-baseline.md)

Summary: Five lifecycle statuses; void_kind CANCEL|ANNUL; orthogonal archive; granular cancel permissions; journal hides closed by default; DRAFT-only edit; register shortcut from DRAFT/READY; apply creates employee_events; Playwright PDF; RU/KK independent effective text.

---

## 5. Current Architecture Summary

```text
Frontend (Next.js) → PO API routes → Service layer → PostgreSQL
                              ↓
                    employee_events (execution)
                              ↓
                    Playwright PDF / HTML print VM
```

PO predates UDE Workspace/Activation path — early document creation at POST.

---

## 6. Current-to-Target Mapping

36 concept mappings. 6 exact, 12 partial, 8 adapter-required, 10 specialization-only.

Detail: [UDE-006-current-to-target-mapping.md](./UDE-006-current-to-target-mapping.md)

---

## 7. Compatibility Guarantees

24 guarantees G001–G024 across behavioral, data, API, rendering, lifecycle, authority dimensions.

**Critical:** Existing records readable; API unchanged; void_kind/archive/cancel scope preserved; no silent text regeneration; employee events not recreated; deploy independent of full migration.

Matrix: [`data/UDE-006-compatibility-guarantees.csv`](./data/UDE-006-compatibility-guarantees.csv)

---

## 8. Shared Core Adoption Strategy

| Option | Verdict |
|---|---|
| A. Direct extraction | Rejected — too risky |
| B. Contracts + adapters | **Recommended foundation** |
| C. Parallel OO + later PO converge | **Recommended execution** |
| D. Full rewrite | **Rejected** |

```text
Shared contracts → PO adapters (read) → OO native → PO converge (optional F)
```

---

## 9. Compatibility Adapter Model

15 adapters A001–A015. Phase C: read-only (A001–A008, A011, A012). Phase F: optional write facades.

Detail: [UDE-006-compatibility-adapter-model.md](./UDE-006-compatibility-adapter-model.md)

---

## 10. Synthetic Activation Strategy

Existing PO → **already activated** (derived view). `activation_at ≈ created_at`. No DOCUMENT_ACTIVATED backfill. PersonnelActivationAdapter read-only.

---

## 11. Locale Compatibility

PO generated/effective RU/KK maps to UDE-003 layers. **Effective text is authority** for legacy. Missing generated → adapter uses effective-only. No silent regeneration.

Diagram: [`diagrams/locale-compatibility-model.svg`](./diagrams/locale-compatibility-model.svg)

---

## 12. Lifecycle Compatibility

| PO behavior | UDE-006 strategy |
|---|---|
| No ReturnToDraft | Preserve; PO-CONV later |
| READY drift (docs vs code) | PO preserve backend; OO use UDE target |
| No signed snapshot | Lazy on next transition |
| Register-from-DRAFT | Preserve via adapter |
| Combined sign/register | Preserve shortcut |
| Incomplete audit | Forward-only; no backfill |

Diagram: [`diagrams/personnel-lifecycle-compatibility.svg`](./diagrams/personnel-lifecycle-compatibility.svg)

---

## 13. Signed Snapshot Strategy (Legacy)

Sufficient data in effective texts + structure. No mass backfill. Optional lazy materialization on next lifecycle transition in PO-CONV. Existing PDF may reference; snapshot text authoritative. **No PDF regeneration required.**

---

## 14. Rendering Compatibility

Reusable: effective-text semantics, language modes, print VM pattern. PO-specific: document titles, item templates, Playwright route. Shared renderer coexists via PersonnelPrintAdapter. **Playwright unchanged.**

---

## 15. Authority Compatibility

| Shared capability | PO mapping |
|---|---|
| mark_ready | ready-for-signature endpoint |
| register | register endpoint |
| cancel | cancel + CANCEL_OWN/SCOPE |
| annul | void endpoint |
| archive/restore | archive/restore + permissions |
| sign | embedded in register shortcut |

Document authority ≠ execution responsibility (apply separate).

---

## 16. Personnel Item Compatibility

HIRE, TRANSFER, TERMINATION, CONCURRENT_DUTY_*, COMPOSITE → Personnel Item Registry (specialization). `employee_id` authoritative in persistence. Adapter maps to OrderItem view.

---

## 17. Employee Identity vs Party Reference (F-003)

**Resolution (ADR-UDE-020):**

- Shared `PartyReference` supports named-person: `type=PERSON, ref=employee_id`
- PO persistence keeps `employee_id` — **no DB replacement**
- **Event Subject ≠ Responsible Party**
- Role-first Party applies to operational obligations; personnel events use employee identity
- Historical employee snapshot stored separately in event projection

---

## 18. Employee Event Boundary

| Rule | Detail |
|---|---|
| employee_events | **Outside** Shared Document Core |
| apply/void chain | PO specialization only |
| Document lifecycle | Does not auto-apply events |
| ADR-035 void chain | Preserved unchanged |
| Future shared projection | Specialization adapter only |

Diagram: [`diagrams/employee-event-boundary.svg`](./diagrams/employee-event-boundary.svg)

---

## 19. Journal Compatibility

PO journal: hides VOIDED + archived; `include_closed` opt-in; `include_archived` alias.

**Preference:** Separate specialization journals initially (PO, OO). Shared Document Journal contract later. **No PO UX change in migration phases A–E.**

---

## 20. API Compatibility

- Existing PO API **remains authoritative**
- Shared contracts internal only until explicit publish WP
- OO gets new API in OO-IMP
- Unified API not required for MVP
- Legacy aliases preserved (`include_archived`)

---

## 21. Data Migration Strategy

**Default: No migration.** Read-time projection. See [UDE-006-data-and-lifecycle-migration-strategy.md](./UDE-006-data-and-lifecycle-migration-strategy.md).

---

## 22. Dual Model Period

```text
PO legacy persistence  ||  OO shared-native persistence
         \___________ shared read contracts ___________/
```

**Accepted controlled stage** — not architectural error.

Diagram: [`diagrams/dual-model-period.svg`](./diagrams/dual-model-period.svg)

---

## 23. Extraction Units

15 units U001–U015 ranked by risk. Lowest: lifecycle types, void_kind, archive guard, audit contract.

Matrix: [`data/UDE-006-extraction-unit-matrix.csv`](./data/UDE-006-extraction-unit-matrix.csv)

---

## 24. Extraction Phases A–F

| Phase | Name | Runtime impact |
|---|---|---|
| A | Baseline | None |
| B | Shared contracts (UDE-007) | None |
| C | Read adapters (UDE-008) | Read-only |
| D | OO native (OO-IMP) | PO none |
| E | Shared services (UDE-009) | PO optional |
| F | PO convergence (PO-CONV) | Ratified WP only |

Diagram: [`diagrams/incremental-extraction-phases.svg`](./diagrams/incremental-extraction-phases.svg)

---

## 25. Characterization Test Strategy

18 categories. P0 mandatory before refactor. Existing PO tests provide partial coverage; UDE-007 adds contract parity + inventory.

Detail: [UDE-006-characterization-and-compatibility-testing.md](./UDE-006-characterization-and-compatibility-testing.md)

---

## 26. Compatibility Harness

Compare Legacy PO Path vs Shared Adapter Path on: lifecycle, effective text, print VM, audit, errors, permissions. Acceptance: **same observable behavior**.

Diagram: [`diagrams/characterization-harness.svg`](./diagrams/characterization-harness.svg)

---

## 27. Rollback Strategy

Independent rollback per phase. Contracts: delete modules. Adapters: flag off. OO: module disable. Schema migration: not planned in A–E.

Diagram: [`diagrams/rollback-boundaries.svg`](./diagrams/rollback-boundaries.svg)

---

## 28. Feature Flags

Conceptual: `ude_po_read_adapter`, `ude_oo_module`, `ude_shared_lifecycle_validation`. Default off. Not implemented in UDE-006.

---

## 29. Observability

Future: adapter metrics, harness mismatch, audit divergence, PDF semantic compare, flag state.

---

## 30. Operational Orders Independence

**Confirmed:** OO starts after UDE-007 contracts; does not wait for PO refactor.

Before OO-IMP-001 required: UDE-007 contracts, UDE architecture (002–005 designs). Not required: PO adapters, PO extraction, unified persistence.

---

## 31. Implementation Roadmap

| WP | Role |
|---|---|
| **UDE-007** | First code — contracts + characterization |
| UDE-008 | Read adapters |
| UDE-009 | Editorial/locale runtime |
| OO-IMP-001–005 | OO MVP on shared core |
| PO-CONV-001 | Optional PO write convergence |

Detail: [UDE-006-implementation-roadmap.md](./UDE-006-implementation-roadmap.md)

---

## 32. Recommended First Implementation WP

**UDE-007 — Shared Runtime Contracts and PO Characterization Baseline**

First WP with code; **no production behavior change**. Unblocks adapters and OO.

---

## 33. UDE-007 Initiation Package

Full scope: [UDE-006-ude-007-initiation-package.md](./UDE-006-ude-007-initiation-package.md)

---

## 34. ADR Addendum

ADR-UDE-017 through ADR-UDE-024 proposed. Detail: [UDE-006-adr-addendum.md](./UDE-006-adr-addendum.md)

---

## 35. Risks and Mitigations

15 risks R001–R015. Top: accidental behavior change (R001), insufficient characterization (R015), audit fabrication (R004), signed regeneration (R005).

Matrix: [`data/UDE-006-risk-matrix.csv`](./data/UDE-006-risk-matrix.csv)

---

## 36. Readiness Review

| Area | Status |
|---|---|
| Baseline | **Ready** |
| Mapping | **Ready** |
| Adapters | **Ready** (conceptual) |
| Migration safety | **Ready** |
| OO independence | **Ready** |
| UDE-007 package | **Ready** |
| PO write convergence | **Deferred** (PO-CONV-001) |
| Unified API | **Deferred** |
| Big-bang rewrite | **Rejected** |

Matrix: [`data/UDE-006-readiness.csv`](./data/UDE-006-readiness.csv)

---

## 37. Conclusions

1. PO production behavior is frozen as compatibility authority
2. **No immediate data migration** required
3. Shared contracts + read adapters + OO native path is the safe strategy
4. Dual model period is expected and acceptable
5. F-003 resolved: employee_id authoritative; PartyReference via adapter
6. Debts D-class must not migrate to shared core
7. **UDE-007** is the first implementation WP
8. **No PO changes in UDE-006**

---

## Mandatory Answers

| # | Question | Answer |
|---|---|---|
| 1 | Compatibility authority? | **UDE-006-current-personnel-orders-baseline.md — actual production API/UI/rendering behavior** |
| 2 | Reusable foundation? | **Status enum, void_kind, lifecycle audit, archive guard, cancel/annul split** |
| 3 | Require adapter? | **Document aggregate view, locale, items, activation, party projection, journal, print VM, lifecycle write facade** |
| 4 | Personnel-specific? | **employee_events, apply/void chain, cancel scope, item semantics, basis policy, Playwright PDF contour** |
| 5 | Debts not in shared core? | **READY doc drift, incomplete audit, UI annul label, broad admin on register** |
| 6 | Immediate PO data migration? | **No** |
| 7 | Synthetic activation for legacy? | **Yes — derived metadata only; activation_at ≈ created_at** |
| 8 | Fabricate historical audit? | **No** (ADR-UDE-021) |
| 9 | Legacy locale authority? | **Existing effective text** |
| 10 | employee_id vs PartyReference? | **Adapter: PartyReference(PERSON, employee_id); DB keeps employee_id** |
| 11 | Event Subject vs Responsible Party? | **Different concepts; employee is event subject in PO** |
| 12 | Preserve apply/void chain? | **Yes — unchanged PO specialization** |
| 13 | Preserve lifecycle behavior? | **Yes — all shortcuts and transitions via adapters** |
| 14 | Preserve cancel/annul? | **Yes — void_kind mapping unchanged** |
| 15 | Preserve archive immutability? | **Yes — archive_guard unchanged** |
| 16 | Legacy without signed snapshot? | **Lazy materialization on next transition; no mass backfill; effective text authority** |
| 17 | Regenerate old PDFs? | **No** |
| 18 | API compatibility? | **PO API authoritative; no breaking changes; legacy aliases kept** |
| 19 | Authority/org scope? | **CANCEL_OWN/SCOPE preserved; ownership on cancel** |
| 20 | Journal behavior? | **Default hide closed; include_closed; separate OO journal initially** |
| 21 | PO on legacy persistence during OO MVP? | **Yes** |
| 22 | Dual model period? | **Yes — controlled expected stage** |
| 23 | First adapters? | **Document, Lifecycle, Locale, Item, Activation, Party, Audit (read-only)** |
| 24 | Lowest-risk extraction units? | **lifecycle types, void_kind, archive guard, audit contract, identity mapping** |
| 25 | Mandatory tests before refactor? | **P0: lifecycle, cancel/annul, archive, authority, journal** |
| 26 | Compare legacy vs shared? | **Compatibility harness — same observable behavior** |
| 27 | Rollback boundaries? | **Per phase: delete contracts / flag off adapters / disable OO module** |
| 28 | Feature flags? | **ude_po_read_adapter, ude_oo_module, ude_shared_lifecycle_validation (default off)** |
| 29 | OO before PO convergence? | **Yes** |
| 30 | UDE runtime required before OO-IMP-001? | **UDE-007 contracts; UDE 002–005 architecture; not PO extraction** |
| 31 | Next WP? | **UDE-007 — Shared Runtime Contracts and PO Characterization Baseline** |
| 32 | Why first code WP? | **Lowest risk; unblocks all paths; characterization before extraction** |
| 33 | ADRs to add? | **ADR-UDE-017 through ADR-UDE-024** |
| 34 | Ready for UDE-007? | **Yes** |
| 35 | PO changes in UDE-006? | **No — explicitly forbidden and not performed** |

---

*End of UDE-006 — Personnel Orders Compatibility and Shared Core Extraction Plan*
