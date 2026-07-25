--------------------------------------------------

Document Status

Document:
WP-PPR-CARD-COORDINATION-002

Title:
Re-application Collection Reconciliation — Application/Domain Contract

Type:
Architecture Work Package (application/domain contract only)

Status:
Draft — Ready for Architecture Review (rev.3)

Revision:
3

Date:
2026-07-24

Depends on:
WP-PPR-CARD-COORDINATION-001 rev.6 (HR Q1–Q7 approved; Q8 deferred),
WP-PR-003, WP-PR-007, WP-PR-008, WP-PPR-APPLICANT-001A, ARCH-002, ADR-054

Purpose:
Минимальный application/domain contract обработки коллекций из повторной personnel application после terminal application: форма решения, инварианты, audit/evidence, транзакционная граница, idempotency. Без реализации.

Out of scope:
Код, API, БД, миграции (Alembic), matcher разделов, UI кадровика, commit/push, изменение transfer integration.

Addresses gaps (normative target):
GAP-020D, GAP-020E, GAP-020F (HR Q7); education ambiguity (HR Q3).

--------------------------------------------------

# WP-PPR-CARD-COORDINATION-002 — Re-application Reconciliation Contract

## 1. Назначение и границы

### 1.1 Проблема

После terminal personnel application допускается новая application (`INV-APP-020C` / `test_terminal_status_allows_new_application`). Текущий transfer:

- для `employment_biography` может потенциально делать blind append (GAP-020D);
- для `education` / `training` блокируется duplicate fingerprint без пути match → action (GAP-020E);
- для `military` блокируется one-active-record guard без reconciliation path (GAP-020F).

HR Q7 (001 §12): при повторной анкете **запрещён blind append** — для каждой proposal record нужны match и явное действие
`add` / `update_version` / `supersede` / `keep_existing` / `manual_review`.

### 1.2 Роль этого WP

| Этот WP определяет | Этот WP не определяет |
|--------------------|----------------------|
| Единую **форму решения** (DTO/типы/состояния) | Fingerprints и matching rules разделов |
| Инварианты fail-closed | UI кадровика / queue UX |
| Audit evidence на каждое решение | Конкретный DDL/Alembic (см. OQ-001 recommendation) |
| Границу транзакции и partial apply | Интеграцию в `transfer_intake_to_ppr` |
| Idempotency key и защиту от повторного apply | Конкретные PPR command payloads per field |
| Plugin-точки для section matchers | Авто-merge / авто-delete неоднозначных записей |

### 1.3 Нормативные HR-решения (из 001 rev.6)

| ID | Правило | Влияние на контракт |
|----|---------|---------------------|
| **Q3** | Неоднозначное образование не объединять и не удалять автоматически | `manual_review` обязателен; запрещены auto-merge / auto-void / auto-supersede при ambiguity |
| **Q7** | Нет blind append; только match + action | `add` допустим только при **confident no-match**; semantic equal → `keep_existing`, не новая версия |
| **Q8** | UEPC Unified Spec отсутствует; не додумывать | См. §9 Doc gaps; останавливается только зависимый slice |

### 1.4 Область коллекций (целевые потребители контракта)

| `section_code` (intake / domain) | Canonical SoT | Matcher ownership | Первый consumer WP (предполагаемый) |
|--------------------------------|---------------|-------------------|-------------------------------------|
| `education` | `person_education` | Section-owned | WP-PPR-CARD-COORDINATION-003+ |
| `training` | `person_training` | Section-owned | WP-PPR-CARD-COORDINATION-003+ |
| `employment_biography` | `person_external_employment` | Section-owned | WP-PPR-CARD-COORDINATION-003+ |
| `military` | `person_military_service` | Section-owned | WP-PPR-CARD-COORDINATION-003+ |

`relatives` и scalar-разделы **вне обязательного scope** этого контракта; при подключении обязаны соблюдать ту же форму решения.

---

## 2. Термины

| Term | Meaning |
|------|---------|
| **Proposal record** | Элемент коллекции из accepted intake payload; не SoT |
| **Canonical record** | Запись SoT раздела PPR (обычно active при match) |
| **Match outcome** | Результат section matcher: `none` / `exact_one` / `ambiguous` / `stale_target` |
| **Semantic equality** | Plugin-нормализованное содержимое proposal ≡ canonical (digests equal under shared algorithm) |
| **Reconciliation decision** | Нормализованное решение: **action** + evidence + (опц.) target; отдельно **apply_status** |
| **Blind append** | `add` без confident match outcome `none` (включая «не смогли сопоставить → добавим») |
| **Confident match** | `exact_one` + `matched_canonical_record_id` + `confidence=high` |
| **Confident no-match** | `none` + `confidence=high` (явное «новая запись», не «неизвестно») |
| **Apply** | Исполнение decision через PPR section commands (WP-PR-008) или no-mutation path для `keep_existing` / `manual_review` |
| **Idempotent replay** | Повторный вызов с тем же execution intent / idempotency key возвращает prior **persisted** decision без новых SoT writes и **без** смены terminal `apply_status` на «replayed» |
| **Execution intent** | Полный набор полей, входящих в idempotency key (§8); HR override = новый intent |

---

## 3. Pipeline (логический)

