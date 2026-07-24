--------------------------------------------------

Document Status

Document:
WP-PPR-CARD-COORDINATION-006

Title:
Education Reconciliation Plugin — Decide-Phase Architecture

Type:
Architecture Work Package (section plugin design only)

Status:
Architecture Approved (rev.3)

Revision:
3

Date:
2026-07-24

Depends on:
WP-PPR-CARD-COORDINATION-002 rev.3 (approved contract),
WP-PPR-CARD-COORDINATION-004 rev.3 (approved engine architecture; commit `4758967453f722dc7d77006ca5dda4d614405e67`),
WP-PPR-CARD-COORDINATION-003 (commit `34598366fc36d14b5ae2f6b2874b4c77598a8b8c` — decision persistence),
WP-PPR-CARD-COORDINATION-005 (commit `c481b44` — common Reconciliation Decision Engine),
WP-PPR-CARD-COORDINATION-001 rev.6 (education field inventory),
WP-PPR-APPLICANT-001A

Purpose:
Описать **decide-phase** `SectionReconciliationPlugin` для `section_code="education"`: proposal/canonical refs, fingerprints, детерминированный match, semantic equality, `choose_exact_action`, HR Q3 / E17, версии matcher/policy и test matrix. Без кода, executor, PPR mutations, transfer wiring, API/UI.

Out of scope:
Код / миграции / Alembic, executor / apply-gate / `confirm_add_precondition` / `to_ppr_command`, PPR writes, `transfer_service` wiring, REST/UI, HR override decide path, изменения WP-003/WP-005, training/employment/military plugins, commit/push.

--------------------------------------------------

# WP-PPR-CARD-COORDINATION-006 — Education Reconciliation Plugin

## 1. Назначение и границы

### 1.1 Проблема

Общий engine (WP-005 / commit `c481b44`) оркестрирует U1 Decide, но **не** знает education semantics. Сегодня transfer по-прежнему делает blind `add_education` и упирается в PPR duplicate guard `_education_fingerprint = (education_kind, institution_name)` (GAP-006 / GAP-020E). Нужен section plugin, который:

- строит `ProposalRecordRef` из accepted intake education slice;
- загружает active canonical `person_education` через PPR read API **внутри plugin**;
- детерминированно выдаёт `MatchOutcome`;
- задаёт static policy для non-equal `exact_one` без auto-degradation canonical данных;
- fail-closed закрывает неполные / year-only даты и ambiguity (HR Q3).

### 1.2 Роль WP-006

| WP-006 определяет | WP-006 не определяет |
|-------------------|----------------------|
| Education `SectionReconciliationPlugin` decide contract | Код реализации |
| Identity / content field sets и match algorithm | Изменения common engine / WP-003 |
| Semantic equality + `choose_exact_action` policy | Executor apply-gate / PPR commands |
| HR Q3 / E17 reason strategy for education | HR override action UI |
| Plugin versions + `section_apply_mode` | Transfer/integration wiring |
| Education test matrix (decide subset) | Training / employment / military plugins |

### 1.3 Жёсткие ограничения

- Plugin **не** мутирует PPR SoT и **не** пишет reconciliation decisions (это engine + WP-003 repository).
- Plugin **не** вызывается engine'ом к PPR read напрямую — только `load_canonical_refs` внутри plugin оборачивает `SectionReadRepository`.
- Digests считает только common `DigestBuilder` (`canon-json-v1`); plugin оставляет `payload_digest=null`, опционально `claimed_payload_digest`.
- `normalized_content` — JSON-native only (WP-004 §3.3.1), включая input-quality block (§4.2).
- Engine path остаётся `decision_source=system` only (WP-004 / WP-005).
- System auto path **никогда** не очищает непустое canonical поле пустым proposal value (§6.5 / §7).

### 1.4 Planned implementation layout (informative; not created here)

| Path | Role |
|------|------|
| `app/personnel_intake/application/reconciliation/plugins/education.py` | `EducationReconciliationPlugin` |
| `tests/personnel_intake/test_reconciliation_education_plugin.py` | Unit match / equality / choose / anti-degradation |
| `tests/personnel_intake/test_reconciliation_education_ambiguity.py` | E17 / T07–T08 / HR Q3 |
| `tests/personnel_intake/test_reconciliation_education_engine_integration.py` | Real plugin + engine (incl. year-only idempotency) |

---

## 2. Исследование кодовой базы (read-only)

### 2.1 Intake education proposal (as-is)

| Concern | Fact |
|---------|------|
| Section code | `education` (`review_status.INTAKE_SECTION_EDUCATION`) |
| Extract | `extract_section_payload` → `draft.payload["education"]` list |
| UI/API shape | `education_type`, `institution`, `year_from`, `year_to`, `specialty`, `qualification`, `document_type`, `diploma_number` |
| Kind map | `resolve_intake_education_kind` — `basic\|internship\|residency\|masters\|phd` → PPR `education_kind` (no intake `other`) |
| Blank type | `normalize_intake_education_type` → `"basic"` (intake submit default; **not** a reconciliation document_type default) |
| Transfer map | `map_education_records` → `education_kind`, `institution_name`, `specialty`, `qualification`, `started_at`, `completed_at`, `diploma_number`, `metadata.{source,document_type}` |
| Dates | Field names historical `year_*`, but submit requires **full calendar day**; year-only / `YYYY-01-01` / `01.01.YYYY` rejected by `is_incomplete_intake_period_date` |
| Submit dup FP | `intake_education_duplicate_fingerprint` = `(kind, institution.strip())` |

