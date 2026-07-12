# OP-RES-006A — Operational Order Initiation, Authorship and Draft Intake Addendum

WP: **OP-RES-006A** — Operational Order Initiation, Authorship and Draft Intake Addendum  
Date: **2026-07-12**  
Status: **Architecture addendum** (no runtime changes)  
Parent: [OP-RES-006 — Unified Document Engine Target Architecture](./OP-RES-006-unified-document-engine-target-architecture.md)

**Artifacts:**

- [Organizational Interview Guide](./OP-RES-006A-organizational-interview-guide.md)
- [`data/`](./data/OP-RES-006A-role-responsibility-matrix.csv) — role, drafting path, provenance, intake, impact matrices
- [`diagrams/`](./diagrams/operational-order-initiation-flow.svg) — initiation, intake, provenance, confirmation diagrams

---

## 1. Executive Summary

OP-RES-006A дополняет целевую архитектуру UDE организационным наблюдением: **производственные приказы часто инициируются и содержательно готовятся вне HR**, а кадровая служба выступает **оператором оформления и координатором документного процесса**, а не автором управленческого решения.

**Главный принцип (новый):**

```text
Content ownership ≠ Document processing ownership
```

**Архитектурное следствие:** UDE должен поддерживать **три drafting paths**, из которых для Operational Orders MVP первым является:

**Model C — Submitted-text Intake** (first-class, не workaround).

Добавлены: контур **Document Initiation and Draft Intake**, модель **text provenance**, **Content Confirmation**, 6 новых ADR (ADR-UDE-011–016), обновлён migration roadmap.

**Рекомендация:** UDE-000 Ratification **может начаться после** OP-RES-006A, но **должна включать** ratification OP-RES-006A findings и организационные интервью как pre-implementation gate.

---

## 2. Organizational Observation

Типичный наблюдаемый процесс (organizational observation, не corpus-derived):

```text
Руководитель производственного подразделения
  → готовит текст проекта
  → передаёт в отдел кадров
  → HR приводит к официальной форме
  → организует перевод / принимает готовый KK
  → редакционная и комплектностная проверка
  → согласование → подпись → регистрация
```

Варианты языкового входа:

- RU only + запрос перевода KK  
- RU + KK оба предоставлены  
- RU + просьба подготовить KK  
- KK only (реже)  

**Статус доказательности:**

| Claim | Status |
|---|---|
| Dept head prepares content | Organizational observation |
| HR formats and coordinates | Organizational observation |
| HR ≠ content author by default | Architectural inference + PO contrast |
| KK often prepared by HR | Organizational observation |
| Author confirms after HR edits | Logical necessity — **requires interview** |
| Approval sequence | **Requires interview** |

---

## 3. Why OP-RES-006 Requires Clarification

OP-RES-006 и OP-RES-005 акцентируют **Model A (semantic-first)**:

```text
Scenario → Structured Inputs → Semantic Model → Generated Text
```

Этот путь **валиден**, но **недостаточен** для Operational Orders, где доминирует:

```text
Submitted Free-text Draft → Intake → Enrichment → Translation
  → Content Confirmation → Official Draft → Approval
```

**Риск без OP-RES-006A:** HR становится неявным content author через `created_by`; submitted text путается с effective text; перевод без provenance; смысловые правки HR без подтверждения автора.

---

## 4. Content Ownership vs Document Processing Ownership

| Dimension | Content Ownership | Document Processing Ownership |
|---|---|---|
| **Кто** | Content Author (dept head/expert) | Document Operator (HR) |
| **За что** | Бизнес-цель, поручения, исполнители, сроки, результат | Официальная форма, реквизиты, комплектность, routing |
| **Системное поле** | `content_author` (declared) | `created_by` (record creator) |
| **Audit** | CONTENT_AUTHORED, CONTENT_CONFIRMED | RECORD_CREATED, EDITORIAL_PROCESSED, REGISTERED |
| **Запрет** | HR ≠ content author by default | Author ≠ registrar by default |

