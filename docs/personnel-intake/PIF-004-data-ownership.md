# PIF-004 — Data Ownership

## Status

**Active (Policy + partial implementation)** — policy initiated 2026-07-08; ownership rules **partially enforced** in production as of 2026-07-24.

| Field | Value |
|-------|-------|
| Parent | [PIF-001](./PIF-001-personnel-intake-framework.md) |
| Identity creation | [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) |
| Form model (target) | [PIF-003](./PIF-003-dynamic-form-model.md) |
| Form model (production) | Static React + backend intake services |
| EPS lifecycle | [PIF-002 §3](./PIF-002-electronic-personal-sheet.md) |

### Implementation snapshot

| Policy area | Production status |
|-------------|-------------------|
| Token-scoped candidate edit | ✅ |
| Draft autosave | ✅ |
| Submit → read-only until rework | ✅ |
| Applicant re-edit after HR/director return | ✅ (revision_requested, under_review + rework) |
| HR on-behalf edit | ✅ (eligibility rules in backend + UI) |
| Intake commit → canonical `person_*` | ❌ Not implemented |
| Post-commit PDF | ❌ Future; preview-PDF at review ✅ |

---

## 1. Purpose

Определить **кто**, **когда** и **на каком основании** может изменять кадровые данные в intake pipeline — до и после перехода в canonical personnel store.

Без явной ownership policy возникает риск:

- кандидат меняет данные после HR approval;
- HR перезаписывает canonical без provenance;
- commit создаёт Person без audit trail;
- post-commit edits смешиваются с intake draft.

---

## 2. Data states

```text
┌─────────────┐     submit      ┌─────────────┐    commit     ┌─────────────┐
│   INTAKE    │ ──────────────► │   INTAKE    │ ────────────► │  CANONICAL  │
│   DRAFT     │                 │  APPROVED   │               │  PERSONNEL  │
│ (mutable)   │ ◄── revision ── │  (locked)   │               │   (SoT)     │
└─────────────┘                 └─────────────┘               └─────────────┘
     ▲                                │
     │                                │ reject
     └────────────────────────────────┘
```

| State | Storage | Authority |
|-------|---------|-----------|
| **Intake Draft** | Intake case draft store | Candidate + HR (policy below) |
| **Intake Approved** | Draft snapshot frozen for commit | HR read + commit trigger |
| **Canonical Personnel** | `person_*` tables | HR via governed edit paths |

---

## 3. Candidate edit rights

### 3.1. When candidate MAY edit

| Case state | Editable by candidate |
|------------|----------------------|
| `INVITED` → first open | ✅ All intake-eligible sections |
| `IN_PROGRESS` | ✅ All intake-eligible sections |
| `REVISION_REQUESTED` | ✅ All intake-eligible sections (production reopen) |
| `under_review` + section `rework_requested` | ✅ Applicant may re-edit (production) |
| `SUBMITTED` | ❌ Read-only |
| `APPROVED` | ❌ Read-only |
| `COMMITTED` | ❌ No access (token invalidated) |

### 3.2. What candidate MAY edit

| Domain | Candidate edit | Notes |
|--------|----------------|-------|
| D1 Identity | ✅ | ИИН may be read-only if pre-filled by HR at invitation |
| D2 Citizenship | ✅ | |
| D3 Contact | ✅ | |
| D4 Identity documents | ✅ | |
| D5 Photo | ✅ | Re-upload allowed until commit |
| D6 Education | ✅ | Repeatable rows |
| D7 Languages | ✅ | |
| D8 Academic titles | ✅ | If section enabled |
| D9 Pre-hire employment | ✅ | |
| D10 Family | ✅ | If section enabled |
| D11 Awards | ✅ | If section enabled |
| D12 Military | ✅ | Basic military block in production intake |
| D13 In-org career | ❌ | Not in intake form |
| D14 Credentials | ❌ | Post-hire / PMF |
| Compliance declarations | ✅ | Required checkbox |

### 3.3. Candidate constraints

- Cannot delete intake case.
- Cannot approve own submission.
- Cannot trigger commit.
- Cannot edit after `SUBMITTED` without HR revision request.

---

## 4. HR edit rights

### 4.1. When HR MAY edit

| Case state | HR edit capability |
|------------|-------------------|
| `IN_PROGRESS` | ⚠️ View only (optional: pre-fill invitation fields) |
| `SUBMITTED` | ✅ Full correction on any field |
| `REVISION_REQUESTED` | ✅ Full correction |
| `APPROVED` | ✅ Correction before commit (re-approval required) |
| `COMMITTED` | ❌ Intake case closed; use canonical edit paths |

### 4.2. What HR confirms

HR **не просто просматривает** — HR **несёт ответственность** за достоверность данных перед commit.

| HR action | Meaning |
|-----------|---------|
| **Review** | Verify candidate entries against documents (offline) |
| **Correct** | Fix transcription errors; provenance = `hr_correction` |
| **Request revision** | Return to candidate with comment |
| **Approve** | Attest data ready for canonical write |
| **Commit** | Authorize irreversible write to personnel store |

