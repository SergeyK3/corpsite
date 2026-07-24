--------------------------------------------------

Document Status

Document:
WP-PPR-CARD-COORDINATION-008

Title:
Education Reconciliation Decision Executor — Apply-Phase Architecture

Type:
Architecture Work Package (section apply design only)

Status:
Architecture Approved (rev.4)

Revision:
4

Date:
2026-07-24

Depends on:
WP-PPR-CARD-COORDINATION-002 rev.3 (approved contract),
WP-PPR-CARD-COORDINATION-004 rev.3 (engine architecture; commit `4758967`),
WP-PPR-CARD-COORDINATION-003 (commit `3459836` — decision persistence),
WP-PPR-CARD-COORDINATION-005 (commit `c481b44` — Reconciliation Decision Engine),
WP-PPR-CARD-COORDINATION-006 rev.3 (commit `67e7649` — education decide plugin),
WP-PPR-CARD-COORDINATION-007 (education plugin implementation — decide-phase),
WP-PR-008 / WP-PR-010 (PPR command / section mutation contracts)

Purpose:
Описать **apply-phase** для сохранённых education reconciliation decisions: eligibility, live apply-gate, mapping в существующие PPR education commands, U2 `per_record` atomicity, idempotent replay, stale/concurrency/partial failure, lifecycle transitions, audit linkage, retry/recovery и test matrix. Без кода, миграций, API/UI, transfer wiring, HR override и изменений WP-003/WP-005/WP-007.

Out of scope:
Код / Alembic / schema changes, REST/UI, `transfer_service` wiring, HR override decide/apply path, training/employment/military executors, изменения WP-003/WP-005/WP-007 API или schema, commit/push.

--------------------------------------------------

# WP-PPR-CARD-COORDINATION-008 — Education Reconciliation Decision Executor

## 1. Назначение и границы

### 1.1 Проблема

U1 Decide (WP-005 + WP-007) уже создаёт durable `personnel_intake_reconciliation_decisions` со `apply_status=pending` и полным execution intent (action, digests, preconditions, idempotency key). Transfer по-прежнему может делать blind `add_education` вне этого контура. Нужен **education apply executor**, который:

- исполняет только допустимые pending decisions;
- внутри одной U2-транзакции делает live apply-gate + (при необходимости) PPR mutation + terminal transition;
- не допускает рассогласования «PPR изменился, decision остался pending» и наоборот;
- для `section_apply_mode=per_record` изолирует partial failure на уровне одной записи.

### 1.2 Роль WP-008

| WP-008 определяет | WP-008 не определяет |
|-------------------|----------------------|
| Education apply-phase contract (U2) | Код реализации |
| Eligibility / gate / command mapping | Изменения WP-003/WP-005/WP-007 |
| Transaction boundary + idempotent replay | Transfer orchestration (OQ-003) |
| Failure/block/retry policy for education | Military U3 executor |
| Audit linkage strategy without schema break | HR override apply |
| Test matrix + acceptance checklist | API/UI |

### 1.3 Жёсткие ограничения

- Executor **не** вызывает `decide_section` и **не** создаёт pending decisions.
- Executor **не** меняет `action` / matcher/policy versions на decision; только terminal `apply_status` (+ `failure_evidence` / optional `reason_code` через существующий WP-003 API).
- System auto path: **нет** `SupersedeEducationRecord` (WP-006 OQ-006-EDU-SUP).
- Anti-degradation decide-time остаётся в силе: executor **не** «дочищает» canonical поля.
- `manual_review` → только `skipped_manual`; никогда PPR mutation.
- WP-003/WP-005/WP-007 API и schema **не** меняются этим WP.

### 1.4 Planned implementation layout (informative; not created here)

| Path | Role |
|------|------|
| `app/personnel_intake/application/reconciliation/executor.py` | Common apply orchestration shell (education-capable) |
| `app/personnel_intake/application/reconciliation/plugins/education_apply.py` | Education gate + `to_ppr_command` / confirm helpers |
| `tests/personnel_intake/test_reconciliation_education_executor.py` | U2 success / block / fail / replay |
| `tests/personnel_intake/test_reconciliation_education_executor_gate.py` | Live precondition matrix |

---

## 2. Исследование кодовой базы (read-only)

### 2.1 Decide outputs (as-is WP-005 / WP-007)

| Concern | Fact |
|---------|------|
| Plugin | `EducationReconciliationPlugin` — `section_apply_mode="per_record"` |
| Actions produced | `add`, `update_version`, `keep_existing`, `manual_review` (never system `supersede`) |
| Persist | `create_pending` → `apply_status=pending`, `row_version=1` |
| Precondition tokens | `none-match:{digest}` / `row_version:{iso}` / `keep:row_version:{iso}` / `manual:{reason}` |
| Canonical optimistic token | `expected_row_version` = `EducationRecord.updated_at.isoformat()` |
| Identity FP | `edu:{kind}\|{'casefold(institution)'}` |
| Domain content | SEMANTIC_FIELDS; quality block ignored for PPR mapping |

### 2.2 Decision terminal API (as-is WP-003)

```text
SqlAlchemyReconciliationDecisionRepository
  transition_to_terminal(TerminalTransitionCommand) -> ReconcileDecisionRecord
  finalize_batch_terminal(...)   # U3 / military; not used by education U2

TerminalTransitionCommand
  decision_id, expected_row_version (decision CAS int),
  to_status ∈ {applied, skipped_manual, blocked, failed},
  failure_evidence (required non-empty for blocked|failed; forbidden for applied|skipped_manual),
  reason_code (optional override at terminal)
```

Allowed transitions: **only** `pending → {applied, skipped_manual, blocked, failed}`.  
`skipped_manual` only when `action=manual_review`.  
`manual_review` cannot → `applied`.

### 2.3 PPR education mutation surface (as-is)

| Command | Handler | Optimistic token | Notes |
|---------|---------|------------------|-------|
| `AddEducationRecord` | `handle_add_education_record` | n/a (insert) | Active dup FP `(education_kind, institution_name or "")` via **read-before-insert** only |