### 2.2 PPR education SoT (as-is)

| Concern | Fact |
|---------|------|
| Section | `PPR-EDUCATION` / `person_education` |
| Active load | `SectionReadRepository.load_active_records(person_id, SECTION_CODE_PPR_EDUCATION)` — `lifecycle_status=active` |
| Domain record | `EducationRecord` — `record_id`, kind, institution_*, specialty, qualification, dates, diploma_number, document_date, metadata, lifecycle, `updated_at` |
| Optimistic token | No `record_version` column; WP-005 `CanonicalRecordRef.row_version` ← serialize `updated_at` (ISO) |
| Dup guard | `_education_fingerprint` = `(education_kind, institution_name or "")` among **active** only |
| Commands (executor later) | `AddEducationRecord`, `UpdateEducationRecord`, `SupersedeEducationRecord`, `VoidEducationRecord` |

### 2.3 Common engine contract (WP-005 / `c481b44`)

Plugin must implement `SectionReconciliationPlugin`:

- attrs: `section_code`, `section_apply_mode`, `policy_version`, `matcher_rule_id`, `matcher_version`
- `build_proposal_refs` / `load_canonical_refs` / `match` / `choose_exact_action`

Engine already owns: digest enrichment, `DecisionNormalizer`, evidence assembly, preconditions, idempotency `recon:v1:…`, U1 `begin_nested()`, persist via WP-003.

**Normalizer education-relevant paths:**

| MatchOutcome | Engine/normalizer result |
|--------------|--------------------------|
| `none` + `high` | `add` / `MATCH_NONE_CONFIDENT` |
| `exact_one` + `high` + `semantically_equal=true` | `keep_existing` / `MATCH_EXACT_KEEP` |
| `exact_one` + `high` + `semantically_equal=false` | plugin `choose_exact_action` → `update_version`\|`supersede` |
| `exact_one` + `high` + `semantically_equal=null` | `INVALID_MATCH_OUTCOME` (U1 rollback) — **not** manual |
| `exact_one` + `low` | `manual_review` / `MATCH_CONFIDENCE_LOW` (anti-degradation §6.5) |
| `ambiguous` | `manual_review` / `MATCH_AMBIGUOUS` |
| confidence ≠ `high` | `manual_review` / `MATCH_CONFIDENCE_LOW` |
| `stale_target` | `manual_review` / `MATCH_STALE_TARGET` |

**E17:** education emits `ambiguous` → persisted reason `MATCH_AMBIGUOUS`; Q3 marker lives in `MatchOutcome.detail` (§8.4). No WP-005 change required.

---

## 3. Plugin identity and versions

```text
EducationReconciliationPlugin
  section_code          = "education"
  section_apply_mode    = "per_record"          # INV-REC-010; WP-002 §5.3
  matcher_rule_id       = "EDU-MATCH-v1"
  matcher_version       = "1.0.0"               # bump ⇒ new execution intent
  policy_version        = "1.0.0"               # bump ⇒ new execution intent
```

| Knob | When to bump |
|------|----------------|
| `matcher_version` | Identity key, **identity/text normalization**, match algorithm, semantic field set, input-quality block shape, date precision rules |
| `policy_version` | Auto/manual policy (e.g. both-null dates → confident add; auto-supersede); `choose_exact_action` thresholds |
| `matcher_rule_id` | Only on incompatible rule family rename (rare); prefer version bump |

**Normative:** любое изменение правил strip/casefold identity normalization **требует** `matcher_version` bump.

---

## 4. Input shape and ref building

### 4.1 `section_payload` contract (plugin-owned)

Engine passes an opaque `Mapping`. Education plugin accepts **one** of:

```text
{ "records": [ <IntakeEducation>, ... ] }     # preferred for decide callers
{ "education": [ <IntakeEducation>, ... ] }   # draft-compatible alias
```

- If both present → prefer `records`.
- Missing / non-list → fail-closed `ReconciliationValidationError` (`INVALID_EDUCATION_PAYLOAD`) **before** U1 savepoint (raised from `build_proposal_refs`).
- Empty list → empty proposal tuple → engine `INCOMPLETE_PROPOSAL_COVERAGE` (engine already requires ≥1 proposal). Integration must not call decide for empty accepted education.

`<IntakeEducation>` fields (as-is intake):

```text
education_type, institution, year_from, year_to,
specialty, qualification, document_type, diploma_number
```

### 4.2 Normalization rules → `normalized_content`

All values JSON-native. Domain date fields are **ISO day strings or null** (never datetime objects).

#### 4.2.1 Domain education fields

| Source field | Normalized key | Rule |
|--------------|----------------|------|
| `education_type` | `education_kind` | `resolve_intake_education_kind`; unknown → fail-closed at build (`INVALID_EDUCATION_TYPE`) |
| `institution` | `institution_name` | `strip`; empty → `""` (not null) for FP alignment with PPR storage shape |
| `specialty` | `specialty` | strip; empty → `null` |
| `qualification` | `qualification` | strip; empty → `null` |
| `year_from` | `started_at` | full ISO day → `"YYYY-MM-DD"`; blank / incomplete/year-only → `null` (precision+raw in quality block) |
| `year_to` | `completed_at` | same as `started_at` |
| `diploma_number` | `diploma_number` | strip; empty → `null` |
| `document_type` | `document_type` | strip; **omitted or blank → `null`**; only explicit non-blank token kept (e.g. `"diploma"`, `"certificate"`). **No implicit default to `"diploma"`.** |

