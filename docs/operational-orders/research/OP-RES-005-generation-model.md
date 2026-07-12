# OP-RES-005 — Operational Orders Generation Model

WP: **OP-RES-005** — Operational Orders Generation Model  
Date: **2026-07-12**  
Mode: **research-only** (read-only analysis; no runtime changes)  
Corpus: `order_samples/Производственные приказы/` — **193 documents** (183 DOCX deep analysis)  
Prior work: [OP-RES-001](./OP-RES-001-corpus-passport.md), [OP-RES-002](./OP-RES-002-structural-pattern-analysis.md), [OP-RES-003](./OP-RES-003-operational-order-taxonomy.md), [OP-RES-004](./OP-RES-004-control-and-execution-model.md)

---

## 1. Executive Summary

OP-RES-005 строит **концептуальную модель генерации** производственных приказов: из структурированного управленческого решения — в состав документа, формулировки пунктов, контроль, приложения и языковые версии.

**Главный результат:** предварительная гипотеза pipeline **подтверждена и уточнена** корпусом:

```text
Scenario → Document Parameters → Order Items → Execution Obligations
  → Clause Rendering → Control Meta-item → Document Assembly
  → Language Rendering → Validation → Preview/Export
  → Execution Projection (handoff only)
```

**Ключевые выводы:**

| Topic | Conclusion |
|---|---|
| Entry point | **Scenario-first** (21 scenarios); free-form item bag — только fallback |
| Generation unit | **Order Item** → 1..N **Execution Obligation** |
| Item Type vs Intent | **Item Type** = render template; **Business Intent** = management meaning |
| Stable Item Types | **14** semantic families confirmed (research registry) |
| Multi-obligation | **~14%** items — split when distinct parties/deadlines |
| Control meta-item | **Auto-generatable** (controller + scope); must stay editable |
| Party | **Role-first**; NamedPerson optional resolution |
| Deadlines | Calendar/period/within_days/from_signature — high formalizability; event/permanent — manual |
| Evidence/Result | **Do not auto-add** if changes management decision |
| Attachments | **Can source obligations** when item delegates to attachment |
| Multilingual | **One semantic model**, independent RU + KK rendering (target); **probable RU-first editorial workflow** — see [OP-RES-005A](./OP-RES-005A-bilingual-drafting-workflow.md) |
| Manual override | Block-level generated/override/effective; regenerate preserves override as stale |
| vs Execution | Generation ends at export; execution = separate contour |

Диаграммы: [`diagrams/operational-order-generation-pipeline.svg`](diagrams/operational-order-generation-pipeline.svg), [`diagrams/generation-model-concept.svg`](diagrams/generation-model-concept.svg), [`diagrams/order-item-generation-anatomy.svg`](diagrams/order-item-generation-anatomy.svg), [`diagrams/multilingual-generation-model.svg`](diagrams/multilingual-generation-model.svg), [`diagrams/generation-execution-boundary.svg`](diagrams/generation-execution-boundary.svg), [`diagrams/scenario-blueprint-model.svg`](diagrams/scenario-blueprint-model.svg)

Machine-readable: [`data/OP-RES-005-item-type-registry.csv`](data/OP-RES-005-item-type-registry.csv), [`data/OP-RES-005-scenario-generation-matrix.csv`](data/OP-RES-005-scenario-generation-matrix.csv), [`data/OP-RES-005-validation-rules.csv`](data/OP-RES-005-validation-rules.csv)

Samples: [`samples/OP-RES-005-anonymized-generation-patterns.md`](samples/OP-RES-005-anonymized-generation-patterns.md), [`samples/OP-RES-005-p0-generation-blueprints.md`](samples/OP-RES-005-p0-generation-blueprints.md)

Research script: [`scripts/op_res_005_generation_probe.py`](scripts/op_res_005_generation_probe.py)

---

## 2. Контекст и цели

### 2.1 Research question

**Какие входные смысловые данные и правила необходимы, чтобы воспроизводимо сформировать корректный текст производственного приказа?**

### 2.2 Scope

| In scope | Out of scope |
|---|---|
| Input model, item registry, clause patterns | Production generator, API, DB, UI |
| Scenario blueprints (P0) | Task/workflow engine |
| Validation rules (conceptual) | Automatic translation |
| Multilingual model (conceptual) | DOCX/HTML/PDF implementation |
| Execution projection descriptor | Personnel Orders changes |

