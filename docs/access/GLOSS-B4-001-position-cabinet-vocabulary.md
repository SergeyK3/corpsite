# GLOSS-B4-001 — Position Cabinet Governance Vocabulary

## Status

**Active (governance glossary)** — 2026-07-05

Authoritative **Tier G terminology** for WP-B4 and downstream work packages. Consolidates vocabulary from [WP-B4-PROBLEM-SPACE-REVIEW.md](./WP-B4-PROBLEM-SPACE-REVIEW.md), [WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md), and **Accepted** architecture (ARCH-001, ADR-050, ADR-051, ADR-036). **No new architectural decisions.** **No Accepted ADR amendment.** **No runtime effect.**

| Field | Value |
|-------|-------|
| Register ID | **GLOSS-B4-001** |
| Work package | WP-B4 — Position Cabinet contour binding prerequisites |
| Supersedes | Ad hoc re-definition of terms in individual WP briefs |
| Invariants referenced | **INV-B4-001**, **INV-B4-002**, **INV-B4-003** ([Problem Space Review §3](./WP-B4-PROBLEM-SPACE-REVIEW.md#3-architectural-invariant-recorded)) |
| Normative sources (unchanged) | ARCH-001 §3–§4; ADR-050; ADR-051; ADR-036; ACCESS-001 P1–P2 |

**Usage rule:** Subsequent WP-B*, WP-B7, WP-X*, and implementation-phase documents **SHOULD cite this register** instead of redefining these terms. Citation does not authorize implementation.

---

## 1. Position Cabinet

| Field | Content |
|-------|---------|
| **Term (EN)** | Position Cabinet |
| **Term (RU)** | Кабинет должности |
| **Definition** | Long-lived **digital representation of an org-unique Position** (штатная единица): operational container for position-bound work, history, configuration, and Permission Template. **1:1** with Position (ADR-050). |
| **Owner** | **Organization / Position** — not Person, not Employee, not Platform User (ARCH-001 §4.1, §4.3; ADR-050). |
| **Lifecycle** | Created **together with** Position; persists through vacancy, leave, and occupant change; ends **only** when Position is abolished / liquidated (ARCH-001 §4.2). |
| **On Employee change** | **Cabinet entity and all position-owned contents persist unchanged.** Only **access** to the Cabinet opens or closes for Persons via Employment / acting (ARCH-001 §4.6). |
| **INV-B4 link** | **INV-B4-001** — Cabinet identity stable across owner change; **INV-B4-003** — Cabinet is the **duty shell** of the position, not of a temporary executor. |

---

## 2. Persistent Workspace

| Field | Content |
|-------|---------|
| **Term (EN)** | Persistent Workspace (of Position) |
| **Term (RU)** | Долговременное рабочее пространство должности |
| **Definition** | **Governance characterisation** of Position Cabinet: the **durable operational locus** where position-bound tasks, results, KPI, dashboards, function documents/knowledge, journals, and Permission Template **accumulate and endure** across occupants. **Synonymous with Position Cabinet** at domain level — not a separate entity (ADR-050). |
| **Owner** | Same as **Position Cabinet** — **Position / organization**. |
| **Lifecycle** | Same as **Position Cabinet** — co-extensive with Position lifecycle. |
| **On Employee change** | **Full workspace state persists** (backlog, history, KPI, dashboards, function artefacts, Template configuration). New occupant **inherits access** to existing workspace; nothing migrates to or from Employee record as «new workspace». |
| **INV-B4 link** | **INV-B4-003** — workspace belongs to the **position**, not the temporary executor; **INV-B4-001** — workspace does not transfer when only acting or absence events occur. |

**Note:** Distinguish from post-login **UI shell** («личный кабинет») — presentation aggregation, not domain ownership (ARCH-001 §8; ADR-007 legacy UX term).

---

## 3. Cabinet Owner

| Field | Content |
|-------|---------|
| **Term (EN)** | Cabinet Owner / Position Occupant |
| **Term (RU)** | Владелец кабинета / постоянный занимающий должность |
| **Definition** | **Person** holding **permanent Position Occupancy** via active **Employment** (Занятие должности) on the Position linked to the Cabinet. Identifies **who permanently holds the position** — not who temporarily acts in it. |
| **Owner** | **Not applicable** — Cabinet Owner is a **role relation** (Person ↔ Position via Employment), not an entity owner. The **Cabinet** remains owned by Position. |
| **Lifecycle** | Begins with Employment start on Position; ends with Employment termination, transfer off Position, or Position abolition. One sequential chain of Owners per Position over time; at most one active Owner per Position at a given time (vacancy = no Owner, Cabinet still exists). |
| **On Employee change** | **Prior Person ceases** to be Cabinet Owner; **successor Person becomes** Cabinet Owner on new permanent Employment. **Cabinet and position-owned data unchanged** — only the identity of the Owner relation changes (INV-B4-001). |
| **INV-B4 link** | **INV-B4-001** — Owner changes **only** on permanent occupancy HR events; **INV-B4-002** — Acting Assignee is **not** Cabinet Owner; **INV-B4-003** — Owner holds the duty; acting Person does not replace Owner. |

---

## 4. Acting Assignment

| Field | Content |
|-------|---------|
| **Term (EN)** | Acting Assignment / Temporary Executor (Acting Assignee) |
| **Term (RU)** | Временное исполнение обязанностей / исполнитель по и.о. |
| **Definition** | **Time-bounded overlay** granting a Person **access** to another Position’s Cabinet **without** closing primary Employment and **without** transferring Cabinet Owner status (ADR-036 `ACTING_ASSIGNMENT`; ADR-051 acting overlay). |
| **Owner** | **Not applicable** — overlay is an **access grant period**, not an ownership relation. Target **Cabinet** remains Position-owned. |
| **Lifecycle** | Defined by acting period (`valid_from` / `valid_to` or equivalent HR event boundaries). Auto-expires at period end; primary Employment of acting Person **unchanged** (ADR-036, ADR-051). |
| **On Employee change** | **Acting overlay unaffected** by unrelated Employee turnover on **other** positions. If **Cabinet Owner** changes on target Position (permanent Employment event), acting rules apply to **new** Owner/access picture — acting **still does not** transfer ownership. Acting Person **never takes** employee-owned data of permanent Owner as their own. **Position-owned history in Cabinet persists**; acting Person does not carry it away (rules A3–A4, Problem Space Review §6). |
| **INV-B4 link** | **INV-B4-002** — core rule: acting = access, not ownership; **INV-B4-001** — acting events **excluded** from owner-change set; **INV-B4-003** — temporary executor uses duty shell, does not become it. |

---

## 5. Position-owned Data

| Field | Content |
|-------|---------|
| **Term (EN)** | Position-owned Data |
| **Term (RU)** | Данные, принадлежащие должности (кабинету) |
| **Definition** | Operational artefacts whose **authoritative binding** is the **Position Cabinet** (persistent workspace), not Person or Employee. Includes tasks and backlog, regular task templates/instances (cabinet-scoped), submitted reports, KPI aggregates, dashboards, function statistics, function/regulatory documents, and future position-scoped Knowledge — per ARCH-001 §4.4–§4.5. |
| **Owner** | **Position Cabinet** (equivalently: **Position** at domain level). |
| **Lifecycle** | Co-extensive with Cabinet; individual records have their own business lifecycle but **remain cabinet-scoped** unless Position is abolished. |
| **On Employee change** | **Fully preserved in Cabinet.** No migration to departing Employee; no reset for incoming Employee. Audit may record which Person acted **in cabinet context** (ARCH-001 §4.5). |
| **INV-B4 link** | **INV-B4-001** — data survives owner change inside same Cabinet; **INV-B4-002** — acting must not reset or migrate position-owned history; **INV-B4-003** — data belongs to duty shell. |

**UI carcase examples (directional only):** `/tasks`, `/dashboards`; reporting history — see `corpsite-ui/lib/positionCabinetNav.ts` ownership hints. **Not implementation scope.**

---

## 6. Employee-owned Data

| Field | Content |
|-------|---------|
| **Term (EN)** | Employee-owned Data |
| **Term (RU)** | Данные, принадлежащие работнику |
| **Definition** | Personal and HR artefacts bound to **Person / Employee**, not to Position Cabinet identity. Includes education profiles, courses, testing, psychological assessments, individual personnel HR history, and Personal File contents (ARCH-001 §4.5; ADR-047 boundary). |
| **Owner** | **Person** (operational shell: **Employee** where used in as-is/contours). |
| **Lifecycle** | Follows Person / Employment career — may span multiple Positions and Cabinets; **not** recreated when Person occupies a new Cabinet. |
| **On Employee change** | When **Cabinet Owner** changes (new Person on Position): **incoming Owner’s** employee-owned data is **their** Person/Employee record — **not** copied from predecessor. **Outgoing Owner retains** their employee-owned data. Acting Assignee **must not** inherit or replace permanent Owner’s employee-owned profile (INV-B4-002, A3). |
| **INV-B4 link** | **INV-B4-002** — acting does not rebind employee-owned data; **INV-B4-001** — employee-owned data **does not define** Cabinet Owner change (ownership split orthogonal to occupancy events). **INV-B4-003** — employee-owned data is **outside** the duty shell’s identity. |

**UI carcase example (directional only):** `/education` — employee-owned section shown in Position Cabinet shell. **Not implementation scope.**

---

## 7. Term relationships (reference)

```text
Position (org-unique)
    │
    ├── 1:1 ──► Position Cabinet  ≡  Persistent Workspace (characterisation)
    │                 │
    │                 ├── Permission Template (configuration)
    │                 └── Position-owned Data
    │
    ├── Employment ──► Cabinet Owner (Person, permanent)
    │
    └── Acting Assignment ──► Acting Assignee (Person, temporary access overlay)

Person / Employee ──► Employee-owned Data  (orthogonal to Cabinet identity)
```

---

## 8. Explicit exclusions

| Exclusion | Detail |
|-----------|--------|
| **New domain entity** | Persistent Workspace is **not** a separate table or ADR entity — glossary label for Position Cabinet |
| **New OQ** | No open questions opened by this register; **OQ-B4-001** remains sole WP-B4 architectural backlog item |
| **ADR amendment** | Definitions derive from Accepted sources only |
| **Implementation mandate** | Glossary does not authorize API, schema, RBAC, or UI work |

---

## 9. Downstream citation

| Consumer | Usage |
|----------|-------|
| **WP-B4 governance document** | Preamble terminology — [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) |
| **WP-B4 ratification package** | Review Board assembly — [WP-B4-RATIFICATION-PACKAGE.md](./WP-B4-RATIFICATION-PACKAGE.md) |
| **WP-B7** | Contour binding discourse |
| **WP-B8** | Policy debt discussions — vocabulary only |
| **Implementation WPs / ADRs** | SHOULD cite GLOSS-B4-001 for consistent terms |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-05 | 1.0 | Initial register — six terms; INV-B4 linkage; derived from WP-B4 Problem Space + Conceptual Review |
| 2026-07-06 | 1.1 | Traceability — link to main WP-B4 governance document |
| 2026-07-06 | 1.2 | Traceability — link to WP-B4-RATIFICATION-PACKAGE |
