# WP-PR-P4 backlog: PPR-MILITARY

Краткий backlog для отдельной секции воинского учёта. **Не смешивать** с PPR-FAMILY и другими секциями.

## Scope

| Item | Описание |
|------|----------|
| **P4-MIL-001** | Миграция `person_military_service` (или эквивалент) + ORM |
| **P4-MIL-002** | Domain: `MilitaryRecord`, `SECTION_CODE_PPR_MILITARY`, validation |
| **P4-MIL-003** | Application write path: add/update/void/supersede через `PprSectionApplicationService` |
| **P4-MIL-004** | Composite read + Query API (`sections["PPR-MILITARY"]`, `military_active_count`) |
| **P4-MIL-005** | UI: секция «Воинский учёт» в личной карточке (CANDIDATE + EMPLOYED) |
| **P4-MIL-006** | Applicability engine: CONDITIONAL по полу/возрасту/гражданству (legal TBD) |
| **P4-MIL-007** | RESTRICTED access policy + redacted read для непривилегированных ролей |

## Out of scope (Phase 1 family)

- Поля воинского учёта в `person_relatives` или `organization_name` родственников
- Импорт воинских данных в секцию «Родственники»
- PMF plugin для military (NONE в каталоге секций)

## Канонические поля (черновик, по WP-PR-003 §2.7)

- категория учёта, звание, ВУС, состав, статус, комиссариат
- документы (приписное, военный билет) — optional Phase 2

## Зависимости

- WP-PR-P4-001 (PPR-FAMILY) — завершён foundation + read/UI pattern
- WP-PR-003 section catalog — `PPR-MILITARY` уже зарегистрирована как CONDITIONAL

## Acceptance (MVP)

1. Отдельная таблица и секция `PPR-MILITARY`, не в family/education/training
2. Write path с canonical events (`PPR_SECTION_*`)
3. Composite read additive-контракт
4. UI read-only с empty state и lifecycle buckets
5. Тесты: repository contract, write path, composite read, API, UI smoke