### 2.3 Inherited foundations (OP-RES-001–004)

- Единый document shell (Header → Preamble → ПРИКАЗЫВАЮ → Items → Attachments → Signature)
- 21 scenario taxonomy; P0 = S_TRAVEL, S_COMMISSION, S_CLINICAL, S_ACCOUNTING (~59%)
- Execution unit: Order Item → Execution Obligation; Control Obligation separate
- Intent × Object × Party × Control × Deadline × Result × Evidence

---

## 3. Методика и исследовательская база

### 3.1 Inputs

- Structural and taxonomy reports OP-RES-002/003
- Execution model OP-RES-004 + matrix CSV
- Anonymized samples (structure + execution patterns)
- Read-only probe `op_res_005_generation_probe.py`: verb stems, clause order, scenario item counts (183 DOCX)

### 3.2 Coverage

| Layer | n | Notes |
|---|---:|---|
| DOCX generation analysis | 183 | 1,855 numbered items (probe) |
| Scenario-mapped docs | 183 | Via OP-RES-003 filename match |
| Item Type registry entries | 14 | Semantic families |
| Scenario generation matrix | 21 | All OP-RES-003 scenarios |
| P0 blueprints | 4 | Detailed anonymized |
| KK template confidence | Low | 7 kk-primary files; 129 bilingual mirror |

### 3.3 Limitations

- Preamble auto-detection in probe undercounts (KK-heavy preambles); OP-RES-002 frequencies used for preamble section
- Verb stem detection at item start undercounts ENSURE/ORGANIZE/DIRECT; OP-RES-002 doc-level counts supplement registry
- No production validation with end users
- 8 DOC + 2 PDF excluded from text probe

---

## 4. Входная модель генерации

### 4.1 Field groups

#### Document Metadata

| Field | Required | Computed | Manual | Draft-unknown |
|---|---|---|---|---|
| document_type (Приказ) | Yes | Default | — | — |
| organization | Yes | Org profile | Override | Possible |
| number | No | — | Yes | Often blank |
| date | Near-mandatory | Today default | Yes | Placeholder OK |
| city | Common | Org default | Yes | Possible |
| language_mode | Yes | From scenario | Yes | — |
| draft_status | Yes | — | — | project/draft |
| signatory | Yes | Director default | Yes | Rare |
| preparer (исп:) | No | — | Yes | Common |

#### Business Context

| Field | Required | Source |
|---|---|---|
| domain | Derived | Scenario |
| order_type | Derived | Scenario |
| scenario_code | **Yes** | User selection |
| business_intent (primary) | Derived | Scenario default |
| managed_object(s) | Derived + override | Scenario + items |
| legal_basis[] | Conditional | Template + manual |
| purpose | Conditional | Manual / scenario |
| initiating_documents[] | Conditional | Manual (memo, application) |

#### Execution Context

| Field | Required | Notes |
|---|---|---|
| responsible_parties[] | Per obligation | Role-first |
| co_executors | Optional | Rare explicit |
| controller | Conditional | Required ~92% docs |
| deadlines[] | Per obligation | Scenario-dependent |
| expected_results[] | Optional | Often derived |
| evidence_expectations[] | Optional | Scenario defaults |
| dependencies[] | Optional | Sequential rare |
| commission_spec | Conditional | S_COMMISSION, S_ACCOUNTING |
| attachment_specs[] | Conditional | 19% docs |

### 4.2 Minimal input set (answer Q1)

**Minimum to generate a valid draft:**

1. `scenario_code`
2. `document_metadata` (type, org, signatory, language_mode)
3. ≥1 **Order Item Definition** with ≥1 **Execution Obligation** (intent + party + object)
4. `controller` when scenario mandates control (P0: always)
5. Scenario-specific mandatory fields (e.g. travel_period for S_TRAVEL, commission composition for S_COMMISSION)

Everything else has scenario defaults or can remain unspecified in draft.

---

## 5. Scenario-driven Generation

### 5.1 Principle (answer Q2)

**Generation should start from scenario**, not arbitrary item collection. Scenario supplies:

- Default item sequence and count range
- Default controller and control scope
- Default preamble basis types
- Default evidence posture (implicit vs ack_list)
- Mandatory/conditional blocks

