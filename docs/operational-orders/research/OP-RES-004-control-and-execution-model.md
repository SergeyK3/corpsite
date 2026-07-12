# OP-RES-004 — Control & Execution Model

WP: **OP-RES-004** — Control & Execution Model  
Date: **2026-07-12**  
Mode: **research-only** (read-only analysis; no runtime changes)  
Corpus: `order_samples/Производственные приказы/` — **193 documents** (183 DOCX deep analysis)  
Prior work: [OP-RES-001](./OP-RES-001-corpus-passport.md), [OP-RES-002](./OP-RES-002-structural-pattern-analysis.md), [OP-RES-003](./OP-RES-003-operational-order-taxonomy.md)

---

## 1. Executive Summary

Исследование подтверждает и уточняет гипотезу **Intent × Managed Object × Responsible Party × Control × Deadline × Expected Result** как ядро преобразования распорядительного пункта в исполнимое управленческое обязательство.

**Главный результат:** минимальная исполнимая единица корпуса — **Order Item (нумерованный пункт)**, декомпозируемый на одно или несколько **Execution Obligation**; **Control Obligation** — отдельная сущность, часто вынесенная в финальный meta-пункт.

| Finding | Corpus signal |
|---|---|
| Primary execution unit | Order Item (~10.5 items/doc; 1,926 items in 183 DOCX) |
| Multi-obligation items | ~14% items (270) with multiple directive verbs |
| Control present | ~92% documents (OP-RES-002); final-item placement 156 docs |
| Control ≠ executor | Distinct roles in 95%+ disciplinary and commission orders |
| P0 scenarios share one model | Yes — parameterised Execution Obligation + optional Control Obligation |
| Attachments as obligation source | 35 docs; 25 item-level attachment refs |
| Explicit evidence required | Minority; ack_list most common explicit form (102 items) |

**Для Document Engine (research):** общие примитивы — `Order Item`, `Execution Obligation`, `Control Obligation`, `Party` (role/named), `Deadline`, `ManagedObjectTag`, `EvidenceExpectation` — без проектирования классов или API.

Диаграммы: [`diagrams/operational-order-execution-model.svg`](diagrams/operational-order-execution-model.svg), [`diagrams/control-responsibility-model.svg`](diagrams/control-responsibility-model.svg), [`diagrams/execution-obligation-anatomy.svg`](diagrams/execution-obligation-anatomy.svg), [`diagrams/execution-lifecycle-concept.svg`](diagrams/execution-lifecycle-concept.svg), [`diagrams/commission-execution-model.svg`](diagrams/commission-execution-model.svg)

Матрица: [`data/OP-RES-004-control-execution-matrix.csv`](data/OP-RES-004-control-execution-matrix.csv)  
Паттерны: [`samples/anonymized-execution-patterns.md`](samples/anonymized-execution-patterns.md)  
Research tooling: [`scripts/op_res_004_execution_probe.py`](scripts/op_res_004_execution_probe.py) (read-only; documented in §3)

---

## 2. Контекст и цели исследования

### 2.1 Research question

**Как распорядительный пункт преобразуется в исполнимое управленческое обязательство?**

Ответ корпуса: пункт задаёт **директиву** (Intent) над **объектом** (Managed Object), адресованную **стороне** (Responsible Party), опционально ограниченную **сроком** и **ожидаемым результатом**; **контроль** чаще оформляется отдельным обязательством, связывающим **Controller** с scope (весь приказ / направление / пункт).

### 2.2 Scope OP-RES-004

| In scope | Out of scope |
|---|---|
| Execution semantics from text | DB, API, UI, workflow engine |
| Control vs responsibility separation | DSL / generation (→ OP-RES-005) |
| 21 scenario profiles | Personnel Orders changes |
| Conceptual domain model | Runtime state machine implementation |

---

## 3. Методика и покрытие корпуса

### 3.1 Inputs

- Structural patterns OP-RES-002 (control placement, item numbering)
- Taxonomy OP-RES-003 (domain, scenario per document)
- Full-text OOXML extraction (183 DOCX)
- Research script `op_res_004_execution_probe.py`: regex probes for items, control, deadlines, evidence (read-only; writes anonymized aggregates only)

### 3.2 Coverage

