# ADR-057 — Personnel Application Aggregate

## Status

**Accepted**

| Field | Value |
|-------|-------|
| Work Package | WP-PPR-APPLICANT-001A |
| Parent | [ARCH-002](../architecture/ARCH-002-personnel-personal-record-architecture.md) |
| Related | [ADR-054](./ADR-054-personnel-personal-record-aggregate-model.md), [ADR-054-NOTE](./ADR-054-NOTE-intended-employment-lifecycle.md), [ADR-048](./ADR-048-person-ownership-identity-creation-policy.md) |
| Implementation spec | [WP-PPR-APPLICANT-001A](../architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md) |
| Date | 2026-07-17 |

---

## Context

Corpsite уже реализует Person (identity), PPR (person-owned cadre data), контекст `CANDIDATE`, intended employment на envelope, карточку Person и HIRE-from-applicant. Отсутствует **production aggregate** для кадрового обращения — эпизода рассмотрения человека после бумажного заявления до Apply приказа.

WP-PPR-APPLICANT-001A фиксирует data model и lifecycle. Настоящий ADR ratifies **aggregate boundaries** и **Source of Truth** rules.

---

## Decision

### D1 — Personnel Application is a separate aggregate

| Aggregate | Role | SoT for |
|-----------|------|---------|
| **Person** | Persistent identity | `person_id`, IIN, name identity, merge chain |
| **PPR** | Personnel Personal Record (logical; Person root per ADR-054) | Person-owned cadre sections (education, training, …) |
| **Personnel Application** | Cadre intake **episode** | One hiring consideration episode: registration, vacancy check, episode contacts, intended placement, director resolution, order link |
| **Personnel Order** | Legal document workflow (separate BC) | Order lifecycle, editorial, sign, register, apply |
| **Employee** | Operational employment shell | Created **only** after Personnel Order **Apply** |

```text
Person (identity)
  └── PPR (cadre dossier SoT)
  └── Personnel Application × N (episode SoT each)
        └── optional 0..1 ↔ 0..1 link → Personnel Order (when linked)
Person ──► Employee (only via Order Apply)
```

Personnel Application **does not own** PPR sections. PPR **does not own** episode process state.

### D2 — `personnel_applications` is SoT of the episode

All episode-specific data lives on **`personnel_applications`**, including:

- application receipt and source;
- vacancy visual check;
- intended placement (org group/unit/position/rate/vacancy text);
- episode contacts (`contact_mobile_phone`, `contact_email`);
- director resolution;
- registration audit (`registered_at`, `registered_by_user_id`, `hr_note`);
- linkage to Personnel Order.

**Not** stored on `personnel_record_metadata` for new flows.

### D3 — Envelope `intended_*` is a temporary compatibility projection

Columns `intended_org_group_id`, `intended_org_unit_id`, `intended_position_id`, `intended_employment_rate` on `personnel_record_metadata` remain **projection only** during transition:

- **Write:** service mirrors **the current active** Personnel Application → envelope after create/update/status change.
- **Switch:** when one active application becomes terminal and **another active application exists**, projection **reassigns** to the remaining active row.
- **Clear:** when **no active application** exists for the Person, envelope `intended_*` is set to **`NULL`** (all four columns).
- **History:** historical intended placement is stored **only** in `personnel_applications`; envelope **must not** retain stale values.
- **Read:** legacy consumers (`hire-defaults`, composite read fallback) may read envelope until migrated; when cleared, they must fall back to application API or return empty.
- **Scope:** when an active application exists, projection applies **including former employees (rehire path)** — not gated on `CANDIDATE`.

Envelope projection is **not** SoT. Removal of dual-write is a follow-up cleanup after 001B/C adoption.

See WP-PPR-APPLICANT-001A §9 (Compatibility Bridge).

### D4 — Former employee: new application, no automatic context switch

When a former employee submits a new paper application:

1. **Reuse** Person and PPR (single envelope).
2. **Create** new Personnel Application row.
3. **Do not** automatically change `hr_relationship_context` from `FORMER_EMPLOYEE` to `CANDIDATE`.