**PPR duplicate guard (as-is — research finding):**

| Mechanism | Present? | Detail |
|-----------|----------|--------|
| DB unique on active `(person_id, education_kind, institution_name)` | **No** | `person_education` has indexes on `person_id` and `(person_id, lifecycle_status)` only (`q1r2s3t4u5w6_pmf_1`) |
| Handler guard | **Yes** | `_assert_no_duplicate_education` loads active rows and compares `_education_fingerprint` before insert/update |
| Transaction-safe under concurrent inserts | **No** | Two U2 sessions can both pass the read check and insert duplicate active rows (TOCTOU) |

**Closed (OQ-008-EDU-ADD-RACE):** executor **must** serialize mutative `add` applies that share the same `(person_id, edu_identity_key)` inside U2 **before** live gate (§5.4). Update race on one target remains protected by `expected_updated_at` CAS (§6.2).
| `UpdateEducationRecord` | `handle_update_education_record` | `expected_updated_at` | `None` field = keep current (**cannot clear** via None) |
| `SupersedeEducationRecord` | exists | `expected_updated_at` | **Out of system education apply** |
| `VoidEducationRecord` | exists | `expected_updated_at` | Out of recon apply |

Participating UoW: `bind_participating_uow(conn)`.  
`PprSectionApplicationService` today exposes `add_education_participating` / void / supersede; **`update_education_participating` отсутствует**.

**Closed (OQ-008-EDU-UPD-API):** implementation WP **обязана** добавить thin `update_education_participating` на `PprSectionApplicationService` (зеркало `add_education_participating`). Прямой вызов domain handler в обход application service **запрещён**.

### 2.4 Contract anchors (WP-002)

- U2 (`per_record`): одна DB-txn = live gate + PPR mutation (если нужна) + terminal status.
- Stale/concurrency → `blocked` + **new decide**; never fallback `add`.
- `add` decide-time snapshot **недостаточен** — live re-check обязателен.
- Idempotent replay terminal `applied`/`skipped_manual` → no SoT writes.
- `blocked` / terminal `failed` → same `decision_id` is terminal; ordinary redecide with **unchanged** intent cannot create a new pending row (same `idempotency_key` → terminal replay). See §10.

---

## 3. Executor identity and entrypoints

```text
EducationReconciliationDecisionExecutor   # logical component (may share common shell)
  section_code = "education"
  section_apply_mode = "per_record"       # from decision / plugin; fail-closed if mismatched

ApplyEducationDecisionCommand
  decision_id: int
  section_payload: Mapping                # accepted education slice for digest verify (§6.1)
  actor_id: int | None                    # PPR event actor; integration-owned
  correlation_id: str | None              # defaults to decision.evidence.correlation_id
  digest_algorithm_version: str = "canon-json-v1"

ApplyEducationSectionCommand              # optional batch driver for N pending education decisions
  application_id: int
  person_id: int
  decision_ids: tuple[int, ...]           # explicit set; order preserved
  # each decision still applied as independent U2
```

**Normative entry:** apply **one** decision per U2 call (`apply_decision`).  
Section-level helper may loop `decision_ids` but **must not** wrap them in one shared write txn.

---

## 4. Which decisions may execute

### 4.1 Eligibility matrix

| Persisted state | Action | Executor behavior |
|-----------------|--------|-------------------|
| `pending` | `add` | Claim U2 lock → gate → `AddEducationRecord` → `applied`, or `blocked`, or full U2 rollback (retryable) |
| `pending` | `update_version` | Claim U2 lock → gate → `UpdateEducationRecord` via `update_education_participating` → same outcomes |
| `pending` | `keep_existing` | Claim U2 lock → gate → **no PPR command** → `applied` |
| `pending` | `manual_review` | Claim U2 lock → **no gate mutation** → `skipped_manual` |
| `pending` | `supersede` | Under lock: category **C** (§5.3) → `validate_deterministic_executable_intent` → `SYSTEM_SUPERSEDE_FORBIDDEN` → terminal **`failed`** + `failure_evidence`; **zero** PPR writes; never executed/mapped to PPR command |
| `applied` / `skipped_manual` | any | Fast external read replay OK; `idempotent_replay=true`; **zero** PPR writes |
| `blocked` / terminal `failed` | any | **Not** success-replay; `redecide_required=true`. Ordinary same-intent decide cannot mint a new pending row — §10 |

### 4.2 Hard rejects (under lock only)

These checks run **only** on `current` loaded with `SELECT … FOR UPDATE` inside U2 (§5.2). They **never** run on the unlocked peek.

| Condition | Error | Decision / PPR effect |
|-----------|-------|------------------------|
| `section_code != "education"` | `INVALID_SECTION_FOR_EDUCATION_EXECUTOR` | U2 rollback; **pending** unchanged |
| plugin/evidence `section_apply_mode` ≠ `per_record` | `INVALID_SECTION_APPLY_MODE` | U2 rollback; **pending** unchanged |
| `decision_source != "system"` | `UNSUPPORTED_DECISION_SOURCE` | U2 rollback; **pending** unchanged |
| `digest_algorithm_version` unsupported | `UNSUPPORTED_DIGEST_ALGORITHM` | U2 rollback; **pending** unchanged |
| missing required evidence fields | `INVALID_DECISION_EVIDENCE` | U2 rollback; **pending** unchanged |
| `action` not in `{add, update_version, keep_existing, manual_review, supersede}` | `INVALID_EDUCATION_APPLY_ACTION` | U2 rollback; **pending** unchanged |

**Not in §4.2:** persisted `action=supersede` is **not** an eligibility rejection. It is handled by `validate_deterministic_executable_intent` as category **C** (§5.3).

---

## 5. Execution flow (normative)

### 5.1 Concurrent claim of a pending decision

