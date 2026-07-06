# PC-MANIFEST-001 — Position Cabinet Functional Manifest

## Status

**Draft (conceptual baseline)** — 2026-07-06

Final **conceptual configuration layer** for Position Cabinet before implementation planning. Defines how a [Cabinet Profile](./PC-PROFILE-001-position-cabinet-functional-profiles.md) becomes **concrete module-level functional configuration** for a specific Position Cabinet.

| Field | Value |
|-------|-------|
| Register ID | **PC-MANIFEST-001** |
| Closes | Conceptual chain: PC-MOD-001 → PC-PROFILE-001 → **PC-MANIFEST-001** |
| Normative baseline (unchanged) | ARCH-001, ARCHITECTURE_GOVERNANCE, ADR-050, ADR-051, ADR-053, ACCESS-001, ACCESS-002 |
| Governance complete | WP-B1…WP-B4 |
| Runtime effect | **None** |

---

## 1. Purpose and scope

### 1.1. Question answered

> **Given a Cabinet Profile and an org-unique Position, what is the resolved functional configuration of that Position Cabinet?**

| In scope | Out of scope |
|----------|--------------|
| Functional Manifest concept and elements | API, schema, migrations |
| Profile → manifest resolution rules | UI layout / component design |
| Product configuration vs security boundary | RBAC, OPS-030, Permission Domain ratification |
| Short profile examples (EXEC, QM, SPEC) | WP-B5, OPS-031, DEBT-DATA-001 repair |
| Implementation readiness gate | Accepted ADR amendment |

### 1.2. Layer model (complete chain)

```text
Position
    → Cabinet Profile          (PC-PROFILE-001 — which modules apply)
    → Module Composition       (enabled T1 / T2 / T3 set)
    → Functional Manifest      (this document — concrete configuration inside modules)
    → Position Cabinet         (Persistent Workspace; Permission Template gates actions)
```

**Invariant:** One Position ↔ one Position Cabinet (ADR-050). Manifest is **configuration of** the Cabinet, not a separate workspace.

---

## 2. Functional Manifest concept

**Functional Manifest** (RU: *функциональный манифест кабинета*) — the **resolved product configuration** for one Position Cabinet: which modules are enabled and **what functional slices** each module exposes (sections, groups, widgets, defaults).

| Property | Description |
|----------|-------------|
| **Product configuration** | Declares **what to show** in the workspace — not who may act |
| **Derived from Profile** | Profile selects modules; Manifest **instantiates** them |
| **Cabinet-scoped** | Bound to Position Cabinet identity; persists across occupant change (INV-B4-001) |
| **Versionable** | Manifest definition may evolve; changes audited in Cabinet History |
| **Consumable** | UI and subsystems read **resolved manifest** — they do not embed profile logic |

**Not:** RBAC, Permission Template, Platform Role, API contract, or database design.

---

## 3. Relationship to prior documents

| Document | Layer | Manifest relationship |
|----------|-------|----------------------|
| [PC-MOD-001](./PC-MOD-001-position-cabinet-functional-composition.md) | Module **catalog** | Manifest elements reference only registered module IDs (`tasks`, `kpi`, …) |
| [PC-PROFILE-001](./PC-PROFILE-001-position-cabinet-functional-profiles.md) | Profile **class** | Profile Required / Conditional / Excluded flags → Manifest **enables or omits** modules |
| **PC-MANIFEST-001** | **Configuration** | Expands enabled modules into sections, groups, widgets, landing, hints |
| Permission Template | Security **inside** modules | Template may **hide actions**; Manifest may **hide surfaces** — both required, neither substitutes the other |

**Resolution order (conceptual):**

```text
1. Resolve Cabinet Profile for Position Cabinet
2. Build Module Composition (enabled modules)
3. Apply Functional Manifest template for that Profile (+ optional org override)
4. Intersect with effective Permission Template / ACCESS policy → final user-visible surface
```

Step 4 grants **no new permissions** — it only removes unreachable UI; denied actions stay denied.

---

## 4. Manifest elements

Each element applies **only within enabled modules** from Module Composition.