```text
Input (person_id, application_id, section_code, proposal[], canonical[])
    ↓
Per proposal: SectionMatcher.match(...)     ← section-owned, NOT part of this WP
    ↓
DecisionNormalizer (this contract)
    → action ∈ {add, update_version, supersede, keep_existing, manual_review}
    → NEVER returns blocked as action
    ↓
Persist decision (pending) + evidence
    ↓
Executor apply-gate (live preconditions inside txn — §5.4 / §7)
    → success: apply_status = applied | skipped_manual
    → invariant/stale/concurrency failure: apply_status = blocked | failed
    ↓
Response may set idempotent_replay=true without mutating persisted apply_status
```

**Ключевое разделение:**

- **Matcher** — section-specific fingerprints/rules.
- **Normalizer** — только `ReconcileAction` (+ reason); не `ApplyStatus`.
- **Executor** — `ApplyStatus`, live precondition re-check, PPR commands.
- **Audit / idempotency** — общие; форма решения едина, matcher — нет.

---

## 4. DTO / типы контракта

### 4.1 Вход

```text
ReconcileSectionInput
  person_id: int
  application_id: int
  section_code: SectionCode
  proposal_records: list[ProposalRecordRef]
  canonical_records: list[CanonicalRecordRef]   # snapshot at decide time
  correlation_id: str | None
  mode: "decide_only" | "decide_and_apply"
  decision_source: "system" | "hr"              # default system
  override_token: str | None                    # required when decision_source=hr
  digest_algorithm_version: str                 # e.g. "canon-json-v1"
  policy_version: str                           # section policy tag used for exact-action choice
```

```text
ProposalRecordRef
  proposal_index: int                           # stable 0..N-1 within (application_id, section_code)
  proposal_fingerprint: str                     # opaque; section matcher helper
  normalized_content: mapping                   # plugin-normalized; input to shared digest
  payload_digest: str                           # shared algorithm over normalized_content
  raw_payload: mapping                          # opaque to common contract
```

```text
CanonicalRecordRef
  record_id: int
  lifecycle_status: "active" | "superseded" | "voided" | ...
  row_version: str | datetime | int             # concurrency token (WP-PR-008 §8)
  record_fingerprint: str
  normalized_content: mapping
  payload_digest: str
```

### 4.2 Match outcome (matcher → normalizer)

```text
MatchOutcome
  kind: "none" | "exact_one" | "ambiguous" | "stale_target"
  confidence: "high" | "low"                    # low ⇒ never drives mutative/keep auto path
  matched_canonical_record_id: int | None
  candidate_canonical_record_ids: list[int]     # non-empty when kind=ambiguous
  semantically_equal: bool | None               # required when kind=exact_one and confidence=high
  matcher_rule_id: str
  matcher_version: str
  detail: mapping
```

| kind | Meaning | Allowed **actions** after normalize |
|------|---------|-------------------------------------|
| `none` + `high` | Уверенно новая запись | `add` |
| `none` + `low` | Нет уверенности | `manual_review` only |
| `exact_one` + `high` + `semantically_equal=true` | Тот же факт уже в SoT | `keep_existing` |
| `exact_one` + `high` + `semantically_equal=false` | Тот же identity, другое содержимое | `update_version` или `supersede` (section policy) |
| `exact_one` + `low` | Сомнительный single hit | `manual_review` only |
| `ambiguous` | ≥2 targets / conflicting signals | `manual_review` only |
| `stale_target` | Target не active / decide-time version unusable | `manual_review` only |

`blocked` **не** является action и **не** возвращается normalizer.

### 4.3 Решение (единая форма)

```text
ReconcileDecision                          # persisted shape
  decision_id: str                         # UUID
  person_id: int
  application_id: int
  section_code: SectionCode
  proposal_index: int
  action: ReconcileAction                  # §4.3.1 — never "blocked"
  match: MatchOutcome
  target_canonical_record_id: int | None   # keep_existing|update_version|supersede
  expected_row_version: str | None         # required for update_version|supersede;
                                           # for keep_existing: captured for evidence/precondition
  expected_canonical_precondition: str     # §8 — opaque token (version / none-match set digest)
  reason_code: DecisionReasonCode
  evidence: DecisionEvidence
  decided_at: datetime                     # UTC
  decision_source: "system" | "hr"
  override_token: str | None
  matcher_rule_id: str
  matcher_version: str
  policy_version: str
  digest_algorithm_version: str
  idempotency_key: str
  apply_status: ApplyStatus                # persisted; §4.4 — no "replayed"
```

#### 4.3.1 `ReconcileAction`

```text
ReconcileAction =
  "add"
  | "update_version"
  | "supersede"
  | "keep_existing"
  | "manual_review"
```

| Action | Meaning | Canonical effect when apply succeeds |
|--------|---------|--------------------------------------|
| `add` | Новая SoT-запись | `AddSectionRecord` |
| `update_version` | Изменение active записи без смены identity | `UpdateSectionRecord` |
| `supersede` | old → superseded, new → active (atomic pair) | `SupersedeSectionRecord` |
| `keep_existing` | Confident exact + semantic equal | **No** SoT mutation / **no** new version; audit decision only |
| `manual_review` | Автоисполнение невозможно/запрещено политикой | **No** SoT mutation; ждёт HR |

**Запрещено эмулировать:**

- blind append;
- auto-merge / auto-void ambiguous education (HR Q3);
- silent skip без decision + evidence;
- «оставить как есть» через `update_version` no-op или пустой supersede — только `keep_existing`.

### 4.4 `ApplyStatus` (persisted) vs response replay