| Phase | Rule |
|-------|------|
| Unlocked peek | **Terminal-only:** return immediately **only** when status is already `applied` / `skipped_manual` / `blocked` / `failed`. **No** eligibility, section, action, digest, or evidence validation on peek |
| Peek = `pending` | **Immediately** open U2 and `SELECT … FOR UPDATE` on the decision row. **Do not** branch on peek for any other work |
| After row lock | Re-classify `apply_status`; run **all** eligibility (§4.2), proposal verify, live gate, and PPR mutation **only** on `current` under lock |
| Mutation owner | Only the session holding the locked `pending` row performs mutating apply work |
| Concurrent loser (same `decision_id`) | Blocks on `FOR UPDATE`, then replays terminal or gets `redecide_required`; if prior holder rolled back retryable error and row still `pending`, this session may proceed |
| Terminal CAS after PPR | If `transition_to_terminal` fails after PPR mutation in U2 → **ROLLBACK entire U2**. Never commit/return a split outcome |

### 5.2 Normative algorithm

```text
apply_decision(conn, cmd):
  # --- Terminal-only unlocked peek (no eligibility on peek) ---
  peek = repo.require_by_id(cmd.decision_id)            # plain SELECT, no FOR UPDATE
  IF peek.apply_status in {applied, skipped_manual}:
      RETURN ApplyResult(peek, idempotent_replay=true)
  IF peek.apply_status in {blocked, failed}:
      RETURN ApplyResult(peek, redecide_required=true)
  # peek == pending OR peek raced to terminal → always claim; never validate peek

  BEGIN U2:
      current = repo.lock_for_update(cmd.decision_id)     # SELECT … FOR UPDATE

      IF current.apply_status in {applied, skipped_manual}:
          ROLLBACK U2
          RETURN ApplyResult(current, idempotent_replay=true)
      IF current.apply_status in {blocked, failed}:
          ROLLBACK U2
          RETURN ApplyResult(current, redecide_required=true)
      ASSERT current.apply_status == pending

      # --- Eligibility + deterministic-invalid (owner only; under lock) ---
      validate_education_eligibility(current)           # §4.2 invocation/routing
          ON error: ROLLBACK U2; RAISE; pending unchanged

      validate_deterministic_executable_intent(current)   # §5.3
          ON deterministic-invalid:                       # executable branch
              transition_to_terminal(
                  failed,
                  failure_evidence=build_deterministic_failure(...),
                  reason_code=mapped_code,
              )
              COMMIT                                      # zero PPR writes
              RETURN failed_new_decide_required

      proposal = rebuild_and_verify_proposal(cmd.section_payload, current)
          ON PROPOSAL_DIGEST_MISMATCH:                     # §5.3 / §6.1
              ROLLBACK U2; RAISE; pending unchanged; zero writes

      IF current.action == manual_review:
          transition_to_terminal(skipped_manual)
          COMMIT
          RETURN skipped_manual

      IF current.action == add:
          acquire_education_identity_lock(                 # §5.4 — before live gate
              person_id=current.person_id,
              identity_key=edu_identity_key(proposal),
          )

      live = load_live_education_canonicals(conn, current.person_id)
      gate = run_education_apply_gate(current, proposal, live)

      IF gate.outcome == block:
          transition_to_terminal(blocked, failure_evidence=gate.evidence,
                                 reason_code=gate.reason_code)
          COMMIT
          RETURN blocked_new_decide_required

      IF current.action == keep_existing:
          transition_to_terminal(applied)
          COMMIT
          RETURN applied

      command = to_ppr_command(current, proposal)
      SAVEPOINT ppr_mutation:
          result = execute_via_section_application_service_participating(conn, command)

      ON SectionDuplicateRecordError / PPR optimistic concurrency:
          ROLLBACK TO SAVEPOINT ppr_mutation
          transition_to_terminal(blocked, failure_evidence=..., reason_code=...)
          COMMIT
          RETURN blocked_new_decide_required

      ON retryable technical / infrastructure error:       # §5.3
          ROLLBACK entire U2
          RAISE / RETURN retryable_pending

      record_apply_linkage(current, result)
      TRY:
          transition_to_terminal(applied)
      ON terminal CAS / post-PPR error:
          ROLLBACK entire U2
          RAISE / RETURN retryable_pending

      COMMIT
      RETURN applied
```

### 5.3 Error classification → lifecycle outcome

| Category | Example codes / signals | U2 effect | Decision after | PPR SoT |
|----------|-------------------------|-----------|----------------|---------|
| **A — Invocation / routing / input** (must not corrupt decision) | `INVALID_SECTION_FOR_EDUCATION_EXECUTOR`, `INVALID_SECTION_APPLY_MODE`, `UNSUPPORTED_DECISION_SOURCE`, `UNSUPPORTED_DIGEST_ALGORITHM`, `INVALID_DECISION_EVIDENCE`, `INVALID_EDUCATION_APPLY_ACTION` (**unknown/unsupported `action` only** — not in `{add, update_version, keep_existing, manual_review, supersede}`), decision not found | **ROLLBACK U2** (or reject before U2 if no txn opened) | **`pending`** unchanged | unchanged |
| **B — Proposal digest mismatch** | `PROPOSAL_DIGEST_MISMATCH` | **ROLLBACK U2** | **`pending`** unchanged | unchanged |
| **C — Deterministic non-executable persisted intent** | persisted `action=supersede` on system path → **`SYSTEM_SUPERSEDE_FORBIDDEN`**; `action=update_version` but `target_canonical_record_id` null; `action=add` but precondition token is `row_version:*` / `keep:*`; `expected_row_version` unparsable for update; precondition/action/evidence tuple internally inconsistent and **cannot** succeed without a genuinely new intent | **`transition_to_terminal(failed)`** under lock | terminal **`failed`** + `failure_evidence` | **unchanged** (zero PPR writes) |
| **D — Live gate / domain block** | `APPLY_STALE_ROW_VERSION`, `APPLY_NO_MATCH_LOST`, `APPLY_CONCURRENCY_PRECONDITION`, `SectionDuplicateRecordError` after savepoint rollback | **`transition_to_terminal(blocked)`** | terminal **`blocked`** + `failure_evidence` | unchanged |
| **E — Retryable technical / infrastructure** | deadlock, serialization failure, connectivity/timeout, post-PPR terminal CAS conflict | **ROLLBACK entire U2** | stays **`pending`** | unchanged |
| **F — Success** | gate OK + PPR OK + terminal CAS OK | **COMMIT U2** | `applied` or `skipped_manual` | changed (mutative) or unchanged (keep/manual) |