| Element | Purpose |
|---------|---------|
| **Enabled modules** | Final on/off set after Profile + overrides (subset of PC-MOD-001 catalog) |
| **Module sections** | Logical subdivisions inside a module (e.g. Tasks: «Мои», «На согласовании», «Регулярные») |
| **Navigation entries** | Ordered eligible nav targets derived from enabled modules/sections — not hardcoded routes |
| **Dashboard widgets** | Which widget **types** appear on dashboards (KPI tiles, backlog summary, exceptions) |
| **Report groups** | Grouping of report types visible in Reports module |
| **Analytics packs** | Predefined analysis bundles (subtree, QM domain, personal scope) |
| **Document categories** | Function document library slices (SOP, regulatory, templates) |
| **Journal presets** | Journal types enabled for the function (shift log, audit trail, office log) |
| **KPI groups** | KPI families shown (compliance, throughput, quality, executive roll-up) |
| **Team scope hints** | Declarative scope hint for Team module (subtree, institution, QM functional) — **not** ACCESS-002 enforcement |
| **Notification groups** | Event categories subscribed by default for the Cabinet |
| **Default landing** | Which module/section opens first when entering the Cabinet |

Elements are **declarative labels and groupings** — not UI components, not permission codes.

---

## 5. Manifest rules

| ID | Rule |
|----|------|
| **MAN-R1** | Manifest is **product configuration**, not RBAC. It does not grant actions or data access. |
| **MAN-R2** | Manifest visibility **must not** be driven by hardcoded Platform Role or `users.role_id` checks (extends PC-PROFILE-001 MOD-VIS-001). |
| **MAN-R3** | Manifest **may restrict** what is shown; it **cannot grant** security access beyond Permission Template + ACCESS policy. |
| **MAN-R4** | Final user-visible surface = **resolved manifest** ∩ **effective permissions** ∩ **Cabinet access** (ADR-051). |
| **MAN-R5** | UI **must consume resolved manifest** — not encode `PC-PROF-*` logic or module matrices inline. |
| **MAN-R6** | Manifest changes on **Profile reassignment** or **manifest version** update — not on occupant change alone. |
| **MAN-R7** | T3 modules (`education`, `competency`) appear when enabled in manifest **and** occupant has Employee context; content remains Employee-owned (GLOSS-B4-001 §6). |
| **MAN-R8** | Vacant Cabinet may retain manifest; **visibility** of actionable surfaces during vacancy = Business Policy (ARCH-001 §4.7.2). |

---

## 6. Conceptual examples

Illustrative only — not registry IDs, not implementation payloads.

### 6.1. PC-PROF-EXEC (Executive / Director)

| Area | Manifest intent |
|------|-----------------|
| **Enabled modules** | tasks, kpi, dashboards, reports, history, notify; conditional team, analytics, docs, hr |
| **Default landing** | dashboards → «Institution status» |
| **Dashboard widgets** | Executive exception panel, approval queue summary, KPI roll-up |
| **KPI groups** | Institution targets, critical deviations |
| **Team scope hint** | Institution / assigned executive subtree |
| **Analytics packs** | Executive roll-up (read-oriented) |
| **Report groups** | Decisions pending, management submissions |
| **hr sections** | Kadrovye **decisions** queue (not HR processing) |
| **Excluded** | Clinical shift journals, HR enrollment execution surfaces |

### 6.2. PC-PROF-QM (Quality Management)

| Area | Manifest intent |
|------|-----------------|
| **Enabled modules** | tasks, kpi, dashboards, reports, history, analytics, docs, notify; conditional journals, team |
| **Default landing** | tasks → «QM assignments» |
| **Dashboard widgets** | Audit backlog, compliance KPI, open findings |
| **KPI groups** | Quality indicators, audit completion |
| **Journal presets** | Audit / inspection log |
| **Document categories** | Regulatory QM, methodology, checklists |
| **Analytics packs** | QM functional domain (not line subtree by default) |
| **Team scope hint** | QM task domain (see OQ-MAN-003 in PC-PROFILE-001) |
| **Excluded** | HR processing, line department management team |

### 6.3. PC-PROF-SPEC (Specialist / Executor)

