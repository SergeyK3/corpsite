# UDE-002 — Submitted Draft Model

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define **Submitted Draft** as the pre-Workspace capture of an external or internal document project — distinct from Document, Official Draft, and Signed Document.

---

## 2. Entity Distinctions

| Entity | Definition | Authority | Lifecycle | Exists in system |
|---|---|---|---|---|
| **Submitted Draft** | Text and artifacts as received from author/unit | Author origin; provenance | Pre-acceptance | Capture record |
| **Draft Workspace** | Editorial and enrichment container | Workspace effective draft + staged SoT | Workspace stages | WorkspaceId |
| **Official Draft** | Validated package ready for Document promotion | Semantic + reconciled effective | OFFICIAL_DRAFT_READY | Inside Workspace |
| **Document Aggregate** | Legal act instance | Document lifecycle + effective text | DRAFT→READY→SIGNED | DocumentId |
| **Signed Document** | Immutable post-signature snapshot | Effective bilingual snapshot | Terminal immutability | Document SIGNED/REGISTERED |

```text
Submitted Draft  ≠  Official Draft  ≠  Document  ≠  Signed Document
```

---

## 3. Submitted Draft Contents

A Submitted Draft **may** contain:

| Content | Required? | Notes |
|---|---|---|
| RU text only | Valid variant (Variant A) | KK declared missing or requested |
| KK text only | Valid variant (Variant C) | RU translation required |
| RU + KK both | Valid variant (Variant B) | Reconciliation may be needed |
| Partial text | Valid (Variant E) | Clarification likely |
| Notes / intent only | Valid (Variant D) | P2; may route to Model A |
| Word file reference | Optional channel | Provenance records channel |
| PDF scan reference | Optional channel | May require retyping |
| Operator notes | Optional | Not submitted text |
| Attachment drafts | Optional | Linked separately |
| Incomplete structure | Allowed | HR enriches in Workspace |

---

## 4. Minimum Submitted Draft (OO MVP P0)

| Requirement | Severity | Check |
|---|---|---|
| Document kind hint or family | Error if ambiguous | I004 |
| Content author declared | Error | I002 |
| Submitting unit declared (OO) | Error | I003 |
| Submitter recorded | Error | I023 |
| Title or identifiable subject | Error | I007 |
| At least one directive body (item text) | Error | I010 |
| RU present OR explicit language policy waiver | Error | I019 |
| KK present OR explicit missing-KK declaration | Error | I020 |
| Provenance: source channel + timestamp | Error | I023–I024 |
| No internal contradictions | Error | I018 |

**Not required at submission:** operative formula, control clause, full semantic model, registration number, signatory final, complete bilingual parity.

---

## 5. Submitted Draft Structure (Conceptual)

```text
SubmittedDraft
├── SubmittedDraftId
├── captured_at
├── submission_channel        # manual | paste | word_upload | future_api | future_template
├── submitter_ref             # who handed to HR (may ≠ content author)
├── content_author_ref        # PartyReference — mandatory
├── submitting_unit_ref       # OrganizationalUnit — OO mandatory
├── initiator_ref             # optional Business Initiator
├── document_kind_hint
├── drafting_path_hint        # inferred or declared
├── locale_payloads[]         # per LocaleCode
│     ├── raw_text
│     ├── completeness        # full | partial | missing_declared
│     └── attachment_refs[]
├── operator_notes            # not part of submitted text authority
└── intake_validation_result  # populated on acceptance attempt
```

---

## 6. Immutability Rules

| Rule | Description |
|---|---|
| S1 | Raw submitted text is **immutable** after capture |
| S2 | Resubmission creates **new** SubmittedDraftSnapshot version |
| S3 | Editorial edits go to **WorkspaceEffectiveDraft**, never overwrite submitted |
| S4 | Provenance chain links submitted → workspace effective → document effective |
| S5 | Submitted Draft ≠ Effective Text (ADR-UDE-005, ADR-UDE-012) |

---

## 7. Submission Channels (Conceptual)

| Channel | Contract input | Implementation |
|---|---|---|
| Manual entry | Typed text in intake form | Deferred (OO-IMP-001) |
| Copy-paste | Pasted text + channel= paste | Deferred |
| Word upload | File ref + extracted text | Deferred |
| Future template | TemplateId + filled fields | Deferred |
| Future API | External system payload | Deferred |

**UDE-002 defines `DraftSubmissionContract` only** — not upload implementation.

### DraftSubmissionContract (conceptual)

| Field | Direction |
|---|---|
| Input | submission_channel, locale_payloads[], metadata refs, attachments[] |
| Output | SubmittedDraftId, intake_validation_result |
| Guarantees | Provenance captured; no Document created; no auto-effective |
| Constraints | content_author ≠ record creator |

---

## 8. Transition from Submitted Draft

```text
Submitted Draft
    │ intake validation
    ├── REJECTED → return to submitter (no Workspace)
    └── ACCEPTED → Draft Workspace created
                      └── SubmittedDraftSnapshot frozen inside Workspace
```

---

## 9. PO vs OO

| Aspect | Personnel Orders | Operational Orders |
|---|---|---|
| Typical entry | Model A/B — may skip Submitted Draft | Model C — Submitted Draft P0 |
| Content author | Often HR | External dept head |
| Minimum draft | Item payload in system | External text intake |
| Workspace | Optional adapter | Required path |

---

*Diagram: [`diagrams/submitted-draft-to-document.svg`](./diagrams/submitted-draft-to-document.svg)*
