# OP-RES-006 — ADR Backlog

WP: **OP-RES-006** (supporting artifact)  
Updated: **OP-RES-006A** (2026-07-12)  
Date: **2026-07-12**  
Status: **Pending ratification** (no separate ADR files created)

ADR должны быть приняты **до начала implementation WP** (после UDE-000).

---

## ADR-UDE-001 — Unified Document Core

| Field | Content |
|---|---|
| **Question** | Должны ли Personnel и Operational Orders использовать один Document Core? |
| **Recommended decision** | **Да.** Один Document Core с specialization через composition + policy/registry. |
| **Alternatives** | (a) Два независимых модуля; (b) наследование классов Document → PersonnelOrder/OperationalOrder |
| **Consequences** | Единый lifecycle, editorial, audit; требует extraction plan; снижает дублирование |
| **Evidence** | OP-RES-002 (единый shell 97%); PO-EDIT-001 alignment; Personnel Orders MVP editorial model |

---

## ADR-UDE-002 — Composition over Duplicated Modules

| Field | Content |
|---|---|
| **Question** | Как специализировать PO и OO без копирования кода? |
| **Recommended decision** | **Composition + policy/registry + plugin-like specialization modules.** |
| **Alternatives** | Class inheritance; microservices per document kind; copy-paste PO module |
| **Consequences** | Registries become extension points; avoids fragile inheritance trees |
| **Evidence** | OP-RES-003 (8 domains orthogonal to shell); gap analysis Class A/B |

---

## ADR-UDE-003 — Order Item and Obligation Separation

| Field | Content |
|---|---|
| **Question** | Является ли Order Item тем же, что Execution Obligation? |
| **Recommended decision** | **Нет.** Order Item = generation/editorial unit; Execution Obligation = semantic management unit. 1 item → 0..N obligations. |
| **Alternatives** | Collapse to single entity; document-level obligations only |
| **Consequences** | Multi-obligation items (~14%); item-level regeneration independent of projection |
| **Evidence** | OP-RES-004 §4; OP-RES-005 generation unit vs obligation |

---

## ADR-UDE-004 — Three Independent Lifecycles

| Field | Content |
|---|---|
| **Question** | Сколько lifecycle существует? |
| **Recommended decision** | **Три независимых:** Document, Localization, Execution. Archive orthogonal to document status. |
| **Alternatives** | Single unified state machine; document status includes execution progress |
| **Consequences** | Interaction rules needed; READY blocked by locale staleness; execution overdue ≠ document state |
| **Evidence** | OP-RES-004 execution lifecycle; OP-RES-005A localization states; PO archive pattern |

---

## ADR-UDE-005 — Generated Text vs Effective Text

| Field | Content |
|---|---|
| **Question** | Что является authority для редактирования и подписания? |
| **Recommended decision** | **Pre-sign authority: semantic model.** **Signing authority: effective localized text.** Generated and effective are distinct layers; override preserved on regeneration (stale, not silent delete). |
| **Alternatives** | Effective text only; generated overwrites override; free-text only |
| **Consequences** | Fingerprint/staleness required; PDF from effective snapshot |
| **Evidence** | PO-EDIT-002 implemented; OP-RES-005 manual override model |

---

## ADR-UDE-006 — Hybrid Multilingual Workflow

| Field | Content |
|---|---|
| **Question** | Symmetric semantic-first или RU-first translation? |
| **Recommended decision** | **Hybrid:** Model A (semantic → RU+KK renderers) as target; Model B (RU effective → translate → reconcile) as editorial mode. Legal equivalence ≠ editorial symmetry. |
| **Alternatives** | Symmetric only; RU-only; machine translation |
| **Consequences** | drafting_path, source_language, per-locale staleness; BC001–BC025 validation |
| **Evidence** | OP-RES-005A (135 bilingual single-DOCX; 75 kk-after-ru); Personnel Orders symmetric generate |

---

## ADR-UDE-007 — Role-first Party Reference

| Field | Content |
|---|---|
| **Question** | Как представлять исполнителя/контролёра? |
| **Recommended decision** | **Role-first PartyReference** with optional NamedPerson resolution snapshot at document date. ФИО — optional resolution, not primary key. |
| **Alternatives** | employee_id only; free-text only; position title strings |
| **Consequences** | Party resolution service; historical snapshot immutability after sign |
| **Evidence** | OP-RES-004 §5 (dative_position vs dative_person); OP-RES-005 role-first |

---

## ADR-UDE-008 — Execution Projection Boundary

| Field | Content |
|---|---|
| **Question** | Где заканчивается Document Engine? |
| **Recommended decision** | Document Engine ends at validated export + **ExecutionObligationDescriptor emission**. Task runtime is downstream. Projection after REGISTERED (draft preview optional). |
| **Alternatives** | Embed task engine in document module; projection at DRAFT always; no projection |
| **Consequences** | Idempotent projection; compensating on VOIDED/ANNUL; PO apply remains HR-specific adapter |
| **Evidence** | OP-RES-004/005 generation-execution boundary; PO apply_service pattern |