| Area | Manifest intent |
|------|-----------------|
| **Enabled modules** | tasks, kpi, dashboards, reports, history, notify; conditional journals, docs; shell education, competency |
| **Default landing** | tasks → «My work» |
| **Dashboard widgets** | Personal backlog, upcoming deadlines, my KPI status |
| **KPI groups** | Position duty metrics |
| **Report groups** | My submissions |
| **Document categories** | Job instructions, local SOPs |
| **Excluded** | team, hr, deep analytics, executive widgets |

---

## 7. Compatibility

| Source | Status | Note |
|--------|--------|------|
| **WP-B4** | Compatible | Manifest bound to Cabinet; acting uses **target** Cabinet manifest; INV-B4-001…003 preserved |
| **GLOSS-B4-001** | Compatible | Position-owned config persists; T3 follows Person |
| **PC-MOD-001** | Compatible | Elements only reference catalog modules |
| **PC-PROFILE-001** | Compatible | Manifest templates keyed by `PC-PROF-*` |
| **ACCESS-001** | Compatible | Manifest hr surfaces align with PD classes; no permission grant |
| **ACCESS-002** | Compatible | Team/analytics scope hints defer to responsibilities — hints ≠ enforcement |
| **ADR-050** | Compatible | Manifest metadata on Cabinet; 1:1 Position ↔ Cabinet |
| **ADR-051** | Compatible | Resolver returns accessible Cabinet → manifest resolved per Cabinet |
| **ADR-053** | Compatible | Template binding orthogonal; manifest does not insert contour rules |
| **Architecture Freeze** | Compatible | No Accepted ADR amendment |

**Excluded tracks:** DEBT-DATA-001, OPS-031, WP-B5 — not referenced as dependencies.

---

## 8. Open questions

| ID | Question | Default stance | Blocks baseline? |
|----|----------|----------------|------------------|
| **OQ-MAN-001** | Where is manifest stored — on Cabinet, Profile template, or separate registry? | **Template per Profile** + **resolved copy per Cabinet** (conceptual) | No |
| **OQ-MAN-002** | Who manages manifest configuration — product ops, HR, org admin? | Org admin + product steward; Profile template changes centrally | No |
| **OQ-MAN-003** | Are org-specific manifest overrides allowed? | **Yes, audited overrides** on top of Profile template; no ad hoc UI hardcode | No |
| **OQ-MAN-004** | Manifest versioning — migrate in-flight Cabinets on template bump? | Version field; breaking changes require migration plan (implementation phase) | No |
| **OQ-MAN-005** | Migration from conceptual manifest to implementation registry? | See §9 — four-step plan; registry holds templates + resolved manifests | No |

---

## 9. Implementation readiness

This document **closes the conceptual chain**. Further work proceeds **only** through a small implementation plan — **no data repair**.

| Step | Deliverable | Scope |
|------|-------------|-------|
| **a) Profile registry** | Catalog of `PC-PROF-*` with module Required/Conditional/Excluded flags | PC-PROFILE-001 → registry |
| **b) Manifest registry** | Profile-keyed manifest **templates** + optional Cabinet-level overrides | PC-MANIFEST-001 §4 elements |
| **c) Resolver extension** | ADR-051 path returns accessible Cabinet + **resolved manifest** (after Template intersection) | No new access algorithm |
| **d) UI consumption** | Shell reads resolved manifest for nav, landing, module sections — **MOD-VIS-001 / MAN-R5 compliant** | Replaces role-hardcoded visibility |

**Explicitly out of implementation plan:** DEBT-DATA-001 repair, OPS-031, backfill, RBAC redesign, WP-B5.

**Suggested next artifact:** local verification / thin **Implementation Plan (PC-IMPL-001)** scoped to steps a–d only — not part of this document.

---

## 10. Conceptual chain closure

```text
PC-MOD-001     What modules exist
PC-PROFILE-001 Which modules each function class uses
PC-MANIFEST-001 How enabled modules are configured for a Cabinet
─────────────────────────────────────────────────────────
Implementation  Registry + resolver + UI consumption (§9)
```

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial draft — manifest concept, elements, rules, examples, readiness gate |