| Layer | n | Notes |
|---|---:|---|
| Documents in registry | 193 | All classified OP-RES-003 |
| DOCX item-level analysis | 183 | 1,926 numbered items parsed |
| DOC (filename only) | 8 | Execution patterns inferred weakly |
| PDF | 2 | Excluded (no OCR) |
| Scenario matrix rows | 21 | Aggregated, no PII |

### 3.3 Validation

- Qualitative review of P0 samples (travel, commission, clinical, accounting) against [`samples/anonymized-execution-patterns.md`](samples/anonymized-execution-patterns.md)
- Cross-check control prevalence with OP-RES-002 (168/183 with control keywords)

---

## 4. Минимальная единица исполнения

### 4.1 Иерархия понятий (research boundaries)

| Concept | Definition | Corpus boundary |
|---|---|---|
| **Document** | Юридически оформленный акт целиком | 1 file = 1 document instance |
| **Order Item** | Нумерованный пункт `1.` / `1.1.` / `1)` | **Primary decomposition unit** |
| **Instruction** | Bullet/subline under item without own number | Part of parent item unless separately numbered |
| **Execution Obligation** | Минимальное исполнимое обязательство смысла | Usually 1 per item; sometimes 2+ |
| **Control Obligation** | Надзор за исполнением (scope-defined) | Often separate final item |

**Весь приказ** как единица исполнения — только для:

- meta-пунктов (вступление в силу);
- единого control «за настоящий приказ»;
- acknowledgement block (ознакомление).

Операционные действия **не** назначаются на document-level.

### 4.2 Sub-units

| Sub-unit | When executable | Example |
|---|---|---|
| **Sub-item** (`1.1`, `1.2`) | Yes — child obligation | Transport access rules |
| **Attachment row** | Yes — if item references attachment | Commission roster in Приложение 1 |
| **Bullet under item** | Usually merged into parent | Department list under «установить перечень» |
| **Periodic duty** | Yes — recurring obligation | Monthly ОППВ, permanent regime |
| **Commission task** | Yes — phase 2 after creation | «оформить акт по результатам» |

### 4.3 Multi-obligation items

**Да**, один пункт может содержать несколько обязательств:

- **270 / 1,926 items (14%)** — heuristic multi-verb detection;
- higher in regulatory mega-orders (pharma, narcotics);
- pattern: «создать комиссию + перечислить состав + возложить обязанности» in one numbered block;
- **recommendation:** parser should split on clausal boundaries when multiple dative addresses appear.

---

## 5. Модель исполнителей и участников

### 5.1 Responsible Party models (corpus-stable)

| Model | Item hits | Recording | Personal vs role |
|---|---:|---|---|
| **dative_person** (ФИО) | 412 | `Иванову И.И.` | Personal; may change without order amendment in practice |
| **dative_position** | 49 | `Заведующему отделения X` | Role-based; survives staff turnover |
| **unit_subject** | 40 | `Отделу фармации` | Organizational executor |
| **commission** | 273 | collective + roster | Multi-party |
| **kk_mandate** | 169 | `жүктелсін`, `тағайындалсын` | Role/person in KK block |
| **director_self** | frequent as controller | «оставляю за собой» | Signatory ≠ executor |
| **undefined** | rare | passive constructions | Requires human interpretation |

### 5.2 External executor

Корпус ММЦ: **внешние исполнители не назначаются** как parties; встречаются **внешние источники финансирования** («за счёт приглашающей стороны») — это condition, не party.

### 5.3 Multiple executors

- **Parallel items** (S_CLINICAL, S_TRAVEL multi-employee): each item → one primary executor;
- **Co-executors** rarely labeled explicitly; inferred from «и» в одном пункте or multiple names;
- **Commission members** — collective execution, not co-executor list on a single duty.

---

## 6. Ответственность и соисполнение

### 6.1 Role taxonomy

| Role | Exclusive? | Corpus note |
|---|---|---|
| Исполнитель | No | Performs the action |
| Ответственный исполнитель | No | Often blurred with executor in «ответственное лицо» |
| Соисполнитель | No | Rarely explicit |
| Координатор | No | Implied in conference/event orders |
| Руководитель | No | May be controller and executor in different items |
| Председатель комиссии | No | Can also be commission member |
| Секретарь | No | Minority of commissions |
| Контролирующее лицо | No | Often different person from executor |
| Принимающий результат | No | Implicit (controller or accounting) |
| Информируемое лицо | No | «довести до сведения» — rare |