```text
ApplyStatus =                                # PERSISTED on decision only
  "pending"
  | "applied"                                # intent fulfilled (incl. keep_existing no-mutation)
  | "skipped_manual"                         # action=manual_review completed as non-apply
  | "blocked"                                # cannot execute: invariant / stale / concurrency
  | "failed"                                 # apply attempted; unit rolled back
```

**`replayed` не является persisted ApplyStatus.**

```text
ReconcileDecisionResult                      # response / view DTO (not a new persisted status)
  decision: ReconcileDecision                # apply_status unchanged on replay
  idempotent_replay: bool                    # true ⇒ prior terminal decision returned
  result_status: "fresh" | "idempotent_replay" | "blocked_new_decide_required"
```

#### 4.4.1 Однозначные переходы persisted `apply_status`

```text
                    ┌──────────────────────────────────────────┐
                    │            DecisionNormalizer              │
                    │  emits action only; apply_status=pending │
                    └───────────────────┬──────────────────────┘
                                        ▼
                                     pending
                    ┌───────────────────┼──────────────────────┐
                    ▼                   ▼                      ▼
               applied            skipped_manual            blocked
          (add|update|              (manual_review)     (invariant/stale/
           supersede|                                    concurrency at
           keep_existing)                                 apply-gate)
                    │                                          │
                    │                                          ▼
                    │                               NEW decide → new decision_id
                    │                               (same row does NOT return
                    │                                pending)
                    ▼
               failed ──(retry same decision_id only if §8 allows
                         and preconditions still hold; else new decide)
```

| From | To | When |
|------|-----|------|
| — | `pending` | Normalizer создал decision |
| `pending` | `applied` | Apply-gate OK; mutative command committed **или** `keep_existing` audit committed (U2 / successful U3) |
| `pending` | `skipped_manual` | `action=manual_review`; intentional non-apply (U2 / U3 atomicity-hold txn §7.3.3) |
| `pending` | `blocked` | Apply-gate: stale/concurrency/invariant/`SECTION_ATOMICITY_HOLD`; **no** SoT mutation; нужен **новый** decide. Для `all_or_nothing` — только через §7.3.2 / §7.3.3, **не** оставляя batch в `pending` |
| `pending` | `failed` | Технический сбой apply unit; для `all_or_nothing` — после rollback рабочей U3, через failure-finalization (§7.3.2) |
| `applied` / `skipped_manual` | *(no change)* | Idempotent replay: response flag only |
| `blocked` / `failed` | *(terminal for this decision_id)* | Исправление = **новый** `decision_id` |

Normalizer **никогда** не выставляет `apply_status=blocked` и **никогда** не возвращает action `blocked`.

#### 4.4.2 Инвариант response ↔ persisted status (`all_or_nothing`)

**Запрещено:** response сообщает `blocked` / `failed` / `blocked_new_decide_required`, пока любое decision того же U3 batch остаётся в persisted `apply_status=pending`.

После любого завершённого U3-исхода (успех, failure-finalization, atomicity-hold) **все** decisions batch имеют terminal status: `applied` | `skipped_manual` | `blocked` | `failed`.

### 4.5 `SectionCode`

```text
SectionCode =
  "education"
  | "training"
  | "employment_biography"
  | "military"
```

### 4.6 `DecisionReasonCode`

| Code | Typical action / apply outcome |
|------|-------------------------------|
| `MATCH_NONE_CONFIDENT` | action=`add` |
| `MATCH_EXACT_KEEP` | action=`keep_existing` (semantic equal) |
| `MATCH_EXACT_UPDATE` | action=`update_version` |
| `MATCH_EXACT_SUPERSEDE` | action=`supersede` |
| `MATCH_AMBIGUOUS` | action=`manual_review` |
| `MATCH_CONFIDENCE_LOW` | action=`manual_review` |
| `MATCH_STALE_TARGET` | action=`manual_review` (decide-time stale) |
| `MATCH_FORBIDDEN_BLIND_APPEND` | apply_status=`blocked` if someone attempted illegal add |
| `HR_Q3_NO_AUTO_MERGE` | action=`manual_review` |
| `SECTION_ATOMICITY_HOLD` | apply_status=`blocked` for mutative siblings under `all_or_nothing` |
| `APPLY_STALE_ROW_VERSION` | apply_status=`blocked` (update/supersede/keep precondition) |
| `APPLY_NO_MATCH_LOST` | apply_status=`blocked` (`add` re-check no longer confident none) |
| `APPLY_CONCURRENCY_PRECONDITION` | apply_status=`blocked` (plugin precondition failed) |
| `IDEMPOTENT_REPLAY` | **response** reason only; persisted status stays `applied`/`skipped_manual` |

Section WPs могут расширять `match.detail`, но **не** вводить новые `ReconcileAction` без revision этого контракта.

### 4.7 Выход секции

```text
ReconcileSectionResult
  person_id: int
  application_id: int
  section_code: SectionCode
  decisions: list[ReconcileDecisionResult]   # coverage complete
  section_apply_mode: "per_record" | "all_or_nothing"
  summary:
    add: int                                 # counts by action
    update_version: int
    supersede: int
    keep_existing: int
    manual_review: int
    blocked: int                             # counts by apply_status=blocked
    failed: int
  idempotent_replay: bool                    # true if call short-circuited as full replay
                                             # (does not rewrite persisted statuses)
```

**Coverage invariant:** каждый `proposal_index` ровно один раз.

