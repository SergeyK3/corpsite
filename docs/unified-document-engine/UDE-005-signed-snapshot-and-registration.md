# UDE-005 — Signed Snapshot and Registration Model

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-009; UDE-004 immutable snapshot; PO register flow

---

## 1. Purpose

Define **Signed Immutable Snapshot** (legal boundary) and conceptual **Registration Model** with `RegistrationPolicy` extension point.

---

## 2. Signed Snapshot — ADR-UDE-009 Refinement

### 2.1 When Created

**At SIGNED transition** — atomic with `DOCUMENT_SIGNED` and `SIGNED_SNAPSHOT_CREATED`.

Not at Activation (UDE-004 baseline is mutable).  
Not at REGISTERED (registration metadata appended separately).

### 2.2 Minimum Contents

| Field group | Content |
|---|---|
| Identity | DocumentId, document_version, document_kind |
| Metadata | Authorship, org, type, dates (pre-registration) |
| Locale | RU effective representation; KK effective representation |
| Structure | Document shell snapshot |
| Items | Order items with semantic payload |
| Attachments | Attachments manifest (refs + hashes) |
| Signer | Signer identity snapshot |
| Reconciliation | Locale reconciliation status at sign |
| Validation | Validation summary at sign |
| Renderer | Template/renderer references |
| Integrity | content_hash |
| Timestamp | created_at |

### 2.3 Immutability at SIGNED

| Becomes immutable | Detail |
|---|---|
| Semantic model | Frozen |
| Generated text | Frozen |
| Effective text | Frozen per locale |
| Locale representations | Frozen |
| Order items | Frozen |
| Attachments manifest | Frozen |
| Structure | Frozen |
| Signer snapshot | Frozen |
| Document version | Pinned |

| Conditionally editable | Detail |
|---|---|
| Non-content metadata | Technical corrections via policy (audit required) |
| Registration fields | Added at REGISTERED only |

### 2.4 PDF Relationship

| Rule | Detail |
|---|---|
| PDF **not** part of signed snapshot core | Separate immutable artifact when produced |
| Re-render allowed | From signed snapshot + renderer ref |
| Authoritative on conflict | **Signed snapshot text** wins over re-rendered PDF |
| Hash | content_hash on snapshot; optional pdf_hash on artifact |
| PO current | Playwright PDF contour unchanged; not redesigned |

### 2.5 Reproducibility

Historical reproducibility = signed snapshot + renderer version + template ref. New renderer may differ visually; legal text from snapshot is authoritative.

### 2.6 Waiver at Sign

Sign with waiver: only non-waivable L* blockers forbidden. Waivers audited as `WAIVER_ISSUED`.

### 2.7 Technical Errors Post-Sign

Content errors → Annul + compensating document (specialization). No silent edit of signed snapshot.

---

## 3. Registration Model

### 3.1 When Number Assigned

**At REGISTERED transition** — atomic with `REGISTRATION_NUMBER_ASSIGNED`.

Default: not at Activation, not at SIGNED.

### 3.2 SIGNED Without REGISTERED

**Yes** — allowed. SIGNED document is legally signed but not yet officially numbered/registered. PO supports SIGNED as register target.

### 3.3 Registration Fields

| Field | At REGISTERED |
|---|---|
| registration_number | Assigned (immutable after) |
| registration_date | Required (immutable after) |
| register/journal | Journal entry official |
| numbering_scope | Per RegistrationPolicy |

### 3.4 Conceptual RegistrationPolicy Extension

| Policy hook | Responsibility |
|---|---|
| `numbering_scope` | Org, kind, year sequence |
| `sequence_reset` | Year reset rules |
| `reservation` | Optional pre-reserve before REGISTERED |
| `duplicate_prevention` | Unique within scope |
| `reservation_cancel` | Release reserved numbers |
| `historical_immutability` | Numbers never reused after VOIDED |

**Not in scope:** DB schema, numbering service implementation.

### 3.5 VOIDED and Registration Number

Number **retained** on voided document for historical audit. Not reassigned to new document.

### 3.6 REGISTERED Editability

**No content edit.** Registration metadata immutable after commit. Corrections via annulment + new document.

### 3.7 Execution Projection

**Default:** Execution Projection permitted after REGISTERED. Specialization may define earlier/later moment via `ProjectionPolicy`.

---

*Diagrams: [`diagrams/signed-snapshot-boundary.svg`](./diagrams/signed-snapshot-boundary.svg), [`diagrams/registration-boundary.svg`](./diagrams/registration-boundary.svg)*
