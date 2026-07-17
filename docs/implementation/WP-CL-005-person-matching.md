--------------------------------------------------

Document Status

Document:
WP-CL-005-person-matching

Title:
Control List Person Matching — Read-Only Match Layer

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-005

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**Read-only matching only** — no Person/PPR writes, no apply, no fuzzy auto-selection

--------------------------------------------------

# WP-CL-005 — Person Matching

## 1. Цель

Сопоставить нормализованный **Person Candidate** (WP-CL-004) с существующими canonical **Person** и вернуть **PersonMatchResult** без создания и изменения PPR.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| `PersonMatchResult`, `PersonMatchCandidate`, `MatchStatus`, `MatchReason` | Person creation / mutation |
| `PersonMatchingService` | Apply в canonical |
| `PersonMatchReadPort` + SQL adapter | Candidate persistence table |
| Unit tests | API / frontend review UI |
| ADR-057 §5.4 / §7 update | Fuzzy matching |

## 3. Архитектурная роль

| Слой | Роль | Canonical? |
|------|------|------------|
| Person Candidate (WP-CL-004) | Normalized import slice | Нет |
| **Person Match Result (WP-CL-005)** | **Read-only matching outcome** | **Нет** |
| Canonical Person (`public.persons`) | Operational identity | Да |
| Review / apply (WP-CL-011+) | Operator decision + controlled write | — |

**Инварианты:**

- Read-only: **не создаёт** и **не изменяет** Person / PPR.
- Domain service **не выполняет** SQL — только через `PersonMatchReadPort`.
- `employee_id` **не используется** как идентичность человека.
- Merged Person: поиск по `active`/`inactive`; redirect через `resolve_survivor` (PPR merge chain).
- Fuzzy matching и auto-confirm по «похожему ФИО» **запрещены**.

## 4. Domain models

### 4.1. MatchStatus

| Value | Meaning |
|-------|---------|
| `exact` | Валидный ИИН → единственный Person без attribute conflict |
| `probable` | FIO+DOB (single hit) или FIO-only (без recommendation) |
| `ambiguous` | Несколько подходящих Person |
| `not_found` | Нет совпадений по доступным ключам |
| `invalid` | ИИН найден, но ФИО/дата рождения конфликтуют |

### 4.2. MatchReason

| Reason | When |
|--------|------|
| `exact_iin` | Primary tier — IIN lookup |
| `probable_fio_birth_date` | FIO + birth_date lookup |
| `weak_fio_only` | FIO-only lookup (no auto recommendation) |
| `multiple_matches` | >1 distinct resolved Person |
| `iin_attribute_conflict` | IIN hit conflicts with candidate FIO/DOB |
| `no_match` | No hits |
| `candidate_incomplete` | Insufficient keys for stronger tiers |

### 4.3. Score / confidence

| Tier | score | confidence | recommended_person_id |
|------|-------|------------|---------------------|
| Exact IIN | 1.0 | 1.0 | resolved id (if no conflict) |
| FIO + DOB | 0.9 | 0.9 | resolved id (single hit) |
| FIO only | 0.5 | 0.5 | **null** (never auto-match) |

## 5. Matching priority

```text
PersonCandidate
  → [1] valid IIN? → find_by_iin → exact | invalid | ambiguous
  → [2] FIO + birth_date? → find_by_fio_and_birth_date → probable | ambiguous
  → [3] normalized FIO? → find_by_normalized_fio → probable (no recommend) | ambiguous | not_found
  → PersonMatchResult
```

**Conflict rule:** если ИИН указывает на Person, но canonical FIO или birth_date расходятся с candidate → `invalid`, без автоматического выбора.

**Merged Person:** каждый hit проходит `resolve_survivor`; `load_person` обогащает survivor attributes.

## 6. PersonMatchReadPort

| Method | Purpose |
|--------|---------|
| `find_by_iin(iin)` | Exact IIN on active/inactive rows |
| `find_by_fio_and_birth_date(...)` | Normalized FIO key + birth_date |
| `find_by_normalized_fio(key)` | FIO-only lookup |
| `resolve_survivor(person_id)` | PPR merge chain redirect |
| `load_person(person_id)` | Survivor enrichment after redirect |

SQL adapter: `SqlAlchemyPersonMatchReadRepository` — raw SQL in infrastructure only.

FIO comparison uses `normalize_comparison_key()` (WP-CL-004) for parity with Person Candidate keys.

## 7. Артефакты

| Артефакт | Путь |
|----------|------|
| Match models | `app/control_list_import/domain/person_match_models.py` |
| Read port | `app/control_list_import/domain/person_match_repository.py` |
| Matching service | `app/control_list_import/matching/service.py` |
| Comparison keys | `app/control_list_import/matching/keys.py` |
| SQL adapter | `app/control_list_import/infrastructure/person_match_repository.py` |
| Tests | `tests/test_wp_cl_005_person_matching.py`, `tests/test_wp_cl_005_person_match_repository.py` |

## 8. Граница matching → review/apply

| Responsibility | Owner |
|----------------|-------|
| Determine match status, hits, confidence | **WP-CL-005** |
| Operator override, approve/reject/defer | WP-CL-011 (review UI) |
| Persist import decisions | Later WP |
| Write to PPR / Employment | Apply events (WP-CL-011+) |

Matching **не** трактует `recommended_person_id` как apply — это подсказка для reviewer (кроме FIO-only, где recommendation всегда null).

## 9. Acceptance

- [x] Domain models: PersonMatchResult, PersonMatchCandidate, MatchStatus, MatchReason
- [x] PersonMatchingService with priority rules
- [x] PersonMatchReadPort + SQL adapter
- [x] Merged Person redirect
- [x] Unit tests: exact IIN, probable FIO+DOB, ambiguous, not_found, invalid conflict, merged, no FIO-only auto-match
- [x] PostgreSQL repository contract tests (IIN/FIO lookups, merge redirect, dedupe, fail-closed resolver)
- [x] ADR-057 updated

## 10. Следующий WP

WP-CL-006 — Подразделение, должность и назначение.
