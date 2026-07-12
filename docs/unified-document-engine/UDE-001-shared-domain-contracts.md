# UDE-001 — Shared Domain Contracts

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Matrix: [`data/UDE-001-contract-matrix.csv`](./data/UDE-001-contract-matrix.csv)

> Conceptual contracts only. No ORM, SQL, API, or runtime code.

---

## Contract Index

| Contract | Scope | Readiness |
|---|---|---|
| Document | Shared aggregate root | Ready |
| DocumentMetadata | Shared | Ready |
| DocumentStructure | Shared | Ready |
| DocumentSection | Shared | Ready |
| OrderItem | Shared shell; specialized payload | Ready |
| OrderItemSequence | Shared | Ready |
| BusinessIntent | Specialization payload | Ready |
| ExecutionObligation | Shared concept; specialized payload | Ready |
| ControlObligation | OO-primary; shared contract | Ready |
| ManagedObject | Shared concept; specialized taxonomy | Ready |
| PartyReference | Shared | Ready |
| Deadline | Shared | Ready |
| ExpectedResult | Specialization-optional | Ready |
| EvidenceExpectation | Specialization-optional | Ready |
| AttachmentReference | Shared | Ready |
| LocaleRepresentation | Shared | Ready |
| GeneratedText | Shared | Ready |
| EffectiveText | Shared | Ready |
| SubmittedText | Shared | Ready |
| TextProvenance | Shared | Ready |
| ContentConfirmation | Shared process contract | Needs clarification |
| ExecutionProjectionDescriptor | Shared handoff | Ready |
| ValidationResult | Shared | Ready |
| DocumentAuditEvent | Shared | Ready |
| DocumentLifecycleState | Shared | Ready |
| LocalizationLifecycleState | Shared | Ready |
| ExecutionLifecycleState | Shared (downstream) | Ready |

---

## Document

| Aspect | Definition |
|---|---|
| **Purpose** | Legal act instance; single consistency boundary for editorial and lifecycle mutations |
| **Responsibility** | Own metadata, structure, items, attachments, locale aggregate state, lifecycle, audit |
| **Mandatory properties** | DocumentId, DocumentKind, organization reference, DocumentLifecycleState, archive state |
| **Mandatory links** | DocumentMetadata, DocumentStructure, OrderItemSequence, DocumentAuditEvent[] |
| **In contract** | Aggregate boundary; authority rules by phase; immutability after SIGNED/REGISTERED |
| **NOT in contract** | ORM mapping; API resource shape; PO employee_events; OO task instances |
| **Personnel Orders** | Uses as PersonnelOrder specialization | 
| **Operational Orders** | Uses as OperationalOrder specialization |
| **Future reuse** | Protocols, commissions, directives — any numbered legal act with shell |

---

## DocumentMetadata

| Aspect | Definition |
|---|---|
| **Purpose** | Identity, ownership, and status of document instance |
| **Responsibility** | Kind selection, numbering, dates, lifecycle state, archive, authorship metadata |
| **Mandatory properties** | DocumentKind, DocumentNumber (nullable in draft), effective date concept, DocumentLifecycleState, ArchiveState, Record Creator reference, signing metadata placeholders |
| **Mandatory links** | Document (parent); optional Content Author PartyReference; optional Submitting Unit |
| **In contract** | Separation of content_author, created_by, document_operator roles |
| **NOT in contract** | employee_id; scenario_id as mandatory; paper journal sequence implementation |
| **Independence** | Fully shared |

---

## DocumentStructure

| Aspect | Definition |
|---|---|
| **Purpose** | Ordered structural shell common to legal acts |
| **Responsibility** | Canonical block sequence; section ordering; attachment placement |
| **Mandatory properties** | Ordered DocumentSection[]; block_kind per section |
| **Mandatory links** | Header, Preamble, Operative Formula, Items region, Attachments region, Signature, optional Agreement, optional Acknowledgement |
| **In contract** | Sequence: Header → Preamble → Formula → Items → Attachments → Signature → Agreement → Acknowledgement |
| **NOT in contract** | HTML layout; PDF page breaks; PO editorial block DB table names |
| **Independence** | Fully shared (97% corpus evidence) |

