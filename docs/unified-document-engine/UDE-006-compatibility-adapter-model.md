# UDE-006 — Compatibility Adapter Model

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Mode: **Conceptual only — no interfaces or code**

---

## 1. Purpose

Define **Personnel Compatibility Adapter** layer transforming PO persistence into UDE shared contract views **without changing persisted data**.

---

## 2. Adapter Architecture

```text
PO Persistence (authoritative)
        │
        ▼
┌───────────────────────────────┐
│  Personnel Compatibility      │
│  Adapter Layer (read-first)   │
└───────────────────────────────┘
        │
        ▼
UDE Shared Contract Views
        │
        ├── OO shared services (read)
        ├── Compatibility harness
        └── Reporting / future orchestrator
```

Diagram: [`diagrams/personnel-compatibility-adapter.svg`](./diagrams/personnel-compatibility-adapter.svg)

---

## 3. Adapter Catalog

### 3.1 PersonnelDocumentAdapter (A001)

| Aspect | Detail |
|---|---|
| Source | `personnel_orders` row + items + attachments |
| Target | `DocumentAggregateView` |
| Mode | **read-only** |
| Mapping | order_id → document_id; kind=PersonnelOrder |
| Phase | C |
| Side effects | None |

### 3.2 PersonnelLifecycleAdapter (A002)

| Aspect | Detail |
|---|---|
| Source | status, void_kind, void_reason, archived_at |
| Target | `DocumentLifecycleView` + `ArchiveStateView` |
| Mode | read-only |
| Mapping | 1:1 status; void_kind preserved |
| Phase | C |

### 3.3 PersonnelLocaleAdapter (A003)

| Aspect | Detail |
|---|---|
| Source | localized_texts + editorial_blocks |
| Target | `LocaleRepresentationView[]` |
| Mode | read-only |
| Rule | **effective text is authority** for legacy |
| Phase | C |

### 3.4 PersonnelItemAdapter (A004)

| Aspect | Detail |
|---|---|
| Source | personnel_order_items |
| Target | `OrderItemView` + `PersonnelItemPayload` |
| Mode | read-only |
| Rule | employee_id stays in payload; no DB rewrite to PartyReference |
| Phase | C |

### 3.5 PersonnelPrintAdapter (A005)

| Aspect | Detail |
|---|---|
| Source | existing print VM builder |
| Target | `SharedPrintViewModel` (conceptual) |
| Mode | read-only |
| Phase | C |

### 3.6 PersonnelAuthorityAdapter (A006)

| Aspect | Detail |
|---|---|
| Source | permission checks + cancel scope |
| Target | `CapabilityDecisionView` |
| Mode | read-only |
| Phase | C |

### 3.7 PersonnelAuditAdapter (A007)

| Aspect | Detail |
|---|---|
| Source | lifecycle_audit rows |
| Target | `LifecycleAuditEventView` |
| Mode | read-only |
| Note | Does not fabricate missing mark_ready events |
| Phase | C |

### 3.8 PersonnelActivationAdapter (A008)

| Aspect | Detail |
|---|---|
| Source | created_at, first save metadata |
| Target | `SyntheticActivationMetadata` |
| Mode | **derived read-only** |
| Rule | No historical DOCUMENT_ACTIVATED fabrication |
| Phase | C |

### 3.9 PersonnelPartyAdapter (A011)

| Aspect | Detail |
|---|---|
| Source | employee_id on items/header |
| Target | `PartyReference(type=PERSON, ref=employee_id)` |
| Mode | read-only projection |
| Phase | C |

### 3.10 Write Adapters (Phase F only)

| Adapter | Purpose | Constraint |
|---|---|---|
| PersonnelLifecycleWriteAdapter | Facade to existing services | Must delegate to PO services |
| PersonnelRegistrationAdapter | Preserve register shortcut | No behavior change |
| PersonnelSnapshotAdapter | Lazy signed snapshot | On transition only; auditable |

---

## 4. Adapter Rules

1. **PO persistence remains authoritative** until ratified migration WP
2. **Read adapters first** — no write through shared layer in Phase C
3. **No silent regeneration** when building views
4. **No audit fabrication** for historical gaps
5. **Side effects** only through existing PO services in Phase F

---

*Matrix: [`data/UDE-006-adapter-matrix.csv`](./data/UDE-006-adapter-matrix.csv)*
