# ADR-038-C.1. Conflict Policy + Apply Gate

Статус: Approved (C.1 implemented)  
Дата: 2026-06-17  
Родитель: [ADR-038-B](ADR-038-B-sync-foundation.md)

## Контекст

Phase B.4 preview классифицировал записи, но B.3 `--apply` применял все resolved overrides без учёта conflicts.

Phase C.1 вводит единую **conflict policy** и **apply gate** для preview и import.

## Реализация

| Модуль | Назначение |
|---|---|
| `app/services/sync/conflict_policy.py` | `classify_sync_override()`, section diff, merge |
| `app/services/sync/preview_service.py` | preview через policy |
| `app/services/sync/import_service.py` | apply gate (`enforce_apply_gate=True` по умолчанию) |

## Classification model

Порядок проверок:

1. **new** → `insert` (apply allowed)
2. **identical** → `skip`
3. **SECTION_OVERLAP** → `conflict` / `review_required` — обе стороны имеют секцию с разными значениями
4. **TARGET_NEWER** → `conflict` / `review_required` — `target.updated_at > incoming.updated_at`
5. **merge** → `update` (apply allowed) — disjoint section changes (Scenario C)
6. **update** → `update` (apply allowed) — source wins

| status | action | apply_allowed |
|---|---|---|
| `new` | `insert` | yes |
| `identical` | `skip` | no |
| `merge` | `update` | yes (section union) |
| `update` | `update` | yes (full replace) |
| `conflict` | `review_required` | no |
| `orphan` | `skip` | no |
| `ambiguous` | `skip` | no |

### Conflict types

- `SECTION_OVERLAP` — Scenario B (приоритет над timestamp)
- `TARGET_NEWER` — target новее incoming при disjoint diff

## Apply gate

`import_hr_sync_package(apply_changes=True, enforce_apply_gate=True)`:

- применяет только `apply_allowed=True` (`new`, `merge`, `update`)
- `conflict` → `blocked_count++`, запись в БД не выполняется
- `identical`, `orphan`, `ambiguous` → skip

Dry-run (`apply_changes=False`) возвращает `apply_allowed_count` без записи.

## Merge semantics (Scenario C)

`merge_profile_overrides()` — union секций: incoming секции заменяют target по ключу, остальные target секции сохраняются.

## Limitations (C.1)

- Нет UI resolution workflow (conflict отображается read-only в Phase D.1 — см. [ADR-038-D.1](ADR-038-D-sync-admin-ui.md))
- Нет `last_sync_at` — overlap detection без истории синхронизации
- `enforce_apply_gate=False` не экспонирован в CLI (escape hatch только в API)
- Conflict Engine Phase C.2+ — approval, item-level merge, audit log

## Тесты

`tests/test_adr038_phase_c1_conflict_policy_apply_gate.py` (11 tests)

## Phase D.1 (UI)

Read-only admin UI: `/admin/sync` — export, upload, preview table, conflict badges без apply.  
API: `tests/test_hr_sync_api.py`