---

## DocumentSection

| Aspect | Definition |
|---|---|
| **Purpose** | Single block within Document Structure |
| **Responsibility** | Holds block_kind; links to locale representations for editorial blocks |
| **Mandatory properties** | section_kind, sequence position, mandatory/optional flag |
| **Mandatory links** | Parent DocumentStructure; LocaleRepresentation[] for text-bearing blocks |
| **In contract** | Maps to editorial block kinds; operative formula as print chrome |
| **NOT in contract** | WYSIWYG widget types; PO `editorial_blocks` column names |

---

## OrderItem

| Aspect | Definition |
|---|---|
| **Purpose** | Numbered generation and editorial unit |
| **Responsibility** | Semantic payload container; locale renderings; obligation attachment point |
| **Mandatory properties** | ItemType, sequence number, semantic_payload (specialized), validation state |
| **Mandatory links** | OrderItemSequence; ExecutionObligation[] (0..N); LocaleRepresentation[]; ValidationResult |
| **In contract** | Item-level regeneration scope; generated/effective/override per block |
| **NOT in contract** | HR event type enums; OO scenario-specific fields in shared mandatory set |
| **Specialization** | `semantic_payload` — Personnel: employee/dates/org; Operational: intent/party/deadline |

---

## OrderItemSequence

| Aspect | Definition |
|---|---|
| **Purpose** | Ordering and numbering discipline for items |
| **Responsibility** | Sequence integrity; sub-numbering rules; control meta-item placement |
| **Mandatory properties** | Ordered item references; numbering scheme |
| **Mandatory links** | DocumentStructure items region; OrderItem[] |
| **In contract** | BC001 numbering validation hooks |
| **NOT in contract** | Auto-renumber implementation |

---

## BusinessIntent

| Aspect | Definition |
|---|---|
| **Purpose** | Management meaning of directive |
| **Responsibility** | Classify what management action the item expresses |
| **Mandatory properties** | Intent classification (specialization registry) |
| **Mandatory links** | OrderItem; optional Scenario |
| **In contract** | Orthogonal to ItemType where possible |
| **NOT in contract** | PO hire/transfer event codes in shared enum |
| **Scope** | Specialization payload; shared contract shape only |

---

## ExecutionObligation

| Aspect | Definition |
|---|---|
| **Purpose** | Minimal executable management duty |
| **Responsibility** | Bind party, deadline, managed object, expected result, evidence |
| **Mandatory properties** | ObligationType=EXECUTION; PartyReference assignee; optional Deadline |
| **Mandatory links** | Parent OrderItem; ManagedObject; optional ExpectedResult; optional EvidenceExpectation; optional AttachmentReference[] |
| **In contract** | 0..N per item; projection source |
| **NOT in contract** | Task runtime status; employee_events table |
| **PO note** | Often collapsed 1:1 with item for MVP |

---

## ControlObligation

| Aspect | Definition |
|---|---|
| **Purpose** | Supervision duty separate from execution |
| **Responsibility** | Assign controller; define supervision scope |
| **Mandatory properties** | ObligationType=CONTROL; PartyReference controller |
| **Mandatory links** | OrderItem or document-level meta-item; scope reference |
| **In contract** | Never merged into ExecutionObligation |
| **NOT in contract** | `controller` boolean on execution row |
| **Scope** | OO-primary; contract shared for future commission protocols |

---

## ManagedObject

| Aspect | Definition |
|---|---|
| **Purpose** | Entity governed by obligation |
| **Responsibility** | Typed reference to process, document, commission, org unit, etc. |
| **Mandatory properties** | ManagedObjectType; reference identifier (specialized) |
| **Mandatory links** | ExecutionObligation or ControlObligation |
| **In contract** | Type taxonomy extensible via registry |
| **NOT in contract** | employee_id as shared mandatory field (PO specialization) |

---

## PartyReference

| Aspect | Definition |
|---|---|
| **Purpose** | Role-first pointer to Party |
| **Responsibility** | Represent assignee, controller, content author without HR turnover fragility |
| **Mandatory properties** | Reference kind (PositionRole, NamedPerson, OrganizationalUnit, Commission, ExternalParty) |
| **Mandatory links** | Optional resolution snapshot at document date |
| **In contract** | Role-first default; NamedPerson optional; frozen snapshot at SIGNED |
| **NOT in contract** | Access permission grants; task assignee runtime |

