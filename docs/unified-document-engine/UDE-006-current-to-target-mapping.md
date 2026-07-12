# UDE-006 — Current-to-Target Mapping

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Mapping Legend

| Type | Meaning |
|---|---|
| **exact_match** | Direct 1:1 mapping, no adapter |
| **partial_match** | Concept aligns; adapter or projection required |
| **adapter_required** | Read/write through compatibility adapter |
| **specialization_only** | Remains PO-specific; not shared |
| **refactor_required** | Future extraction WP only |
| **incompatible** | Must not force into shared model |
| **unknown** | Deferred clarification |

---

## 2. Core Mappings

### 2.1 Document Layer

| PO | UDE Target | Type |
|---|---|---|
| `PersonnelOrder` | Document Aggregate + Personnel Specialization | partial_match |
| `order_id` | DocumentId (adapter mapping) | adapter_required |
| `order_class=PERSONNEL` | DocumentKind.PersonnelOrder | exact_match |
| `created_at` (early create) | Synthetic Activation timestamp | adapter_required |

### 2.2 Items

| PO | UDE Target | Type |
|---|---|---|
| `PersonnelOrderItem` | OrderItem + personnel payload | partial_match |
| `item_type_code` | ItemType (personnel registry) | specialization_only |
| `employee_id` | Event Subject (authoritative) + PartyReference via adapter | adapter_required |
| `payload` JSONB | Personnel semantic payload | specialization_only |

### 2.3 Locale / Editorial

| PO | UDE Target | Type |
|---|---|---|
| `personnel_order_localized_texts` | LocaleRepresentation (legacy) | partial_match |
| Editorial blocks | LocaleRepresentation + Generated/Effective | partial_match |
| `review_status` STALE/REVIEW_REQUIRED | LocalizationLifecycleState | partial_match |
| RU/KK independent effective | UDE-003 independent locale model | exact_match (behavior) |

### 2.4 Lifecycle

| PO | UDE Target | Type |
|---|---|---|
| `status` | DocumentLifecycleState | exact_match |
| `void_kind` | Void Model | exact_match |
| `archived_at` | ArchiveState orthogonal | exact_match |
| `lifecycle_audit` | Shared Lifecycle Audit | partial_match |
| register shortcut | RegistrationAdapter + Sign skip | adapter_required |
| apply | ExecutionProjection (not lifecycle) | specialization_only |

### 2.5 Rendering

| PO | UDE Target | Type |
|---|---|---|
| Print View Model | Effective Localized Document / Print VM | partial_match |
| PDF route | Renderer artifact (PO contour) | specialization_only |
| HTML preview | Renderer preview | partial_match |

### 2.6 Execution

| PO | UDE Target | Type |
|---|---|---|
| `employee_events` | Personnel Execution Projection | specialization_only |
| apply/void chain | AnnulPolicy + Projection void | specialization_only |
| ADR-035 void chain | Specialization check L024 | specialization_only |

---

## 3. Mapping Summary Counts

| Type | Count |
|---|---|
| exact_match | 6 |
| partial_match | 12 |
| adapter_required | 8 |
| specialization_only | 10 |
| refactor_required | 0 (deferred to phases) |
| incompatible | 0 |

---

*Full matrix: [`data/UDE-006-current-to-target-matrix.csv`](./data/UDE-006-current-to-target-matrix.csv)*  
*Diagram: [`diagrams/personnel-current-to-ude-target.svg`](./diagrams/personnel-current-to-ude-target.svg)*
