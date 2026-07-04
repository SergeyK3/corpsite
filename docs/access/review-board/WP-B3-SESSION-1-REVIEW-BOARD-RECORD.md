# WP-B3 Review Board Session 1 — Record

## Executive HR Decision Capability (PD-5.1)

## Status

**Session complete** — 2026-07-04

Formal governance record for **WP-B3 Review Board Session 1**. **No runtime effect.** **No implementation authority.**

| Field | Value |
|-------|-------|
| Session | WP-B3 Review Board Session 1 |
| Package | WP-B3 — Executive HR Decision Model / Capability |
| Brief | [WP-B3-REVIEW-BOARD-BRIEF.md](./WP-B3-REVIEW-BOARD-BRIEF.md) |
| Approval authority | Executive sponsor + HR policy owner + ops lead |
| Attestation | **Pending signature** |
| Runtime effect | **None** |

---

## Session outcome (summary)

| Field | Value |
|-------|-------|
| **Overall outcome** | **Ratified with Policy Debt** |
| **Date** | 2026-07-04 |
| **Positive class** | Organizational permission class **Кадровое решение** (PD-5.1) — management decision authority changing position assignment state within defined calendar boundaries; executive **approval** authority for кадровые решения on Position Cabinet baseline — **ratified** per ACCESS-001 §5.1 meaning and domain invariants EHD-INV-1…5 |
| **DEBT-B2-001** | **Closed** — positive class defined at governance layer |
| **DEBT-B1-001** | **Continues** — transitional `access_roles.code` mapping for PD-5.1 deferred to **WP-B8** |
| **WP-B3 Session 2** | **Not required** |
| **Formal WP-B3 closure** | **Pending** — attestation signatures (executive sponsor + HR policy owner + ops lead) |

**Explicit session boundaries (recorded):**

- Does **not** approve ACCESS-001 §7 rows or set `policy_status=approved`.
- Does **not** promote ACCESS-001 to **Approved** (WP-X2).
- Does **not** authorize OPS-030, ADR-053 AC3 closure, or Phase 2.6b.
- Does **not** define transitional `access_roles.code`, contour binding, or runtime behaviour.
- Implementation gates **unchanged**.

---

## Question records

---

### Q-A1 — Executive HR Decision authority definition

#### 1. Question

What constitutes **Executive HR Decision authority** in organizational terms — distinct from HR document preparation (PD-5.2), enrollment execution, HR oversight visibility (PD-5.3), and management responsibilities (ACCESS-002)?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ARCH-001 | Permissions follow Employment → Position Cabinet; not User-centric |
| ADR-050 | Permission Template inside Position Cabinet (1:1) |
| ADR-051 | Template load → expand → union; enforcement cutover not in Phase 2.6 |
| ADR-053 | Binding is Cabinet configuration; transitional `access_roles` namespace |

#### 3. Governance considerations

WP-B1 accepted domain `PD-5.1` with organizational meaning already stated in ACCESS-001 §5.1. WP-B3 must ratify that meaning as the **positive permission class** — not rediscover the domain. The class governs **approval** authority on Cabinet baseline, separate from HR **execution** (PD-5.2), HR **oversight visibility** (PD-5.3), and **management responsibilities** (ACCESS-002). Conflation at executive contours is the primary governance risk (O2, GR-B3-07).

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §5.1 | Meaning: approve hire, transfer, dismiss, appoint acting duties |
| ACCESS-001 §5.1 | Not the same as HR preparation, enrollment, sysadmin, management visibility (ACCESS-002), line boundary (§5.4) |
| ACCESS-002 | Management responsibilities orthogonal — not substitute for permission class |
| WP-B1 | `PD-5.1` domain taxonomy ratified with Policy Debt |
| WP-B2 | P5, P6, P7, P8, P12 ratified — prohibitions and orthogonality fixed |

#### 5. Board decision

**Accepted**

#### 6. Rationale