**Сохранённый принцип OP-RES-006/005A:** Legal equivalence ≠ editorial symmetry.

---

## 5. Roles and Responsibilities

Полная матрица: [`data/OP-RES-006A-role-responsibility-matrix.csv`](./data/OP-RES-006A-role-responsibility-matrix.csv)

| Role | Responsibility | PO vs OO |
|---|---|---|
| Business Initiator | Initiates need | OO: dept head; PO: often HR |
| Content Author | Management content | OO: external to HR; PO: often HR |
| Submitting Unit | Org unit source | OO: production dept |
| Document Operator | System record + form | Both: HR |
| Editorial Processor | Structure, numbering | Both: HR |
| Translation Requester | Initiates KK need | OO: often HR on behalf |
| Translator | Produces translation | Both: HR translator |
| Localization Reviewer | KK quality | Both |
| Content Reviewer | Meaning preserved | OO: **Content Author** |
| Approver / Signer / Registrar | Standard lifecycle | Both |

**Недопустимое автоматическое отождествление:**

- Record Creator ≠ Content Author  
- Document Operator ≠ Content Author  
- Translator ≠ Content Author  
- Localization Reviewer ≠ Content Reviewer (default)

**Связь с Party model:** Content Author и Initiator — `PartyReference`; process roles (Operator, Translator) — system actors в audit, не Party permissions.

---

## 6. Operational Order Initiation

```text
Business Initiator → Content Author → Submitting Unit → Draft Submission
  → HR Intake → Editorial Processing → Translation
  → Content Confirmation → Approval → Signature → Registration
```

Diagram: [`diagrams/operational-order-initiation-flow.svg`](./diagrams/operational-order-initiation-flow.svg)

| Stage | Confirmed | Logical | Interview needed |
|---|---|---|---|
| Dept prepares draft | Observation | — | Channel (email/Word) |
| HR intake | Observation | — | SLA / queue |
| HR enrichment | Observation | — | What HR may add unilaterally |
| Translation | Observation | — | Who translates |
| Content confirmation | — | Yes | Mandatory? |
| Approval order | — | — | Yes |

---

## 7. Draft Submission Models

| Model | Input | Typical channel |
|---|---|---|
| Full text RU | Complete RU draft | Word, paste, scan+retype |
| Full text RU+KK | Both languages | Single or dual paste |
| RU + translation request | RU only | Explicit missing-KK flag |
| KK only | KK draft | Rare; RU required |
| Brief / notes | Intent only | → Model A generation |
| Partial bilingual | One complete, one partial | Variant E |

**Intake не предполагает** единый канал — UDE фиксирует provenance независимо от канала.

---

## 8. Three Drafting Paths

Diagram: [`diagrams/three-drafting-paths.svg`](./diagrams/three-drafting-paths.svg)  
Matrix: [`data/OP-RES-006A-drafting-path-matrix.csv`](./data/OP-RES-006A-drafting-path-matrix.csv)

### Model A — Semantic-first

`Scenario → Structured Inputs → Semantic Model → RU/KK Rendering → Official Draft`

- **OO:** P2 (parallel development)  
- **PO:** Primary path today  

### Model B — Internal RU-first

`RU Draft → Translation → KK → Reconciliation → Official Draft`

- **OO:** P1 after intake  
- **PO:** Symmetric generate + editorial (OP-RES-005A)  

### Model C — Submitted-text Intake (P0)

`Submitted RU/KK → Intake → Enrichment → Semantic Mapping → Editorial → Translation → Content Confirmation → Official Draft`

- **OO MVP:** **P0 first-class path**  
- **May transition** to Model A after semantic mapping complete  
- **Not a workaround**

---

## 9. Submitted-text Intake

### 9.1 Boundary: Document Initiation and Draft Intake

**Ответственность:**