---

## Deadline

| Aspect | Definition |
|---|---|
| **Purpose** | Temporal constraint on obligation |
| **Responsibility** | Express due date, duration, or event-relative timing |
| **Mandatory properties** | DeadlineType; value or event anchor |
| **Mandatory links** | ExecutionObligation |
| **In contract** | Typed semantics (fixed date, N days, by event, continuous, permanent) |
| **NOT in contract** | Task scheduler cron expressions |

---

## ExpectedResult

| Aspect | Definition |
|---|---|
| **Purpose** | Declared outcome of obligation |
| **Responsibility** | Optional explicit result description |
| **Mandatory properties** | Result text or structured descriptor (specialized) |
| **In contract** | Do not auto-add by default (OP-RES-005) |
| **Scope** | Specialization-optional; shared contract shape |

---

## EvidenceExpectation

| Aspect | Definition |
|---|---|
| **Purpose** | Proof required for obligation closure |
| **Responsibility** | Declare evidence type and acknowledgment requirements |
| **Mandatory properties** | EvidenceType; optional attachment linkage |
| **Mandatory links** | ExecutionObligation; optional AttachmentReference |
| **In contract** | Distinct from implicit ack lists |
| **Scope** | OO-rich; PO often absent |

---

## AttachmentReference

| Aspect | Definition |
|---|---|
| **Purpose** | File or structured artifact linked to document or obligation |
| **Responsibility** | Reference storage; optional locale; obligation source role |
| **Mandatory properties** | AttachmentKind; storage reference; optional title |
| **Mandatory links** | DocumentStructure or ExecutionObligation |
| **In contract** | Scan, roster, plan, basis document roles |
| **NOT in contract** | S3 bucket names; upload API |

---

## LocaleRepresentation

| Aspect | Definition |
|---|---|
| **Purpose** | Per-locale block state |
| **Responsibility** | Hold generated, effective, provenance, localization lifecycle state |
| **Mandatory properties** | LocaleCode; GeneratedText; EffectiveText; LocalizationLifecycleState; TextProvenance; drafting_path |
| **Mandatory links** | OrderItem or DocumentSection; optional ContentConfirmation |
| **In contract** | Per-block granularity; mandatory locales for READY gate |
| **NOT in contract** | Machine translation service |

---

## GeneratedText

| Aspect | Definition |
|---|---|
| **Purpose** | System-produced prose from semantic model |
| **Responsibility** | Idempotent output of generation; fingerprint source |
| **Mandatory properties** | Text content; generation version reference |
| **Mandatory links** | LocaleRepresentation; TextProvenance (source_type=GENERATED) |
| **In contract** | Regenerable; not signing authority alone |
| **NOT in contract** | Template engine implementation |

---

## EffectiveText

| Aspect | Definition |
|---|---|
| **Purpose** | Authoritative wording for signing |
| **Responsibility** | override ?? generated; frozen at SIGNED |
| **Mandatory properties** | Text content; override flag; fingerprint |
| **Mandatory links** | LocaleRepresentation |
| **In contract** | Signing authority pre-sign; immutable post-sign |
| **NOT in contract** | Rich text editor widget |

---

## SubmittedText

| Aspect | Definition |
|---|---|
| **Purpose** | Text as received at intake before official acceptance |
| **Responsibility** | Preserve author-origin wording; provenance anchor |
| **Mandatory properties** | Text content; intake timestamp; source actor/unit |
| **Mandatory links** | LocaleRepresentation; TextProvenance (source_type=SUBMITTED) |
| **In contract** | Never auto-equal to EffectiveText |
| **NOT in contract** | Email attachment parser |

---

## TextProvenance

