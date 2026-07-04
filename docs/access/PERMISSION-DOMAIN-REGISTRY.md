# PERMISSION-DOMAIN-REGISTRY — Organizational Permission Domain Registry

## Status

**Reviewed (derived)** — 2026-07-04

Governance consolidation document. Defines the official catalog of **Organizational Permission Domains** as declared in [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) (**Reviewed**). **No runtime effect.** **No new policy.**

| Field | Value |
|-------|-------|
| Source of truth | [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) §5 — normative policy document |
| Purpose | WP-B1 approval artifact; implementation traceability |
| Ratification program | [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) — WP-B1 |
| Does not modify | ACCESS-001, ACCESS-002, ADRs, architecture |

---

## 1. Purpose

This registry is the **single catalog view** of Organizational Permission Domains for Policy Ratification (Tier G, Phase G1) and downstream implementation traceability.

| Role | Document |
|------|----------|
| **Normative policy** | [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) — permission domains (§5), principles (§4), contour matrix (§7) |
| **Registry (this document)** | Consolidated domain catalog for organizational approval under WP-B1 |
| **Contour binding** | ACCESS-001 §7 — which contours receive which `access_roles` under an approved domain |
| **Execution** | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) — after ACCESS-001 **Approved** |

ACCESS-001 remains authoritative. If this registry and ACCESS-001 diverge, **ACCESS-001 prevails**. This document introduces **no** domains, codes, or bindings not already stated in ACCESS-001 **Reviewed** text.

---

## 2. Registry principles

| # | Principle |
|---|-----------|
| R1 | **No new policy.** Every registry entry is extracted from ACCESS-001 §5. Consolidation only — no additions, splits, or redefinitions. |
| R2 | **ACCESS-001 is origin.** Each domain cites its source section. Domains not defined in ACCESS-001 §5 do not appear in this registry. |
| R3 | **Approved domains only for implementation binding.** OPS-030 and `permission_template_contour_rule` inserts require the contour’s domain ratified and the §7 row `policy_status=approved` under ACCESS-001 **Approved**. |
| R4 | **Registry has no runtime effect.** Ratifying a domain in this registry does not insert contour rules, populate `access_role_id`, or change enforcement. Legacy `access_grants` remain authoritative until ADR-051 cutover phases. |
| R5 | **Orthogonal to management responsibilities.** Permission domains (ACCESS-001) do not establish management authority, hierarchy, or subtree scope — [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md). |
| R6 | **Transitional codes are candidates, not assignments.** `access_roles.code` values listed here are **candidate only** per ACCESS-001; approval requires explicit ratification per domain and contour. |
| R7 | **Negative boundaries are domains.** §5.4 defines an informational permission domain as a **boundary** (what not to bind) — it is a first-class registry entry, not an absence of policy. |

---

## 3. Permission Domain Registry

Four domains are defined in ACCESS-001 §5. §5.5 describes mapping procedure only — it is **not** a permission domain.

---

### PD-5.1 — Кадровое решение

