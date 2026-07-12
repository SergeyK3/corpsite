# UDE-006 — Data and Lifecycle Migration Strategy

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Principle

**No migration until a concrete shared persistence need is proven.**

Default: read-time projection via adapters.

---

## 2. Data Migration Modes Evaluated

| Mode | Verdict for PO |
|---|---|
| No migration | **Default** — identity, lifecycle, archive, items, employee_events |
| Lazy adaptation | **Recommended** — locale views, audit projection |
| Read-time projection | **Recommended** — adapter layer Phase C |
| Background backfill | **Deferred** — signed snapshot only with explicit WP |
| Explicit migration | **Future** — shared persistence unification only when proven |
| Dual-write | **Rejected** until Phase F+ with ratification |

---

## 3. Per-Group Strategy

| Group | Strategy | Notes |
|---|---|---|
| Identity | No migration | order_id remains PK |
| Lifecycle | Read-time projection | status/void_kind unchanged |
| Audit | Lazy adaptation | No backfill missing events |
| Archive | No migration | archived_at already correct |
| Localized text | Read-time projection | Effective = authority |
| Editorial blocks | Read-time projection | Map to UDE-003 |
| Items | No migration | employee_id in place |
| Snapshots | Lazy on next transition | No mass regeneration |
| Registration | No migration | order_number as-is |
| Employee events | **Never migrate/recreate** | ADR-035 chain preserved |
| PDF artifacts | No migration | Existing prints retained |

---

## 4. Synthetic Activation

### 4.1 Model

```text
existing PO row → considered already activated
                → synthetic activation metadata (derived)
                → NO historical rewrite
```

### 4.2 Rules

| Question | Answer |
|---|---|
| Synthetic activation event needed? | **Derived metadata only** — not persisted audit |
| Compute activation_at? | Yes: `created_at` or first-save timestamp |
| Backfill required? | **No** |
| Virtual adapter-only? | **Yes** — PersonnelActivationAdapter |
| Fabricate audit history? | **No** (ADR-UDE-021) |
| Legacy DRAFT | Treated as activated DRAFT |
| SIGNED/REGISTERED/VOIDED | Activated + lifecycle state as stored |

### 4.3 Optional Migration Marker

Future: `ude_compatibility_version` column — **deferred** until shared persistence WP. Not required for Phase C.

---

## 5. Lifecycle Compatibility

| Difference | Strategy |
|---|---|
| No ReturnToDraft | Preserve; implement in PO-CONV only |
| READY editability drift | **Normalize to UDE target for new OO**; PO preserve backend behavior |
| No signed snapshot | Lazy snapshot-on-next-transition (Phase F) |
| Register-from-DRAFT | **Preserve** via RegistrationAdapter |
| Combined sign/register | **Preserve** as PO shortcut |
| Apply/void chain | **Preserve** as specialization |
| Incomplete audit | Do not backfill; add forward on convergence |

---

## 6. Signed Snapshot Strategy (Legacy PO)

| Question | Answer |
|---|---|
| Sufficient data for snapshot? | **Yes** — effective texts + structure + items + signer fields |
| Use stored effective texts? | **Yes** — authority |
| Use existing PDF as artifact? | Optional reference; snapshot text authoritative |
| Historical backfill? | **No mass backfill** |
| snapshot-on-first-read? | Read-only projection only; not legal mutation |
| snapshot-on-next-transition | **Preferred** when PO-CONV implements Sign |
| SIGNED/REGISTERED existing | Unchanged; lazy materialization if needed |
| Silent regeneration? | **Prohibited** |

---

## 7. Locale Compatibility

| PO Field | UDE Mapping |
|---|---|
| generated RU/KK | Generated Text layer |
| effective RU/KK | Effective Text — **authority for legacy** |
| manual edit flags | Override provenance |
| STALE / REVIEW_REQUIRED | LocalizationLifecycleState |
| missing generated | Adapter uses effective-only; no regen |
| legacy only-effective | Valid; fingerprint optional deferred |

**Rule:** Existing effective text is authority. No silent regeneration on adapter read.

---

## 8. Dual Model Period

Expected controlled stage:

```text
PO legacy-native persistence  ||  OO shared-native persistence
         \                      /
          \   shared read contracts /
           \   adapters           /
            \____________________/
```

Not an architectural error. See ADR-UDE-018.

Diagram: [`diagrams/dual-model-period.svg`](./diagrams/dual-model-period.svg)

---

*Matrix: [`data/UDE-006-data-migration-matrix.csv`](./data/UDE-006-data-migration-matrix.csv)*  
*Diagram: [`diagrams/personnel-lifecycle-compatibility.svg`](./diagrams/personnel-lifecycle-compatibility.svg)*