| Aspect | Definition |
|---|---|
| **Purpose** | Origin metadata for locale text |
| **Responsibility** | Audit reproducibility; distinguish SUBMITTED/GENERATED/TRANSLATED/MANUAL |
| **Mandatory properties** | TextSourceType; source_actor; source_unit; source_timestamp; derived_from_version |
| **Mandatory links** | LocaleRepresentation |
| **In contract** | Per-block minimum (ADR-UDE-013) |
| **NOT in contract** | Git-style diff storage |

---

## ContentConfirmation

| Aspect | Definition |
|---|---|
| **Purpose** | Content Author acknowledgment of meaning preservation |
| **Responsibility** | Gate READY when content-class editorial changes detected |
| **Mandatory properties** | Confirmed by PartyReference; timestamp; change class scope |
| **Mandatory links** | Document or LocaleRepresentation; Content Author |
| **In contract** | Form-only edits exempt (default policy); resets on new content change |
| **NOT in contract** | E-signature integration |
| **Readiness** | Needs clarification — interview gate for mandatory policy per change class |

---

## ExecutionProjectionDescriptor

| Aspect | Definition |
|---|---|
| **Purpose** | Downstream handoff payload for one obligation |
| **Responsibility** | Emit stable descriptor after REGISTERED; idempotent |
| **Mandatory properties** | Obligation identity; PartyReference snapshot; Deadline snapshot; ManagedObject snapshot |
| **Mandatory links** | Source OrderItem; source ExecutionObligation; Document reference |
| **In contract** | Outside aggregate; eventual consistency OK |
| **NOT in contract** | Task CRUD; reminder scheduling |
| **Specialization** | PO adapter → employee_events; OO adapter → task contour (future) |

---

## ValidationResult

| Aspect | Definition |
|---|---|
| **Purpose** | Outcome of validation checks |
| **Responsibility** | Collect errors and warnings; block or warn transitions |
| **Mandatory properties** | ValidationCode[]; ValidationSeverity per finding; scope (document/item/locale) |
| **Mandatory links** | Validated entity (Document, OrderItem, LocaleRepresentation) |
| **In contract** | Errors block READY; warnings auditable; waiver policy hook |
| **NOT in contract** | Specific V001/BC001 implementation |

---

## DocumentAuditEvent

| Aspect | Definition |
|---|---|
| **Purpose** | Append-only history of document mutations |
| **Responsibility** | Legal trace; actor; timestamp; event kind |
| **Mandatory properties** | Event kind; actor; timestamp; payload summary |
| **Mandatory links** | Document |
| **In contract** | Immutable; no delete/update |
| **NOT in contract** | Event store technology |

---

## DocumentLifecycleState

| Aspect | Definition |
|---|---|
| **Purpose** | Current state in document lifecycle |
| **Responsibility** | Gate editing, signing, registration, void |
| **Mandatory properties** | One of: DRAFT, READY_FOR_SIGNATURE, SIGNED, REGISTERED, VOIDED |
| **Mandatory links** | DocumentMetadata; transition history via DocumentAuditEvent |
| **In contract** | Archive orthogonal; void_kind CANCEL vs ANNUL |
| **NOT in contract** | Workflow engine states |

---

## LocalizationLifecycleState

| Aspect | Definition |
|---|---|
| **Purpose** | Per-locale alignment with semantic source |
| **Responsibility** | Track CURRENT, STALE, REVIEW_REQUIRED |
| **Mandatory properties** | State; stale_reason; optional waiver |
| **Mandatory links** | LocaleRepresentation |
| **In contract** | Mandatory locale STALE blocks READY |
| **NOT in contract** | Production enum file (architecture-level set only) |

---

## ExecutionLifecycleState

| Aspect | Definition |
|---|---|
| **Purpose** | Downstream execution progress |
| **Responsibility** | Track task/obligation fulfillment outside document aggregate |
| **Mandatory properties** | One of research set: created, waiting, in_progress, completed, overdue, cancelled, etc. |
| **Mandatory links** | Execution contour (not Document aggregate) |
| **In contract** | Independent of DocumentLifecycleState |
| **NOT in contract** | Storage in document table |

---

*Detailed independence and coupling: see [`data/UDE-001-contract-matrix.csv`](./data/UDE-001-contract-matrix.csv) and [`data/UDE-001-dependency-matrix.csv`](./data/UDE-001-dependency-matrix.csv).*