### 6.2 Multi-role on same participant

**Да.** Example pattern (disciplinary): employee is subject of item 1; department head controls in item 2; same head not executor of item 1. Director signs all but executes none.

### 6.3 Responsibility vs control

| Phrase | Classification |
|---|---|
| «Контроль возложить на…» | **Control Obligation** |
| «Ответственность возложить на…» | **Blended** — accountability + oversight |
| «Взять на контроль…» | **Embedded control duty** (ongoing) |
| «Обеспечить исполнение…» | **Execution** (not control) |
| «Назначить ответственным…» | **Execution** — assigns ongoing duty |

**Не автоматически одно понятие:** совпадение возможно только когда одна формулировка несёт оба смысла; в дисциплинарных приказах расходятся стабильно.

---

## 7. Контроль исполнения

### 7.1 Prevalence (OP-RES-002 + probe)

| Signal | Documents / items |
|---|---|
| Control keywords anywhere | 168 / 183 docs (92%) |
| Control in final 1–2 items | 156 docs |
| No explicit control | ~15 docs (8%) |
| Embedded «взять на контроль» | 12 items; 7 docs |
| «Оставляю за собой» | Dominant in S_TRAVEL, S_FUNDS |
| «Контроль возложить на [должность]» | S_COMMISSION, S_ACCOUNTING |
| Multi-controller | S_DISCIPLINE (items 2–3) |
| Report on progress | 3 items; rare |

### 7.2 Control scope

| Scope | Description | Frequency |
|---|---|---|
| **order** | Entire document | Dominant |
| **item** | Single пункт | Disciplinary, embedded |
| **direction** | Functional line («по лечебной работе») | Disciplinary |
| **self** | Director retains control | Travel, funds |
| **formal** | No deadline, no reporting | Majority |

### 7.3 Control with reporting

Explicit reporting («представить информацию о ходе») — **редкость** в корпусе. Control is **organizational**, not task-tracker oriented.

---

## 8. Модели сроков

### 8.1 Deadline types observed

| Type | Item hits | Formalizable? | Examples |
|---|---:|---|---|
| **calendar_date** | 265 | High | `11–13 марта 2026`, event dates |
| **until_event** | 255 | Medium | «по окончании конференции» |
| **from_signature** | 40 | High | «со дня подписания» |
| **period_range** | 16 | High | Travel, event windows |
| **within_n_days** | 6 | High | «в течение 3 рабочих дней» |
| **monthly** | 7 | High | ОППВ billing |
| **quarterly** | 3 | Medium | Reporting cycles |
| **permanent** | 5 | Low | «постоянно действующая» |
| **no_deadline** | majority | N/A | Ongoing duties |

### 8.2 Semantically undefined (corpus)

- «по мере необходимости» — not counted but qualitative
- «незамедлительно» — rare
- «до полного исполнения» — implied in control, not metric
- срок из внешнего документа без календарной привязки
- permanent regime without review date

### 8.3 Start triggers

| Trigger | Usage |
|---|---|
| Date of signature | Meta-items, regulations |
| Date of acknowledgement | Disciplinary (HR must ack within 3 days) |
| After event | Funds report after conference |
| Calendar start | Travel departure date |

---

## 9. Expected Result

### 9.1 Explicit vs implicit

**Чаще implicit** — выводится из глагола Intent:

| Result model | Item hits | Verb source |
|---|---:|---|
| maintain_regime | 97 | обеспечить, соблюдать |
| create_object | 74 | создать, утвердить |
| conduct_action | 69 | провести, организовать, направить |
| state_change | 48 | взять на контроль, ввести |
| acknowledgement | 25 | ознакомить |
| provide_report | 8 | представить отчёт |

### 9.2 Result by scenario (P0)

| Scenario | Typical expected result |
|---|---|
| S_TRAVEL | Employee traveled; expenses settled |
| S_COMMISSION | Commission constituted; later act produced |
| S_CLINICAL | Service mode organized; event held |
| S_ACCOUNTING | Inventory/act completed |

---

## 10. Execution Evidence

### 10.1 Explicit evidence in corpus

| Evidence type | Item hits | When required |
|---|---:|---|
| **ack_list** | 102 | Disciplinary, commissions (Танысу парағы) |
| **report** | 30 | Funds, some accounting |
| **protocol** | 18 | Commissions, procurement |
| **act** | 6 | Asset commission |
| **payment** | 8 | Financial transfers |
| **signed_doc** | 2 | Rare explicit |