**Not in domain compare / future PPR command mapping from decide:** `institution_type`, `document_date`, `employee_context_id`, verification/import audit fields.

#### 4.2.2 Reconciliation input-quality block (digest-stable)

`normalized_content` **MUST** include a stable nested object (proposals and canonicals):

```text
reconciliation_input_quality: {
  started_at:  { precision: "missing"|"day"|"incomplete", raw: string|null },
  completed_at: { precision: "missing"|"day"|"incomplete", raw: string|null },
}
```

| precision | When | `raw` |
|-----------|------|-------|
| `missing` | source absent / whitespace-only after trim | `null` |
| `day` | valid full calendar day | trimmed source token that parsed (or ISO day for canonical) |
| `incomplete` | non-empty after trim but not a full day (year-only `"2019"`, Jan-1 heuristic, `01.01.YYYY`, non-ISO, etc.) | **trimmed raw token as-is** (e.g. `"2019"`, `"2020"`) |

Rules:

- Domain `started_at` / `completed_at` remain `null` when precision ≠ `day`.
- **Semantic equality and future `to_ppr_command` use only domain education fields** (§5.2) — they **ignore** `reconciliation_input_quality`.
- **Common `payload_digest` hashes the full `normalized_content`**, including the quality block → `"2019"`, `"2020"`, and genuinely missing produce **different digests**.
- Incomplete/year-only still force manual_review (§6); fixing year-only to a full day changes digest ⇒ **new** idempotency intent (not conflict with prior year-only decision).

Canonical quality block:

- SoT date present → `precision="day"`, `raw=<ISO day>`;
- SoT date null → `precision="missing"`, `raw=null`.

### 4.3 `ProposalRecordRef`

```text
proposal_index          = stable 0..N-1 in input list order
raw_payload             = shallow copy of intake element (opaque audit)
normalized_content      = domain fields + reconciliation_input_quality (§4.2)
proposal_fingerprint    = EDU identity FP string (§5.1)
claimed_payload_digest  = null   # optional self-check only
payload_digest          = null   # engine fills over full normalized_content
```

### 4.4 `load_canonical_refs`

**Closed (OQ-006-EDU-LOAD):** use `SectionReadRepository.load_active_records` only.

```text
load_canonical_refs(conn, person_id, digest_algorithm_version):
  records = SectionReadRepository(conn).load_active_records(
               person_id, SECTION_CODE_PPR_EDUCATION
             )
  # ONLY lifecycle_status=active (repository filter)
  FOR each EducationRecord r:
    yield CanonicalRecordRef(
      record_id = r.record_id,
      lifecycle_status = "active",
      row_version = isoformat_utc_or_naive(r.updated_at),  # optimistic token
      record_fingerprint = EDU identity FP from canonical fields (§5.1),
      normalized_content = {
        education_kind,
        institution_name ("" if null),
        specialty, qualification,          # null if blank
        started_at / completed_at,         # ISO day or null
        diploma_number,
        document_type,                     # metadata.document_type if non-blank else null
        reconciliation_input_quality: { ... },  # §4.2.2 canonical rules
      },
      claimed_payload_digest = null,
      payload_digest = null,
    )
```

Superseded/voided rows are **not** loaded → they do not participate in match or add precondition digests (WP-005 `build_add_precondition` already filters `lifecycle_status=="active"`).

### 4.5 Identity / text normalization (normative v1)

Conservative matcher over the existing PPR duplicate fingerprint — **not** a byte-identical PPR fingerprint:

| Step | Rule (v1 — normative) |
|------|------------------------|
| Strip | leading/trailing whitespace only |
| Case | storage preserves original casing; identity key and text equality use `casefold()` |
| Internal whitespace | **not** collapsed in v1 (no optional collapse) |
| Empty institution | after strip, `""` → identity incomplete (§6.3) |

```text
edu_identity_key(content) =
  (education_kind, casefold(strip(institution_name)))
```

Canonical `institution_name is None` → treat as `""` before strip/casefold.

Changing this normalization algorithm **requires** `matcher_version` bump.

---

## 5. Fingerprints and semantic fields

### 5.1 Identity fingerprint (matcher helper)

PPR/intake seed (GAP-006): `(education_kind, institution)` among active rows. Education plugin applies §4.5 normalization on top:

```text
proposal_fingerprint / record_fingerprint =
  "edu:" + education_kind + "|" + casefold(strip(institution_name))
```

Used for candidate grouping and opaque helper fields — **not** for `payload_digest` / idempotency.

**Closed (OQ-006-EDU-ID):** v1 identity remains `(kind, casefold(institution))`. Richer identity (e.g. specialty) deferred; would be a `matcher_version` bump after product decision.

### 5.2 Domain content compare set (semantic equality)

```text
SEMANTIC_FIELDS = (
  education_kind,          # also identity
  institution_name,        # casefold(strip) compare
  specialty,               # casefold; null==null
  qualification,           # casefold; null==null
  started_at,              # exact ISO day string or null
  completed_at,            # exact ISO day string or null
  diploma_number,          # casefold; null==null
  document_type,           # casefold; null==null — no default
)
```