The organization accepts **Executive HR Decision authority** as the organizational permission class for **executive approval** of кадровые решения — the right and duty to **approve** hire, transfer, dismiss, and acting-duty appointments on Position Cabinet baseline. An HR Decision is a **management decision** that **changes the state of a position assignment** within **defined calendar boundaries** (EHD-INV-1). This is distinct from кадровое **оформление** (PD-5.2), HR oversight visibility (PD-5.3), and ACCESS-002 management responsibilities. Definition aligns with ACCESS-001 §5.1 and WP-B1 `PD-5.1` review sheet without extending scope.

#### 7. Downstream consequence

**WP-B4**, **WP-B7** — may reference ratified class boundary when assigning or dispositioning contours; no row approval by this decision.

---

### Q-A2 — Решение vs оформление action boundary

#### 1. Question

Which organizational actions fall within кадровое **решение** (approve hire, transfer, dismiss, appoint acting duties) versus кадровое **оформление** (PD-5.2)?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-053 §2.2 | `HR_ENROLLMENT_MANAGER` exists in `access_roles` catalog — organizational meaning is governance-owned, not ADR-defined |
| ADR-051 | Resolver expands Template permissions; does not assign organizational class semantics |
| ADR-050 | Cabinet is binding anchor for permission policy |

#### 3. Governance considerations

ACCESS-001 explicitly separates decision from execution (§5.1 vs §5.2; P6, P7). WP-B2 ratified P6 (`HR_ENROLLMENT_MANAGER` = оформление, not решение). Board must affirm action boundary so executive approval is not absorbed into HR processing class. This boundary is prerequisite for coherent WP-B4 (HR head) and WP-B7 (Director) work.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §5.1 | Решение actions: approve hire, transfer, dismiss, appoint acting duties |
| ACCESS-001 §5.2 | Оформление: prepare documents, perform enrollment, execute кадровые процессы |
| WP-B2 P6 | `HR_ENROLLMENT_MANAGER` semantic = оформление only |
| WP-B2 P7 | No substitute codes for решение |
| WP-B1 PD-5.2 | Кадровое оформление domain ratified |

#### 5. Board decision

**Accepted**

#### 6. Rationale

**Кадровое решение** covers organizational **approval** decisions: hire, transfer, dismiss, appoint acting duties. **Кадровое оформление** (PD-5.2) covers HR department **processing**: prepare, record, execute, and document HR Decisions **authored by the Director Position Cabinet** — these activities are **not** HR Decisions (EHD-INV-4). The HR department is never the author of an HR Decision. Approval precedes or authorizes execution; execution does not substitute for approval. Boundary matches ACCESS-001 §5.1/§5.2 and ratified P6/P7.

#### 7. Downstream consequence

**WP-B4** — HR head contour `(73, 86)` remains PD-5.2 scope only; **WP-B7** — Director cannot receive `HR_ENROLLMENT_MANAGER` for PD-5.1.

---

### Q-A3 — Positive organizational permission class

#### 1. Question

What is the **positive organizational permission class** for `PD-5.1` — the minimum governance definition required to disposition DEBT-B1-001 and DEBT-B2-001?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-053 | Transitional binding via `access_roles`; class-to-code mapping is organizational policy consumed at implementation |
| ADR-053 §3.4 | Binding not derived from title or occupant |
| ADR-050 | Class policy attaches to Cabinet Permission Template baseline |

#### 3. Governance considerations

The missing capability identified in Problem Space Review is **positive class definition**, not catalog engineering. Minimum governance definition is organizational vocabulary: what PD-5.1 **is** as a permission class. Transitional `access_roles.code` is a separate policy debt item (DEBT-B1-001) explicitly separable from class definition per WP-B3 scope and ACCESS-RATIFICATION-PROGRAM WP-B8 inputs. Board may close DEBT-B2-001 (principles layer) while DEBT-B1-001 (code mapping) continues.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §5.1 | Separate decision/approval class required; not modeled in Reviewed text — WP-B3 must ratify |
| ACCESS-001 §5.1 | `HR_ENROLLMENT_MANAGER` must not represent this class |
| WP-B1 DEBT-B1-001 | Code not defined — resolution WP-B3 |
| WP-B2 DEBT-B2-001 | Positive class not defined — resolution WP-B3 |
| WP-B2 P7 | Separate class required — negative rule ratified |