Rehire semantics and HIRE eligibility for `FORMER_EMPLOYEE` → **WP-PPR-APPLICANT-002 / WP-PO-REHIRE**.

### D5 — Active application invariant (Phase 1)

At most **one active** Personnel Application per Person.

**Terminal statuses:** `completed`, `withdrawn`, `cancelled`, `resolution_rejected`.

Domain predicates (normative):

```python
TERMINAL_APPLICATION_STATUSES = frozenset({...})

def is_terminal_application_status(status: str) -> bool: ...
def is_active_application_status(status: str) -> bool:
    return status not in TERMINAL_APPLICATION_STATUSES
```

Enforcement:

1. Partial unique index on `person_id` WHERE NOT terminal (same status set);
2. Service guard before INSERT;
3. Architecture guard test — index predicate and domain predicates **must stay synchronized**.

### D6 — Applicant roster (long-term vs transition)

| Mode | Rule |
|------|------|
| **Target (long-term)** | Person appears in applicant roster iff **has active Personnel Application** |
| **Transition (001B–C)** | Person appears if **active Personnel Application** OR legacy `hr_relationship_context = CANDIDATE` (without active employee) |

Transition preserves WP-UI-PPR-CANDIDATE-v1 demo rows until backfill/migration completes.

### D7 — Personnel Order linkage (0..1 ↔ 0..1)

| Side | Cardinality | Rule |
|------|-------------|------|
| Application → Order | **0..1** | `personnel_order_id` nullable — application may have no order |
| Order → Application | **0..1** | UNIQUE index when FK set — order links to at most one application |

- Link is **optional on both sides** until HR binds a draft HIRE order to the episode.
- Service layer validates linked order type is **HIRE** before bind.
- **READY_FOR_SIGNATURE gate** and director resolution enforcement → **WP-PPR-APPLICANT-002** (out of 001A/B/C scope).

### D8 — Retention

| Artifact | Retention |
|----------|-----------|
| **Personnel Application row** | **Permanent** (full episode history) |
| Intake draft payload, submitted payload, one-time tokens | **Not part of this aggregate** — WP-PPR-INTAKE-001; ephemeral with TTL |

### D9 — IIN validation

- Single **production** utility module (e.g. `app/domain/iin.py`) — **not** `scripts/import_hr_control_list.py`.
- Phase 1 registration: **12 decimal digits** + normalization; **no checksum** until legacy data audit completes.
- Checksum algorithm adoption is a separate decision after audit.

### D10 — Data types

- `application_received_at` → **`DATE`** (calendar date of paper receipt).
- Event timestamps (`registered_at`, `vacancy_checked_at`, `director_resolution_at`, `created_at`, `updated_at`) → **`TIMESTAMPTZ`**.

---

## Consequences

### Positive

- Clear separation: identity / dossier / episode / legal order / employment.
- Repeat applications (e.g. after one year) without overwriting history.
- Former employee path does not corrupt `hr_relationship_context` prematurely.
- Roster decouples from envelope context over time.

### Negative / follow-up

- Dual-write envelope projection adds temporary complexity (Compatibility Bridge).
- HIRE-from-person still requires `CANDIDATE` until rehire WP — former employee with new application may need APPLICANT-002 path.
- Architecture guard + partial index must be maintained together.

---

## References

- [WP-PPR-APPLICANT-001A](../architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md)
- [PIF-001](../personnel-intake/PIF-001-personnel-intake-framework.md)
- [WP-PO-REHIRE-001](../personnel-orders/work-packages/WP-PO-REHIRE-001-termination-hr-context.md)

---

## Decision Log

| Date | Change |
|------|--------|
| 2026-07-17 | Initial acceptance — aggregate boundaries, SoT, compatibility bridge, invariants |
| 2026-07-17 | Compatibility Bridge: clear envelope when no active application; historical intended_* only on application rows; Order linkage 0..1 ↔ 0..1 |