`reconciliation_input_quality` is **excluded** from semantic equality.

`semantically_equal = true` iff all SEMANTIC_FIELDS compare equal under §4.5 rules.

### 5.3 Document type (OQ-006-EDU-DOC — closed)

| Source | Normalized `document_type` |
|--------|----------------------------|
| Proposal omitted / blank | `null` |
| Proposal explicit non-blank (e.g. `"diploma"`) | stripped token (e.g. `"diploma"`) |
| Canonical missing / blank `metadata.document_type` | `null` |
| Canonical explicit non-blank | stripped token |

Implications:

- `null` → explicit value: allowed auto enrichment (`update_version`) when otherwise eligible (§7).
- explicit canonical → proposal `null`: **anti-degradation** → `exact_one` + `low` → manual (§6.5).
- No implicit `"diploma"` default on either side.

---

## 6. Matching algorithm

### 6.1 Overview

**Rev.3 ordering:** identity completeness and candidate lookup **precede** input-quality gating. Ambiguity (HR Q3) is evaluated before incomplete-date downgrade; incomplete dates on a unique identity hit yield `exact_one` + `low` (not `none` + `low`).

```text
match(proposal, canonicals) -> MatchOutcome:

  iq = proposal.normalized_content.reconciliation_input_quality
  has_incomplete = (iq.started_at.precision == "incomplete"
                    OR iq.completed_at.precision == "incomplete")

  # --- Step 1: identity completeness (before candidate lookup) ---
  IF identity incomplete (institution empty after strip/casefold):
      RETURN MatchOutcome(
        match_kind="none",
        match_confidence="low",
        semantically_equal=null,
        candidate_canonical_record_ids=(),
        detail={ reason: "INCOMPLETE_IDENTITY", reconciliation_input_quality: iq },
      )

  # --- Step 2: active candidate lookup ---
  candidates = [c in canonicals
                where edu_identity_key(c) == edu_identity_key(proposal)]

  # --- Step 3: ≥2 candidates — ambiguity wins over incomplete dates ---
  IF len(candidates) >= 2:
      RETURN MatchOutcome(
        match_kind="ambiguous",
        match_confidence="high",
        candidate_canonical_record_ids=sorted(ids),
        matched_canonical_record_id=null,
        semantically_equal=null,
        detail={
          reason: "HR_Q3_AMBIGUOUS_IDENTITY",   # Q3 marker (audit)
          identity_key: ...,
          reconciliation_input_quality: iq,       # preserved even if incomplete
        },
      )

  # --- Step 4: exactly one candidate ---
  IF len(candidates) == 1:
      target = candidates[0]
      equal = semantic_equal(domain_fields(proposal), domain_fields(target))
      clearing = clearing_fields(proposal, target, has_incomplete)  # §6.5

      IF has_incomplete:
          RETURN MatchOutcome(
            match_kind="exact_one",
            match_confidence="low",
            matched_canonical_record_id=target.record_id,
            candidate_canonical_record_ids=(target.record_id,),
            semantically_equal=equal,   # may be true; low blocks keep/update
            detail={
              reason: "INCOMPLETE_OR_YEAR_ONLY_DATE",
              reconciliation_input_quality: iq,
              clearing_fields: clearing,
              differing_fields: [...] if not equal else [],
            },
          )

      IF not equal AND clearing != []:
          RETURN MatchOutcome(
            match_kind="exact_one",
            match_confidence="low",
            matched_canonical_record_id=target.record_id,
            candidate_canonical_record_ids=(target.record_id,),
            semantically_equal=false,
            detail={
              reason: "CANONICAL_VALUE_CLEARING_FORBIDDEN",
              reconciliation_input_quality: iq,
              clearing_fields: clearing,
              differing_fields: [...],
            },
          )

      RETURN MatchOutcome(
        match_kind="exact_one",
        match_confidence="high",
        matched_canonical_record_id=target.record_id,
        candidate_canonical_record_ids=(target.record_id,),
        semantically_equal=equal,
        detail={
          reconciliation_input_quality: iq,
          differing_fields: [...] if not equal else [],
        },
      )

  # --- Step 5: zero candidates ---
  IF has_incomplete:
      RETURN MatchOutcome(
        match_kind="none",
        match_confidence="low",
        semantically_equal=null,
        candidate_canonical_record_ids=(),
        detail={
          reason: "INCOMPLETE_OR_YEAR_ONLY_DATE",
          reconciliation_input_quality: iq,
        },
      )

  IF proposal.started_at is null AND proposal.completed_at is null:
      RETURN MatchOutcome(
        match_kind="none",
        match_confidence="low",
        semantically_equal=null,
        candidate_canonical_record_ids=(),
        detail={
          reason: "BOTH_DATES_MISSING",
          reconciliation_input_quality: iq,
        },
      )

  RETURN MatchOutcome(
    match_kind="none",
    match_confidence="high",
    semantically_equal=null,
    candidate_canonical_record_ids=(),
    detail={ reconciliation_input_quality: iq },
  )
```

### 6.2 Outcome → action (via common normalizer + plugin)