---

## ADR-UDE-009 — Immutable Signed Snapshot

| Field | Content |
|---|---|
| **Question** | Что immutable после подписания? |
| **Recommended decision** | **Effective localized text + signatory metadata + registration metadata** frozen at SIGNED/REGISTERED. Semantic model changes require amendment/compensating document, not silent regeneration. |
| **Alternatives** | Regenerate after sign; mutable signed docs; PDF-only immutability |
| **Consequences** | Signed snapshot store; reproducible PDF; audit trail |
| **Evidence** | PO locked statuses; PO-LC-006 archived immutability; OP-RES-005 no post-sign regenerate |

---

## ADR-UDE-010 — Incremental Migration from Personnel Orders

| Field | Content |
|---|---|
| **Question** | Как перейти без big-bang rewrite? |
| **Recommended decision** | **6-phase staged extraction.** OO MVP in Phase 4 without full PO refactor. Adapters + feature flags. PO convergence last (Phase 6). |
| **Alternatives** | Big-bang rewrite; OO waits for full PO refactor; parallel duplicate modules |
| **Consequences** | Longer timeline but lower risk; compatibility guarantees mandatory |
| **Evidence** | Gap analysis (16 Class A components); production PO MVP constraints |

---

## ADR-UDE-011 — Content Author vs Record Creator *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Должен ли создатель записи в системе считаться автором содержания? |
| **Recommended decision** | **Нет.** `content_author` (PartyReference) и `created_by` (record creator) — раздельные обязательные метаданные для OO. |
| **Alternatives** | Implicit author from creator; single owner field |
| **Consequences** | Intake must declare author; audit distinguishes RECORD_CREATED vs CONTENT_AUTHORED |
| **Evidence** | Organizational observation; PO `created_by` pattern; OP-RES-006A |

---

## ADR-UDE-012 — Submitted-text Intake as First-class Drafting Path *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Является ли submitted-text intake временным workaround? |
| **Recommended decision** | **Нет.** Model C — полноценный P0 drafting path для Operational Orders MVP. |
| **Alternatives** | Scenario-first only; intake as import feature |
| **Consequences** | OO-IMP-001 prioritizes intake; scenario generation parallel (OO-IMP-003) |
| **Evidence** | Organizational observation; OP-RES-005A bilingual patterns; dept-prepared drafts |

---

## ADR-UDE-013 — Text Provenance per Locale *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Нужно ли фиксировать происхождение текста per locale block? |
| **Recommended decision** | **Да**, минимум per block: `source_type`, `source_actor`, `source_unit`, `derived_from_version`. |
| **Alternatives** | Document-level only; no provenance |
| **Consequences** | SUBMITTED vs TRANSLATED vs GENERATED distinguishable; audit reproducibility |
| **Evidence** | OP-RES-006A; mixed RU submitted + KK translated workflow |

---

## ADR-UDE-014 — Content Confirmation after Editorial Changes *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Должен ли content author подтверждать смысл после правок HR? |
| **Recommended decision** | **Да** для content changes; **нет** для form-only edits (default policy). Blocks READY/approval when pending. |
| **Alternatives** | HR self-approve; no confirmation; always confirm |
| **Consequences** | Content confirmation workflow; change classification (form vs content) |
| **Evidence** | Organizational observation; logical necessity — interview to confirm policy |

---

## ADR-UDE-015 — HR as Document Operator, not Default Content Owner *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Является ли HR автором производственного приказа по умолчанию? |
| **Recommended decision** | **Нет** для Operational Orders. HR = Document Operator / Editorial Processor. |
| **Alternatives** | HR as default author; merged roles |
| **Consequences** | Access capabilities split; journal shows correct authorship |
| **Evidence** | Organizational observation; PO contrast (HR often author for personnel) |

---

## ADR-UDE-016 — Hybrid Source of Truth during Draft Intake *(OP-RES-006A)*

| Field | Content |
|---|---|
| **Question** | Что является SoT когда semantic model ещё неполная? |
| **Recommended decision** | **Staged SoT:** Early intake = submitted+provenance; Editorial = partial semantic + effective under reconciliation; READY = validated semantic + reconciled effective. |
| **Alternatives** | Submitted text as SoT throughout; effective-only |
| **Consequences** | Relaxes OP-RES-006 ADR-UDE-005 during early draft only; tightens at READY |
| **Evidence** | OP-RES-006A; submitted text ≠ effective text principle |

---

## Ratification Order *(updated OP-RES-006A)*

1. ADR-UDE-001, ADR-UDE-002 (foundation)  
2. ADR-UDE-003, ADR-UDE-004, ADR-UDE-005 (domain model)  
3. ADR-UDE-006, ADR-UDE-007 (localization + parties)  
4. ADR-UDE-008, ADR-UDE-009 (boundaries + immutability)  
5. ADR-UDE-010 (migration)  
6. **ADR-UDE-011–016 (authorship, intake, provenance — OP-RES-006A)**  

All **16** ADRs should be ratified in **UDE-000** before **UDE-001** begins.