### 10.2 Implicit evidence

Majority of operational obligations: **no formal evidence** specified — compliance assumed through organizational practice.

**Когда явно:** дисциплина (ознакомление), командировки/средства (авансовый отчёт), комиссии (акт).

---

## 11. Зависимости между пунктами

### 11.1 Corpus frequency

| Dependency type | Hits | Notes |
|---|---:|---|
| Parallel items | Dominant | S_CLINICAL, S_TRAVEL |
| Sequential (event trigger) | Qualitative | S_FUNDS: transfer → report after event |
| per_attachment | 25 | «согласно приложению» |
| per_item_ref | 3 | Weak explicit refs |
| upon_approval | Rare | Plans, regulations |
| supersede | 1 | «утратил силу» — rare |

### 11.2 Patterns

- **Commission flow:** item 1 create → (work implied) → control item
- **Discipline:** sanction → control → awareness (sequential awareness)
- **Travel:** parallel conditions (expenses, salary) + self-control

---

## 12. Комиссии и рабочие группы

See [`diagrams/commission-execution-model.svg`](diagrams/commission-execution-model.svg).

### 12.1 Three perspectives (confirmed)

| Perspective | Research role |
|---|---|
| **Commission as Party** | Who acts (chair, members, secretary) |
| **Commission as Managed Object** | What is created («комиссия по…») |
| **Commission as Execution Mechanism** | How work is done (inspection → act) |

### 12.2 Corpus facts (57 commission docs)

- Chair: **49/57**; Secretary: **36/57** (surprisingly frequent)
- Term / quorum: **rarely stated**
- Permanent vs temporary: **usually implicit** from subject
- Roster: **inline 80%** / attachment **20%**
- Two-phase execution: **create commission** (order item) ≠ **commission produces act** (implied)

---

## 13. Приложения как источник обязательств

### 13.1 Corpus

- **35 docs** reference attachments
- **25 items** say «согласно приложению»
- **24 DOCX** contain tables (inline attachment)

### 13.2 Attachment content types

| Content | Creates obligations? |
|---|---|
| Commission roster | Yes — when item 1 references it |
| Plans / schedules | Yes — execution tied by reference |
| Training lists | Yes — S_TRAINING |
| Budget tables | Qualitative — FINANCE |
| Blank forms | No — template only |

**Да**, приложение может создавать **самостоятельные обязательства**, отсутствующие в основном тексте, **если** пункт приказа делегирует исполнение «согласно приложению N».

---

## 14. Execution Lifecycle

### 14.1 States inferred from text + practice

| State | Textual anchor |
|---|---|
| created | Appears on signature / «вступает в силу» |
| pending_start | Before effective date |
| in_progress | During travel period, event prep |
| waiting_dependency | After event, before report |
| completed | Rarely stated |
| partially_completed | Not in text |
| overdue | Not in text (inferred organisationally) |
| continuously_active | Permanent regimes |
| superseded | 1 doc «утратил силу» |
| closed_by_controller | Organizational, not textual |

### 14.2 vs Document Lifecycle

| Document Lifecycle | Execution Lifecycle |
|---|---|
| draft → signed → registered → voided | created → in_progress → done |
| Managed by document module | Managed per obligation |
| Single state per document | Multiple states per document |

**Чётко разные:** подписание не завершает исполнение; void document ≠ auto-cancel all obligations (needs legal analysis — out of scope).

---

## 15. Изменение, отмена и замена поручений

### 15.1 Corpus signals (rare)

| Construction | Hits | Effect level |
|---|---:|---|
| признать утратившим силу | 1 | document / prior order |
| внести изменения | qualitative | document |
| изложить в новой редакции | rare | item |
| exclude/include commission member | rare | commission roster |

### 15.2 What changes affect

| Change type | Typical target |
|---|---|
| New order supersedes | Prior document |
| Item amendment | Single item obligation |
| Staff turnover | Executor identity (without order) — **organizational gap** |
| Extended deadline | Not in corpus explicitly |

Корпус **слабо покрывает** amendment patterns — future orders module must support them normatively even if corpus is sparse.

---

## 16. Сценарный анализ

### 16.1 P0 scenarios (~59% corpus)