| Match | Confidence | Equal | Action path |
|-------|------------|-------|-------------|
| `none` | `high` | n/a | `add` / `MATCH_NONE_CONFIDENT` |
| `none` | `low` | n/a | `manual_review` / `MATCH_CONFIDENCE_LOW` |
| `ambiguous` | `high` | n/a | `manual_review` / `MATCH_AMBIGUOUS` (E17 / HR Q3) |
| `exact_one` | `high` | `true` | `keep_existing` / `MATCH_EXACT_KEEP` |
| `exact_one` | `high` | `false` | `choose_exact_action` (§7) — enrichment / value→value only |
| `exact_one` | `low` | `true` or `false` | `manual_review` / `MATCH_CONFIDENCE_LOW` — **never** keep/update (incomplete or clearing) |
| `stale_target` | `high` | n/a | `manual_review` / `MATCH_STALE_TARGET` (reserved) |

**Note:** `exact_one` + `low` with `semantically_equal=true` (domain equal after null-normalization but incomplete dates) still routes to manual — confidence gate, not equality.

### 6.3 Fail-closed branches (plugin)

| Condition | Behavior |
|-----------|----------|
| Unknown `education_type` | Fail at `build_proposal_refs` — no MatchOutcome |
| Empty institution | `none` + `low` → manual (before candidate lookup) |
| ≥2 active with same identity key | `ambiguous` + `high` → manual (HR Q3); **even if** proposal has incomplete dates; Q3 + input-quality in `detail` |
| Incomplete / year-only + **zero** candidates | `none` + `low` → manual; quality.raw in digest |
| Incomplete / year-only + **exactly one** candidate | `exact_one` + `low` → manual; **matched id + candidate ids retained**; no keep/update even if domain equal |
| Both domain dates null + zero candidates | `none` + `low` → manual (not confident `add`) |
| Canonical non-empty → proposal null/empty on any SEMANTIC_FIELD (no incomplete override) | `exact_one` + `low` → manual; ids retained |
| `exact_one` + `high` without bool `semantically_equal` | Forbidden — engine `INVALID_MATCH_OUTCOME` |

### 6.4 What is intentionally not matched

- Fuzzy institution name similarity (edit distance) — **out**.
- Matching across different `education_kind` — distinct identities.
- Superseded/voided history as decide candidates — **out** (active-only).
- Card display year-truncation (GAP-012) — irrelevant to compare.

### 6.5 Anti-degradation (canonical value clearing)

```text
clearing_fields(proposal, target, has_incomplete):
  fields = []
  FOR field in SEMANTIC_FIELDS:
    IF canonical domain value is non-empty
       AND proposal domain value is empty/null:
         fields.append(field)
  # Incomplete date ⇒ domain date null; if canonical had a day, counts as clearing
  IF has_incomplete:
    IF iq.started_at.precision == "incomplete"
       AND target.started_at is non-null:
         ensure "started_at" in fields
    IF iq.completed_at.precision == "incomplete"
       AND target.completed_at is non-null:
         ensure "completed_at" in fields
  RETURN fields
```

**Non-empty** means: non-null string/date after domain normalization (for `institution_name`, non-empty after strip; identity fields normally already match on `exact_one` path).

When clearing is detected on a unique identity match **without** incomplete-date override:

- `match_kind = exact_one`, `match_confidence = low`
- `matched_canonical_record_id` and `candidate_canonical_record_ids` **retained**
- `semantically_equal = false`
- **never** auto `update_version`

When **incomplete/year-only** on unique identity (§6.1 step 4):

- Always `exact_one` + `low` → manual
- `matched_canonical_record_id` and `candidate_canonical_record_ids` **retained**
- `semantically_equal` computed but **ignored** for auto path — no `keep_existing` / `update_version` even if domain-equal after null-normalization
- `clearing_fields` populated when incomplete/null simultaneously clears a canonical value (e.g. canonical `started_at` day + proposal year-only → domain null)

Applies field-by-field to dates, specialty, qualification, diploma_number, document_type.

---

## 7. Semantic equality and `choose_exact_action`

### 7.1 Equality

See §5.2–§5.3. Null-safe: `null` equals `null`; `null` ≠ non-null.

### 7.2 Static policy (system auto path)

`choose_exact_action` is reached only for `exact_one` + `high` + `semantically_equal=false` (engine). Anti-degradation already filtered clearing cases to `low`.

```text
CONTENT_PATCH_FIELDS = (
  specialty, qualification, diploma_number, document_type,
  started_at, completed_at,
)

is_allowed_auto_delta(proposal_value, canonical_value):
  # value → value change OR null → value enrichment
  IF canonical_value is null AND proposal_value is non-empty: RETURN true   # enrichment
  IF canonical_value is non-empty AND proposal_value is non-empty
     AND values differ: RETURN true                                      # value→value
  IF canonical_value is non-empty AND proposal_value is empty/null: RETURN false  # clearing
  RETURN false  # null→null is equality, not a delta

choose_exact_action(match, proposal, target) -> "update_version" | "supersede":
  ASSERT match.exact_one and match_confidence == high
  ASSERT semantically_equal is False
  ASSERT NOT clearing_fields(proposal, target, has_incomplete=false)

  FOR each differing SEMANTIC_FIELD:
    ASSERT field in CONTENT_PATCH_FIELDS
    ASSERT is_allowed_auto_delta(proposal[field], target[field])

  RETURN "update_version"
```

If assertions fail (should not happen if match §6 is correct) → plugin raises validation error → U1 fail-closed.

**Normative system auto path:**

