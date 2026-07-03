# ARCH-001 — Foundation Consolidation Review

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Complete** — 2026-07-03 |
| Type | Architecture corpus consistency review (read-only analysis + cross-reference fixes) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Scope | Foundation phase documents only; no redesign, no invariant changes |

**Review constraint:** this review did **not** change architectural decisions, introduce concepts, or amend ARCH-001 baseline. Only cross-references, navigation, and status wording were updated where noted below.

---

## 1. Executive conclusion

The foundation documentation set is **architecturally coherent**. ARCH-001 remains the **baseline**; [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) and [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) are **implementation contracts derived from it**, not baseline amendments. No contradictions were found between invariants, entity definitions, or the authorization chain across documents.

**Recommendation:** the foundation is **ready to proceed with Tier 2 consumer-subsystem assessments** (`events-telegram`, `working-contacts`, `directory-contacts`, …). Consumer assessments inherit the confirmed chain and must not redefine Position, Employment, Cabinet, or resolver semantics.

**Separate gate:** **production implementation** remains blocked until ADR-050 and ADR-051 are **approved** (currently **Proposed**) and subsystem migration ADRs (e.g. ADR-049) exist — unchanged from [foundation summary §8](./ARCH-001-foundation-summary.md).

---

## 2. Documents reviewed