- Принять проект текста (внешний или внутренний)  
- Определить content author, submitting unit, initiator  
- Определить языковую комплектность  
- Выполнить intake validation (I001–I026)  
- Создать official draft workspace  
- Сохранить provenance  

**Draft Intake НЕ должен:**

- Считать submitted text официальным автоматически  
- Считать документ READY автоматически  
- Назначать HR content author  
- Считать KK проверенным без localization review  
- Скрывать происхождение правок  

Diagram: [`diagrams/submitted-text-intake-flow.svg`](./diagrams/submitted-text-intake-flow.svg)

---

## 10. Text Provenance

Matrix: [`data/OP-RES-006A-text-provenance-matrix.csv`](./data/OP-RES-006A-text-provenance-matrix.csv)  
Diagram: [`diagrams/text-provenance-model.svg`](./diagrams/text-provenance-model.svg)

### 10.1 Text layers

| Layer | Definition | = effective? |
|---|---|---|
| **submitted_text** | As received from author/unit | **No** |
| **generated_text** | From semantic model | No |
| **translated_text** | Derived from other locale | No |
| **manually_authored_text** | Written in workspace | No |
| **effective_text** | Signing authority (pre-sign) | **Yes** |

### 10.2 Research source types (not production enum)

`SUBMITTED` · `GENERATED` · `TRANSLATED` · `MANUALLY_AUTHORED` · `MANUALLY_EDITED` · `IMPORTED_LEGACY`

### 10.3 Per-block attributes (minimum)

`source_type`, `source_language`, `source_actor`, `source_unit`, `source_timestamp`, `derived_from_version`, `effective_state`, `stale_state`, `content_confirmed_by`, `localization_reviewed_by`

### 10.4 Provenance granularity recommendation

**Минимально достаточно:** per **locale block** (item body, preamble, etc.)  
**Дополнительно:** document-level aggregate bilingual readiness  
**Не требуется на MVP:** per-sentence provenance  

---

## 11. Intake Validation

Matrix: [`data/OP-RES-006A-intake-validation-matrix.csv`](./data/OP-RES-006A-intake-validation-matrix.csv)

| Layer | Examples | Severity mix |
|---|---|---|
| Metadata | initiator, content_author, submitting_unit | errors |
| Structural | title, items, formula, control | errors/warnings |
| Semantic | executors, deadlines, controller | warnings + clarification |
| Localization | RU present, KK missing flag, parity | errors per policy |
| Provenance | submitter, author, translation origin | errors |

**Clarification required** — не блокер, но блокирует продвижение до ответа.

---

## 12. Editorial Processing

HR / Editorial Processor:

- Приводит к document shell (header, formula, numbering)  
- Добавляет обязательные реквизиты  
- Может добавить control meta-item (если отсутствует)  
- Может нормализовать преамбулу  
- Выполняет semantic mapping (progressive)  
- Классифицирует правки: **form-only** vs **content**  

**Form-only (не требует content confirmation по умолчанию):**

- Нумерация, заголовок chrome, город, дата placeholder, формула «ПРИКАЗЫВАЮ», исп: line  

**Content (требует confirmation):**

- Исполнители, сроки, предмет поручений, controller, состав комиссии, смысл приложений  

---

## 13. Translation Request and Fulfilment

| Step | Actor |
|---|---|
| Detect missing KK | Intake / Localization |
| Request translation | Translation Requester (often HR) |
| Produce KK | Translator |
| Mark source | `source_type=TRANSLATED`, `derived_from_version` |
| Review | Localization Reviewer |
| Staleness | RU effective change → KK STALE (BC023) |

**Один язык SUBMITTED, второй TRANSLATED** — штатный случай (Variant A).

---

## 14. Content Confirmation

Diagram: [`diagrams/content-confirmation-flow.svg`](./diagrams/content-confirmation-flow.svg)

**Content Confirmation** — явное подтверждение Content Author, что производственный смысл сохранён после редакционной обработки.