| Situation | Action |
|-----------|--------|
| All SEMANTIC_FIELDS equal | `keep_existing` |
| Same identity; only null→value and/or value→value on CONTENT_PATCH_FIELDS | **`update_version`** |
| Same identity; any canonical→null clearing | **`manual_review`** (`exact_one`+`low`) |
| Ambiguity (≥2 identity candidates) | **`manual_review`** (`MATCH_AMBIGUOUS`) — even with incomplete dates |
| Incomplete / year-only + zero candidates | **`manual_review`** (`none`+`low`) |
| Incomplete / year-only + exactly one candidate | **`manual_review`** (`exact_one`+`low`; ids retained) |
| Both dates missing + zero candidates | **`manual_review`** (not `add`) |
| ≥1 day-precision date; no identity candidate; no incomplete | **`add`** |
| Auto history replace via supersede | **Not auto** (§7.3) |

### 7.3 `supersede` on education system auto path (OQ-006-EDU-SUP — closed)

Education plugin `choose_exact_action` **never returns `supersede`** on the system auto path.

- Non-equal eligible exact → always `update_version`.
- Supersede remains available to future HR override / executor policy via `policy_version` bump if product later requires it.
- Rationale: auto-supersede is HR-sensitive and close to Q3 risk (silent history split).

---

## 8. Auto vs manual boundary (E17 / HR Q3)

### 8.1 Always `manual_review` (system path)

| Case | MatchOutcome | Reason (engine) | Notes |
|------|--------------|-----------------|-------|
| ≥2 active same `(kind, institution)` | `ambiguous` / `high` | `MATCH_AMBIGUOUS` | Q3 marker + input-quality in `detail`; **even if** year-only/incomplete |
| Incomplete / year-only + **zero** candidates | `none` / `low` | `MATCH_CONFIDENCE_LOW` | quality.raw in digest |
| Incomplete / year-only + **one** candidate | `exact_one` / `low` | `MATCH_CONFIDENCE_LOW` | matched id + candidate ids retained; no keep/update |
| Both domain dates null + zero candidates | `none` / `low` | `MATCH_CONFIDENCE_LOW` | not confident `add` |
| Empty institution / incomplete identity | `none` / `low` | `MATCH_CONFIDENCE_LOW` | before candidate lookup |
| Canonical value clearing (non-incomplete path) | `exact_one` / `low` | `MATCH_CONFIDENCE_LOW` | ids retained |
| Decide-time stale target (if emitted) | `stale_target` | `MATCH_STALE_TARGET` | |

### 8.2 Allowed system auto mutative / keep paths

| Case | Action | Notes |
|------|--------|-------|
| No identity candidate; identity complete; no incomplete dates; **not** both-null dates | `add` | Executor live re-check still required |
| Exact one; full semantic equal; **high** confidence | `keep_existing` | Requires no incomplete dates |
| Exact one; high; only enrichment / value→value content deltas | `update_version` | |

### 8.3 Explicitly forbidden on system auto path

- Auto-merge of ambiguous education rows.
- Auto-void / auto-delete.
- Auto-`supersede`.
- `add` when confidence ≠ high.
- `keep_existing` / `update_version` when `exact_one` + `low` (incomplete or clearing).
- Auto clear of any non-empty canonical SEMANTIC_FIELD.
- Treating year-only / incomplete dates as day-equal to canonical.
- Blind append ignoring identity candidates (GAP-020E / Q7).

### 8.4 E17 / Q3 reason strategy (OQ-006-EDU-Q3R — closed)

| Item | Normative rev.3 |
|------|-----------------|
| Persisted `reason_code` | `MATCH_AMBIGUOUS` (via common normalizer) |
| Q3 audit marker | `MatchOutcome.detail.reason = "HR_Q3_AMBIGUOUS_IDENTITY"` (and identity_key) |
| `HR_Q3_NO_AUTO_MERGE` as persisted reason | **Not** used in rev.3 (would need engine preferred-reason hook) |

---

## 9. Evidence / digests / preconditions (plugin obligations)

| Obligation | Detail |
|------------|--------|
| Digests | Full `normalized_content` including `reconciliation_input_quality`; JSON-native only |
| Semantic / PPR mapping | Domain SEMANTIC_FIELDS only; quality block excluded from equality/commands |
| Ambiguous | non-empty `candidate_canonical_record_ids`; include `reconciliation_input_quality` in `detail` when present |
| Ambiguous + incomplete | still `ambiguous`/`high`/`MATCH_AMBIGUOUS`; **all** candidate ids; Q3 marker; input-quality preserved |
| Exact (high or low) | `matched_canonical_record_id` + `candidate_canonical_record_ids` when unique identity hit |
| Exact + low (incomplete) | ids retained; `clearing_fields` when incomplete clears canonical; no keep/update |
| Exact + high | `semantically_equal` strict bool |
| Match detail | `reconciliation_input_quality` copied into `MatchOutcome.detail` on all paths |
| Fingerprints | non-empty identity helper strings |
| Row version | non-empty `updated_at` token for update path |

Year-only fix idempotency: prior decide with `raw="2019"` vs later decide with full day ⇒ different `proposal_payload_digest` ⇒ different `recon:v1:…` key ⇒ **new** decision (`idempotent_replay=false`), not `ReconciliationConflictError`.

---

## 10. Deferred to executor / integration (not WP-006)