| Field | Value |
|-------|-------|
| **Domain ID** | `PD-5.1` |
| **Name** | Кадровое решение |
| **Purpose** | Executive approval of кадровые решения on Cabinet baseline — distinct from HR processing, sysadmin, and management visibility |
| **Organizational meaning** | Right and duty to **approve** кадровые решения: hire, transfer, dismiss, appoint acting duties |
| **Source (ACCESS-001)** | [§5.1](./ACCESS-001-organizational-permission-matrix.md#51-кадровое-решение); principles P5, P6, P7 |
| **Typical holders** | Director / Acting Director (`Директор` / исполняющий обязанности) |
| **Not the same as** | HR document preparation; enrollment execution; `HR_ENROLLMENT_MANAGER`; `SYSADMIN_CABINET`; management visibility (ACCESS-002); line informational domain (§5.4) |
| **Related contours** | `(1, 78, 62)` — Директор — **rejected** for `SYSADMIN_CABINET`; requires this domain if executive baseline is ever approved (ACCESS-001 §7) |
| **Related access_roles** | **None defined.** Separate decision/approval permission class **not modeled** in Reviewed ACCESS-001. `HR_ENROLLMENT_MANAGER` **must not** represent this class. `SYSADMIN_CABINET` **rejected** for Director per P4/P5/P7 |
| **ACCESS-001 stance** | Policy debt — domain defined; transitional `access_roles.code` **not** assigned |
| **Current status** | **Ratified with Policy Debt** — 2026-07-04 (WP-B1). No transitional `access_roles.code` defined; debt resolution → **WP-B3**. No approved contour binding. **No runtime effect.** |

---

### PD-5.2 — Кадровое оформление

| Field | Value |
|-------|-------|
| **Domain ID** | `PD-5.2` |
| **Name** | Кадровое оформление |
| **Purpose** | HR department execution of кадровые процессы on Cabinet baseline — document preparation and enrollment, not executive decision |
| **Organizational meaning** | Prepares documents, performs enrollment, executes кадровые процессы (ADR-045 «Кадровые процессы» contour) |
| **Source (ACCESS-001)** | [§5.2](./ACCESS-001-organizational-permission-matrix.md#52-кадровое-оформление); principle P6 |
| **Typical holders** | HR department / кадровая служба (`Отдел кадров`) |
| **Not the same as** | Кадровое решение (§5.1); кадровый контроль (§5.3); line informational boundary (§5.4); management responsibilities (ACCESS-002) |
| **Related contours** | `(1, 73, 86)` — Руководитель отдела кадров — **pending**; likely this domain; not approved until class + code ratified (ACCESS-001 §7) |
| **Related access_roles** | `HR_ENROLLMENT_MANAGER` — **transitional code (candidate only)**; **if and only if** approved for a specific HR-service Cabinet contour |
| **ACCESS-001 stance** | HR head contour pending class confirmation — likely §5.2, not approved yet |
| **Current status** | **Defined (Reviewed)** — pending organizational ratification under WP-B1; Phase 2.6b MVP candidate after ratification + §7 row approval |

---

### PD-5.3 — Кадровый контроль / наблюдение

| Field | Value |
|-------|-------|
| **Domain ID** | `PD-5.3` |
| **Name** | Кадровый контроль / наблюдение (HR oversight visibility) |
| **Purpose** | HR oversight visibility permission domain — see кадровые процессы for control/compliance without HR processing execution |
| **Organizational meaning** | May **see** кадровые процессы for HR control/compliance within approved HR operational scope; **does not execute** HR processing |
| **Source (ACCESS-001)** | [§5.3](./ACCESS-001-organizational-permission-matrix.md#53-кадровый-контроль--наблюдение-hr-oversight-visibility); principles P8; §3 visibility boundary |
| **Typical holders** | Deputy for administrative affairs, legal service, other authorized oversight roles |
| **Not the same as** | `HR_ENROLLMENT_MANAGER` unless explicit organizational delegation approved; management visibility / personnel subtree oversight (ACCESS-002 §3.1); кадровое решение (§5.1) |
| **Related contours** | `(1, 78, 77)` — Зам по адм вопросам — **pending**; likely this domain, not `HR_ENROLLMENT_MANAGER` by default (ACCESS-001 §7) |
| **Related access_roles** | **None defined** in Reviewed ACCESS-001. No dedicated `access_roles.code` in transitional catalog; ADR-045 / access baseline when approved — runtime mechanism only, not policy owner |
| **ACCESS-001 stance** | Deputy admin contour pending class confirmation — likely §5.3; management remit for deputy → ACCESS-002 |
| **Current status** | **Defined (Reviewed)** — pending organizational ratification under WP-B1; no approved `access_roles` baseline in Reviewed policy |

---

### PD-5.4 — Линейное информирование

| Field | Value |
|-------|-------|
| **Domain ID** | `PD-5.4` |
| **Name** | Линейное информирование (informational permission domain) |
| **Purpose** | Negative permission boundary for line department heads — defines what baseline `access_roles` binding **must not** grant; does not assign management responsibility |
| **Organizational meaning** | Organizational permission boundary: line heads may need **information** on results of relevant кадровые процессы for their own staff — expressed as a permission domain, not as management remit |
| **Source (ACCESS-001)** | [§5.4](./ACCESS-001-organizational-permission-matrix.md#54-линейное-информирование-informational-permission-domain); principles P9; §3 visibility boundary |
| **Typical holders** | Heads of clinical, laboratory, and other line departments (permission-boundary purposes only) |
| **Not the same as** | HR processing (`HR_ENROLLMENT_MANAGER`); executive decision (§5.1); ACCESS-002 management responsibilities. Management visibility scope → ACCESS-002 exclusively |
| **Related contours** | Twelve **rejected** line-head contours in ACCESS-001 §7 citing §5.4: `(1, 42, 74)`, `(1, 43, 75)`, `(1, 44, 64)`, `(1, 45, 71)`, `(1, 46, 72)`, `(1, 47, 68)`, `(1, 48, 73)`, `(1, 49, 69)`, `(1, 50, 66)`, `(1, 53, 70)`, `(1, 54, 67)`, `(1, 55, 65)` — all `HR_ENROLLMENT_MANAGER` **rejected**. *(Not PD-5.4 inventory: `(1, 55, 9)` and `(1, 56, 88)` are rejected §7 rows for other reasons.)* |
| **Related access_roles** | **None approved.** No approved `access_roles` baseline for §5.4 in Reviewed ACCESS-001 — negative boundary only (what **not** to bind). `HR_ENROLLMENT_MANAGER` explicitly **rejected** for line heads |
| **ACCESS-001 stance** | Informational domain is boundary policy, not an approved code assignment |
| **Current status** | **Defined (Reviewed)** — pending organizational ratification under WP-B1; contour rows already **rejected** for HR processing codes per §7 |

---

### Registry summary

| Domain ID | Name | Related access_roles (Reviewed) | §7 contours explicitly linked | Current status |
|-----------|------|--------------------------------|--------------------------------|----------------|
| `PD-5.1` | Кадровое решение | None defined | 1 (Director — rejected pending class) | **Ratified with Policy Debt** (WP-B3 debt) |
| `PD-5.2` | Кадровое оформление | `HR_ENROLLMENT_MANAGER` (candidate) | 1 (HR head — pending) | Defined — not ratified |
| `PD-5.3` | Кадровый контроль / наблюдение | None defined | 1 (Deputy admin — pending) | Defined — not ratified |
| `PD-5.4` | Линейное информирование | None (negative boundary) | 12 (line heads — rejected) | Defined — not ratified |

**Contours without §5 domain assignment:** ACCESS-001 §7 pending/rejected rows for statistics, QM, finance, pharmacy, generic deputies, test contour, and non-admin titles are **not** assigned to a §5 domain in Reviewed policy. They remain in the contour matrix only — outside this domain registry until ACCESS-001 defines additional domains.

---

## 4. Relationships

### 4.1. ACCESS-001

| Dimension | Relationship |
|-----------|--------------|
| **Authority** | ACCESS-001 §5 is normative; this registry is a **derived catalog** for WP-B1 approval |
| **Scope split** | Domains (this registry) + contour matrix (§7) + principles (§4) together form ACCESS-001 policy |
| **Approval** | Domain ratification under WP-B1 does not alone approve §7 rows — class clarification precedes OPS-030 insert (§5.5) |

### 4.2. ACCESS-002

| Dimension | ACCESS-001 (this registry) | ACCESS-002 |
|-----------|------------------------------|------------|
| **Policy object** | Organizational **permission domains** | Management **responsibilities** |
| **Visibility** | HR oversight visibility (PD-5.3); HR informational boundary (PD-5.4) | Management visibility from personnel responsibility (§3.1) |
| **Independence** | Approving a domain or `access_roles` binding **does not** approve any ACCESS-002 responsibility |

Shared contours (e.g. line heads, deputy admin, Director) may appear in both documents with **orthogonal** policy layers. Cross-layer alignment is WP-X1 in [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md).

### 4.3. ADR-053

| ADR-053 contract | Registry role |
|------------------|---------------|
| `permission_template.access_role_id` binding | Binds **Approved** domain → approved `access_roles.code` on Cabinet Template baseline |
| `permission_template_contour_rule` | Inserts only when ACCESS-001 §7 row is `approved` **and** domain/class ratified |
| Transitional single-code expansion (Phase 2.6) | Emits one `access_roles.code` per Template — sufficient only where domain maps to an approved code |
| AC3 ops mapping annex | Satisfied by ACCESS-001 **Approved** (matrix + domains); registry supports WP-B1 traceability |

ADR-053 defines **how** binding works. ACCESS-001 and this registry define **which** domains exist and **which** contours may bind. Neither ADR-053 nor this registry substitutes for ACCESS-001 **Approved** status.

```text
ACCESS-002          ACCESS-001 §5 + this registry          ADR-053
(management         (permission domains)                  (binding model)
 responsibilities)         │                                  │
       │                   ▼                                  │
       │            Approved §7 rows                          │
       │                   └──────────────► OPS-030 ────────►│
       │                                      contour rules   │
       └─ orthogonal ───────────────────────────────────────┘
```

---

## 5. Ratification status

Governance approval table for WP-B1.

| Domain ID | Domain | Policy status | Approved by | Approval date | Notes |
|-----------|--------|---------------|-------------|---------------|-------|
| `PD-5.1` | Кадровое решение | **Ratified with Policy Debt** | Pending signature (HR policy owner + ops lead + architecture lead) | 2026-07-04 | No transitional `access_roles.code` defined. Debt **DEBT-B1-001** → resolution **WP-B3**. No runtime effect. |
| `PD-5.2` | Кадровое оформление | **Pending ratification** | — | — | `HR_ENROLLMENT_MANAGER` candidate for `(1, 73, 86)` only after domain + row approved |
| `PD-5.3` | Кадровый контроль / наблюдение | **Pending ratification** | — | — | No dedicated code in Reviewed policy; `(1, 78, 77)` pending |
| `PD-5.4` | Линейное информирование | **Pending ratification** | — | — | Negative boundary; 12 line-head §7 rows citing §5.4 already rejected for `HR_ENROLLMENT_MANAGER` |

**WP-B1 status:** **Open** — 1/4 domains recorded (PD-5.1). Remaining: PD-5.2, PD-5.3, PD-5.4.

**WP-B1 completion signal:** all four rows reach **Ratified** or **Ratified with Policy Debt** with approver signatures recorded; then ACCESS-001 document-level **Approved** remains separate (WP-X2).

---

## 6. Implementation notes

| Statement | Detail |
|-----------|--------|
| **No runtime effect** | This registry does not modify schema, insert contour rules, populate templates, or change guards / `/auth/me` / JWT |
| **Blocked until ACCESS-001 Approved** | Document status **Reviewed** does not authorize OPS-030 or Phase 2.6b |
| **Blocked until §7 rows approved** | Domain ratification alone does not permit `permission_template_contour_rule` insert |
| **Blocked until ADR-053 AC3** | Ops mapping annex sign-off (WP-X3) required before production backfill |
| **Enforcement unchanged** | Legacy `access_grants` and user-centric paths remain authoritative through Phase 2.6 per ADR-053 §3.5 |
| **Engineering must not infer domains** | Shadow logs, grants, and occupant data do not substitute for ratified registry + matrix (ACCESS-001 P11) |

---

## 7. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial registry — four domains derived from ACCESS-001 §5; WP-B1 approval artifact |
| 2026-07-04 | 0.3 | PD-5.4 §7 inventory: 12 rows citing §5.4 (aligned to ACCESS-001 §7; corrects erroneous count of 13) |