| Scenario | n | Complexity | Shared model? |
|---|---:|---|---|
| **S_TRAVEL** | 33 | Low — template 5 items | Yes |
| **S_COMMISSION** | 28 | Medium — roster + control | Yes |
| **S_CLINICAL** | 35 | Medium — parallel units | Yes |
| **S_ACCOUNTING** | 18 | Medium — commission + act | Yes |

**Вывод:** одна **общая Execution Model** с scenario parameters (see matrix CSV).

### 16.2 P0 execution profile summary

| Scenario | Intent | Object | Executor | Controller | Deadline | Result | Evidence |
|---|---|---|---|---|---|---|---|
| S_TRAVEL | направить | сотрудники | named/role | director_self | period | travel_done | memo |
| S_COMMISSION | создать | комиссии | positions | chief_accountant | none | constituted | ack |
| S_CLINICAL | организовать | процессы | heads | deputy_clinical | event_date | service_ready | implicit |
| S_ACCOUNTING | утвердить | имущество | commission | chief_accountant | none | act_done | act |

### 16.3 Full scenario matrix

All 21 scenarios: [`data/OP-RES-004-control-execution-matrix.csv`](data/OP-RES-004-control-execution-matrix.csv)

---

## 17. Матрица Intent × Object × Party × Control

Aggregated scenario matrix columns:

`scenario_code`, `domain`, `order_type`, `business_intent`, `managed_object`, `execution_unit`, `primary_responsible_party`, `co_executors`, `controller`, `deadline_type`, `deadline_expression`, `recurrence`, `expected_result`, `execution_evidence`, `dependencies`, `commission_involved`, `attachment_driven`, `control_scope`, `docs_in_corpus`, `notes`

**Cross-domain invariant:** every scenario has **Intent + Object + Party**; **Control** present in ~90%+; **Deadline** scenario-dependent; **Evidence** often `implicit`.

---

## 18. Концептуальная Control & Execution Model

```text
Operational Order
│
├── Document Shell (OP-RES-002)
│
├── Order Item[]
│     ├── Execution Obligation[]
│     │     ├── Intent
│     │     ├── Managed Object(s)
│     │     ├── Responsible Party
│     │     ├── Co-executors?
│     │     ├── Deadline?
│     │     ├── Expected Result (explicit or derived)
│     │     ├── Evidence expectation?
│     │     └── Dependencies?
│     │
│     └── Control Obligation?  (may be separate item)
│           ├── Controller Party
│           ├── Scope (order | item | direction)
│           └── Reporting? (rare)
│
├── Commission / Working Group?  (Party + Mechanism)
├── Attachment?  (optional obligation source)
└── Acknowledgement block?  (evidence of distribution)
```

**Подтверждено корпусом** с уточнением: Control Obligation — sibling of Execution Obligation, not always embedded field.

---

## 19. Разграничение Document Lifecycle и Execution Lifecycle

| Aspect | Document | Execution |
|---|---|---|
| Unit | Whole act | Item / obligation |
| Trigger | Signature, registration | Effective date, event, acknowledgement |
| Completion | Registration / void | Result delivered (often implicit) |
| Control | Legal validity | Managerial oversight |
| Evidence | Signed PDF, journal entry | Act, report, ack list |

Personnel Orders: same split — apply reads structured payload; document state ≠ employment event completion.

---

## 20. Степень покрытия и исключения

| Area | Coverage |
|---|---|
| Item-level execution | High (183 DOCX) |
| Control models | High |
| Deadline formalization | Medium (calendar good; event-typed fair) |
| Evidence | Medium-low (implicit dominant) |
| Dependencies | Low explicit |
| Amendment / supersede | Low (sparse corpus) |
| IT-driven execution | Negligible (1 doc) |
| PDF/DOC gap | 10 files partial |

---

## 21. Архитектурные выводы (research → Document Engine)

### 21.1 Shared primitives (all domains)

1. **Order Item** — anchor for obligations  
2. **Execution Obligation** — actionable unit  
3. **Control Obligation** — separable oversight link  
4. **Party reference** — role-first, named optional  
5. **ManagedObject tags** — plural per obligation  
6. **Deadline** — optional structured or textual  
7. **ExpectedResult** — derived from intent if not explicit  
8. **EvidenceExpectation** — optional, scenario-defaulted  
9. **Scenario taxonomy** (OP-RES-003) — parameterizes defaults  