| Item | Owner |
|------|-------|
| `confirm_add_precondition` (live none re-check / FP lock) | Executor WP |
| `to_ppr_command` → `Add` / `Update` / (`Supersede` only if future policy) | Executor WP |
| Wire `decide_section` into transfer after accept | Integration WP (OQ-003) |
| HR override action selecting supersede/manual resolution | Separate HR WP |
| Richer identity than `(kind, institution)` | Future `matcher_version` |
| Relax both-null → confident `add` | Future `policy_version` bump |

---

## 11. Test matrix (education plugin + engine)

| ID | Case | Setup | Expect |
|----|------|-------|--------|
| EDU-01 | Confident new | no identity match; ≥1 day-precision date; no incomplete | `add` / `MATCH_NONE_CONFIDENT` |
| EDU-02 | Re-app identical | active equal on all SEMANTIC_FIELDS | `keep_existing` |
| EDU-03 | Exact enrichment / value→value | same identity; null→value and/or value→value on patch fields | `update_version`; `expected_row_version` set |
| EDU-04 | Ambiguous Q3 | two active same kind+institution | `manual_review` / `MATCH_AMBIGUOUS`; all candidate ids; detail Q3 marker |
| EDU-04a | Ambiguity + year-only | ≥2 candidates + proposal `year_from="2019"` | `ambiguous`/`high`/`MATCH_AMBIGUOUS`; candidate ids set; input-quality in detail; **not** `none`+`low` |
| EDU-05a | Year-only, zero candidates | proposal `year_from="2019"`; no identity match | `none`+`low`/`MATCH_CONFIDENCE_LOW`; quality.raw=`"2019"`; domain date null |
| EDU-05b | Year-only, one candidate | proposal `year_from="2019"`; one active match | `exact_one`+`low`/`MATCH_CONFIDENCE_LOW`; matched id + candidate ids retained; no keep/update even if domain equal |
| EDU-05c | Digest distinct incomplete vs missing | `"2019"` vs `"2020"` vs omitted | three different `payload_digest`s |
| EDU-05d | Year-only fix idempotency | decide with `"2019"` then re-decide with full ISO day | new intent / new decision_id; **not** conflict |
| EDU-06 | Empty institution | institution blank | `manual_review` / low; not `add` |
| EDU-07 | Unknown education_type | bad type | fail at build; zero decisions |
| EDU-08 | Different kind same school | basic@X vs masters@X | `add` if dates allow confident none |
| EDU-09 | Casefold institution | `"МГУ"` vs `"мгу"` | identity match (no whitespace-collapse) |
| EDU-10 | Null→value specialty | canonical null; proposal non-empty | `update_version` |
| EDU-11 | choose never supersede | eligible non-equal exact high | `choose_exact_action==update_version` |
| EDU-12 | Matcher version bump | same payload; matcher_version+ | new idempotency key |
| EDU-13 | Coverage / ordering | N records | indices 0..N-1; ordered `decision_ids` |
| EDU-14 | Inactive ignored | superseded/voided same FP not loaded | match vs **active** only |
| EDU-15 | Engine U1 rollback | partial invalid later proposal | zero new rows from call |
| EDU-16 | E17 | ambiguous education | manual; `MATCH_AMBIGUOUS` + detail Q3 marker |
| EDU-17 | document_type omitted | proposal omits/blank document_type | normalized `null` (no default) |
| EDU-17a | document_type enrichment | canonical null; proposal `"diploma"` | `update_version` |
| EDU-17b | document_type clearing | canonical `"diploma"`; proposal null | `exact_one`+`low` → manual; ids retained |
| EDU-18 | Both dates missing | complete identity; both dates null/missing; no candidate | `none`+`low` → **manual**, not `add` |
| EDU-19a-blank | Clear exact date (blank) | canonical `started_at` day; proposal blank→domain null | `exact_one`+`low`; matched id + candidate ids retained |
| EDU-19a-year | Clear exact date (year-only) | canonical `started_at` day; proposal `year_from="2019"` | `exact_one`+`low`; ids retained; `clearing_fields` includes `started_at` |
| EDU-19b | Clear specialty | canonical non-empty; proposal null | `exact_one`+`low` → manual |
| EDU-19c | Clear qualification | same | `exact_one`+`low` → manual |
| EDU-19d | Clear diploma_number | same | `exact_one`+`low` → manual |
| EDU-19e | Clear document_type | canonical explicit; proposal null | `exact_one`+`low` → manual |

Executor apply rows — **out of WP-006**.

---

## 12. Acceptance checklist (approved)