**Normative:** categories A/B/E never write `apply_status` or `failure_evidence`. Category C is the **only** path to terminal `failed` in education apply.

**Deterministic-invalid examples (category C — executable under lock):**

```text
validate_deterministic_executable_intent(current):
  IF action == supersede:
      RETURN deterministic_invalid(
          code=SYSTEM_SUPERSEDE_FORBIDDEN,
          detail="system education apply never executes supersede",
      )
  IF action in {update_version, keep_existing} AND target_canonical_record_id IS NULL:
      RETURN deterministic_invalid(MISSING_TARGET_FOR_EXACT_ACTION)
  IF action == add AND expected_canonical_precondition NOT LIKE "none-match:%":
      RETURN deterministic_invalid(INVALID_ADD_PRECONDITION_TOKEN)
  IF action in {update_version, keep_existing}
     AND expected_canonical_precondition NOT LIKE "row_version:%"
     AND expected_canonical_precondition NOT LIKE "keep:row_version:%":
      RETURN deterministic_invalid(INVALID_EXACT_PRECONDITION_TOKEN)
  IF action == update_version AND parse_iso_datetime(expected_row_version) fails:
      RETURN deterministic_invalid(INVALID_EXPECTED_ROW_VERSION)
  RETURN ok
```

### 5.4 Inter-decision add-race serialization (OQ-008-EDU-ADD-RACE)

PPR has **no** DB-enforced active identity uniqueness (§2.3). Per-decision `FOR UPDATE` alone does **not** serialize two different pending `add` decisions for the same `(person_id, edu_identity_key)`.

**Normative (education `add` only):** inside U2, **after** decision row lock and eligibility, **before** live gate:

```text
acquire_education_identity_lock(person_id, identity_key):
  # Transaction-scoped advisory lock; released on U2 commit/rollback
  lock_key = stable_int64_hash("recon-edu-identity", person_id, identity_key[0], identity_key[1])
  SELECT pg_advisory_xact_lock(lock_key)
```

| Path | Serialization |
|------|---------------|
| `add` | **Required** identity lock (person + `edu_identity_key`) before live gate |
| `update_version` | **Not** identity lock; target protected by `expected_updated_at` CAS on `record_id` |
| `keep_existing` | Same as update (target + row_version gate) |
| `manual_review` | No identity lock; no PPR |

Under lock, at most one mutative `add` for a given identity commits at a time across **different** `decision_id`s. Loser re-runs live gate after winner commits → `blocked` + `APPLY_NO_MATCH_LOST` (or `APPLY_CONCURRENCY_PRECONDITION` if none-match digest drifted); **≤1** active PPR row; no split outcome.

### 5.5 Invariant TXN-EDU-1

After a **committed** U2, exactly one row in §5.3 category F or D/C terminal applies.

**Also normative:**

- Unlocked peek is **terminal-only**; eligibility runs **only** under `FOR UPDATE`.
- Categories A/B/E: no `apply_status` / `failure_evidence` writes.
- Category C: terminal `failed` with zero PPR writes — never “maybe failed”.
- Category E / post-PPR CAS conflict: full U2 rollback → **`pending`**.
- Post-PPR terminal CAS conflict: full U2 rollback (never split-commit).
- **Forbidden:** unlocked pending mutation; handler bypass; PPR durable change without matching terminal in same commit.

---

## 6. Precondition validation (live apply-gate)

Все checks — **внутри** U2, на live active education set (`SectionReadRepository.load_active_records` / plugin-equivalent normalization).

### 6.1 Shared reload

```text
live_canonicals = EducationReconciliationPlugin.load_canonical_refs(conn, person_id, digest_algo)
# fail-closed on INVALID_CANONICAL_* (unexpected type / missing tokens)
```

Rebuild proposal domain from decision evidence + stored digests:

- Executor **does not** trust stale in-memory decide snapshot.
- Proposal content for equality/command mapping comes from decide-time `proposal_payload_digest` verification against a re-supplied or stored normalized content.

**Closed (OQ-008-EDU-PROP):** WP-003 stores digests/fingerprints/evidence but **not** full `normalized_content`. Caller re-supplies accepted education `section_payload`; executor rebuilds proposal ref via `build_proposal_refs` and verifies `payload_digest == decision.proposal_payload_digest` (and index/fingerprint match). Transfer/integration WP owns carrying the accepted payload.

**Closed (OQ-008-EDU-MISMATCH):** on digest/index/fingerprint mismatch:

- decision remains `pending`;
- **zero** PPR writes and **zero** `apply_status` / `failure_evidence` writes;
- raise `PROPOSAL_DIGEST_MISMATCH`;
- retry with the correct payload against the same `decision_id` is allowed (after a new claim).

### 6.2 Gate by action

#### `add`

```text
confirm_add_precondition(proposal, live_canonicals):
  1) Identity completeness still holds (institution non-empty after strip/casefold)
  2) No live candidate with edu_identity_key == proposal key
     else BLOCK APPLY_NO_MATCH_LOST
  3) Recompute none-match precondition over live active payload digests
     MUST equal decision.expected_canonical_precondition
     else BLOCK APPLY_CONCURRENCY_PRECONDITION
  4) Proposal still confident-add eligible under WP-006 rules
     (not incomplete dates; not both-null dates)
     else BLOCK APPLY_CONCURRENCY_PRECONDITION
       (decide/apply drift — new decide required)
```

Never insert on failed confirm. Never fallback from lost no-match to a different action.

#### `update_version`