### 21.2 Not shared with Personnel Orders

- Payload facts (travel destination vs hire date)
- Default evidence (ack list vs personnel acknowledgement)
- Apply/integration to HR SoT

### 21.3 Orthogonal layers

```text
Document Shell (shared)
  × Taxonomy / Scenario (class-specific)
  × Execution Obligations (instance-specific)
```

---

## 22. Риски преждевременной формализации

| Risk | Mitigation |
|---|---|
| Treating control as executor field | Keep Control Obligation separate |
| Single deadline per order | Model item-level deadlines |
| Forcing explicit result everywhere | Allow derived results from intent |
| Ignoring attachment obligations | Parse attachment refs |
| Role = employee only | Support unit, commission, role |
| Building task manager UI too early | Execution model ≠ workflow product |
| Collapsing 21 scenarios into 21 classes | Use scenario parameters on common model |

---

## 23. Рекомендации для OP-RES-005 (Generation Model)

1. **Generate Order Items first**, then split into Execution Obligations where multi-verb.
2. **Template P0 scenarios** (travel 5-item, commission 2-item) as generation baselines.
3. **Auto-insert control meta-item** when scenario default has `controller` (90%+ cases).
4. **Party resolution:** role → position lookup; named → employee link optional.
5. **Deadline:** structured for calendar/within_days; textual fallback for events.
6. **Evidence:** scenario-level default (`implicit` vs `ack_list` vs `advance_report`).
7. **KK/RU:** parallel obligations share structure, not merge fields.
8. **Do not generate task IDs or workflow states** — generation produces text + structured snapshot only.

---

## 24. Обязательные выводы (прямые ответы)

| # | Question | Answer |
|---|---|---|
| 1 | Минимальная исполнимая единица? | **Order Item** (или подпункт), декомпозируемый в **Execution Obligation** |
| 2 | Несколько обязательств в одном пункте? | **Да**, ~14% пунктов; чаще в регламентных приказах |
| 3 | Исполнитель vs ответственный vs контролёр? | **Разные роли**; контролёр редко исполняет действие |
| 4 | Несколько ролей у одного участника? | **Да**, в разных пунктах |
| 5 | Scope контроля? | **Преимущественно весь приказ**; также пункт и направление |
| 6 | Сроки для формализации? | Календарные, период, within N days, from signature, monthly |
| 7 | Неопределённые сроки? | until_event (vague), permanent, no_deadline, as_needed |
| 8 | Результат исполнения? | Часто **implicit** из глагола; create/conduct/maintain/ack |
| 9 | Подтверждение исполнения? | Часто implicit; explicit: ack_list, report, act, protocol |
| 10 | Приложения как обязательства? | **Да**, когда пункт ссылается на приложение |
| 11 | Комиссии в исполнении? | **Party + Object + Mechanism**; двухфазное исполнение |
| 12 | Изменение/отмена? | **Редко в корпусе**; normative need exceeds textual examples |
| 13 | Execution vs document lifecycle? | **Ортогональны** |
| 14 | P0 одной моделью? | **Да**, с scenario parameters |
| 15 | Общее для Document Engine? | Order Item, Execution/Control Obligation, Party, Intent, Object, Deadline, Result, Evidence |

---

## Appendix A — Artifacts

| File | Role |
|---|---|
| [`OP-RES-004-control-and-execution-model.md`](OP-RES-004-control-and-execution-model.md) | This report |
| [`data/OP-RES-004-control-execution-matrix.csv`](data/OP-RES-004-control-execution-matrix.csv) | Scenario matrix |
| [`data/OP-RES-004-corpus-probe-stats.txt`](data/OP-RES-004-corpus-probe-stats.txt) | Probe aggregates (no PII) |
| [`scripts/op_res_004_execution_probe.py`](scripts/op_res_004_execution_probe.py) | Read-only research script |
| [`samples/anonymized-execution-patterns.md`](samples/anonymized-execution-patterns.md) | Pattern library |

## Appendix B — Research tooling justification

Script `op_res_004_execution_probe.py` added because:

- Manual review of 1,926 items is not reproducible
- Script is read-only, writes only to `research/data/`
- Output contains no ФИО (aggregates and role codes only)
- Needed to validate multi-obligation rate and deadline frequencies

---

*OP-RES-004 complete. Research documentation only. No source files modified.*