Free-form mode (no scenario) is research fallback (`S_GENERAL`, 1 doc) — not primary UX.

### 5.2 P0 deep verification

#### S_TRAVEL — Travel hypothesis verified

Corpus (33 docs, avg 6.6 items) confirms pattern:

1. Direct employee(s) — **verified** (primary intent направить)
2. Period/place in item 1 — **verified**
3. Funding/expenses item — **verified** (FUND=11 hits in scenario)
4. Salary preservation — **verified** (boilerplate item 3)
5. Control — **verified** (director_self dominant; CONTROL=44)
6. Trailing basis (application) — **verified** (OP-RES-002)

Variation: multiple employees → parallel items, not one packed item.

#### S_COMMISSION — Commission hypothesis verified with nuance

1. Create commission — **verified** (CREATE_COMMISSION=21)
2. Composition inline — **verified** (~80%; attachment ~20%)
3. Control delegated (chief accountant) — **verified** (typical)
4. Separate «approve composition» item — **optional**; usually merged into item 1
5. Secretary — **optional** (~63% in OP-RES-004)

### 5.3 Full matrix

See [`data/OP-RES-005-scenario-generation-matrix.csv`](data/OP-RES-005-scenario-generation-matrix.csv) — all 21 scenarios with blocks, item counts, control defaults, attachments.

---

## 6. Order Item Model

### 6.1 Structure (answer Q3)

**Primary generation unit: Order Item.** Rendering iterates obligations inside item.

```text
OrderItem
├── sequence
├── item_kind              ← render template (Item Type)
├── execution_obligations[] ← 1..N
├── control_obligation?     ← usually separate item
├── language_renderings{kk,ru}
├── attachment_ref?
├── dependencies[]
└── manual_override_state
```

### 6.2 Preliminary model — confirmed with edits

| Field | Status |
|---|---|
| sequence | Confirmed |
| item_kind | Confirmed — separate concept |
| primary_intent | Lives on ExecutionObligation |
| execution_obligations[] | Confirmed |
| responsible_parties | Per obligation |
| managed_object, action, conditions, deadline, expected_result, evidence | Confirmed on obligation |
| dependencies, attachment_ref | Confirmed |
| language_variants | Confirmed — per block/locale |
| manual_override_state | Confirmed — aligns PO-EDIT-001 |

### 6.3 Item Kind vs Business Intent (answer Q4)

| Aspect | Item Kind | Business Intent |
|---|---|---|
| Layer | Presentation / template | Semantics / management |
| Example | `CREATE_BODY` | `создать` |
| Cardinality | Stable small set (~14) | Open verb set (OP-RES-003) |
| Mapping | Many intents → one Item Kind | One intent may map to different kinds by context |
| Enum? | Research registry only | Taxonomy reference |

**Boundary:** Item Kind answers *how to render*; Intent answers *what decision*.

### 6.4 Multi-intent items (answer Q5–7)

**Confirmed:** one item may combine intents (~14%, OP-RES-004).

**Keep together when:**

- Same party and deadline
- Sub-parts are roster/lines under one directive (commission composition)
- Boilerplate cluster (travel items 2+3)

**Split into sub-items or separate items when:**

- Different responsible parties (dative addresses)
- Different deadlines/triggers
- Control obligation (always separate item in 81% docs)
- ACKNOWLEDGE with explicit deadline (S_DISCIPLINE)
- Regulatory enumerations → sub-numbering 1.1, 1.2 (same item, child obligations)

---

## 7. Execution Obligation Rendering

Obligation → text via **Clause Rendering** (§9). Components:

```text
Action → Managed Object → Responsible Party → Conditions → Deadline → Expected Result → Evidence
```

Order varies by language (RU action-first; KK mandate suffix). Semantic content invariant.

---

## 8. Item Type Registry

### 8.1 Stable types (answer Q5)

**14 semantic families** confirmed (not 1:1 with verbs):