```text
  target_id = decision.target_canonical_record_id
  live_target = find active by record_id
  IF missing / not active → BLOCK APPLY_STALE_ROW_VERSION
  IF live_target.row_version != decision.expected_row_version → BLOCK APPLY_STALE_ROW_VERSION
  IF edu_identity_key(proposal) != edu_identity_key(live_target) → BLOCK APPLY_CONCURRENCY_PRECONDITION
  IF clearing_fields(proposal, live_target) non-empty → BLOCK APPLY_CONCURRENCY_PRECONDITION
     # defensive: decide should have prevented; never auto-clear at apply
  IF semantic_equal → treat as keep path? → BLOCK APPLY_CONCURRENCY_PRECONDITION
     # action/update intent drift; new decide
  Re-validate is_allowed_auto_delta on differing CONTENT_PATCH_FIELDS
     else BLOCK APPLY_CONCURRENCY_PRECONDITION
```

Optimistic CAS on PPR `expected_updated_at = parse(decision.expected_row_version)` remains mandatory at handler level.

#### `keep_existing`

```text
  live_target active by target_id
  live_target.row_version == decision.expected_row_version
  semantic_equal(proposal_domain, live_domain) is True
  else BLOCK APPLY_STALE_ROW_VERSION (or APPLY_CONCURRENCY_PRECONDITION if identity lost)
  No PPR command
```

#### `manual_review`

No live gate; → `skipped_manual` (after eligibility under lock).

### 6.3 PPR runtime signals (maps to §5.3)

| Signal | §5.3 category | Terminal / rollback |
|--------|---------------|---------------------|
| `SectionOptimisticConcurrencyConflictError` | D | `blocked` + `APPLY_STALE_ROW_VERSION` |
| `SectionDuplicateRecordError` on add/update | D | `blocked` + `APPLY_NO_MATCH_LOST` / `APPLY_CONCURRENCY_PRECONDITION` |
| Retryable technical/infrastructure | E | full U2 rollback; stay `pending` |
| Post-PPR terminal CAS conflict | E | full U2 rollback; stay `pending` |

---

## 7. `to_ppr_command` mapping (education)

### 7.1 Action → command

| Action | PPR command | Notes |
|--------|-------------|-------|
| `add` | `AddEducationRecord` | Domain fields from verified proposal normalized_content |
| `update_version` | `UpdateEducationRecord` via **`update_education_participating`** | Patch CONTENT_PATCH_FIELDS only; identity fields omitted (`None` = keep); no handler bypass |
| `keep_existing` | `None` | Audit terminal only |
| `manual_review` | `None` | `skipped_manual` |
| `supersede` | **forbidden** | System education executor must not emit |

### 7.2 Field mapping

```text
AddEducationRecord:
  person_id            = decision.person_id
  education_kind       = normalized.education_kind
  institution_name     = normalized.institution_name or None   # "" → None
  specialty            = normalized.specialty
  qualification        = normalized.qualification
  started_at           = date.fromisoformat(normalized.started_at) | None
  completed_at         = date.fromisoformat(normalized.completed_at) | None
  diploma_number       = normalized.diploma_number
  document_date        = None                                  # out of recon domain
  metadata             = {
                          "source": "personnel_intake_reconciliation",
                          "document_type": normalized.document_type,  # may be null
                          "reconciliation_decision_id": decision.decision_id,
                        }

UpdateEducationRecord:
  person_id            = decision.person_id
  record_id            = decision.target_canonical_record_id
  expected_updated_at  = parse_iso_datetime(decision.expected_row_version)
  education_kind       = None                                  # keep
  institution_name     = None                                  # keep (identity)
  specialty / qualification / started_at / completed_at / diploma_number
                       = proposal domain values for changed patch fields;
                         unchanged patch fields may be omitted (None=keep)
  metadata             = merge(live.metadata, {
                          "document_type": normalized.document_type,
                          "source": "personnel_intake_reconciliation",
                          "reconciliation_decision_id": decision.decision_id,
                        })
                       # only when document_type is among differing fields OR always merge audit keys
```

**Anti-degradation at command layer:** never pass empty string/`null` intending to clear a non-empty canonical SEMANTIC_FIELD. `UpdateEducationRecord` cannot clear via `None` anyway; executor must not invent void/supersede to clear.

### 7.3 Command identity for PPR envelope

```text
command_id = "recon-apply:" + decision.idempotency_key
command_type = ADD_EDUCATION | UPDATE_EDUCATION
correlation_id = cmd.correlation_id or evidence.correlation_id
```

This reuses PPR command idempotency as a **secondary** shield if a future bug splits transactions (should not happen under TXN-EDU-1). Primary shield remains single U2 commit.

---

## 8. Atomicity model (`per_record`)

### 8.1 U2 unit (education)

| Step | In U2 txn? |
|------|------------|
| Unlocked peek (terminal-only) | **No** — outside U2 |
| `SELECT … FOR UPDATE` claim of decision row | Yes (required for pending) |
| Eligibility + deterministic-invalid validation | Yes (under lock only) |
| `pg_advisory_xact_lock` for `add` identity (§5.4) | Yes (before live gate) |
| Proposal digest verification | Yes |
| Live canonical load + gate | Yes |
| PPR participating mutation (`*_participating`) | Yes |
| `transition_to_terminal` | Yes |
| Sibling education decisions | **No** — separate U2 |

### 8.2 Partial failure across section

- Block/commit of decision A **does not** roll back already committed U2 for decision B (INV-REC-010).
- `manual_review` A → `skipped_manual` does **not** block apply of B.
- No `SECTION_ATOMICITY_HOLD` for education (that reason is U3/`all_or_nothing` only).
- Concurrent appliers on the **same** `decision_id`: one row-lock owner; loser waits then replays/redecides (§5.1).
- Concurrent appliers on **different** `decision_id`s with same `add` identity: serialized by §5.4 identity lock; ≤1 active PPR row.

### 8.3 Consistency pairs