---

## 5. Инварианты и fail-closed

### 5.1 Нормативные инварианты

| ID | Invariant | Fail-closed behavior |
|----|-----------|----------------------|
| **INV-REC-001** | Blind append запрещён | `add` только при decide-time `none`∧`high` **и** успешном live re-check (§5.4); иначе `apply_status=blocked`, never insert |
| **INV-REC-002** | Нет уверенного mutate/keep path ⇒ `manual_review` | `ambiguous` \| decide-time `stale_target` \| `confidence=low` ⇒ action=`manual_review` only |
| **INV-REC-003** | Нет auto-merge / auto-delete ambiguity (HR Q3) | → `manual_review` + `HR_Q3_NO_AUTO_MERGE` |
| **INV-REC-004** | Canonical не меняется decision-фазой | `pending` / `manual_review` / `keep_existing` не делают version churn; mutate только executor для add/update/supersede |
| **INV-REC-005** | `update_version`/`supersede` требуют target + `expected_row_version` | Incomplete decide rejected; at apply missing/mismatch → `blocked` |
| **INV-REC-006** | Stale не становится `add` | Любой stale/concurrency failure → `blocked` + новый decide; **запрещён** fallback `add` |
| **INV-REC-007** | Полное покрытие proposal | Incomplete decide → abort decide unit |
| **INV-REC-008** | Matcher section-owned | Нет registered plugin → fail-closed; нет universal matcher |
| **INV-REC-009** | Idempotent execution intent | Same idempotency key → return prior decision; no new SoT rows; persisted status unchanged |
| **INV-REC-010** | Partial independence (`per_record`) | `manual_review` A не блокирует apply B при `per_record` |
| **INV-REC-011** | Decide/apply race closed | See §5.4; concurrent insert between decide and apply for `add` → `blocked`, not insert |
| **INV-REC-012** | `keep_existing` no new version | Audit+idempotency yes; no `Update`/`Supersede`/`Add` |
| **INV-REC-013** | Action ≠ ApplyStatus | `manual_review` is action; `blocked` is apply_status only |

### 5.2 DecisionNormalizer (только action)

```text
normalize(match, section_policy) -> (action, reason_code):
  if match.confidence != high:
      return manual_review, MATCH_CONFIDENCE_LOW
  if match.kind == ambiguous:
      return manual_review, MATCH_AMBIGUOUS   # education may add HR_Q3 in evidence
  if match.kind == stale_target:
      return manual_review, MATCH_STALE_TARGET
  if match.kind == none:
      return add, MATCH_NONE_CONFIDENT
  if match.kind == exact_one:
      if match.semantically_equal is not True and match.semantically_equal is not False:
          return manual_review, MATCH_CONFIDENCE_LOW   # missing flag ⇒ fail-closed
      if match.semantically_equal:
          return keep_existing, MATCH_EXACT_KEEP
      return section_policy.choose_exact_action(...)
          # update_version → MATCH_EXACT_UPDATE
          # supersede → MATCH_EXACT_SUPERSEDE
  return manual_review, MATCH_CONFIDENCE_LOW
```

**Запрещено:** `none`+`low` → `add`; normalizer → `blocked`; semantic equal → `update_version`/`supersede`.

### 5.3 Section atomicity mode

| Mode | Default candidates | Effect |
|------|--------------------|--------|
| `per_record` | education, training, employment_biography | Независимые U2 txns (§7) |
| `all_or_nothing` | military until OQ-002 | Обязательный U3: успешный batch — одна txn; неуспех — rollback рабочей txn + отдельная failure-finalization txn (§7.3) |

До явной фиксации plugin WP: `0..N` → `per_record`; `military` → fail-closed default `all_or_nothing` (OQ-002).

### 5.4 Apply-gate: закрытие race decide → apply

Все live checks выполняются **внутри** apply-транзакции соответствующего unit (§7).

| Action | Live precondition inside apply txn | On failure |
|--------|--------------------------------------|------------|
| `update_version` / `supersede` | Target exists, `lifecycle_status=active`, `row_version == expected_row_version` | `apply_status=blocked` + `APPLY_STALE_ROW_VERSION`; **new decide**; never fallback `add` |
| `keep_existing` | Target still active; semantic equality still holds (re-digest or plugin confirm); optional row_version match per plugin | `blocked` + stale reason; **new decide**; no mutation |
| `add` | **Обязательно** повторно подтвердить confident no-match на актуальном canonical set **или** эквивалентный section/plugin concurrency precondition (e.g. lock/predicate «no conflicting fingerprint») | `blocked` + `APPLY_NO_MATCH_LOST` / `APPLY_CONCURRENCY_PRECONDITION`; **new decide**; **never** insert; **never** fallback `add` after lost no-match |
| `manual_review` | No SoT mutation | `skipped_manual` |

Decide-time canonical snapshot **недостаточен** для `add` commit.

---

## 6. Audit evidence

Каждый `ReconcileDecision` обязан нести `DecisionEvidence`. Absent evidence → invalid (fail-closed).

### 6.1 Обязательные поля