| # | Document | Status (at review) | Role |
|---|----------|-------------------|------|
| 1 | [ARCHITECTURE_GOVERNANCE.md](./ARCHITECTURE_GOVERNANCE.md) | Active (baseline pending ARCH-001 approval) | Baseline principles; governance rules |
| 2 | [ARCH-001-position-permission-model.md](./ARCH-001-position-permission-model.md) | Draft (Architecture Review) | **Baseline** — target domain model |
| 3 | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) | Draft | Assessment queue and template |
| 4 | [ARCH-001-foundation-summary.md](./ARCH-001-foundation-summary.md) | Draft | Consolidated foundation conclusions |
| 5 | [ARCH-001-task-subsystem-assessment.md](./ARCH-001-task-subsystem-assessment.md) | Draft — Complete | Tier 0 pilot |
| 6 | [ARCH-001-positions-org-structure-assessment.md](./ARCH-001-positions-org-structure-assessment.md) | Draft — Complete | Tier 1 #1 |
| 7 | [ARCH-001-personnel-employment-assessment.md](./ARCH-001-personnel-employment-assessment.md) | Draft — Complete | Tier 1 #2 |
| 8 | [ARCH-001-access-rbac-assessment.md](./ARCH-001-access-rbac-assessment.md) | Draft — Complete | Tier 1 #3 |
| 9 | [ARCH-001-platform-user-identity-assessment.md](./ARCH-001-platform-user-identity-assessment.md) | Draft — Complete | Tier 1 #4 |
| 10 | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | **Proposed** | Implementation contract: Position + Cabinet |
| 11 | [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | **Proposed** | Implementation contract: Cabinet Access Resolver |

**Total:** 11 documents. All Tier 0 and Tier 1 assessments marked **Complete** in the assessment program status tracker.

---

## 3. Baseline vs implementation contract hierarchy

Verified consistent across the corpus:

```text
ARCHITECTURE_GOVERNANCE  ← baseline principles (from ARCH-001 when accepted)
        │
        ▼
ARCH-001 (Draft)         ← authoritative domain model; NOT amended by ADR-050/051
        │
        ├── Foundation assessments (Draft) — fit/gap analysis; confirm baseline sufficient
        ├── Foundation summary (Draft)     — consolidated conclusions
        │
        ▼
ADR-050 (Proposed)       ← HOW to implement org-unique Position + Position Cabinet
        │
        ▼
ADR-051 (Proposed)       ← HOW to resolve Employment → Cabinet → effective permissions
        │
        ▼
Consumer ADRs (future)   ← subsystem-specific enforcement (ADR-049, ADR-042 B5/E1, …)
```

ADR-050 explicitly states it **does not amend ARCH-001** (§7). ADR-051 explicitly **defers** Position/Cabinet lifecycle to ADR-050 and **does not** redefine the baseline entity model.

---

## 4. Terminology consistency

| Term | Baseline (ARCH-001) | ADR-050 | ADR-051 | Assessments | Verdict |
|------|---------------------|---------|---------|-------------|---------|
| **Person** | Canonical human identity; not User, Employee, Cabinet | Temporary occupant via Employment; never Cabinet owner | Authorization subject via User linkage | Consistent | **OK** |
| **Employment (Занятие должности)** | = `person_assignments`; opens Cabinet access for period | FK to org-unique Position; grants access (enforcement in ADR-051) | Primary resolver input | Consistent | **OK** |
| **Position** | Org-unique staffing unit; not global catalog | Org-unique entity; distinct from title taxonomy | Consumed via Employment → Cabinet map | Consistent | **OK** |
| **Position Cabinet** | 1:1 with Position; long-lived; owned by Position | Strict 1:1; created with Position; survives vacancy | Accessible set member; Template host | Consistent | **OK** |
| **Permission Template** | Inside Cabinet; not on User/Person | Configuration on Cabinet (I8) | Evaluated per accessible Cabinet | Consistent | **OK** |
| **Platform User** | Auth only — login, password, status | Auth only (I7) | Authentication entry; not authorization source | Consistent | **OK** |
| **Platform Role / user roles** | Transitional as-is (`public.roles`, `users.role_id`) | Not introduced | Explicitly not architectural entities (R14) | Marked transitional in foundation summary §4 | **OK** |

**Note (not a contradiction):** ARCH-001 §2.3 and ADR-007 use **«личный кабинет»** for **UI entry shell**; **Position Cabinet** is the **operational container**. All documents preserve this distinction.

**Note (not a contradiction):** **Employee** remains an **operational shell** (ADR-050 §4.2, personnel-employment assessment) — not Employment truth. Consistent across corpus.

---

## 5. Invariant consistency

Cross-checked mandatory invariants from ARCH-001, ADR-050 (I1–I13), ADR-051 (R1–R17), and foundation summary §3.

| Invariant theme | Consistent? | Notes |
|-----------------|-------------|-------|
| Person does not define permissions / own Cabinet | **Yes** | ARCH-001 §3.1, §4.3; ADR-050 I6; ADR-051 R3, R15 |
| Platform User auth only | **Yes** | ARCH-001 §3.7, §8; ADR-050 I7; ADR-051 R1, R2, R12 |
| Employment opens Cabinet access | **Yes** | ARCH-001 §3.2; ADR-050; ADR-051 §5 |
| Permission Template inside Cabinet | **Yes** | ARCH-001 §3.5; ADR-050 I8; ADR-051 R5 |
| Effective permissions = union of accessible Cabinets | **Yes** | ARCH-001 §3.6, §10; access-rbac §3.2; ADR-051 §5–§6 |
| Acting adds Cabinets; never replaces primary | **Yes** | ARCH-001 §9; ADR-050 §5.5; ADR-051 R7 |
| Vacancy: Cabinet persists; no primary access | **Yes** | ARCH-001 §4.7.1; ADR-050 §5.6; ADR-051 §5.4 |
| No Slot entity | **Yes** | ARCH-001 §15.0; ADR-050 I12; ADR-051 R13 |
| Cabinet id stable across rename/occupant change | **Yes** | ADR-050 I13; ADR-051 R9 |
| JWT auth-only; no effective permissions in token | **Yes** | access-rbac §2.2; platform-user-identity; ADR-051 R12 |
| Operational objects → Cabinet first (Person exceptions) | **Yes** | ARCH-001 §4.5; tasks assessment; foundation summary §2 |

**No contradictory invariant definitions** were found. ADR-051 operational invariants **restate and specialize** ADR-050/ARCH-001 for the resolver layer without conflicting meanings.

---

## 6. Document status ladder

| Layer | Status | Interpretation |
|-------|--------|----------------|
| ARCH-001 | Draft (Architecture Review) | Baseline candidate — not yet Accepted |
| ARCHITECTURE_GOVERNANCE | Active (pending ARCH-001 approval) | Principles orienting; full binding after ARCH-001 Accepted |
| Foundation assessments + summary | Draft | Analysis artifacts — complete for foundation phase |
| ADR-050, ADR-051 | **Proposed** | Authored implementation contracts — pending architecture session approval |
| ADR-049 (Tasks transition) | Not yet authored | Correctly still referenced as future in tasks assessment |

The status ladder is **internally consistent**: Draft baseline → Proposed implementation contracts → (future) Accepted → implementation.

---

## 7. Issues found

| ID | Severity | Issue | Resolution |
|----|----------|-------|------------|
| I1 | **Navigation** | ADR-050 metadata said ADR-051 «not yet published» | **Fixed** — link to ADR-051 (Proposed) |
| I2 | **Navigation** | Foundation summary said ADR-050/051 must be «authored and approved» without reflecting authored state | **Fixed** — Proposed status; planning vs approval gate clarified |
| I3 | **Navigation** | positions-org-structure §8/§9 used «New ADR (e.g. ADR-050)» and unchecked author checkbox | **Fixed** — links to ADR-050; checkbox marked done (Proposed) |
| I4 | **Navigation** | personnel-employment §8 used «New ADR (e.g. ADR-051)» | **Fixed** — link to ADR-051 |
| I5 | **Navigation** | tasks assessment dependency pointed to vague «dedicated cabinet schema ADR» | **Fixed** — explicit ADR-050 + ADR-051 links |
| I6 | **Navigation** | access-rbac §8 referenced ADR-050/051 as «assessment #1/#2» without links | **Fixed** — direct ADR links |
| I7 | **Navigation** | ARCHITECTURE_GOVERNANCE lacked ADR-050/051 in related documents | **Fixed** — added as implementation contracts |
| I8 | **Navigation** | assessment-program §9 still listed resolver design as future output | **Fixed** — ADR-050/051 marked authored (Proposed) |

**No architectural issues** (contradictions, duplicate definitions with different meanings, or baseline drift) were identified.

**Intentionally unchanged (not issues):**

- ADR-049 remains «New ADR (required)» in tasks assessment — correct; not in scope of this foundation review.
- ARCH-001 does not reference ADR-050/051 — correct; baseline predates implementation contracts and must not be modified.
- Blocked-on-ADR-050/051 language in assessments remains valid for **implementation**; assessments correctly describe as-is runtime gaps.

---

## 8. Fixes applied (cross-references only)

| File | Change |
|------|--------|
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | ADR-051 metadata: link + Proposed status |
| [ARCH-001-foundation-summary.md](./ARCH-001-foundation-summary.md) | ADR-050/051 links; Proposed status; planning vs approval; implementation readiness rows; related docs; v1.1 history |
| [ARCH-001-positions-org-structure-assessment.md](./ARCH-001-positions-org-structure-assessment.md) | ADR-050 links in §8, §9 P0 checklist |
| [ARCH-001-personnel-employment-assessment.md](./ARCH-001-personnel-employment-assessment.md) | ADR-050/051 links in §8 |
| [ARCH-001-task-subsystem-assessment.md](./ARCH-001-task-subsystem-assessment.md) | Dependency paragraph → ADR-050 + ADR-051 |
| [ARCH-001-access-rbac-assessment.md](./ARCH-001-access-rbac-assessment.md) | ADR-050/051 links in §8 Required |
| [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) | §9 outputs updated; consolidation review link |
| [ARCHITECTURE_GOVERNANCE.md](./ARCHITECTURE_GOVERNANCE.md) | Related documents: ADR-050, ADR-051 |

---

## 9. Architectural contradiction check

| Check | Result |
|-------|--------|
| ADR-050 introduces entities beyond ARCH-001 baseline | **No** — implements existing entities only |
| ADR-051 redefines Position/Cabinet lifecycle | **No** — consumes ADR-050; defines resolver only |
| Permission source moved back to Platform User | **No** — all documents agree auth-only on User |
| Slot entity introduced | **No** — explicitly rejected everywhere |
| User roles introduced as permanent architecture | **No** — marked transitional/obsolete |
| Effective permissions use MAX rank / role merge | **No** — union semantics consistent (ADR-051 §5.1, access-rbac §3.2) |
| Vacancy deletes Cabinet or grants anonymous access | **No** — Cabinet persists; zero occupants |
| Acting replaces primary Employment access | **No** — additive only |
| Conflicting Employment terminology | **No** — Занятие должности = Employment = `person_assignments` throughout |

**Confirmation:** no architectural contradictions were introduced by ADR-050, ADR-051, or the cross-reference updates.

---

## 10. Readiness for Tier 2 assessments

| Criterion | Ready? |
|-----------|--------|
| ARCH-001 baseline defined and assessed | **Yes** |
| Foundation assessments complete (Tier 0 + Tier 1) | **Yes** |
| Confirmed chain documented | **Yes** — foundation summary §2 |
| Implementation contracts authored | **Yes** — ADR-050, ADR-051 (Proposed) |
| Consumer scope bounded (no baseline redefinition) | **Yes** — assessment program §7 |
| Corpus cross-references current for ADR-050/051 | **Yes** — after fixes in §8 |

### Recommendation

**Proceed with Tier 2 consumer-subsystem assessments** starting with `events-telegram` (queue #5) per [assessment program §6](./ARCH-001-assessment-program.md).

Consumer assessments should:

- Reference [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) and [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) as **Proposed** implementation contracts.
- Treat ARCH-001 as baseline; report subsystem fit and required consumer ADR amendments only.
- **Not** reopen Position/Cabinet/resolver semantics unless a genuine baseline gap is found (none identified in foundation phase).

**Do not** begin production schema work, resolver enforcement, or `users.role_id` demotion until architecture session **approves** ADR-050 and ADR-051.

---

## 11. Suggested follow-ups (outside this review scope)

These are **recommendations for a future architecture session**, not changes made by this review:

1. **Accept ARCH-001** (Draft → Accepted) and update ARCHITECTURE_GOVERNANCE status accordingly.
2. **Accept ADR-050 and ADR-051** (Proposed → Accepted) after session review.
3. **Author ADR-049** (Tasks transition) — still the primary open implementation contract for the tasks pilot.
4. Update assessment-program status tracker verdict rows to note ADR-050/051 authored (optional cosmetic).

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial foundation consolidation review |