| Outcome | PPR SoT | Decision status |
|---------|---------|-----------------|
| Success mutative | Changed | `applied` |
| Success keep | Unchanged | `applied` |
| Success manual | Unchanged | `skipped_manual` |
| Gate / domain block | Unchanged | `blocked` + `failure_evidence` |
| Deterministic non-executable intent (§5.3 C) | Unchanged | terminal `failed` + `failure_evidence` |
| Invocation / routing / digest mismatch (§5.3 A/B) | Unchanged | stays **`pending`** (U2 rollback; no status write) |
| Retryable technical/infrastructure error | Unchanged | stays **`pending`** (full U2 rollback) |
| Terminal CAS conflict after PPR mutation | Unchanged | stays **`pending`** (full U2 rollback) |
| Proposal digest mismatch | Unchanged | stays **`pending`** (no status write) |
| Process crash mid-U2 before commit | Unchanged | stays `pending` (retryable) |

---

## 9. Audit / evidence / PPR linkage

### 9.1 Decide-time evidence (unchanged)

WP-005 evidence remains source of match intent. Executor **does not** rewrite decide evidence on success (WP-003 `transition_to_terminal` does not patch `evidence` JSON).

### 9.2 `failure_evidence` (blocked / failed)

Required non-empty object. Minimal education shape:

```text
failure_evidence:                         # only for committed blocked | terminal failed
  source: "intake_reconciliation_apply"
  at: ISO-8601
  gate: "add" | "update_version" | "keep_existing" | "deterministic_failed"
  reason_code: APPLY_* | deterministic failure code
  detail: { ... live ids, observed_row_version, observed_precondition, exception_type ... }
  decision_id: int
  idempotency_key: str
```

Retryable infra errors **do not** write `failure_evidence` (U2 rolls back; row stays `pending`).

### 9.3 Success linkage without schema change

| Mechanism | Role |
|-----------|------|
| `metadata.reconciliation_decision_id` on PPR row | Durable back-pointer from education row → decision |
| `command_id = recon-apply:{idempotency_key}` | Join to PPR command/event store |
| Apply response DTO | `section_record_id`, `ppr_command_id`, `result_updated_at` |

**Open for later persistence WP (not required to start executor):** additive `ppr_command_id` / `result_section_record_id` columns on reconciliation decisions (WP-004 already deferred this).

### 9.4 Keep / manual audit

- `keep_existing` → `applied` with no SoT event (INV-REC-012).
- `manual_review` → `skipped_manual`; no SoT event.

---

## 10. Idempotency, replay, retry / recovery

### 10.1 Apply-time idempotency and retryable pending

| Scenario | Behavior |
|----------|----------|
| Re-apply `applied` / `skipped_manual` | Fast unlocked read OK; `idempotent_replay=true`; **no** PPR call |
| Re-apply `blocked` / terminal `failed` | Not success; `redecide_required=true` |
| Retryable error left row `pending` | Re-claim with `FOR UPDATE` and apply again on the **same** `decision_id` |
| Concurrent double apply on `pending` | One `FOR UPDATE` owner; loser waits, then replay/redecide; ≤1 mutation |
| Proposal digest mismatch | Stay `pending`; raise `PROPOSAL_DIGEST_MISMATCH`; retry with correct payload |

**Retryable technical/infrastructure errors** (deadlock, serialization failure, DB connectivity/timeout, process crash before commit, terminal CAS conflict after PPR in the same U2, etc.):

1. **ROLLBACK entire U2** (PPR + decision writes undone);
2. decision remains **`pending`**;
3. the **same** decision may be applied again — no new decide required.

**Forbidden recovery hacks:** artificially mutating re-supplied payload, `expected_canonical_precondition`, `matcher_version`, or `policy_version` solely to bypass idempotency / mint a new key.

### 10.2 Terminal `failed` vs ordinary redecide

**Terminal `failed`** (§5.3 category **C** only) is for **deterministically non-executable** persisted intent detected by `validate_deterministic_executable_intent` under lock. It is **not** used for transient/infrastructure failures (category E) or invocation/routing errors (category A).

Implications under current WP-003:

- `failed` (like `blocked`) is terminal for that `decision_id`.
- A naïve “just call `decide_section` again” with the **same** intent material produces the **same** `idempotency_key` → engine/repository returns terminal replay / `REDECIDE_TERMINAL_REQUIRES_NEW_INTENT` and **does not** create a new pending decision.
- Therefore ordinary same-intent redecide **cannot** recover `blocked`/`failed`. Product recovery requires a **real** new intent (material SoT/proposal/precondition change that naturally yields a new key) or a future persistence WP — **not** fake version bumps.

**Closed (OQ-008-EDU-RETRY):** retryable path = stay `pending` + re-apply. Terminal `failed` ≠ transient retry bucket.

### 10.3 Stale / concurrent change recovery

| Signal | Status | Next step |
|--------|--------|-----------|
| `APPLY_STALE_ROW_VERSION` | `blocked` | New decide only when intent/precondition naturally changes |
| `APPLY_NO_MATCH_LOST` | `blocked` | Same — new decide after live SoT change |
| `APPLY_CONCURRENCY_PRECONDITION` | `blocked` | Same |
| Retryable technical/infra | stays `pending` | Re-apply same `decision_id` |
| Terminal CAS after PPR | stays `pending` (U2 rolled back) | Re-apply same `decision_id` |
| Terminal `failed` (deterministic) | `failed` | Real new intent required; no fake key bypass |

Never auto-convert blocked update → add (INV-REC-006).

---

## 11. Lifecycle transitions (education)

```text
pending ──apply success (add|update|keep)──────────────► applied
pending ──manual_review────────────────────────────────► skipped_manual
pending ──gate / domain block──────────────────────────► blocked
pending ──deterministic-invalid intent (§5.3 C)──────────► failed (terminal; zero PPR)
pending ──invocation/routing input (§5.3 A)──────────────► pending (U2 rollback; no writes)
pending ──retryable technical/infra / post-PPR CAS fail─► pending (U2 rolled back; re-apply OK)
pending ──PROPOSAL_DIGEST_MISMATCH─────────────────────► pending (no writes; retry payload)

applied / skipped_manual ──re-entry──► same row (response replay only)
blocked / failed ──re-entry──────────► redecide_required
         └── ordinary same-intent decide does NOT create new pending
             (idempotency key terminal replay)
```

Response DTO (apply):

