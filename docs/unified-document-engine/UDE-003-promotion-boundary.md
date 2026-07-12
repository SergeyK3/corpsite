# UDE-003 — Promotion Boundary

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define exactly what crosses the boundary from **Editorial Core** (via OfficialDraftPackage) into **Document Aggregate** at promotion, and what remains in Draft Workspace.

---

## 2. Promotion Flow

```text
Draft Workspace
  └── Editorial Core + Localization Core
        └── Editorial Validation (E* + BC*)
              └── OfficialDraftPackage (frozen)
                    └── Promotion Command (UDE-004)
                          └── Document Aggregate created (DRAFT)
```

Editorial Core **prepares** the package. **Promotion orchestration** (UDE-004) **executes** the transfer.

---

## 3. Document Aggregate Receives

| Payload | Maps to |
|---|---|
| DocumentKind + specialization ref | DocumentMetadata |
| content_author, submitting_unit, operator→created_by | DocumentMetadata |
| drafting_path, org ref | DocumentMetadata + LocalizationPolicy |
| DocumentStructure (ordered sections) | DocumentStructure |
| OrderItem[] with sequence | OrderItemSequence + OrderItem[] |
| semantic_model_snapshot | OrderItem.semantic_payload, ExecutionObligation[], etc. |
| Per-locale editorial blocks (effective + generated + provenance) | LocaleRepresentation[] |
| AttachmentReference[] (official) | AttachmentReference[] |
| Editorial + localization ValidationResult | Initial ValidationResult on Document |
| ContentConfirmation state | ContentConfirmation on Document |
| Promotion audit summary ref | First DocumentAuditEvent: RECORD_CREATED, WORKSPACE_PROMOTED |

**New identities at promotion:** DocumentId, DocumentLifecycleState=DRAFT, Lifecycle Audit stream.

---

## 4. Does NOT Transfer

| Remains in Workspace archive | Reason |
|---|---|
| SubmittedText raw copies | Historical; provenance ref only |
| ClarificationRequests[] | Pre-official process |
| Full DraftAuditEvent[] | Separate audit contour |
| WorkspaceEffectiveDraft intermediates | Superseded by official effective |
| Intake validation (I*) | Intake phase complete |
| Rejected/abandoned package versions | History |
| Operator draft notes | Non-official |

---

## 5. Post-Promotion Editorial Core Role

After promotion, **same Shared Editorial Core contracts** operate on Document Aggregate:

| Behavior | Rule |
|---|---|
| Write lock | DRAFT only (PO-EDIT R10; UDE-004 lifecycle) |
| Regeneration | Same rules; fingerprint on semantic |
| Localization | Same staleness model |
| READY gate | Lifecycle transition — UDE-004 |

Workspace frozen read-only. Document becomes new consistency boundary.

---

## 6. Promotion Blockers (Editorial)

All must pass before OfficialDraftPackage assembly:

| Gate | Check family |
|---|---|
| E101 | Mandatory sections present all locales |
| E102 | All required blocks have effective text |
| E103 | No STALE mandatory locale |
| E104 | No open REVIEW_REQUIRED without waiver |
| E105 | Override consistency (no orphan overrides) |
| E106 | Editorial ordering valid |
| E107 | BC P0 errors clear |
| E108 | Content confirmation satisfied (if policy) |
| E109 | Semantic enrichment complete (W201) |
| E110 | Attachment completeness |

Detail: [UDE-003-editorial-validation.md](./UDE-003-editorial-validation.md)

---

## 7. Workspace After Promotion

| State | Access |
|---|---|
| WorkspaceState | DOCUMENT_PROMOTED (frozen) |
| OfficialDraftPackage | Immutable archive |
| SubmittedText | Read-only reference |
| Draft Audit | Read-only |
| Link | WorkspaceId ↔ DocumentId bidirectional ref |

---

*Diagram: [`diagrams/promotion-boundary.svg`](./diagrams/promotion-boundary.svg)*