#### 5. Board decision

**Accepted**

#### 6. Rationale

The **positive organizational permission class** for `PD-5.1` is ratified as:

> **Кадровое решение (Executive HR Decision)** — the organizational permission class for **management decisions** that change position assignment state within defined calendar boundaries, granting executive **approval authority** for кадровые решения (hire, transfer, dismiss, appoint acting duties) on Position Cabinet Permission Template baseline, per ACCESS-001 §5.1. HR Decision existence is independent of recording medium (EHD-INV-2). Each HR Decision has exactly one author — the subject occupying the Director Position Cabinet; the HR department is never the author (EHD-INV-3).

This closes **DEBT-B2-001**. **DEBT-B1-001** continues: transitional `access_roles.code` mapping for this class is **not** ratified in Session 1 — deferred to **WP-B8**.

#### 7. Downstream consequence

**DEBT-B2-001** → closed. **DEBT-B1-001** → continues → **WP-B8**. **WP-B7** — class exists for Director disposition policy; row `approved` still requires code agreement per §5.5 and WP-B7 session.

---

### Q-B1 — Cabinet contour qualification

#### 1. Question

How is qualification for this class expressed on a **Position Cabinet contour** without relying on job title alone — consistent with P1 and Architecture Baseline principle 5?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ARCH-001 | Authority follows position occupancy |
| ADR-050 | Position is org-unique staffing unit; Cabinet is its digital representation |
| ADR-053 §3.4 | Forbidden: title inference, occupant inference, grant-copy for baseline binding |
| ADR-051 | Evaluation uses Cabinet Template configuration |

#### 3. Governance considerations

P1 (ratified) assigns permissions to **Position Cabinet**, not User or title string. Qualification must be expressed as: identified org-unique contour `(client_scope_id, org_unit_id, catalog_position_id)` receives PD-5.1 class **when organizational policy assigns that class to that contour** — following approved matrix disposition in WP-B7, not automatic assignment from catalog position name «Директор». Title describes typical holder archetype in §5.1; binding policy uses contour identity per ADR-053.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| WP-B2 P1 | Permission assigned to Position Cabinet |
| WP-B2 P2 | Occupants not source of truth for baseline |
| WP-B2 P5 | Director title ≠ automatic code assignment |
| ACCESS-001 §7 | Director contour `(1, 78, 62)` identified by contour tuple — not title alone |
| WP-B1 PD-5.1 | Typical holders Director/Acting Director — archetype only |

#### 5. Board decision

**Accepted**

#### 6. Rationale

Qualification for PD-5.1 is expressed by **organizational policy assignment of the class to a specific Position Cabinet contour** — org-unique `(client_scope_id, org_unit_id, catalog_position_id)` — when approved through governance (WP-B7), not by catalog position title label alone. **Authorship** of HR Decisions attaches to the subject **occupying the Director Position Cabinet** — exactly one author per HR Decision; the HR department is never the author (EHD-INV-3). Occupancy of the Director Cabinet contour is the operational precondition for authorship and authority; class assignment is a **policy decision on the contour**, consistent with P1 and Architecture Baseline principle 5.

#### 7. Downstream consequence

**WP-B7** — contour-level class assignment and `policy_status`; **WP-X1** — shared executive contours require cross-layer alignment before row approval.

---

### Q-B2 — Acting Director relationship

#### 1. Question

How does **Acting Director** (исполняющий обязанности) relate to the Executive HR Decision class?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ARCH-001 | Authority follows position occupancy **including acting** |
| ADR-050 | Acting is occupancy mode on Position / Cabinet model |
| ADR-051 | Acting overlay addressed in separate cutover program (C2) — not WP-B3 |