```text
ApplyDecisionResult
  decision: ReconcileDecisionRecord
  idempotent_replay: bool
  result_status:
      "applied"
    | "skipped_manual"
    | "blocked_new_decide_required"
    | "failed_new_decide_required"
    | "idempotent_replay"
    | "retryable_pending"            # U2 rolled back; decision still pending
  ppr_command_id: str | None
  section_record_id: int | None
```

---

## 12. Interaction with plugin surface

WP-007 plugin today is decide-only. WP-008 defines **education apply helpers** (same package, new module) without changing `SectionReconciliationPlugin` protocol in WP-005:

```text
confirm_education_add_precondition(decision, proposal, live_canonicals) -> GateResult
build_education_ppr_command(decision, proposal, live_target|None) -> Add|Update|None
```

Aligns with WP-002 §10.1 plugin apply methods; protocol widening across all sections is deferred to a common executor WP if needed. Education may implement helpers first.

---

## 13. Non-goals

| Non-goal | Rationale |
|----------|-----------|
| Code / migrations | Implementation WP after review |
| Transfer wiring | Integration WP (OQ-003) |
| HR override / supersede auto | Separate HR WP; WP-006 closed no auto-supersede |
| Military U3 / `finalize_batch_terminal` usage | Not education |
| Changing `_education_fingerprint` casing to casefold | PPR guard stays as-is; live identity uses plugin casefold |
| WP-003 evidence patch / new columns | Deferred; linkage via metadata + command_id |
| API/UI | Out |

---

## 14. Test matrix (education apply)

| ID | Case | Setup | Expect |
|----|------|-------|--------|
| EX-01 | Add success | pending add; live none for identity; precondition matches | PPR insert; decision `applied`; metadata has decision_id |
| EX-02 | Keep success | pending keep; live equal + same row_version | no PPR mutation; `applied` |
| EX-03 | Update success | pending update; live active + CAS ok; enrichment delta | `UpdateEducationRecord`; `applied`; updated_at advanced |
| EX-04 | Manual skip | pending manual_review | `skipped_manual`; no PPR |
| EX-05 | Add race lost | concurrent active same identity before apply | `blocked` + `APPLY_NO_MATCH_LOST`; no insert |
| EX-06 | Add set digest drift | other education added (different FP) | `blocked` + `APPLY_CONCURRENCY_PRECONDITION` |
| EX-07 | Update stale version | live `updated_at` ≠ expected | `blocked` + `APPLY_STALE_ROW_VERSION`; no write |
| EX-08 | Keep stale / unequal | target changed semantically | `blocked`; no write |
| EX-09 | Idempotent re-apply applied | call apply twice after success | second `idempotent_replay`; still one PPR row |
| EX-10 | Re-apply blocked | apply on blocked decision | `redecide_required`; no PPR |
| EX-11 | U2 atomicity success | mutation+terminal same commit | no pending+mutated split |
| EX-12 | Retryable technical/infra | injected deadlock/timeout/serialization during/after PPR before commit | **full U2 rollback**; decision stays **`pending`**; SoT unchanged; re-apply same id succeeds when fault cleared |
| EX-12b | Post-PPR terminal CAS conflict | force decision CAS fail after PPR mutation in U2 | **full U2 rollback**; stay `pending`; never commit mutated-but-pending |
| EX-13 | Partial section | two pending; first blocks, second applies | B `applied` independent of A (per_record) |
| EX-14 | Proposal digest mismatch | wrong re-supplied payload under lock | raise `PROPOSAL_DIGEST_MISMATCH`; stay `pending`; zero PPR/status writes; retry with correct payload OK |
| EX-15 | Persisted system supersede | pending `action=supersede` (synthetic persisted row) | under lock: category **C** → `failed` + `failure_evidence` with `SYSTEM_SUPERSEDE_FORBIDDEN`; zero PPR writes; **not** `INVALID_EDUCATION_APPLY_ACTION`; `redecide_required` on re-entry |
| EX-16 | Anti-clear at apply | live non-empty specialty; proposal null (synthetic pending update) | `blocked`; no clear |
| EX-17 | Command id stability | successful add | `command_id=recon-apply:{idempotency_key}` present in PPR command/event path |
| EX-18 | Active-only load | voided same FP present | add gate ignores voided; may apply |
| EX-19 | Concurrent claim (two connections, same decision) | two sessions `apply_decision` same pending | one row-lock owner; loser replays/redecides; ≤1 PPR mutation |
| EX-20 | Same-intent redecide after blocked | `blocked` then `decide_section` identical intent | no new pending row |
| EX-21 | Inter-decision add race (two connections) | two **different** pending `add` decisions, same `person_id` + same `edu_identity_key` | identity lock serializes; **≤1** active PPR row; winner `applied`; loser `blocked` (`APPLY_NO_MATCH_LOST`); no split outcome |
| EX-22 | Deterministic failed (zero PPR) | synthetic pending update with null `target_canonical_record_id` under lock | `failed` + `failure_evidence`; zero PPR writes; `redecide_required` on re-entry |
| EX-23 | Update race on one target | two pending updates same `record_id`; stale `expected_row_version` on one | one `applied`; other `blocked` + `APPLY_STALE_ROW_VERSION`; single coherent row version |

Executor apply rows for transfer E2E — out of WP-008 (integration).

---

## 15. Acceptance checklist