| Code | Corpus signal | Role |
|---|---|---|
| DIRECT | 24+ docs | Travel, training direction |
| ASSIGN | 25 docs | Responsibility |
| APPROVE | 51 docs | Plans, regulations |
| CREATE_BODY | 57 docs | Commissions |
| DEFINE_COMPOSITION | sub-render | Roster inside CREATE_BODY |
| ORGANIZE | 46 docs | Events, clinical |
| ENSURE | 47 docs | Regimes, resources |
| ESTABLISH | 20 docs | Rules, modes |
| AUTHORIZE | 6 docs | Transport access |
| FUND | 33 docs | Expenses, transfers |
| REPORT | 30 items | Reports, acts |
| ACKNOWLEDGE | 25 items | HR ack |
| DELEGATE | 81 docs | Duty assignment |
| CONTROL | 168 docs | Meta control |
| META_EFFECT | 60% docs | Effective date |
| REPEAL_AMEND | rare | Supersede |
| OTHER | fallback | Manual |

Full registry: [`data/OP-RES-005-item-type-registry.csv`](data/OP-RES-005-item-type-registry.csv)

---

## 9. Clause Rendering Patterns

### 9.1 RU patterns

Dominant: `[Verb] [Party_dative] [object/action] [deadline clause].`

Alternatives:

- Party-first: «Заведующему … обеспечить …» (~2% explicit)
- Passive/legal: «Расходы … оплатить за счёт …» (no party)
- Control boilerplate: fixed templates

### 9.2 KK patterns (limited evidence)

- Mandate suffix: `… жүктелсін / тағайындалсын / жіберілсін`
- Control: `Бақылау … жүктелсін / өзіме қалдырамын`
- Attachment: `N-қосымша`

**Not confirmed** for full clause library — P0 KK skeletons partial only.

### 9.3 Normalization

| Difference | Type |
|---|---|
| Action vs party order | Stylistic / language |
| Deadline inline vs separate sentence | Stylistic |
| Expected result explicit vs implicit | Semantic — do not force |
| KK mirror vs RU-only | Composition |

---

## 10. Preamble and Basis Generation

### 10.1 Corpus variants (OP-RES-002)

| Kind | Docs | Placement |
|---|---:|---|
| Legal chain | 110 | Preamble |
| Purpose (В целях) | 112 | Preamble |
| Memo | 34 | Preamble / trailing |
| Application | common in travel | Trailing |
| Protocol | disciplinary | Preamble |
| No formal basis | rare | Direct ПРИКАЗЫВАЮ |

### 10.2 Model

```text
PreambleDefinition
├── purpose?                    ← separable
├── legal_basis[]               ← ordered list
├── initiating_documents[]      ← memo, application, protocol
├── production_necessity?       ← free text flag
└── render_placement            ← preamble | trailing | per_item
```

**Auto-insert safe:** purpose template, generic org boilerplate.  
**Manual review required:** specific memo/application/protocol references with numbers/dates.

**Link to ПРИКАЗЫВАЮ:** preamble ends with order formula transition; trailing basis rendered after items (S_TRAVEL).

---

## 11. Control Meta-item Generation

### 11.1 Rules (answer Q8–9)

| Condition | Control |
|---|---|
| Scenario default has controller | **Generate meta-item** |
| S_DISCIPLINE | Embedded multi-controller — **do not** only auto-final |
| Controller = signatory | Template «оставляю за собой» |
| Controller = role | Template «возложить на [должность]» |
| Scope | Default `order`; item/direction when scenario specifies |

**Hypothesis confirmed:** auto-control from `controller + control_scope`, **editable**, not runtime-automated.

**Placement:** last or penultimate (before META_EFFECT); W010 if not.

**Data required:** `controller_party_ref`, `control_mode` (self|delegated), `control_scope`, optional `reporting_requirement`.

---

## 12. Party Resolution

### 12.1 Semantic types

| Type | Use |
|---|---|
| NamedPerson | Travel named employee; discipline subject |
| PositionRole | **Preferred** default |
| OrganizationalUnit | Department executor |
| Commission | Collective body |
| WorkingGroup | Rare — treat as Commission |
| ExternalParty | Not in corpus as executor |

### 12.2 Role-first (answer Q10)

**Store role/function in semantic model**; resolve NamedPerson at generation time optional.

| Case | Representation |
|---|---|
| Permanent duty | PositionRole only |
| Travel specific person | NamedPerson + optional position inline |
| Commission chair | PositionRole (+ optional name inline) |
| Legal immutability | Snapshot resolved names in **rendering snapshot**, not in semantic SoT |
| Staff turnover | Must not change document meaning — role-first preserves intent |

---

## 13. Deadline Rendering