### 4.3. HR override provenance

Every HR field change in intake must record:

| Attribute | Value |
|-----------|-------|
| `changed_by` | HR user id |
| `changed_at` | Timestamp |
| `source` | `hr_correction` |
| `previous_value` | Candidate-entered value (if any) |
| `comment` | Optional for minor fixes; required for material changes |

At commit, HR overrides **take precedence** over candidate values in canonical write.

---

## 5. When data becomes canonical (personnel)

### 5.1. Commit gate

Data becomes **canonical personnel data** at successful **Intake Commit**:

```text
HR Approved + Commit confirmed
  → TX: create/link Person (ADR-048)
  → TX: write section records to person_*
  → TX: emit personnel_record_events
  → Case → COMMITTED
```

| Before commit | After commit |
|---------------|--------------|
| Intake draft | `person_*` tables |
| No `person_id` required on case | `person_id` mandatory |
| Reversible (case abandon) | Governed by PF edit policy |
| Not visible in Personnel Card | Visible in Personnel Card |

### 5.2. Person creation policy (ADR-048 alignment)

| Scenario | Policy |
|----------|--------|
| New hire, no existing Person | Create Person shell at commit with `source = intake` |
| Rehire, Person exists | Link to existing `person_id`; merge intake domains |
| IIN match to existing Person | HR must confirm linkage before commit (no silent merge) |
| Commit without IIN | Blocked unless explicit exception policy (TBD PIF-2) |

**Default:** Person materialization at **Commit**, not at Invitation — avoids orphan persons for withdrawn hires.

### 5.3. Events emitted at commit (illustrative)

| Event type | Trigger |
|------------|---------|
| `PERSON_CREATED_FROM_INTAKE` | New person shell |
| `INTAKE_COMMITTED` | Case completed |
| `IDENTITY_RECORDED` | D1 written |
| `EDUCATION_RECORDED` | D6 rows written |
| … | Per domain |

Exact taxonomy — PIF-2 / alignment with `personnel_record_events`.

---

## 6. Post-commit edit policy

After commit, intake case is **closed**. Further changes use **Personal File governance**, not intake form.

| Need | Path |
|------|------|
| Typo correction | HR Processes → Personal File edit (provenance: `manual_correction`) |
| New education after hire | HR entry or PMF import — not EPS re-open |
| Candidate wants to change submitted data | HR manual correction; **no** candidate re-access to EPS |
| Full re-intake | New intake case (exception; HR-initiated) |

### 6.1. When re-editing is allowed (canonical)

| Situation | Allowed | Authority |
|-----------|---------|-----------|
| HR discovers error within 30 days of commit | ✅ | HR + audit comment |
| Material change (IIN, DOB) | ✅ | HR senior / dual control (TBD) |
| Candidate requests change | ✅ | HR applies after document verify |
| Self-service post-commit | ❌ | Not in PIF scope |
| Re-open committed intake case | ❌ | Create amendment record instead |

---

## 7. Ownership matrix (summary)

| Data phase | Owner | Candidate | HR | System |
|------------|-------|-----------|-----|--------|
| Invitation metadata | HR | — | Create/revoke | Issue token |
| Draft values | Shared | Edit (in progress) | View / correct (submitted+) | Validate/autosave |
| Approved snapshot | HR | Read-only | Approve/commit | Lock |
| Canonical personnel | Organization | Read-only (future PC) | Governed edit | Audit/events |
| Generated PDF | Organization | Receive preview at review | Generate / download | Render from draft (✅); post-commit from canonical (future) |

---

## 8. Conflict resolution

| Conflict | Resolution |
|----------|------------|
| Candidate vs HR value at commit | HR override wins; both preserved in provenance |
| Duplicate IIN existing Person | HR explicit link decision; block auto-merge |
| Partial section approval | All mandatory sections must pass before commit |
| Validation warning vs HR judgment | HR may accept with documented comment |

---

## 9. RBAC (conceptual)

| Role | Permissions |
|------|-------------|
| `hr_intake_operator` | Create invitation, review, revise, approve, commit |
| `hr_intake_viewer` | Read cases; no commit |
| `candidate` | Token-scoped edit on own case only |
| `system` | Validation, autosave, commit TX |

Align with [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md): mutate in «Кадровые процессы».

---

## 10. Non-goals

- RBAC implementation details.
- Dual-control workflow engine.
- Amendment / diff UI for post-commit edits.

---

## 11. Related documents

| Document | Role |
|----------|------|
| [PIF-001](./PIF-001-personnel-intake-framework.md) | Pipeline and principles |
| [PIF-002](./PIF-002-electronic-personal-sheet.md) | Lifecycle states |
| [PIF-003](./PIF-003-dynamic-form-model.md) | Field-level `hr_editable` |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person creation |
| [ADR-043 Phase A1](../adr/ADR-043-phase-a1-override-governance.md) | Override provenance patterns |
| [PMF-PILOT-FREEZE](../personnel-migration/PMF-PILOT-FREEZE.md) | Sibling program ownership (import path) |