| Case | Confirmation |
|---|---|
| Текст принят без смысловых изменений | Acknowledge |
| Формулировки отредактированы, смысл сохранён | Acknowledge |
| Исполнители / сроки / control изменены | **Required** |
| Структура пунктов изменена с semantic impact | **Required** |
| Только form-only правки | Not required (policy default) |
| Перевод KK требует терминологии | Localization review + optional author confirm |

**Блокирует:** READY_FOR_SIGNATURE и approval при pending content confirmation (OO policy default).

Audit: `CONTENT_CONFIRMATION_REQUESTED`, `CONTENT_CONFIRMED`, `CONTENT_CONFIRMATION_REJECTED`.

---

## 15. Localization Review

Отдельно от Content Confirmation:

- **Localization Reviewer** — KK terminology, calques, structural parity (BC001–BC025)  
- **Content Reviewer** — management meaning (Content Author)  

Оба могут быть required перед READY.

---

## 16. Approval Boundary

Diagram: [`diagrams/intake-localization-approval-boundary.svg`](./diagrams/intake-localization-approval-boundary.svg)

| Contour | Ends when |
|---|---|
| Draft Intake | Official draft workspace created |
| Localization | Mandatory locales CURRENT; review complete |
| Approval/Sign | Content confirmed; READY; reconciled package |

Document lifecycle status остаётся `DRAFT` до READY — editorial substates **не** новые production enums.

---

## 17. Source of Truth during Intake

### Hybrid SoT model (OP-RES-006A refinement of OP-RES-006)

| Stage | Authority |
|---|---|
| **Early Intake** | submitted text + provenance (не effective) |
| **Editorial Draft** | semantic model (partial OK) + effective text under reconciliation |
| **Ready for Signature** | validated semantic model + reconciled effective locales |
| **After Signature** | immutable effective bilingual snapshot |

**Уточнения:**

- submitted text **≠** automatic SoT  
- semantic model **может быть неполной** на intake  
- effective text **может временно вести** редакционное представление  
- content ownership остаётся у Content Author  
- перед READY — semantic/effective consistency confirmed  

---

## 18. Lifecycle Interaction

Editorial substates (research — derived conditions + audit, **not** document status enum):

`submitted` · `intake_review` · `clarification_required` · `editorial_processing` · `translation_required` · `translation_in_progress` · `content_confirmation_required` · `bilingual_reconciliation` · `ready_for_approval`

| Relationship | Rule |
|---|---|
| Document Lifecycle | DRAFT until READY_FOR_SIGNATURE |
| Localization Lifecycle | Independent STALE/CURRENT per locale |
| Editorial substates | Derived from validation + audit |
| Content Confirmation | Gates READY (OO default) |

---

## 19. Audit Requirements

**Обязательный принцип:** Record creator ≠ Content author.

| Event | Distinguishes |
|---|---|
| ORDER_INITIATED | Business initiator |
| DRAFT_SUBMITTED | Who provided text |
| CONTENT_AUTHOR_DECLARED | Author ≠ creator |
| RECORD_CREATED | Document operator |
| SUBMITTED_TEXT_CAPTURED | Provenance per block |
| EDITORIAL_PROCESSED | HR form changes |
| TRANSLATION_REQUESTED / COMPLETED | Translation chain |
| LOCALIZATION_REVIEWED | KK quality |
| CONTENT_CONFIRMED / REJECTED | Author acknowledgment |
| APPROVED / SIGNED / REGISTERED | Standard lifecycle |

---

## 20. Access and Authority Implications

Capabilities (не permission keys):

| Capability | Typical holder |
|---|---|
| submit_operational_draft | Dept head / delegate |
| create_draft_on_behalf | HR Document Operator |
| declare_content_author | HR at intake |
| accept_draft_into_intake | HR |
| request_clarification | HR |
| edit_official_form | HR Editorial Processor |
| request_translation | HR / Author |
| provide_translation | Translator |
| review_localization | Localization Reviewer |
| confirm_content | Content Author |
| reject_editorial_changes | Content Author |
| reconcile_bilingual | HR |
| approve / register | Approver / Registrar |