Mapping from OP-RES-004 models (answer Q11–12):

| Model | RU pattern | Formalizable | Manual |
|---|---|---|---|
| exact_date | до [date] | **Yes** | — |
| before_date | не позднее [date] | **Yes** | — |
| period_range | с [d1] по [d2] | **Yes** | — |
| within_duration | в течение N рабочих дней | **Yes** | Rare |
| from_signature | со дня подписания | **Yes** | — |
| from_acknowledgement | со дня ознакомления | Medium | Sometimes |
| until_event / after_event | по окончании [event] | Medium | **Yes** |
| period | за [month] [year] | **Yes** | — |
| recurring | ежемесячно | **Yes** | — |
| permanent | на постоянной основе | Low | **Yes** |
| as_needed | по мере необходимости | Low | **Yes** |
| immediately | незамедлительно | Medium | Sometimes |
| attachment_defined | согласно приложению N | Medium | If attachment vague |
| external_document_defined | в сроки [doc] | Low | **Yes** |
| unspecified | (omit) | N/A | Default OK |

---

## 14. Expected Result and Evidence

### 14.1 Answers Q13

| Question | Answer |
|---|---|
| Same item as action? | **Often implicit** — no extra sentence |
| Separate item? | When distinct duty (report, ack) |
| In attachment? | When attachment defines deliverables |
| Implicit? | **Default** for operational duties |
| Auto from scenario? | **Derived** for result; **cautious** for evidence |

**Do not auto-add evidence** (advance report, ack) unless scenario/user explicitly requires — changes legal meaning.

### 14.2 Pattern table

See [`samples/OP-RES-005-anonymized-generation-patterns.md`](samples/OP-RES-005-anonymized-generation-patterns.md) §4–5.

---

## 15. Commission Generation Model

Three roles (OP-RES-004 confirmed):

1. **Managed Object** — «комиссия по …»
2. **Party** — chair, members, secretary
3. **Execution Mechanism** — inspection → act (phase 2 often implicit)

**Generation blocks:**

| Block | Required | Notes |
|---|---|---|
| CREATE_BODY | Yes | Item 1 |
| DEFINE_COMPOSITION | Usually inline | Attachment if large |
| Task definition | Sometimes separate item | «провести инвентаризацию» |
| Term/quorum | Rare | Manual if needed |
| CONTROL | Yes | Typically chief accountant |

Permanent vs temporary: inferred from subject; not explicit in most docs.

---

## 16. Attachment Generation Model

### 16.1 Answer Q14

**Yes** — attachment can be obligation source when main text says «согласно приложению N» (25 items, 35 docs).

### 16.2 Attachment types

| Type | Data structure | Main text link | Own obligations? |
|---|---|---|---|
| Commission roster | rows: role, position, optional name | item 1 | Indirect |
| Plan/schedule | dated rows | APPROVE item | Yes |
| Employee list | rows | DIRECT items | Yes |
| Budget/smeta | amounts | FUND item | Qualitative |
| Form/template | blank | reference only | **No** |

### 16.3 Document Engine concept

**Semantic model:** `AttachmentDefinition` linked to `OrderItem`.  
**Export:** separate section in same SemanticDocument **or** linked artifact — both valid; choice deferred to OP-RES-006. Generation must preserve **reference integrity** (V009).

---

## 17. Multilingual Generation

### 17.1 Corpus

| Mode | Docs |
|---|---|
| ru_only | 1 |
| kk + ru mirror | 129 |
| kk/bilingual presence | 176 |

### 17.2 Answer Q16

**Yes** — RU and KK **must** build independently from one semantic model:

- Same structure (items, obligations, parties)
- Independent `LanguageRenderer` per locale
- No auto-copy RU→KK
- Manual edit per locale
- Regenerate restores generated snapshot per locale; override preserved (PO-EDIT-004 pattern)

### 17.3 Personnel Orders alignment

Shared: block-level editorial model, effective_text pipeline, kk+ru storage, kk-ru print composition at render time only.

### 17.4 Risks

- Incomplete KK templates
- Morphology (dative, case)
- Official unit title translations
- Legacy interleaved layouts

### 17.5 OP-RES-005A findings (bilingual workflow validation)

> **Added by OP-RES-005A** — refines §17 without replacing the target generation model.

[OP-RES-005A](./OP-RES-005A-bilingual-drafting-workflow.md) проверяет гипотезу RU-first translation workflow:

| OP-RES-005 claim | OP-RES-005A refinement |
|---|---|
| Independent RU + KK render from semantic model | **Remains target architecture** (Model A) |
| Implicit symmetric drafting | **Not corpus-default** — 0 cross-file RU/KK pairs; 135 intra-doc bilingual |
| — | **Model B required:** RU effective draft → translation → KK → reconciliation |
| — | **75/135** bilingual docs: KK block after RU block (layout signal, not org proof) |
| — | **50/135** show translation drift — staleness + reconciliation mandatory |

**Clarified wording:**

> Целевая Generation Model допускает независимый RU и KK rendering из общей semantic model. Фактический editorial workflow **вероятно асимметричен (RU-first)**; архитектура должна поддерживать translation workflow, **language-version staleness** и **bilingual consistency validation** ([BC001–BC025](./data/OP-RES-005A-bilingual-consistency-checks.csv)).

**Legal vs editorial:** legal equivalence of signed RU/KK ≠ symmetric drafting process (see OP-RES-005A §2).

---

## 18. Manual Override and Regeneration

### 18.1 Modes

| Mode | Description |
|---|---|
| GENERATED | From clause renderer |
| MANUALLY_EDITED | override_text set |
| REGENERATED | New generated; override → stale/review-required |
| LOCKED | Post-approval (conceptual) |

### 18.2 Answer Q17

**Override levels:** whole document, locale, item, obligation, preamble, control — all valid.

**On input change:**

| Changed | Regenerate | Preserve override |
|---|---|---|
| Party role | Affected items | Yes — mark stale |
| Travel dates | Items 1,3 | Yes |
| Scenario | Full structure | Warn — may invalidate |
| Controller | Control item | Yes |
| RU effective text (asymmetric mode) | Corresponding KK blocks | Yes — mark **STALE** / REVIEW_REQUIRED (OP-RES-005A) |

**Restore autogen:** explicit reset-to-generated per block (PO-EDIT pattern).

**Distinguish:** `generated_text` vs `effective_text` — **required**.

**OP-RES-005A:** when `drafting_path = ru_first_translated`, a manual RU edit after KK derivation must flag KK locale blocks stale without auto-overwriting KK text.

---

## 19. Document Assembly

### 19.1 Block order (semantic)

Confirmed OP-RES-002 shell — unchanged.

### 19.2 Semantic vs Visual

| Semantic Generation | Visual Formatting |
|---|---|
| Block sequence, item text, attachment content | Fonts, margins, tables |
| Numbering logic | DOCX styles |
| Bilingual block pairing | Page layout (mirror/interleave) |

Generation Model outputs **`SemanticDocument`** — format-agnostic. DOCX/HTML/PDF are exporters.

---

## 20. Validation Model

See [`data/OP-RES-005-validation-rules.csv`](data/OP-RES-005-validation-rules.csv):

- **11 errors** (semantic + text)
- **10 warnings** (subject matter)

Key gates: scenario selected, mandatory items, executor, controller when required, no placeholders, both locales if bilingual.

**OP-RES-005A extension:** bilingual orders require **consistency validation** ([OP-RES-005A checks](./data/OP-RES-005A-bilingual-consistency-checks.csv)) — structural/entity checks automated; terminology human-only. Block READY if KK locale is STALE or REVIEW_REQUIRED.

---

## 21. Generation Pipeline

### 21.1 Stages

| # | Stage | Mandatory | Repeatable | Manual OK |
|---|---|---|---|---|
| 1 | Scenario Selection | Yes | — | — |
| 2 | Input Collection | Yes | Yes | Yes |
| 3 | Semantic Item Construction | Yes | Yes | Yes |
| 4 | Obligation Validation | Yes | Yes | — |
| 5 | Clause Rendering | Yes | Yes | — |
| 6 | Control Meta-item Generation | Conditional | Yes | Yes |
| 7 | Document Assembly | Yes | Yes | — |
| 8 | Language Rendering | Yes | Yes | Yes (edit) |
| 9 | Manual Adjustment | No | Yes | Yes |
| 10 | Final Validation | Yes | Yes | — |
| 11 | Preview / Export | Yes | Yes | — |
| 12 | Execution Projection | Optional handoff | — | — |

