# UDE-002 — Text Provenance Model

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: OP-RES-006A §10; ADR-UDE-013; UDE-001 TextProvenance contract

---

## 1. Purpose

Refine Text Provenance for the Draft Intake and Draft Workspace phases. Provenance answers: **who provided this text, from where, how was it derived, and who confirmed it?**

---

## 2. Provenance Granularity

| Level | Required at MVP | Use |
|---|---|---|
| **Draft (document-level aggregate)** | Yes | Bilingual readiness summary; submission channel; overall drafting_path |
| **Locale** | Yes | Per-locale completeness; translation origin; localization review |
| **Section / Block** | **Yes — minimum sufficient** | preamble, item body, formula, etc. |
| **Item** | Yes (when items identified) | Order item body, basis, control |
| **Sentence** | No | Deferred — not required for MVP |

**Recommendation:** Per **locale block** (section or item body) as minimum. Aligns with OP-RES-006A and UDE-001 LocaleRepresentation.

---

## 3. Text Layers in Workspace

| Layer | Location | = Effective? | = Semantic SoT? |
|---|---|---|---|
| **SubmittedText** | DraftBlock.submitted | No | No (Stage 1 SoT) |
| **WorkspaceEffectiveDraft** | DraftBlock.workspace_effective | Interim authority | Partial (Stage 2) |
| **GeneratedText** | DraftBlock.generated (after enrichment) | No | Derived |
| **TranslatedText** | DraftBlock.workspace_effective (KK) | No | No |
| **OfficialEffectiveDraft** | Workspace promotion package | Yes pre-document | Aligned (Stage 4) |
| **EffectiveText** | Document LocaleRepresentation | Yes pre-sign | Aligned (Stage 4→5) |

---

## 4. TextProvenance Attributes

### 4.1 Mandatory (per block, MVP)

| Attribute | Type (conceptual) | Description |
|---|---|---|
| **source** | TextSourceType | SUBMITTED, GENERATED, TRANSLATED, MANUALLY_AUTHORED, MANUALLY_EDITED |
| **author** | PartyReference or system actor | Content origin actor |
| **organization** | OrganizationalUnit ref | Submitting or source unit |
| **language** | LanguageCode | Editorial language of this block |
| **submitted_at** | timestamp | First capture time |
| **derived_from** | version ref | Prior block version or locale snapshot |
| **translation_origin** | LocaleCode + version ref | Source locale for TRANSLATED blocks |
| **edited_by** | system actor | Last editorial operator |
| **confirmed_by** | PartyReference | Content Author confirmation (when applicable) |

### 4.2 Additional (carried to Document)

| Attribute | Description |
|---|---|
| source_timestamp | Last provenance-affecting change |
| localization_reviewed_by | Localization Reviewer sign-off |
| edit_class | form_only | content (drives confirmation) |
| stale_reason | Propagates to LocalizationLifecycleState |

---

## 5. Provenance Chain

```text
Author submits RU text
  → source=SUBMITTED, author=ContentAuthor, org=SubmittingUnit
HR edits numbering (form-only)
  → workspace_effective updated, edited_by=Operator, derived_from=v1
  → submitted preserved, provenance fork
HR translates to KK
  → source=TRANSLATED, translation_origin=RU@v3, edited_by=Translator
Author confirms content
  → confirmed_by=ContentAuthor
Promotion to Document
  → provenance copied to LocaleRepresentation.TextProvenance
```

**Rule P1:** No silent overwrite — every effective change records `derived_from`.  
**Rule P2:** SUBMITTED blocks remain queryable after promotion.  
**Rule P3:** TRANSLATED without `translation_origin` is validation error (I025).

---

## 6. Provenance by Phase

| Phase | Provenance focus |
|---|---|
| Intake | Capture SUBMITTED; record submitter ≠ author distinction |
| Editorial | Record MANUALLY_EDITED; classify form vs content |
| Translation | Record TRANSLATED + translation_origin |
| Enrichment | Record GENERATED when semantic render produces text |
| Confirmation | Record confirmed_by |
| Promotion | Snapshot provenance into Document contracts |

---

## 7. Mixed-Origin Case (Variant A — standard)

```text
RU block: source=SUBMITTED, author=DeptHead
KK block: source=TRANSLATED, translation_origin=RU@v2, edited_by=HRTranslator
```

Both blocks in same Workspace; localization policy requires KK review before OFFICIAL_DRAFT_READY.

---

## 8. Mapping to UDE-001 Contracts

| UDE-001 Contract | UDE-002 usage |
|---|---|
| SubmittedText | Immutable layer in DraftBlock |
| TextProvenance | Per-block provenance record |
| LocaleRepresentation | Target shape at Document promotion |
| ContentConfirmation | confirmed_by + gate linkage |

---

## 9. What Provenance Is NOT

- Not access control
- Not workflow state
- Not lifecycle enum
- Not a substitute for Draft Audit (audit logs events; provenance describes text origin)

---

*Matrix: [`data/UDE-002-provenance-matrix.csv`](./data/UDE-002-provenance-matrix.csv)*  
*Diagram: [`diagrams/draft-provenance-model.svg`](./diagrams/draft-provenance-model.svg)*