- [x] Education apply uses **U2 per decision**; no shared mutative txn across education decisions
- [x] `section_apply_mode` must be `per_record`
- [x] Eligible actions only: add / update_version / keep_existing / manual_review
- [x] System path never **executes** supersede/void; persisted `supersede` → category **C** terminal `failed` (EX-15)
- [x] Unlocked peek is **terminal-only** (`applied`/`skipped_manual`/`blocked`/`failed`); **no** eligibility on peek
- [x] Pending path: immediate U2 + `SELECT … FOR UPDATE`; eligibility only on `current` under lock
- [x] Only row-lock owner runs verify, gate, and PPR mutation
- [x] Error taxonomy §5.3: A/B/E never write status; C→`failed`; D→`blocked`; deterministic-invalid has executable branch
- [x] `add` uses `pg_advisory_xact_lock` on `(person_id, edu_identity_key)` before live gate (§5.4)
- [x] Inter-decision same-identity add race: ≤1 active PPR row; loser `blocked`; no split outcome (EX-21)
- [x] Update race on one target remains `expected_updated_at` CAS protected (EX-23)
- [x] Live add confirm: identity none + `none-match` precondition equality
- [x] Live update/keep: active target + `expected_row_version` CAS semantics
- [x] Updates go through `update_education_participating` (no handler bypass)
- [x] TXN-EDU-1: committed U2 never splits PPR mutation from decision terminal; post-PPR terminal CAS conflict rolls back entire U2
- [x] Gate failures → `blocked` + non-empty `failure_evidence`
- [x] Retryable technical/infrastructure errors → full U2 rollback → stay `pending` → same decision re-applicable
- [x] Terminal `failed` only for deterministic non-executable intent (not transient errors)
- [x] Ordinary same-intent decide after `blocked`/`failed` does **not** create a new pending row
- [x] No fake payload/precondition/policy_version bypass of idempotency
- [x] `PROPOSAL_DIGEST_MISMATCH` leaves `pending`, zero PPR/status writes, correct-payload retry OK
- [x] Idempotent replay of `applied`/`skipped_manual` performs zero PPR writes
- [x] PPR linkage via `metadata.reconciliation_decision_id` + stable `command_id`
- [x] No WP-003/WP-005/WP-007 API/schema changes required to accept this design
- [x] No transfer/API/UI/HR scope creep
- [x] Test matrix EX-01–EX-23 (incl. EX-19/21 two-connection claim/race, EX-22 deterministic failed) covers education apply risks

---

## 16. Open questions

| ID | Question | Resolution (rev.3) |
|----|----------|--------------------|
| **OQ-008-EDU-PROP** | Where does apply get proposal normalized_content? | **Closed:** re-supply + digest verify. |
| **OQ-008-EDU-RETRY** | How to retry after apply trouble? | **Closed:** retryable infra → stay `pending` + re-apply; terminal `failed` only §5.3 C; same-intent redecide cannot mint new pending. |
| **OQ-008-EDU-LINK** | Durable `ppr_command_id` column? | **Deferred:** metadata + `command_id` sufficient for v1. |
| **OQ-008-EDU-MISMATCH** | Proposal digest mismatch? | **Closed:** stay `pending`; zero writes; `PROPOSAL_DIGEST_MISMATCH`; correct-payload retry OK. |
| **OQ-008-EDU-UPD-API** | Missing `update_education_participating`? | **Closed:** thin wrapper on `PprSectionApplicationService`; no handler bypass. |
| **OQ-008-EDU-KEEP-RV** | Keep gate row_version? | **Closed:** active+equal **and** `expected_row_version`. |
| **OQ-008-EDU-ADD-RACE** | Two pending adds, same identity? | **Closed:** no DB unique; handler is read-before-insert; executor serializes with `pg_advisory_xact_lock(person_id, edu_identity_key)` before live gate; loser `blocked`. |
| **OQ-003** (from 002/004) | Transfer wiring? | Still **integration WP**. |
| **OQ-HR-001** | HR override apply | Separate HR WP. |

---

## 17. Traceability

| Source | Mapping |
|--------|---------|
| 002 §4.4 ApplyStatus transitions | §4, §11 |
| 002 §5.4 apply-gate | §6 |
| 002 §7.1–7.2 U2 per_record | §5, §8 |
| 002 §8 idempotency / replay | §10 |
| 002 §10.1 confirm_add / to_ppr_command | §6, §7, §12 |
| 004 executor deferrals / `ppr_command_id` | §9, OQ-008-EDU-LINK |
| 006 §7 / §10 executor deferrals; no auto-supersede | §7, §13 |
| 003 `transition_to_terminal` | §2.2, §5 |
| 005 precondition token formats | §2.1, §6 |
| 007 SEMANTIC_FIELDS / identity / per_record | §2.1, §5.4, §7 |
| PPR `Add`/`Update` education handlers + `_assert_no_duplicate_education` | §2.3, §5.4, §7 |
| `person_education` schema (no active identity UNIQUE) | §2.3, §5.4, OQ-008-EDU-ADD-RACE |

---

## 18. Review notes

### 18.1 rev.3 → rev.4

| Review item | Change in rev.4 |
|-------------|-----------------|
| Persisted `action=supersede` | **Category C** only: `validate_deterministic_executable_intent` → `SYSTEM_SUPERSEDE_FORBIDDEN` → `pending→failed` under lock with `failure_evidence`; zero PPR. **Removed** from §4.2 eligibility as category A |
| `INVALID_EDUCATION_APPLY_ACTION` | Category **A** reserved for **unknown/unsupported** `action` values outside the contract set |
| EX-15 | Updated to expect terminal `failed`, not eligibility rollback |

### 18.2 rev.2 → rev.3

| Review item | Change in rev.3 |
|-------------|-----------------|
| Unlocked peek | **Terminal-only** returns; pending → immediate U2 + `FOR UPDATE`; **removed** `ASSERT eligibility(peek)`; all §4.2 checks under lock only |
| Error taxonomy | Normative §5.3 table A–F; executable `validate_deterministic_executable_intent` → `failed`; removed ambiguous “may terminal→failed” comment |
| Inter-decision add race | Research: no DB unique; read-before-insert only; **`pg_advisory_xact_lock(person_id, edu_identity_key)`** before live gate; EX-21 |
| Update race | Explicitly unchanged: `expected_updated_at` CAS; EX-23 |
| TXN-EDU-1 / §8 / checklist / OQ | Aligned to rev.3 |

### 18.3 Summary

WP-008 rev.4 resolves the supersede contradiction: eligibility no longer rejects persisted supersede; it is deterministically terminal-failed under lock with `SYSTEM_SUPERSEDE_FORBIDDEN`, while unknown actions remain category A invocation errors.