**Generation ends:** step 11. Step 12 is boundary export only.

**OP-RES-005A — optional asymmetric path** (when `drafting_path = ru_first_translated`):

```text
RU Clause Rendering → RU Review → Translation Trigger → KK Draft (human/translator)
  → Bilingual Reconciliation → Staleness Check → Final Validation
```

Symmetric path (Model A) skips translation trigger; both locales generated from semantic model in parallel.

Diagram: [`diagrams/operational-order-generation-pipeline.svg`](diagrams/operational-order-generation-pipeline.svg) · OP-RES-005A: [`diagrams/bilingual-drafting-workflow.svg`](diagrams/bilingual-drafting-workflow.svg)

---

## 22. P0 Scenario Blueprints

Detailed blueprints: [`samples/OP-RES-005-p0-generation-blueprints.md`](samples/OP-RES-005-p0-generation-blueprints.md)

| Scenario | Docs | Share | Items (typical) |
|---|---:|---:|---|
| S_TRAVEL | 33 | 17.1% | 5–7 |
| S_COMMISSION | 28 | 14.5% | 2–4 |
| S_CLINICAL | 35 | 18.1% | 3–15 |
| S_ACCOUNTING | 18 | 9.3% | 3–10 |
| **P0 total** | **114** | **~59%** | — |

---

## 23. Boundary with Execution Model

### 23.1 Answer Q18

| Generation | Execution |
|---|---|
| Text + semantic snapshot | Tasks, statuses, evidence files |
| Validates document completeness | Tracks completion |
| Ends at export | Begins after registration/signing (future) |

### 23.2 Execution Obligation Descriptor (handoff)

```text
ExecutionObligationDescriptor
├── source_document_id
├── source_item_sequence
├── obligation_id
├── intent
├── responsible_party_ref
├── deadline_semantics
├── expected_result
├── evidence_expectation
├── control_obligation_ref
└── dependencies[]
```

No event bus / task engine designed here.

Diagram: [`diagrams/generation-execution-boundary.svg`](diagrams/generation-execution-boundary.svg)

---

## 24. Conceptual Generation Model

```text
OperationalOrderDefinition
│
├── Scenario
├── DocumentMetadata
├── PreambleDefinition
├── OrderItemDefinitions[]
│     └── ExecutionObligationDefinitions[]
├── ControlObligationDefinition?      ← often as final OrderItem
├── AttachmentDefinitions[]
├── SignatureDefinition
├── AgreementDefinition?              ← episodic
├── AcknowledgementDefinition?        ← discipline, commissions
├── LanguageRenderings{kk,ru}
├── ValidationResult
└── ExecutionProjection[]             ← handoff snapshot
```

**Confirmed** with additions: `AgreementDefinition`, `AcknowledgementDefinition` as optional blocks (OP-RES-002).

**Not proven:** amendment workflow (`REPEAL_AMEND` sparse); external party executor.

Diagram: [`diagrams/generation-model-concept.svg`](diagrams/generation-model-concept.svg)

---

## 25. Coverage and Limitations

| Area | Coverage |
|---|---|
| P0 blueprints | High |
| P1 scenarios | Medium (matrix only) |
| Item Type registry | High for P0; tail scenarios thinner |
| KK generation templates | **Low** |
| Amendment generation | **Low** (corpus sparse) |
| Attachment auto-parse | Medium — reference confirmed; row→obligation heuristic |

---

## 26. Risks of Premature Formalization

| Risk | Mitigation |
|---|---|
| 14 Item Types → production enum | Keep research registry; version templates |
| Auto evidence/report | Scenario flag + user confirm |
| RU→KK copy | Independent renderers |
| Generation = task manager | Strict boundary §23 |
| One template per folder | Scenario codes, not folders |
| Forcing split all multi-verb items | Heuristic + warning W005 |
| Assuming symmetric bilingual drafting | Support RU-first translation mode (OP-RES-005A) |
| Ignoring KK staleness after RU edit | Per-locale STALE flags |
| READY before KK reconciliation | Block or require waiver (interview) |

---

## 27. Conclusions