---

## 21. Operational Orders MVP Implications

**P0 Drafting Path: Model C — Submitted-text Intake**

Minimum capabilities:

1. Create document from submitted text  
2. Declare initiator, content author, submitting unit  
3. Insert RU; insert KK if provided; flag KK missing  
4. Request translation  
5. Preserve provenance per block  
6. Edit effective RU/KK independently  
7. STALE second locale after first changes  
8. BC bilingual checks  
9. Content confirmation  
10. Transition to approval/signature lifecycle  

**Structured scenario-first (Model A)** — parallel or next phase (OO-IMP-003).

---

## 22. Personnel vs Operational Differences

| Aspect | Personnel Orders | Operational Orders |
|---|---|---|
| Content author | Often HR | External dept head |
| Primary path | Model A/B (HR generates) | **Model C (intake)** |
| Record creator | HR | HR (не author) |
| Submitted free-text | Rare | **Dominant** |
| Content confirmation | Rare | **Expected** |
| Translation | Symmetric generate | Delegation to HR common |

**Shared in UDE:** provenance, effective text, staleness, lifecycle, audit, intake contour (usable by PO for edge cases).

---

## 23. Impact on OP-RES-006

Matrix: [`data/OP-RES-006A-op-res-006-impact-matrix.csv`](./data/OP-RES-006A-op-res-006-impact-matrix.csv)

Точечные обновления внесены в OP-RES-006 documents (marked OP-RES-006A). Основные:

- Principle 15: Content ≠ Processing ownership  
- §7: Draft Intake boundary  
- §8: New entities  
- §15–17: Three drafting paths, provenance  
- §21: Editorial substates  
- §25, §32: Audit and capabilities  
- Roadmap, ADR, ratification criteria  

---

## 24. ADR Additions

See updated [OP-RES-006-adr-backlog.md](./OP-RES-006-adr-backlog.md) — ADR-UDE-011 through ADR-UDE-016.

---

## 25. Migration Roadmap Changes

See updated [OP-RES-006-migration-roadmap.md](./OP-RES-006-migration-roadmap.md).

**Revised sequence:**

1. UDE-000 — Ratification (OP-RES-006 + 006A)  
2. UDE-001 — Terminology and Roles  
3. UDE-002 — Draft Intake and Text Provenance  
4. UDE-003 — Shared Editorial and Localization Core  
5. OO-IMP-001 — Submitted-text Intake MVP  
6. OO-IMP-002 — Content Confirmation and Translation Workflow  
7. OO-IMP-003 — Scenario-driven Generation  
8. OO-IMP-004 — Lifecycle and Approval  
9. OO-IMP-005 — Execution Projection  

---

## 26. Organizational Interview Questions

Full guide: [OP-RES-006A-organizational-interview-guide.md](./OP-RES-006A-organizational-interview-guide.md)

20 questions prepared for HR and department heads.

---

## 27. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| HR implicit content author | Explicit content_author field + audit |
| Submitted = effective confusion | Separate layers + no auto-promotion |
| Missing content confirmation | Default block READY; ADR-UDE-014 |
| Over-engineered provenance | Per-block minimum granularity |
| Intake-only forever | Parallel Model A roadmap |
| Form/content change blur | Change classification policy |
| KK delay blocks business | Waiver policy + interview |
| Interview delays UDE-000 | Ratify architecture; policy as pre-IMP gate |

---

## 28. Open Questions

1. Mandatory KK before approval — org policy?  
2. Authoritative locale on conflict  
3. Multi-author orders  
4. HR full rewrite frequency  
5. Content confirmation — always or scenario-based?  
6. Electronic intake channel priority  
7. Who may waive missing KK?  

---

## 29. Recommendations for UDE-000