```text
DecisionEvidence
  source: "intake_reconciliation"
  application_id: int
  section_code: SectionCode
  proposal_index: int
  proposal_fingerprint: str
  proposal_payload_digest: str
  digest_algorithm_version: str
  match_kind: MatchOutcome.kind
  match_confidence: MatchOutcome.confidence
  semantically_equal: bool | None
  matcher_rule_id: str
  matcher_version: str
  policy_version: str
  candidate_canonical_record_ids: list[int]
  matched_canonical_record_id: int | None
  canonical_payload_digest_at_match: str | None
  expected_canonical_precondition: str
  action: ReconcileAction
  reason_code: DecisionReasonCode
  decision_source: "system" | "hr"
  override_token: str | None
  before_snapshot_ref: str | None
  after_intent_digest: str              # for keep_existing: equals before / canonical digest
  correlation_id: str | None
  idempotency_key: str
```

### 6.2 Evidence по action

| Action | Дополнительно обязательно | SoT event intent |
|--------|---------------------------|------------------|
| `add` | `match_kind=none`, `confidence=high`; live re-check evidence on apply | `PPR_SECTION_UPDATED` create |
| `update_version` | target, `expected_row_version`, before digest | `PPR_SECTION_UPDATED` update |
| `supersede` | old id, replacement intent, `expected_row_version` | `PPR_SECTION_SUPERSEDED` + new update |
| `keep_existing` | target id, both digests equal, `MATCH_EXACT_KEEP` | **No** SoT event; reconciliation audit only |
| `manual_review` | reason_code; candidates when ambiguous | **No** SoT event |

### 6.3 Audit sink (контракт persistence readiness)

До executor integration **обязателен** durable per-decision store с unique(`idempotency_key`) — см. §13 OQ-001 recommendation. Alembic/DDL **не** входят в этот WP.

При idempotent replay: вернуть тот же `decision_id` и тот же persisted `apply_status`; response `idempotent_replay=true`; новых SoT events нет.

---

## 7. Граница транзакции и частичное применение

### 7.1 Единицы работы

| Unit | Scope | Когда обязателен | Commit rule |
|------|-------|------------------|-------------|
| **U1 Decide** | `(application_id, section_code)` → all decisions | Always | Полный coverage; иначе abort decide, zero apply |
| **U2 Apply record** | one decision | **Только** `section_apply_mode=per_record` | Одна DB-транзакция: live apply-gate + PPR mutation (если нужна) + audit terminal status + idempotency write |
| **U3 Apply section batch** | all decisions of section | **Обязателен** при `all_or_nothing` (не optional) | См. §7.3: successful U3 **или** rollback + failure-finalization **или** atomicity-hold txn; U2 не используется |

### 7.2 `per_record`

1. Decide (U1) полный.
2. Каждый применимый decision — свой U2:
   - `manual_review` → `skipped_manual`;
   - `keep_existing` → `applied` (audit only);
   - `add`/`update_version`/`supersede` → gate + command → `applied`, или `blocked`/`failed`.
3. Failure/blocked одного U2 **не** откатывает уже committed siblings.
4. Compensation = новый decide / HR.

### 7.3 `all_or_nothing` (U3 обязателен)

1. Decide (U1) полный; все decisions batch стартуют как `pending`.
2. U2 **не** используется.
3. Исход U3 — ровно один из путей ниже. Смешивать «rollback SoT, но decisions остались `pending`» **запрещено** (§4.4.2).

#### 7.3.1 Успешная U3 (одна DB-транзакция)

В **одной** рабочей транзакции коммитятся вместе:

- все live apply-gates batch;
- все PPR mutations batch (если есть);
- terminal audit / `apply_status` updates (`applied` и/или `skipped_manual` по действиям);
- idempotency linkage.

Условие входа: нет `manual_review`, запрещающего partial materialization (§7.3.3), и все gates для mutative/`keep_existing` проходят. После commit **ни одно** decision batch не остаётся `pending`.

#### 7.3.2 Неуспешная U3 (rollback + отдельная failure-finalization)

Если в рабочей U3-транзакции любой live apply-gate / mutative path падает (stale, concurrency, invariant, технический сбой):

1. **Рабочая транзакция полностью rollback** — PPR mutations отсутствуют (SoT unchanged).
2. Затем выполняется **отдельная короткая failure-finalization transaction**, которая атомарно:
   - переводит **все** decisions этого batch из `pending` в `blocked` или `failed` (по характеру причины; один batch — согласованная классификация);
   - сохраняет evidence причины на каждом decision (или batch-linked evidence, доступное с каждого decision).
3. Только после commit failure-finalization response может сообщать `blocked` / `failed` / `blocked_new_decide_required`.
4. Caller инициирует **новый** decide (новые `decision_id`); зависших `pending` нет.

**Запрещено:** откатить рабочую txn и вернуть response `blocked`, оставив decisions в `pending`.

#### 7.3.3 `manual_review` при запрете partial materialization (один исход)

Если section policy запрещает partial materialization и в batch есть хотя бы один `action=manual_review`:

- canonical / PPR mutations **не** выполняются;
- каждый `manual_review` → persisted `apply_status=skipped_manual`;
- каждый зависимый mutative / `keep_existing` decision → persisted `apply_status=blocked` + reason `SECTION_ATOMICITY_HOLD`;
- эти terminal statuses (+ evidence + idempotency linkage без mutative command ids) фиксируются **одной** DB-транзакцией **без** PPR mutations;
- после commit зависших `pending` нет.

Это не «failure-finalization после rollback мутаций»: мутации не начинаются. Отдельный выбор реализации («commit hold» vs «abort attempt») **не допускается** — нормативен только этот исход.

### 7.4 Связь с transfer