1. **Generation is scenario-driven**, building **Order Items** and **Execution Obligations**, not free text.
2. **14 Item Types** cover corpus; CONTROL and META_EFFECT are meta-items.
3. **Control meta-item** auto-generation is viable with editable output.
4. **Role-first parties** and **structured deadlines** enable high automation for P0.
5. **Attachments** and **commissions** have explicit generation sub-models.
6. **Multilingual:** target = one semantic model, dual independent render; **observed editorial practice likely RU-first translation** within same document (OP-RES-005A).
7. **Manual override** at block level with stale-on-regenerate.
8. **Validation** separates errors vs warnings before release.
9. **Execution projection** is handoff data, not generation scope.

---

## 28. Recommendations for OP-RES-006

1. Define **`SemanticDocument`** and **`OperationalOrderDefinition`** as architecture primitives (no DB yet).
2. Reuse **Document Shell** from PO-EDIT-001; add `OperationalItemPayload`.
3. Implement **ScenarioTemplateRegistry** (21 entries) referencing Item Type registry.
4. Plan **ClauseRenderer** interface: `render(obligation, locale) → text`.
5. Plan **EditorialBlock** persistence mirroring Personnel Orders (kk/ru rows).
6. Defer **Execution Engine** integration — consume `ExecutionObligationDescriptor` only.
7. Prioritize P0 templates in implementation order: S_TRAVEL → S_COMMISSION → S_CLINICAL → S_ACCOUNTING.
8. KK template library as **separate workstream** with legal review.
9. **OP-RES-005A:** add `drafting_path`, `source_language`, translation workflow, language-version staleness, bilingual consistency validation (see [OP-RES-005A §24](./OP-RES-005A-bilingual-drafting-workflow.md)).

---

## Appendix A — Mandatory Questions (direct answers)

| # | Question | Answer |
|---|---|---|
| 1 | Minimal data for generation? | scenario + metadata + ≥1 obligation (intent, party, object) + controller when required |
| 2 | Start from scenario or arbitrary items? | **Scenario-first** |
| 3 | Primary generation unit? | **Order Item** (obligations inside) |
| 4 | Item Type vs Business Intent? | Item Type = render template; Intent = management meaning |
| 5 | Stable Item Types count? | **14** semantic families (+ OTHER) |
| 6 | Multiple obligations in one item? | **Yes** when same party/deadline; commission roster |
| 7 | When split? | Different parties, deadlines, control, ack, regulatory sub-enums |
| 8 | Auto-generate control item? | **Yes**, editable |
| 9 | Data for control? | controller_party, control_mode, control_scope |
| 10 | Executor representation? | **Role-first**; NamedPerson when required |
| 11 | Deadlines one-to-one text? | Calendar, period, within_days, from_signature, monthly |
| 12 | Manual deadline wording? | until_event, permanent, as_needed, external_doc |
| 13 | Auto expected result/evidence? | Result: derive OK; Evidence: **no auto** if changes duty |
| 14 | Attachment as obligation source? | **Yes**, when referenced |
| 15 | Commission order generation? | CREATE_BODY + inline/attachment composition + CONTROL |
| 16 | Independent RU/KK from semantic model? | **Yes (target)**; editorial mode may be RU-first translation (OP-RES-005A) |
| 17 | Preserve manual edits on regen? | **Yes** — override kept, marked stale |
| 18 | Generation vs execution boundary? | Export ends generation; execution is downstream |
| 19 | P0 covered by common model? | **Yes**, scenario parameters |
| 20 | Shared with Personnel Orders? | Document shell, editorial blocks, bilingual model, effective_text, validation gate, separation structured vs text |

---

## Appendix B — Artifacts

| File | Role |
|---|---|
| [`OP-RES-005-generation-model.md`](OP-RES-005-generation-model.md) | This report |
| [`data/OP-RES-005-item-type-registry.csv`](data/OP-RES-005-item-type-registry.csv) | Item Type registry |
| [`data/OP-RES-005-scenario-generation-matrix.csv`](data/OP-RES-005-scenario-generation-matrix.csv) | Scenario generation matrix |
| [`data/OP-RES-005-validation-rules.csv`](data/OP-RES-005-validation-rules.csv) | Validation rules |
| [`data/OP-RES-005-corpus-probe-stats.txt`](data/OP-RES-005-corpus-probe-stats.txt) | Probe aggregates |
| [`scripts/op_res_005_generation_probe.py`](scripts/op_res_005_generation_probe.py) | Read-only probe |

---

*OP-RES-005 complete. Research documentation only. No source files modified. No production code.*