1. Ratify OP-RES-006 **with OP-RES-006A amendments**  
2. Accept ADR-UDE-011–016  
3. Accept Model C as OO MVP P0 path  
4. Schedule organizational interviews before OO-IMP-001  
5. Freeze terminology: Content Author, Document Operator, submitted_text, effective_text  
6. Do **not** block UDE-000 on interview completion — block **OO-IMP-001** instead  

---

## 30. Conclusions

OP-RES-006A устраняет риск проектирования UDE только для semantic-first generation. Operational Orders требуют **Submitted-text Intake как полноценного архитектурного пути** с явным разделением content ownership и document processing ownership.

**Можно начать UDE-000 после OP-RES-006A** — это последнее архитектурное уточнение перед ratification.

---

## Mandatory Questions — Direct Answers

| # | Question | Answer |
|---|---|---|
| 1 | Content author OO? | **Руководитель производственного подразделения / предметный эксперт** — не HR по умолчанию |
| 2 | Record creator? | **Document Operator (HR)** — `created_by` в системе |
| 3 | HR operator but not author? | **Да** — штатная модель для OO |
| 4 | Submitting unit? | **OrganizationalUnit reference** + audit; declared at intake |
| 5 | Drafting paths? | **Model A, B, C** — все три; OO MVP начинает с C |
| 6 | Submitted-text first-class? | **Да** — P0, не workaround |
| 7 | Submitted text? | Текст проекта **как передан** автором/подразделением до официальной обработки |
| 8 | Submitted vs effective? | Submitted **≠** effective; promotion только после intake + editorial acceptance |
| 9 | Provenance RU/KK? | Per-block `source_type`, `source_actor`, `derived_from_version`, timestamps |
| 10 | One submitted, one translated? | **Да** — Variant A; RU SUBMITTED + KK TRANSLATED |
| 11 | Кто за перевод? | **Translator** (often HR); requested by Translation Requester |
| 12 | Кто за смысл? | **Content Author**; HR сохраняет через Content Confirmation |
| 13 | Правки → confirmation? | **Content changes** yes; **form-only** no (default policy) |
| 14 | Approval без автора? | **Нет** (OO default) при content changes; form-only may proceed |
| 15 | HR изменил только форму? | Audit `EDITORIAL_FORM_ONLY`; no confirmation required (default) |
| 16 | SoT на intake? | **submitted text + provenance**; semantic model partial |
| 17 | SoT перед подписанием? | **Validated semantic + reconciled effective locales** |
| 18 | Не сделать HR владельцем решения? | Separate `content_author` from `created_by`; audit; content confirmation |
| 19 | Обязательные audit events? | INITIATED, SUBMITTED, AUTHOR_DECLARED, RECORD_CREATED, PROVENANCE_CAPTURED, CONTENT_CONFIRMED, SIGNED |
| 20 | Capabilities руководителя? | submit_operational_draft, confirm_content, reject_editorial_changes |
| 21 | Capabilities HR? | create_on_behalf, intake, edit_official_form, request/provide translation, reconcile, register |
| 22 | Missing KK? | Blocks READY (default); translation_required substate; waiver policy TBD |
| 23 | Submitted RU+KK validation? | I019–I021 + BC001–BC006 parity; localization review |
| 24 | Partial translation staleness? | Complete locale CURRENT → incomplete STALE/REVIEW_REQUIRED until completion |
| 25 | Изменения OP-RES-006? | Principle 15, intake boundary, 3 paths, provenance, SoT hybrid, audit, roadmap — see §23 |
| 26 | Новые ADR? | **ADR-UDE-011–016** |
| 27 | Roadmap change? | Intake-first OO MVP; UDE-002 intake/provenance before scenario generation |
| 28 | OO MVP first path? | **Model C — Submitted-text Intake** |
| 29 | UDE-000 после addendum? | **Да** — ratify 006+006A; interviews before OO-IMP-001 |
| 30 | Вопросы для интервью? | 20 вопросов — см. Interview Guide; KK policy, confirmation rules, authoritative locale |

---

*End of OP-RES-006A Addendum*