`transfer_intake_to_ppr` (INV-TRANSFER-020A/B) остаётся orchestration layer. Контракт задаёт decide/apply port вместо blind `AddSectionRecord`. Transfer-level completed replay по-прежнему short-circuit; record-level защита — §8.

---

## 8. Idempotency и execution intent

### 8.1 Execution intent → idempotency key

Ключ обязан различать разные intents и **не** молча replay-ить решение после смены matcher/policy/digest algorithm.

```text
idempotency_key = durable_hash(
  "recon",
  application_id,
  section_code,
  proposal_index,
  action,
  digest_algorithm_version,              # versioned shared digest algo
  proposal_payload_digest,               # digest under that algorithm
  target_canonical_record_id | "none",
  expected_canonical_precondition,       # row_version | none-match set digest | equality digest
  decision_source,                       # system | hr
  override_token | "none",               # HR override MUST supply distinct token
  matcher_rule_id,
  matcher_version,
  policy_version
)
```

| Change | Effect |
|--------|--------|
| HR override | Новый `override_token` (+ обычно `decision_source=hr`) → **новый** key/intent |
| Matcher or policy version bump | Новый key → **нет** silent replay старого decision |
| Digest algorithm version bump | Новый key |
| Same intent | Lookup prior decision; response `idempotent_replay=true`; persisted status untouched |
| Same logical proposal, different action/target/precondition | Новый key; не overwrite prior applied без явной HR/supersede chain |

### 8.2 Правила replay / conflict

| Scenario | Behavior |
|----------|----------|
| Same key, persisted `applied` or `skipped_manual` | Return same decision; `idempotent_replay=true`; no SoT writes |
| Same key, persisted `blocked` or `failed` | Do not treat as success replay; new decide with new key/precondition (or controlled retry only if documented for `failed` and preconditions still hold) |
| Unique constraint violation on insert of different decision_id with same key | Fail closed — persistence must enforce durable **UNIQUE(idempotency_key)** |
| Completed intake transfer replay | Transfer short-circuit; no new recon applies |

### 8.3 Persistence requirement (pre-executor)

До включения executor в transfer path:

1. Durable per-decision rows (или эквивалент) с **UNIQUE** idempotency key.
2. Link `idempotency_key` ↔ `decision_id` ↔ PPR `command_id` (когда был mutative apply).
3. Alembic **не** создаётся в WP-002; создаётся в persistence/implementation WP после review.

---

## 9. Q8 / Doc gaps

| Gap | Impact on 002 | Rule |
|-----|---------------|------|
| **GAP-018** UEPC Unified Spec | Не блокирует форму решения / txn / idempotency | Не выдумывать UEPC laws; WP-PR-003 + UEPC-UL + inventory 001 |
| GAP-006 richer education FP | Не блокирует 002; может сузить education matcher WP | До ответа HR: `low`/`ambiguous` → `manual_review` |
| Military cardinality (OQ-002) | Не блокирует общий контракт | Default `all_or_nothing` + fail-closed |

---

## 10. Подключение разделов последующими WP

### 10.1 Plugin interface

```text
SectionReconciliationPlugin
  section_code: SectionCode
  section_apply_mode: "per_record" | "all_or_nothing"
  policy_version: str
  build_proposal_refs(payload, digest_algorithm_version) -> list[ProposalRecordRef]
  load_canonical_refs(person_id, digest_algorithm_version) -> list[CanonicalRecordRef]
  normalize_content(record_like) -> mapping          # feeds shared digest algorithm
  match(proposal, canonicals) -> MatchOutcome        # sets semantically_equal for exact_one
  choose_exact_action(match, proposal, target)
      -> "update_version" | "supersede"              # only when not semantically_equal
  confirm_add_precondition(proposal, live_canonicals) -> MatchOutcome | Ok
      # must re-affirm confident none OR section concurrency predicate
  to_ppr_command(decision) -> PprCommand | None      # None for keep_existing / manual_review
```

**Shared digest (норматив рекомендации OQ-005):** common versioned canonical-JSON digest algorithm в common layer; plugin поставляет `normalized_content`, **не** свой несовместимый hash без version tag.

Common engine:

1. Resolve plugin (missing → fail-closed).
2. Build refs → match → normalize (§5.2) → evidence (§6) → persist pending.
3. Apply per §5.4 + §7.

### 10.2 Ожидаемые section WPs

| Order | Section | Matcher notes (informative) | Code anchors (read-only) |
|-------|---------|-----------------------------|--------------------------|
| A | `education` | FP `(kind, institution)`; equal → `keep_existing`; ambiguity → manual (Q3) | `_education_fingerprint`, supersede handler |
| B | `training` | FP `(kind, title, org)`; Q4 may force manual if kind missing | `_training_fingerprint` |
| C | `employment_biography` | Highest blind-append risk; define confident none vs equal vs ambiguous | add/supersede external employment |
| D | `military` | ≤1 active; equal→keep / differ→supersede or manual | `MILITARY_ACTIVE_RECORD_ALREADY_EXISTS` |

### 10.3 Обязанности section WP

1. Fingerprint/match/`semantically_equal` + versions.
2. `choose_exact_action` только для non-equal exact.
3. `confirm_add_precondition` for race-safe `add`.
4. `section_apply_mode` + `policy_version`.
5. Section rows from §11.
6. Не менять enum actions / evidence minima / ApplyStatus model.

### 10.4 Integration WP