#### 3. Governance considerations

ACCESS-001 §5.1 lists Acting Director as typical holder. Governance question is whether acting occupancy uses **same PD-5.1 class** or requires separate class. Separate domain would multiply policy debt; same class with acting occupancy follows ARCH-001 acting principle. Acting mechanics in resolver are implementation (C2) — WP-B3 defines organizational class only.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §5.1 | Typical holders: Director / Acting Director |
| WP-B2 P5 | Acting Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` by title |
| WP-B2 P7 | Separate решение class required if modeled — applies to Acting Director archetype |
| WP-B1 PD-5.1 | Executive approval scope includes appoint acting duties |

#### 5. Board decision

**Accepted**

#### 6. Rationale

**Acting Director** occupying an executive Position Cabinet with assigned PD-5.1 class holds the **same organizational permission class** — кадровое решение — when performing executive кадровые approval duties. Acting is an **occupancy mode**, not a separate permission domain. **Transfer of the Director Position Cabinet** to an Acting Director during a valid delegation period **automatically transfers authorship** of HR Decisions to the Acting Director for the duration of that delegation — an organizational consequence of **Cabinet ownership**, not job title inference (EHD-INV-5). Appoint acting duties remains within решение scope; executing оформление for acting appointment remains PD-5.2.

#### 7. Downstream consequence

**WP-B7** — acting executive contours dispositioned under same class policy; **C2** (implementation program) — acting resolver overlay separate from this governance decision.

---

### Q-C1 — Separation from ACCESS-002

#### 1. Question

How is the permission class **separated from ACCESS-002** executive management responsibilities (organizational information, responsibility for results, subtree scope)?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-050 | Cabinet model shared; policy layers are separate documents |
| ADR-051 | Access resolver computes permissions; management scope is separate consumer program |
| ADR-053 | Permission Template binding does not encode management responsibilities |

#### 3. Governance considerations

P12 ratified: ACCESS-001 and ACCESS-002 are orthogonal. WP-B1 PD-5.1 sheet stated executive ACCESS-002 responsibilities do not substitute for PD-5.1. Board must affirm so WP-B3 ratification is not misread as ACCESS-002 Track A progress or as substituting management remit for HR decision permission.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §3 | ACCESS-002 owns management responsibilities; ACCESS-001 owns permission domains |
| ACCESS-002 | Reviewed — not Approved; does not gate WP-B3 |
| WP-B2 P12 | Orthogonal layers — ratified |
| WP-B1 PD-5.1 | Ratifying domain does not ratify ACCESS-002 responsibilities on Director contour |

#### 5. Board decision

**Accepted**

#### 6. Rationale

PD-5.1 **Кадровое решение** is an ACCESS-001 **organizational permission class** only. It does **not** approve, assign, or substitute ACCESS-002 executive management responsibilities (organizational information, responsibility for results, subtree scope). Both layers may apply to the same Cabinet contour independently after respective ratification tracks. P12 governs.

#### 7. Downstream consequence

**Track A (WP-A*)** — ACCESS-002 ratification proceeds independently; **WP-X1** — cross-layer boundary before shared-contour binding approvals.

---

### Q-C2 — ADR-045 executive read scope

#### 1. Question

How does **ADR-045 executive read scope** relate to PD-5.1 — complementary mechanism versus substitute for the permission class?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-045 | Personnel / HR processes split — runtime visibility and process contours |
| ADR-053 | Runtime mechanisms do not replace organizational policy owner for permission class |
| ADR-051 | Resolver may consume multiple inputs at enforcement — governance ownership separate |

#### 3. Governance considerations

WP-B1 explicitly excluded ADR-045 executive read scope as substitute for PD-5.1. ADR-045 addresses runtime read/process visibility; PD-5.1 addresses organizational **approval permission** on Cabinet baseline. Board affirms complementary relationship to prevent ADR-045 substitution (GR-B3-08).

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| ACCESS-001 §5.1 | Not the same as ADR-045 executive read scope as substitute |
| WP-B2 P5 | ADR-045 executive read scope separate from sysadmin, HR processing, ACCESS-002 |
| WP-B1 PD-5.1 | ADR-045 executive read scope **not** substitute for this domain |

#### 5. Board decision

**Accepted**

#### 6. Rationale

ADR-045 executive read scope is a **complementary runtime mechanism** for process visibility — **not** a substitute for the PD-5.1 organizational permission class. Organizational approval authority for кадровые решения is owned by ACCESS-001 §5.1 / PD-5.1. ADR-045 does not satisfy P7's requirement for a separate решение class on Cabinet baseline.

#### 7. Downstream consequence

**WP-B8** — transitional/runtime alignment questions remain separate; **WP-B7** — no ADR-045-based baseline binding for PD-5.1.

---

### Q-D1 — Policy debt disposition

#### 1. Question

What is the **governance disposition** of DEBT-B1-001 and DEBT-B2-001 — closed with a defined class, or continued with explicit rationale, owner, and implications for Director contour binding?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-053 §2.2 | Not every domain has dedicated `access_roles.code` in transitional catalog |
| ADR-053 AC3 | Ops mapping annex requires approved organizational policy — code mapping may follow class |
| ADR-053 §3.4 | Class policy precedes engineering binding |

#### 3. Governance considerations

DEBT-B1-001 and DEBT-B2-001 describe one gap at two layers. Coherent disposition: close principles/taxonomy debt (positive class defined); continue code-mapping debt until WP-B8. Director contour `(1, 78, 62)` cannot move to `approved` until class **and** matching code agreed per §5.5 — class now defined; code remains open — Director binding path blocked at code step, not class step.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| WP-B1 DEBT-B1-001 | Transitional code not defined — WP-B3 resolution |
| WP-B2 DEBT-B2-001 | Positive class not defined — WP-B3 resolution |
| ACCESS-001 §5.5 | Class clarification precedes OPS-030 insert |
| ACCESS-RATIFICATION-PROGRAM WP-B3 | May record policy debt for code — Phase 2.6b MVP without Director still valid |

#### 5. Board decision

**Accepted**

#### 6. Rationale

| Debt | Disposition | Detail |
|------|-------------|--------|
| **DEBT-B2-001** | **Closed** | Positive organizational permission class for PD-5.1 ratified (Q-A3) |
| **DEBT-B1-001** | **Continues** | Transitional `access_roles.code` for PD-5.1 **not** ratified — deferred to **WP-B8**; owner pending assignment (HR policy owner + ops lead + architecture lead) |

**Director contour implication:** `(1, 78, 62)` remains **rejected** for substitute codes; may not become `approved` until WP-B8/WP-B7 resolve code mapping — class governance prerequisite now satisfied.

#### 7. Downstream consequence

**WP-B8** — DEBT-B1-001 code mapping; **WP-B7** — Director row disposition; **WP-B4** — may proceed for HR-service scope independent of DEBT-B1-001.

---

### Q-D2 — Session boundary without implementation

#### 1. Question

Is it acceptable to record a WP-B3 outcome **without** §7 row approval, OPS-030 authorization, ACCESS-001 **Approved** status, or runtime effect?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-053 AC2 | Phase 2.6 read-path / shadow — no enforcement flip from policy ratification |
| ADR-053 AC3 | Pending — separate gate |
| ADR-051 §10 | Enforcement cutover separate program |

#### 3. Governance considerations

WP-B1 and WP-B2 established precedent: substantive ratification without implementation unlock. Same must hold for WP-B3 or governance leaks into Tier B (GR-B3-02). ACCESS-RATIFICATION-PROGRAM explicitly separates work-package ratification from WP-X2 and OPS-030.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| WP-B1 | No §7 approvals, no OPS-030, no runtime effect |
| WP-B2 | Implementation gates unchanged after ratification |
| ACCESS-RATIFICATION-PROGRAM | Ratification ≠ execution |
| WP-B3 initiation §3 | Governance only — no implementation |

#### 5. Board decision

**Accepted**

#### 6. Rationale

WP-B3 Session 1 outcome is valid **without** §7 row approval, OPS-030 authorization, ACCESS-001 **Approved** promotion, or runtime effect. Governance class ratification is intentionally upstream of document promotion (WP-X2), contour disposition (WP-B7), and execution (OPS-030 / AC3).

#### 7. Downstream consequence

Implementation gates **unchanged** — ACCESS-001 **Reviewed**; OPS-030 **Blocked**; AC3 **Pending**; legacy enforcement authoritative.

---

### Q-D3 — Ratification record wording

#### 1. Question

What ratification record wording prevents misread as contour approval or implementation authorization?

#### 2. Architectural facts

| Source | Fact |
|--------|------|
| ADR-053 | Contour rules in `permission_template_contour_rule` — ops execution artefact |
| ADR-050 | Cabinet configuration separate from governance record |

#### 3. Governance considerations

WP-B2 ratification record pattern applies: explicit negative statements on what ratification does **not** authorize. Required to mitigate R2, R5, GR-B3-02 for executive contour where stakeholder pressure for Director binding is highest.

#### 4. Constraints

| Source | Constraint |
|--------|------------|
| WP-B2 §11 | Model wording: does not approve §7 rows, OPS-030, Approved status |
| WP-B3 initiation SC-6 | Same explicit boundary required |
| ACCESS-RATIFICATION-PROGRAM P11 | Engineering does not substitute for WP approval |

#### 5. Board decision

**Accepted**

#### 6. Rationale

Ratification record **must include**:

> This WP-B3 ratification accepts the organizational permission class **Кадровое решение (PD-5.1)** as defined in Session 1. It **does not** approve ACCESS-001 §7 rows, promote ACCESS-001 to **Approved**, authorize OPS-030 or Phase 2.6b, close ADR-053 AC3, insert contour rules, assign transitional `access_roles.code`, or change runtime enforcement. DEBT-B1-001 continues for code mapping (WP-B8).

#### 7. Downstream consequence

**WP-B3 closure record** — wording template for attestation signatures; **OPS-030** — remains blocked.

---

## Final session summary

### Questions accepted

| # | Question |
|---|----------|
| Q-A1 | Executive HR Decision authority definition |
| Q-A2 | Решение vs оформление boundary |
| Q-A3 | Positive organizational permission class |
| Q-B1 | Cabinet contour qualification |
| Q-B2 | Acting Director relationship |
| Q-C1 | Separation from ACCESS-002 |
| Q-C2 | ADR-045 executive read scope |
| Q-D1 | Policy debt disposition |
| Q-D2 | Session boundary without implementation |
| Q-D3 | Ratification record wording |

**Total accepted:** 10 / 10 mandatory questions.

### Questions deferred

None.

### Questions rejected

None.

### Questions requiring Policy Debt

| # | Question | Policy debt effect |
|---|----------|-------------------|
| Q-A3 | Positive class — code mapping not ratified | **DEBT-B1-001 continues** → WP-B8 |
| Q-D1 | Split debt disposition | **DEBT-B2-001 closed**; **DEBT-B1-001 continues** |

### Policy debt register (post–Session 1)

| Debt ID | Status | Item | Resolution WP |
|---------|--------|------|---------------|
| **DEBT-B2-001** | **Closed** | Positive кадровое решение permission class — ratified Session 1 | — |
| **DEBT-B1-001** | **Open** | Transitional `access_roles.code` for PD-5.1 not ratified | **WP-B8** |

### Remaining governance work

| Item | Owner / WP | Status |
|------|------------|--------|
| WP-B3 attestation signatures | Executive sponsor + HR policy owner + ops lead | **Pending** |
| WP-B3 formal closure | Program register | **Pending** signatures |
| DEBT-B1-001 resolution | WP-B8 | **Open** |
| PERMISSION-DOMAIN-REGISTRY update | Governance session | **Pending** — reflect PD-5.1 class ratified; code debt → WP-B8 |
| WP-B1 / WP-B2 attestation | Parallel administrative | **Pending** — does not block WP-B3 |
| **WP-B4** | Next executable Track B WP | **Ready** — HR-service scope |
| **WP-B7** | Director row | Class defined; code mapping blocks `approved` until WP-B8 + WP-B7 |

### Whether WP-B3 Session 2 is required

**No.**

All mandatory Review Board questions were **Accepted** in Session 1. Overall outcome **Ratified with Policy Debt** is complete for session purposes. No unresolved governance gap requiring re-session. Remaining open item (DEBT-B1-001 code mapping) is assigned to **WP-B8**, not WP-B3 Session 2.

### WP-B3 readiness for decision recording

| Criterion | Status |
|-----------|--------|
| Session 1 decisions recorded | ☑ |
| Overall outcome determined | ☑ **Ratified with Policy Debt** |
| DEBT disposition coherent | ☑ |
| Implementation gates unchanged | ☑ verified |
| Attestation signatures | ☐ **Pending** |
| WP-B3 formally **Closed** | ☐ **Pending** signatures |

**Finding:** WP-B3 is **ready for formal decision recording** upon attestation. Session 1 governance work is **complete**; formal closure blocked on signatures only — same pattern as WP-B1 and WP-B2.

---

## Ratified governance definition (Session 1)

Organizational permission class ratified — **not** implementation binding:

| Field | Ratified definition |
|-------|---------------------|
| **Class ID** | PD-5.1 — **Кадровое решение** (Executive HR Decision) |
| **Organizational meaning** | A **management decision** that **changes the state of a position assignment** within **defined calendar boundaries** (EHD-INV-1); executive **approval authority** for кадровые решения: hire, transfer, dismiss, appoint acting duties |
| **Medium independence** | An HR Decision **exists independently of recording medium** — director visa on application, paper order, electronic workflow, or other organizational record. The medium does not define existence of the HR Decision (EHD-INV-2) |
| **Authorship** | Every HR Decision has **exactly one author** — the subject currently holding the **Director Position Cabinet**, including Acting Director during a valid delegation period. The **HR department is never the author** (EHD-INV-3) |
| **PD-5.2 boundary** | HR department performs **processing** — prepares, records, executes, and documents HR Decisions. These activities belong to **кадровое оформление** (PD-5.2); they are **not** HR Decisions (EHD-INV-4) |
| **Binding subject** | Position Cabinet Permission Template baseline (P1) |
| **Qualification** | Organizational policy assignment to org-unique Director Cabinet contour — authorship follows **Cabinet occupancy**, not title inference alone |
| **Acting Director** | Same PD-5.1 class when occupying Director Cabinet with valid delegation; **transfer of Director Position Cabinet automatically transfers authorship** to Acting Director for delegation duration — Cabinet ownership consequence, not title (EHD-INV-5) |
| **Excluded** | PD-5.2 оформление as HR Decision; PD-5.3 oversight; PD-5.4 line boundary; ACCESS-002 responsibilities; ADR-045 as substitute; `HR_ENROLLMENT_MANAGER`; `SYSADMIN_CABINET` |
| **Transitional code** | **Not ratified** — DEBT-B1-001 continues → WP-B8 |
| **Runtime effect** | **None** |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | WP-B3 Review Board Session 1 — Ratified with Policy Debt; DEBT-B2-001 closed; DEBT-B1-001 continues → WP-B8 |
| 2026-07-04 | 0.2 | Domain invariant alignment — EHD-INV-1…5 reflected in ratified definition and Q-A1/A2/A3, Q-B1, Q-B2 rationales; no new decisions or debt |