- [x] Plugin scoped to `section_code=education` decide-phase only
- [x] `section_apply_mode=per_record`
- [x] Identity key `(education_kind, casefold(strip(institution)))`; strip+casefold normative; no internal whitespace collapse in v1
- [x] Identity described as conservative matcher over PPR dup FP (not byte-identical); normalization changes bump `matcher_version`
- [x] SEMANTIC_FIELDS include specialty/qualification/exact dates/diploma/document_type; quality block excluded from equality
- [x] `reconciliation_input_quality` in `normalized_content`; digests differ for `"2019"` / `"2020"` / missing
- [x] Input-quality gating **after** identity lookup; ambiguity before incomplete downgrade (§6.1 rev.3)
- [x] Year-only: zero candidates → `none`+`low` (EDU-05a); one candidate → `exact_one`+`low` with ids (EDU-05b); ambiguity+incomplete → `MATCH_AMBIGUOUS` (EDU-04a)
- [x] Year-only fix → new intent (EDU-05d)
- [x] Anti-degradation: canonical non-empty → proposal null ⇒ `exact_one`+`low` with ids retained (EDU-19b–e, EDU-17b); date clearing blank vs year-only (EDU-19a-blank/a-year)
- [x] Incomplete exact-one never keep/update even if domain-equal
- [x] Auto `update_version` only for null→value or value→value
- [x] No document_type default; OQ-006-EDU-DOC closed
- [x] Both-null dates ⇒ not confident `add` (EDU-18); OQ-006-EDU-DATE closed
- [x] Ambiguity → `MATCH_AMBIGUOUS` + Q3 detail marker; OQ-006-EDU-Q3R closed
- [x] No auto-supersede; OQ-006-EDU-SUP closed
- [x] Identity stays `(kind, institution)` in v1; OQ-006-EDU-ID closed
- [x] Load via `SectionReadRepository.load_active_records`; OQ-006-EDU-LOAD closed
- [x] `exact_one`+`high` always sets bool `semantically_equal`
- [x] No WP-003/WP-005 API/schema changes required
- [x] Test matrix EDU-01–EDU-19e + EDU-04a + EDU-05a–d + EDU-19a-blank/a-year covers decide scope
- [x] Executor / transfer / HR override deferred

---

## 13. Open questions — closed in rev.2

| ID | Resolution (rev.2) |
|----|--------------------|
| **OQ-006-EDU-SUP** | **Closed** — no auto-`supersede` on system path; always `update_version` when eligible. |
| **OQ-006-EDU-Q3R** | **Closed** — persisted reason `MATCH_AMBIGUOUS`; Q3 marker in `MatchOutcome.detail`. |
| **OQ-006-EDU-DOC** | **Closed** — omitted/blank → `null` both sides; only explicit tokens kept; null→value enrich OK; value→null manual. |
| **OQ-006-EDU-ID** | **Closed** — v1 identity `(kind, casefold(institution))`; richer key needs future `matcher_version`. |
| **OQ-006-EDU-DATE** | **Closed** — both-null dates do **not** yield confident `add` → `manual_review`; relax only via `policy_version` bump. |
| **OQ-006-EDU-LOAD** | **Closed** — `SectionReadRepository.load_active_records`. |

No open education-plugin OQs remain for rev.3 architecture review. Integration/executor OQs from WP-002/004 stay outside this document.

---

## 14. Non-goals

| Non-goal | Rationale |
|----------|-----------|
| Code / tests implementation | Implementation WP after review |
| Executor apply-gate / PPR commands | Executor WP |
| Transfer wiring | Integration WP |
| HR override UI / decide entrypoint | Separate WP |
| Changing `_education_fingerprint` in PPR handlers | Not required for decide plugin v1 |
| Training / employment / military plugins | Separate section WPs |
| Relatives / scalar sections | Out of reconciliation scope |
| Commit / push | Excluded |

---

## 15. Traceability

| Source | Mapping |
|--------|---------|
| 002 §1.3 Q3 / INV-REC-003 | §8 |
| 002 §5.2 normalizer | §6.2 |
| 002 §10.2 row A education | §5–§7 |
| 002 T07–T08, T21 | §11 EDU-04, EDU-16, EDU-02/03 |
| 004 §4.2 plugin protocol | §3, §4 |
| 004 E17 | §8.4 |
| 005 engine commit `c481b44` | §2.3 |
| 001 §4.3 education rows 20–30 | §2.1, §4.2 |
| `education_type.py` / `map_education_records` | §4 |
| `section_handlers._education_fingerprint` | §5.1 |
| `SectionReadRepository.load_active_records` | §4.4 |

---

## 16. Review notes

### 16.2 rev.2 → rev.3

| Review item | Change in rev.3 |
|-------------|-----------------|
| Input-quality gating order | Moved **after** identity lookup; ambiguity (≥2) evaluated before incomplete downgrade |
| Ambiguity + incomplete dates | `ambiguous`/`high`/`MATCH_AMBIGUOUS` with all candidate ids + Q3 marker + input-quality (EDU-04a) |
| Incomplete + one candidate | `exact_one`+`low` (not `none`+`low`); ids retained; no keep/update even if domain-equal (EDU-05b) |
| Incomplete + zero candidates | unchanged `none`+`low` (EDU-05a) |
| Date clearing evidence | EDU-19a split: blank vs year-only; `clearing_fields` on incomplete canonical clear |
| §6.1 / §6.3 / §8 / §9 / tests | Aligned to new ordering |

### 16.3 rev.1 → rev.2

| Review item | Change in rev.2 |
|-------------|-----------------|
| Canonical clearing via auto update | Forbidden: `exact_one`+`low` + retained ids; EDU-19a–e |
| Year-only digest collapse | `reconciliation_input_quality` with precision+raw in `normalized_content`; EDU-05c/d |
| document_type default `"diploma"` | Removed; OQ-DOC closed |
| Optional whitespace collapse | Removed; strip+casefold only; matcher_version on change |
| Both-null confident add | Forbidden; OQ-DATE closed |
| All remaining EDU OQs | Closed in §13 |
| Auto supersede | Explicitly closed no |
| E17 reason | `MATCH_AMBIGUOUS` + detail Q3 marker |

### 16.4 Summary

WP-006 rev.3 reorders match evaluation so HR Q3 ambiguity is never masked by incomplete-date downgrade, while unique-identity incomplete proposals retain target ids for evidence without permitting auto keep/update.
