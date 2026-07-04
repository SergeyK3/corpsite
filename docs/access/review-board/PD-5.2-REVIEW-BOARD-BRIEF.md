# Review Board Brief — WP-B1 Session 2

## PD-5.2 — Кадровое оформление

> Template: [REVIEW-BOARD-BRIEF-TEMPLATE.md](./REVIEW-BOARD-BRIEF-TEMPLATE.md)

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B1 Review Board Session 2 |
| Date prepared | 2026-07-04 |
| Domain ID | `PD-5.2` |
| Domain name | Кадровое оформление |
| Work package | WP-B1 — Permission Domain Taxonomy |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Briefing only** — no ratification recorded |
| Prior sessions | PD-5.1 — Ratified with Policy Debt (2026-07-04); [WP-B1 package §6](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md#6-ratification-outcome) |
| Sources | [ACCESS-001](../ACCESS-001-organizational-permission-matrix.md) §5.2, P6; [PERMISSION-DOMAIN-REGISTRY](../PERMISSION-DOMAIN-REGISTRY.md); [WP-B1 package](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) |
| Runtime effect | **None** |

---

## 1. Domain definition

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.2` |
| **Name** | Кадровое оформление |
| **Purpose** | HR department execution of кадровые процессы on Cabinet baseline — document preparation and enrollment, not executive decision |
| **Organizational meaning** | Prepares documents, performs enrollment, executes кадровые процессы (ADR-045 «Кадровые процессы» contour) |
| **ACCESS-001 source** | [§5.2](../ACCESS-001-organizational-permission-matrix.md#52-кадровое-оформление); principle P6 |
| **Registry entry** | [PERMISSION-DOMAIN-REGISTRY §3 — PD-5.2](../PERMISSION-DOMAIN-REGISTRY.md#pd-52--кадровое-оформление) — **Defined (Reviewed)** — pending ratification |

---

## 2. Scope

PD-5.2 governs organizational permission policy for HR-service processing and enrollment execution on Cabinet Permission Template baseline.

**In scope for Session 2:**

- Ratification of domain taxonomy.
- Boundary review vs PD-5.1, PD-5.3, PD-5.4, and ACCESS-002.
- Review of whether `HR_ENROLLMENT_MANAGER` is the correct **candidate** transitional code for this domain (acknowledgment only — not contour assignment).

**Out of scope for Session 2:**

- ACCESS-001 §7 row approval for `(1, 73, 86)` — WP-B4, WP-B7.
- OPS-030 / Phase 2.6b — Tier B.
- PD-5.1 transitional code — WP-B3 (DEBT-B1-001).
- PD-5.3, PD-5.4 ratification — separate sessions.
- ACCESS-002 management responsibilities — Track A.

---

## 3. Explicitly inside the domain

| Item | Detail |
|------|--------|
| **Organizational duty** | Prepare HR documents; perform enrollment; execute кадровые процессы within HR-service operational remit |
| **Typical holders** | HR department / кадровая служба (`Отдел кадров`) |
| **Primary contour (ACCESS-001 stance)** | `(1, 73, 86)` — Руководитель отдела кадров — pending; likely this domain |
| **Transitional code (candidate)** | `HR_ENROLLMENT_MANAGER` — if and only if approved for a specific HR-service Cabinet contour (§5.2) |
| **Principle P6** | `HR_ENROLLMENT_MANAGER` means кадровое оформление in policy vocabulary |
| **ADR-045 reference** | «Кадровые процессы» operational contour — execution, not executive approval |

---

## 4. Explicitly outside the domain

| Item | Owner / domain |
|------|----------------|
| Executive approval (hire, transfer, dismiss, acting) | PD-5.1 |
| HR oversight visibility without execution | PD-5.3 |
| Line-head informational boundary | PD-5.4 |
| Management responsibilities, subtree, tasks, reports | ACCESS-002 |
| Sysadmin / break-glass | Explicit sysadmin policy (P4, P5) |
| Director / Acting Director as HR processor by title | Excluded (P5, P7) |
| Line department heads as HR processors | Excluded (P9); twelve §7 rows rejected |
| Deputy admin default HR processing | Excluded by default — §5.3 unless delegation |
| §7 row `approved` | WP-B7 |
| Enforcement cutover | ADR-051 §10 Phase 3+ |

---

## 5. Architectural references (Accepted — fixed)

| ADR / doc | Fixed position relevant to PD-5.2 |
|-----------|-----------------------------------|
| **ARCH-001** | Permissions follow Employment → Cabinet |
| **ADR-050** | Template inside Cabinet 1:1 |
| **ADR-051** | Resolver expansion; legacy authoritative until cutover |
| **ADR-053** | `access_role_id` → `access_roles.code`; `HR_ENROLLMENT_MANAGER` ∈ catalog; Phase 2.6 single-code; grants untouched |
| **ADR-053 §3.4** | No grant-copy binding |
| **ADR-053 AC2** | No enforcement flip from ratification |
| **ACCESS-001 P1, P11** | Cabinet-assigned; no engineering inference |

**Architectural consistency:** No architectural contradiction identified.

---

## 6. Relationship analysis

### 6.1 ACCESS-001

| Dimension | Relationship |
|-----------|--------------|
| **Authority** | §5.2 normative; brief derived |
| **P6** | `HR_ENROLLMENT_MANAGER` = оформление, not решение |
| **§7** | `(73, 86)` pending — likely §5.2 |
| **§5.5** | Domain ratification ≠ contour insert |

### 6.2 ACCESS-002

| Dimension | PD-5.2 | ACCESS-002 |
|-----------|--------|------------|
| **Policy object** | HR processing permission on baseline | Management responsibilities |
| **HR head `(73, 86)`** | Pending PD-5.2 candidate | No line management subtree (§7 example) |
| **Independence** | Ratifying PD-5.2 does not ratify ACCESS-002 responsibilities | M2 |

**Ambiguity:** None identified.

### 6.3 ADR-050 / ADR-051 / ADR-053

Factual: binding attaches to Cabinet Template via approved contour rule; resolver emits code on shadow path when bound; OPS-030 gated on ACCESS-001 **Approved** + §7 + AC3.

### 6.4 Sibling domains

| Domain | Relationship |
|--------|--------------|
| **PD-5.1** | Decision vs execution; `HR_ENROLLMENT_MANAGER` must not represent решение |
| **PD-5.3** | Oversight vs execution |
| **PD-5.4** | Line heads rejected for `HR_ENROLLMENT_MANAGER` |

---

## 7. Contour analysis

### Contour 1 — Primary association (pending)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 73, 86)` |
| **Position** | Руководитель отдела кадров |
| **Organizational rationale** | HR-service head per §5.2 typical holders |
| **Association** | Likely PD-5.2 per ACCESS-001 §7 |
| **Policy status** | `pending` |

### Contour 2 — Exclusion (executive)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 78, 62)` — Директор |
| **Association** | Excluded — PD-5.1; not `HR_ENROLLMENT_MANAGER` (P5, P7) |
| **Policy status** | `rejected` (`SYSADMIN_CABINET`) |

### Contour 3 — Exclusion (deputy admin)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 78, 77)` |
| **Association** | Excluded from PD-5.2 by default — likely PD-5.3 |
| **Policy status** | `pending` |

### Contour 4 — Exclusion (line heads)

| Field | Value |
|-------|-------|
| **Contours** | Twelve §7 rows citing §5.4 — e.g. `(1, 42, 74)` … `(1, 55, 65)` |
| **Association** | Excluded — P9 |
| **Policy status** | `rejected` for `HR_ENROLLMENT_MANAGER` |

**Contours reviewed:** 4 groups (1 association, 3 exclusion groups).

---

## 8. Review questions requiring governance confirmation

| # | Question |
|---|----------|
| **Q1** | Is **кадровое оформление** the correct class for HR department / кадровая служба? |
| **Q2** | Is `HR_ENROLLMENT_MANAGER` the candidate transitional code for this domain only — not Director, deputy, or line heads? |
| **Q3** | Is `pending` on `(1, 73, 86)` acceptable if taxonomy is ratified now and binding deferred to WP-B4/B7? |
| **Q4** | Does PD-5.2 exclude executive decision authority (PD-5.1)? |

---

## 9. Architectural answers already fixed

| Question | Fixed answer |
|----------|--------------|
| Grant-copy / shadow inference binding? | **No** |
| Ratification changes enforcement? | **No** |
| Ratification authorizes OPS-030? | **No** |
| `HR_ENROLLMENT_MANAGER` in `access_roles` catalog? | **Yes** (ADR-053) |
| PD-5.2 ratifies ACCESS-002 responsibilities? | **No** |
| PD-5.2 subsumes PD-5.1? | **No** (P6, P7) |
| Architecture redesign required? | **No** |

---

## 10. Remaining governance questions

| # | Topic | Nature |
|---|-------|--------|
| **G1** | HR-service as holder class | Organizational — Q1 |
| **G2** | `HR_ENROLLMENT_MANAGER` semantic scope | Organizational — Q2 |
| **G3** | Defer contour binding to WP-B4/B7 | Process — Q3 |
| **G4** | PD-5.1 / PD-5.2 separation | Organizational — Q4 |
| **G5** | Non-HR contours and PD-5.2 | Organizational |

**Unresolved architectural questions:** None.

---

## 11. Readiness for Board decision

| Criterion | Assessment |
|-----------|------------|
| Domain definition complete per ACCESS-001 §5.2 | Yes |
| Boundaries consistent with sibling domains | Yes — WP-B1 package §4 |
| Architectural conflicts | None |
| Prior session (PD-5.1) recorded | Yes |
| Materials sufficient for Board to render decision | Yes |

**Approval status:** **Not ratified** — briefing only. Board selects outcome in §14.

---

## 12. Risks

| ID | Risk | Mitigation |
|----|------|------------|
| **R1** | `HR_ENROLLMENT_MANAGER` on non-HR contours | P5, P9; Q2 |
| **R2** | Conflation with PD-5.1 | Q4; P6, P7 |
| **R3** | Ratification mistaken for contour approval | §5.5; WP-B7 |
| **R4** | Conflation with ACCESS-002 on HR head | §7 example; WP-X1 |
| **R5** | Engineering grant-copy bind | ADR-053 §3.4 |
| **R6** | Deferred taxonomy affects downstream WPs | Master Plan sequencing — factual |

---

## 13. Possible policy debt items

Recorded **only if** Board chooses **Ratified with Policy Debt**.

| Debt ID (proposed) | Condition | Resolution WP |
|--------------------|-----------|---------------|
| **DEBT-B1-002** | Code acceptance deferred | WP-B4 |
| **DEBT-B1-003** | Class assignment on `(73, 86)` deferred | WP-B4 |

Contour `pending` after taxonomy ratification may be normal per §5.5 — not automatically debt.

---

## 14. Decision options (Review Board)

| Option | Meaning |
|--------|---------|
| **Ratified** | PD-5.2 taxonomy accepted |
| **Ratified with Policy Debt** | Taxonomy accepted; debt item(s) in §13 recorded |
| **Deferred** | Further policy work before re-session |
| **Rejected** | Domain not accepted — ACCESS-001 revision cycle |

**Session must not:** modify §7 rows; insert contour rules; open OPS-030; change enforcement.

---

## 15. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Session 2 brief |
| 2026-07-04 | 0.2 | Aligned to neutral [REVIEW-BOARD-BRIEF-TEMPLATE](./REVIEW-BOARD-BRIEF-TEMPLATE.md) |
