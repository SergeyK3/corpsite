# UDE-001 — Shared Extension Points

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Matrix: [`data/UDE-001-extension-point-matrix.csv`](./data/UDE-001-extension-point-matrix.csv)

> Extension points enable specialization without modifying shared core. No registry implementation in UDE-001.

---

## Extension Point Model

```text
Shared Core
├── reads DocumentKind
├── resolves Policy bundle
└── dispatches to Registries
        ├── Personnel Specialization Module
        └── Operational Specialization Module
```

Diagram: [`diagrams/extension-point-model.svg`](./diagrams/extension-point-model.svg)

---

## Registry Catalog

| Registry | What extends | Owner | Specialization hook |
|---|---|---|---|
| **Document Kind Registry** | New document kinds | UDE platform | Register kind → policy bundle |
| **Scenario Registry** | Business blueprints | Per specialization | PO: optional; OO: 21 scenarios |
| **Item Type Registry** | Clause templates, semantic validators | Per specialization | PO: 5 types; OO: 14 families |
| **Renderer Registry** | Locale prose generation | Per specialization | Shared orchestration; specialized renderers |
| **Validation Registry** | Semantic, structural, locale rules | Per specialization + shared core | V* shared; BC* shared; kind hooks |
| **Projection Registry** | Execution handoff adapters | Per specialization | PO: employee_events; OO: task contour |
| **Lifecycle Registry** | Transition guards, void policies | Shared + per-kind hooks | PO: cancel/annul; OO: content confirmation gate |
| **Attachment Registry** | Attachment kinds and roles | Shared + per-kind | Commission roster, basis scan, etc. |
| **Party Resolution Registry** | Role→person resolution rules | Shared platform | Org structure adapter |
| **Localization Registry** | drafting_path policies, mandatory locales | Shared + per-kind | OO: submitted_intake defaults |

---

## Scenario Registry

| Aspect | Definition |
|---|---|
| **Extends** | Generation defaults: item sequence, obligation templates, managed objects |
| **Owner** | Specialization module |
| **Connects** | DocumentKind → scenario list → GenerationContract |
| **PO** | Item-first picker; scenario optional |
| **OO** | Scenario-first (P2); intake-first (P0) without scenario |
| **First use** | OO-IMP-003 (parallel); not UDE-002 |

---

## Item Type Registry

| Aspect | Definition |
|---|---|
| **Extends** | Semantic payload schema, renderer binding, validation rules |
| **Owner** | Specialization module |
| **Connects** | OrderItemContract → ItemType → Renderer + Validator |
| **PO** | HIRE, TRANSFER, TERMINATION, CONCURRENT_*, COMPOSITE |
| **OO** | DIRECT, CREATE_BODY, CONTROL, TRAVEL, etc. |
| **First use** | UDE-003 (editorial); OO-IMP-003 (generation) |

---

## Renderer Registry

| Aspect | Definition |
|---|---|
| **Extends** | Locale-specific prose templates per ItemType |
| **Owner** | Specialization module |
| **Connects** | GenerationContract → RendererContract |
| **Shared** | Orchestration, idempotency, fingerprint |
| **Forbidden** | Renderer owning semantic mutations |
| **First use** | UDE-003 (shared orchestration contract) |

---

## Validation Registry

| Aspect | Definition |
|---|---|
| **Extends** | Rule sets: semantic (V*), bilingual (BC*), lifecycle guards |
| **Owner** | Shared framework + specialization hooks |
| **Connects** | ValidationContract → ValidationResult |
| **Shared rules** | BC001–BC025 architecture; ready_gate pattern |
| **First use** | UDE-005 |

---

## Projection Registry

| Aspect | Definition |
|---|---|
| **Extends** | ExecutionProjectionDescriptor emission per DocumentKind |
| **Owner** | Specialization adapter |
| **Connects** | REGISTERED document → downstream contour |
| **PO** | apply_service → employee_events |
| **OO** | obligation → task engine (future) |
| **First use** | OO-IMP-005; PO already has adapter |

---

## Lifecycle Registry

| Aspect | Definition |
|---|---|
| **Extends** | Per-kind transition guards, void_kind handling, confirmation gates |
| **Owner** | Shared LifecycleContract + kind policies |
| **Connects** | LifecycleContract → DocumentLifecycleState |
| **OO hook** | Content confirmation before READY |
| **First use** | UDE-003 (editorial locks); OO-IMP-004 |

---

## Attachment Registry

| Aspect | Definition |
|---|---|
| **Extends** | AttachmentKind definitions and obligation linkage rules |
| **Owner** | Shared + specialization |
| **Connects** | AttachmentContract → AttachmentReference |
| **First use** | OO-IMP-001 (intake attachments) |

---

## Party Resolution Registry

| Aspect | Definition |
|---|---|
| **Extends** | Resolution policies for PartyReference kinds |
| **Owner** | Shared platform (org context adapter) |
| **Connects** | PartyReference → ResolvedPartySnapshot |
| **Forbidden** | Mixing with access permissions |
| **First use** | UDE-003 |

---

## Localization Registry

| Aspect | Definition |
|---|---|
| **Extends** | Mandatory locales, drafting_path defaults, staleness policies |
| **Owner** | Shared LocalizationContract + kind policy |
| **Connects** | DraftingPath → LocalizationPolicy |
| **OO default** | submitted_intake, ru mandatory, kk mandatory at READY |
| **First use** | UDE-002, UDE-003 |

---

## Document Kind Registry

| Aspect | Definition |
|---|---|
| **Extends** | New document specializations |
| **Owner** | UDE platform |
| **Connects** | DocumentKind → full policy bundle (all registries) |
| **Current kinds** | PersonnelOrder, OperationalOrder |
| **Future** | Protocol, CommissionAct, Directive |
| **First use** | UDE-001 (conceptual); UDE-003 (editorial core wiring) |

---

## Priority Order for Implementation

| Priority | Extension point | WP |
|---|---|---|
| 1 | Localization Registry | UDE-002, UDE-003 |
| 2 | Document Kind Registry | UDE-003 |
| 3 | Lifecycle Registry (confirmation hook) | UDE-002, OO-IMP-002 |
| 4 | Attachment Registry | OO-IMP-001 |
| 5 | Party Resolution Registry | UDE-003 |
| 6 | Item Type Registry | OO-IMP-003 |
| 7 | Renderer Registry | OO-IMP-003 |
| 8 | Scenario Registry | OO-IMP-003 |
| 9 | Validation Registry | UDE-005 |
| 10 | Projection Registry | OO-IMP-005 |

---

## Registries NOT Needed at MVP

| Registry | Reason deferred |
|---|---|
| Universal block_kind registry | PO-EDIT-001 block kinds sufficient; extract in UDE-006 |
| Cross-kind scenario sharing | No evidence of shared scenarios between PO/OO |
| External party resolution | Rare in corpus; free-text fallback |

---

*Machine-readable matrix: [`data/UDE-001-extension-point-matrix.csv`](./data/UDE-001-extension-point-matrix.csv)*