- Wire engine into transfer (scope: OQ-003).
- Ensure durable decision store exists **before** executor wiring (OQ-001).
- Preserve `personnel_intake_transfers` idempotency.

---

## 11. Матрица тестов (контрактная)

| # | Case | Setup | Expect |
|---|------|-------|--------|
| T01 | Confident new | `none`/`high` | action=`add` → `applied`; one insert |
| T02 | Blind append forbidden | `none`/`low` or missing match | action=`manual_review` **or** apply `blocked` if illegal add attempted; zero inserts |
| T03 | Exact update | exact, not equal, policy update | `update_version` → `applied` |
| T04 | Exact supersede | exact, not equal, policy supersede | atomic supersede pair |
| T05 | Keep existing | exact/`high` + semantically equal | action=`keep_existing`, reason `MATCH_EXACT_KEEP`; audit written; **no** new canonical version/row |
| T06 | Re-app identical record | terminal→new app→same education/training/emp_bio/military payload as canonical | `keep_existing` + audit; row count unchanged |
| T07 | Ambiguous match | ≥2 candidates | `manual_review`; no merge/delete/update |
| T08 | Education HR Q3 | ambiguous education | no auto-merge/void; `HR_Q3_NO_AUTO_MERGE` or `MATCH_AMBIGUOUS` |
| T09 | Stale at decide | `stale_target` | action=`manual_review` (not blocked action) |
| T10 | Stale at apply (version) | decide update/supersede; concurrent canonical edit | apply_status=`blocked` + `APPLY_STALE_ROW_VERSION`; no mutate; **not** fallback `add`; new decide |
| T11 | Race: insert between decide and apply | decide `add`/`none`/`high`; concurrent conflicting canonical insert before apply | apply re-check fails → `blocked` (`APPLY_NO_MATCH_LOST` or concurrency); **no** insert; new decide |
| T12 | Idempotent re-run | same execution intent twice | response `idempotent_replay=true`; persisted status remains `applied`/`skipped_manual` (**not** `replayed`); no duplicate rows |
| T13 | Matcher/policy version bump | prior applied; new matcher_version/policy_version | **new** key; no silent replay of old decision |
| T14 | HR override key | system decision exists; HR override with override_token | distinct idempotency key / new decision_id |
| T15 | Transfer replay | completed transfer recalled | transfer idempotent_replay; no new recon mutates |
| T16 | Partial apply | one manual_review, one add; `per_record` | manual → `skipped_manual`; add → `applied` (own U2) |
| T17 | all_or_nothing U3 paths | (a) success batch; (b) mid-batch gate fail; (c) manual_review + mutative sibling, no partial materialization | (a) one txn: SoT mutations + terminal statuses + idempotency. (b) working txn rollback → SoT unchanged; failure-finalization txn sets **all** batch decisions `blocked`/`failed` + evidence; **zero** left `pending`; response blocked only after that. (c) one txn, no PPR writes: manual→`skipped_manual`, mutative/keep→`blocked`+`SECTION_ATOMICITY_HOLD`. U2 not used |
| T18 | Coverage | omitted proposal | decide fails |
| T19 | Missing plugin | unregistered section | fail-closed |
| T20 | Re-app emp_bio | overlapping employer/position | not blind duplicate (GAP-020D) |
| T21 | Re-app education | same FP prior row | keep/update/supersede/manual — not hard-fail only (GAP-020E) |
| T22 | Re-app military | active exists | keep/supersede/manual — not second active (GAP-020F) |
| T23 | Action/status separation | normalizer outputs | never emits action=`blocked`; blocked only as ApplyStatus |

---

## 12. Non-goals (этот WP)

| Non-goal | Rationale |
|----------|-----------|
| Реализация section matchers | Section plugin WPs |
| UI кадровика | UX WP |
| Alembic / создание таблиц в этом WP | Persistence WP after review; OQ-001 recommends durable store first |
| Изменение transfer API/routes | Integration WP |
| Универсальный matcher | INV-REC-008 |
| Авто-merge / auto-delete образования | HR Q3 |
| relatives / scalar sections | Out of scope |
| GAP-018 / UEPC Unified Spec | Q8 deferred |
| Commit / push | Excluded |

---

## 13. Open architectural questions

| ID | Question | Architectural recommendation (rev.2) | Still open? | Blocks |
|----|----------|--------------------------------------|-------------|--------|
| **OQ-001** | Физическая форма durable store | **Рекомендация:** dedicated per-decision persistence с **UNIQUE(idempotency_key)** обязательна **до** executor integration. Reuse-only transfer metadata **недостаточен** как единственный store. Конкретное имя таблицы/DDL — implementation WP; **Alembic в 002 не создавать**. | Table shape TBD | Persistence WP before executor |
| **OQ-002** | `military` always `all_or_nothing`? | Fail-closed default `all_or_nothing` | Yes | Military plugin |
| **OQ-003** | Engine на всех transfers или только re-app? | Prefer all collection transfers (safer) | Yes | Integration WP |
| **OQ-004** | exact non-equal: static policy vs HR for update vs supersede? | Static policy for auto-path; HR via override_token | Yes | Section plugins / UI |
| **OQ-005** | Digest algorithm ownership | **Рекомендация:** общий versioned canonical-JSON digest algorithm в common layer; section plugin предоставляет `normalized_content` (+ field set). Section-local opaque hashes без `digest_algorithm_version` — запрещены для idempotency digests. | Algo bytes TBD | Common digest module WP |

