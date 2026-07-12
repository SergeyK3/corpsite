# UDE-006 — Implementation Roadmap

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Adoption Strategy (Ratified)

**Rejected:** D. Full rewrite, A. Direct extraction without adapters

**Recommended:**

```text
Shared contracts
  → compatibility adapters (read-first)
    → OO native shared-core implementation
      → incremental PO convergence (optional Phase F)
```

---

## 2. Extraction Phases A–F

### Phase A — Baseline and Characterization

| Item | Detail |
|---|---|
| Goal | Freeze behavior; capture tests |
| Deliverables | Baseline doc, test inventory, route map |
| Runtime | None |
| Exit | Characterization minimum P0 defined |

### Phase B — Shared Contracts in Code (UDE-007)

| Item | Detail |
|---|---|
| Goal | Types/contracts only in new modules |
| Deliverables | Lifecycle types, error taxonomy, contract stubs |
| Runtime | **No behavior change** |
| Exit | Contracts compile; existing tests green |

### Phase C — Read-only Adapters (UDE-008)

| Item | Detail |
|---|---|
| Goal | PO → shared views |
| Deliverables | A001–A008, A011, A012 adapters |
| Runtime | Read paths only; no write delegation |
| Exit | Harness parity pass |

### Phase D — OO Native Shared Core

| Item | Detail |
|---|---|
| Goal | OO-IMP-001 through OO-IMP-005 |
| Deliverables | Separate OO persistence; full UDE path |
| Runtime | PO unchanged |
| Exit | OO MVP lifecycle + rendering |

### Phase E — Selected Shared Services

| Item | Detail |
|---|---|
| Goal | lifecycle validation, audit helpers, locale utils |
| Deliverables | UDE-009; shared libraries consumed by OO |
| Runtime | PO may opt-in read-only |
| Exit | OO uses shared services in production |

### Phase F — Optional PO Write-path Convergence (PO-CONV-001)

| Item | Detail |
|---|---|
| Goal | Incremental PO migration |
| Deliverables | ReturnToDraft, signed snapshot, full audit |
| Runtime | **Separate ratified WP** |
| Exit | Compatibility harness + user acceptance |

Diagram: [`diagrams/incremental-extraction-phases.svg`](./diagrams/incremental-extraction-phases.svg)

---

## 3. Extraction Order (Units)

Lowest risk first:

1. U001 lifecycle types
2. U005 void_kind resolver
3. U003 archive guard
4. U004 audit contract
5. U009 document identity
6. U014 write lock policy
7. U012 journal filter protocol
8. U006/U007 locale utilities (UDE-009)
9. U011 cancel scope (stay PO-specialized longer)

---

## 4. Implementation WP Roadmap

| WP | Phase | Notes |
|---|---|---|
| **UDE-007** | A–B | **First implementation WP** |
| UDE-008 | C | Read adapters |
| UDE-009 | E | Editorial/locale runtime |
| OO-IMP-001 | D | Submitted-text intake |
| OO-IMP-002 | D | Content confirmation |
| OO-IMP-003 | D | Scenario generation |
| OO-IMP-004 | D | Lifecycle + rendering |
| OO-IMP-005 | D | Execution projection |
| PO-CONV-001 | F | Optional convergence |

---

## 5. Rollback Boundaries

| Phase | Rollback |
|---|---|
| A | N/A (docs only) |
| B | Delete contract modules |
| C | Disable adapter flag; PO path only |
| D | Disable OO module flag |
| E | Fallback to OO-local copies |
| F | Revert to PO service delegation |

Diagram: [`diagrams/rollback-boundaries.svg`](./diagrams/rollback-boundaries.svg)

---

## 6. Feature Flags (Conceptual)

| Flag | Default | Purpose |
|---|---|---|
| `ude_po_read_adapter` | off | Enable adapter read path |
| `ude_shared_lifecycle_validation` | off | Shared L-series in OO |
| `ude_oo_module` | off | OO feature visibility |
| `ude_oo_lifecycle` | off | OO lifecycle commands |

Rollback: flag off → legacy path.

---

## 7. Observability (Future)

- adapter invocation metrics
- harness mismatch alerts
- lifecycle failure by L-rule
- snapshot generation failures
- audit divergence detector
- PDF semantic comparison results
- feature flag state in deploy manifest

---

## 8. Operational Orders Independence

**Confirmed:** OO does not wait for PO refactor.

### Prerequisites before OO-IMP-001

| Component | Required? |
|---|---|
| UDE-007 shared contracts | **Yes** |
| UDE-002 intake architecture | Yes (design) |
| UDE-003 editorial architecture | Yes (design) |
| UDE-004 activation | Yes (OO native) |
| UDE-005 lifecycle | Yes (OO native in OO-IMP-004) |
| PO adapters | **No** — OO uses native path |
| PO extraction | **No** |

### May be stubs in OO MVP

- Full signed snapshot persistence (minimal at SIGNED)
- Registration numbering service (simple sequence)
- Event bus

### May use PO-inspired patterns without extraction

- void_kind resolution logic
- archive guard pattern
- append-only audit shape
- ready gate pattern

---

## 9. Recommended First Implementation WP

**UDE-007 — Shared Runtime Contracts and PO Characterization Baseline**

| Criterion | Why UDE-007 wins |
|---|---|
| Risk | Lowest — no behavior change |
| Blocks | Unblocks UDE-008, OO-IMP-001 |
| Evidence | Characterization before extraction (ADR-UDE-023) |
| vs PO Adapter only | Adapters need contracts first |
| vs OO intake first | OO needs shared types |
| vs characterization alone | UDE-007 includes both contracts + test baseline |

---

*Roadmap CSV: [`data/UDE-006-roadmap.csv`](./data/UDE-006-roadmap.csv)*  
*Diagram: [`diagrams/implementation-roadmap.svg`](./diagrams/implementation-roadmap.svg)*