---

## 14. Предполагаемые файлы будущей реализации

> Прогноз. **В этом WP не создаются.**

### 14.1 Common

| Path | Role |
|------|------|
| `app/personnel_intake/domain/reconciliation/models.py` | DTOs |
| `app/personnel_intake/domain/reconciliation/actions.py` | actions, reason codes, ApplyStatus |
| `app/personnel_intake/domain/reconciliation/invariants.py` | INV-REC-* |
| `app/personnel_intake/domain/reconciliation/digest.py` | shared versioned canonical-JSON digest |
| `app/personnel_intake/application/reconciliation/normalizer.py` | actions only |
| `app/personnel_intake/application/reconciliation/engine.py` | orchestration |
| `app/personnel_intake/application/reconciliation/executor.py` | apply-gate + commands |
| `app/personnel_intake/application/reconciliation/idempotency.py` | key + replay response |

### 14.2 Plugins

| Path | Role |
|------|------|
| `.../plugins/education.py` | match + semantic equal + add precondition |
| `.../plugins/training.py` | same |
| `.../plugins/employment_biography.py` | same |
| `.../plugins/military.py` | same + atomicity mode |
| `.../registry.py` | section_code → plugin |

### 14.3 Persistence / integration / tests (later WPs)

| Path | Role |
|------|------|
| durable decision repository + **future** Alembic (not in 002) | UNIQUE idempotency_key |
| `transfer_service.py` | wire after persistence ready |
| `tests/personnel_intake/test_reconciliation_contract.py` | T01–T05, T07–T14, T18–T19, T23 |
| `tests/personnel_intake/test_reconciliation_reapplication.py` | T06, T12, T15, T20–T22 |
| `tests/personnel_intake/test_reconciliation_concurrency.py` | T10–T11, T17 |
| `tests/personnel_intake/test_reconciliation_education_ambiguity.py` | T07–T08 |

### 14.4 Не трогать в 002 / до persistence WP

- `corpsite-ui/**`
- `alembic/versions/**` (явно: не в этом document WP)
- universal matcher module

---

## 15. Traceability

| Source | Mapping |
|--------|---------|
| 001 HR Q3 | INV-REC-003, T07–T08 |
| 001 HR Q7 | INV-REC-001/002/012, actions incl. `keep_existing`, T02/T05–T06/T20–T22 |
| 001 HR Q8 / GAP-018 | §9 |
| 001 GAP-020D/E/F | §1.1, T20–T22 |
| WP-PR-008 | apply commands; row_version |
| WP-PR-007 | §6.2 event intent |
| INV-TRANSFER-020A/B | §7.4, T15 |
| INV-APP-020C | re-application precondition |

---

## 16. Review resolution

### 16.1 rev.1 → rev.2

| Review item | Change in rev.2 |
|-------------|-----------------|
| No-mutation identical re-app | Action `keep_existing` + `MATCH_EXACT_KEEP` + T05/T06 |
| Decide/apply race on `add` | §5.4 live re-check; INV-REC-011; T11 |
| `all_or_nothing` txn | U3 mandatory; U2 only `per_record`; T17 |
| `replayed` as ApplyStatus | Removed; response `idempotent_replay` / `result_status`; T12 |
| Idempotency contradictions | Versioned digest + matcher/policy + source/override + precondition in key; UNIQUE constraint requirement; T13–T14 |
| `manual_review` vs `blocked` | Action vs ApplyStatus; normalizer never emits blocked; §4.4.1; T23 |
| OQ-001 / OQ-005 | Recommendations recorded; Alembic still not in 002 |

### 16.2 rev.2 → rev.3

| Review item | Change in rev.3 |
|-------------|-----------------|
| U3 success vs failure contradiction | §7.3.1 successful single txn; §7.3.2 rollback working txn + separate failure-finalization → all `blocked`/`failed` |
| Response `blocked` with `pending` left | Forbidden (§4.4.2) |
| `manual_review` + no partial materialization | Single normative outcome §7.3.3 (`skipped_manual` + sibling `blocked`/`SECTION_ATOMICITY_HOLD`, one txn, no PPR writes) |
| T17 | Asserts SoT rollback, no pending hang, atomic terminal fixation for all three U3 paths |

---

## 17. Acceptance for this document WP (rev.3)

- [x] DTO/типы и состояния (§4), включая `keep_existing`
- [x] `manual_review` (action) vs `blocked` (ApplyStatus) разведены; transitions однозначны
- [x] §4.4.2: response blocked/failed ⇒ no batch decision left `pending`
- [x] Инварианты и fail-closed (§5), включая apply-gate race (§5.4)
- [x] Audit evidence для всех actions, включая `keep_existing` (§6)
- [x] Транзакции: U2 only `per_record`; U3 success / failure-finalization / atomicity-hold (§7.3)
- [x] Idempotency execution intent / key / UNIQUE durability requirement (§8)
- [x] OQ-001 / OQ-005 recommendations; Alembic not created (§13)
- [x] Plugin path (§10)
- [x] Test matrix updated (§11: T01–T23, T17 clarified)
- [x] Non-goals (§12)
- [x] Q8 doc-gap handling (§9)
- [ ] Code / API / DB / migrations — **not started** (by design)

---

*End of WP-PPR-CARD-COORDINATION-002 rev.3. Contract only; implementation deliberately not started. Ready for architecture re-review.*
