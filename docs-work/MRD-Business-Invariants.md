# Business Invariants — MRD (Месячный эталонный набор данных)

**Status:** Active specification (pre WP-MRD-001)  
**Date:** 2026-07-19  
**Version:** 1.0  
**Parent:** [ADR-058 Monthly Reference Dataset](../docs/adr/ADR-058-monthly-reference-dataset-architecture.md)  
**Related:** [ADR-058 Architecture Assessment](./ADR-058-monthly-reference-architecture-assessment.md)

---

## 1. Назначение

Документ фиксирует **обязательные бизнес-инварианты** модели MRD — правила, которые **всегда** должны выполняться в целевой системе.

Использование:

| Consumer | Как применять |
|----------|---------------|
| **Схема БД** | UNIQUE, CHECK, FK, partial indexes |
| **Доменная модель** | Aggregate roots, value objects, invariant guards |
| **Сервисы** | Transaction boundaries, orchestration, reconcile |
| **API** | Validation, error codes, idempotency |
| **Contract / integration tests** | Обязательные сценарии до merge WP-MRD-001+ |

Документ **не является ADR** и **не дублирует** архитектурные решения ADR-058; он переводит их в **проверяемые правила**.

---

## 2. Область действия

### In scope

- Месячный эталонный набор данных (**MRD**): версии, entries, ACTIVE pointer.
- **Detected Difference**: lifecycle, reconcile, logical key, supersession.
- **Confirmed Change**: Event Log подтверждений.
- **Difference Origin**: обязательность и справочник.
- **Versioning / Fork**: новая версия, новый период.
- **Import** как producer (`IMPORT_COMPARE`) — границы влияния на MRD.

### Out of scope

- Operational `employees`, PPR, кадровые приказы (кроме будущего producer origin).
- Legacy Baseline / Publish Baseline (as-is до cutover).
- UI/UX, RBAC matrices (кроме следствий инвариантов).
- Конкретный DDL, имена таблиц, HTTP paths — в WP-MRD-001.

### Терминология

| Код | Документы |
|-----|-----------|
| MRD, Detected Difference, Confirmed Change, Difference Origin | Месячный эталонный набор данных, обнаруженное различие, подтверждённое изменение, происхождение различия |

---

## 3. Уровни обеспечения

| Уровень | Код | Описание |
|---------|-----|----------|
| **Database** | `DB` | CHECK / UNIQUE / FK / partial unique index; триггеры только если иначе невозможно |
| **Domain model** | `DOM` | Инварианты агрегата; выбрасывание domain exception при нарушении |
| **Application service** | `SVC` | Оркестрация, транзакции, reconcile, cross-aggregate rules |
| **Contract test** | `CT` | API/schema contract: запрос → ожидаемый код ошибки / shape |
| **Integration test** | `IT` | Сквозной сценарий через сервисы + БД (test DB) |

**Принцип:** критичные инварианты дублируются на **DB + DOM/SVC**; пов поведенческие — **SVC + IT**. `CT` обязателен, если инвариант exposed через public API.

---

## 4. Сводная таблица инвариантов

| ID | Инвариант (кратко) | DB | DOM | SVC | CT | IT |
|----|-------------------|:--:|:---:|:---:|:--:|:--:|
| [INV-MRD-01](#inv-mrd-01) | Один ACTIVE MRD на период | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-MRD-02](#inv-mrd-02) | MRD меняется только через Confirmed Change | — | ✓ | ✓ | ✓ | ✓ |
| [INV-MRD-03](#inv-mrd-03) | MRD — только подтверждённые данные | ✓ | ✓ | ✓ | — | ✓ |
| [INV-MRD-04](#inv-mrd-04) | CLOSED MRD неизменяем | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-MRD-05](#inv-mrd-05) | Confirm только в ACTIVE MRD периода | — | ✓ | ✓ | ✓ | ✓ |
| [INV-MRD-06](#inv-mrd-06) | Entry mutation только в ACTIVE версии | ✓ | ✓ | ✓ | — | ✓ |
| [INV-DD-01](#inv-dd-01) | Confirm только при DETECTED | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-DD-02](#inv-dd-02) | Detected Difference не удаляется физически | ✓ | ✓ | ✓ | — | ✓ |
| [INV-DD-03](#inv-dd-03) | CONFIRMED / REJECTED необратимы | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-DD-04](#inv-dd-04) | SUPERSEDED — корректная цепочка замещения | ✓ | ✓ | ✓ | — | ✓ |
| [INV-DD-05](#inv-dd-05) | Не более одного open DETECTED на logical key | ✓ | ✓ | ✓ | — | ✓ |
| [INV-DD-06](#inv-dd-06) | Reconcile не пересоздаёт CONFIRMED/REJECTED | — | ✓ | ✓ | — | ✓ |
| [INV-DD-07](#inv-dd-07) | UNCHANGED не материализуется как difference | — | ✓ | ✓ | — | ✓ |
| [INV-CC-01](#inv-cc-01) | Confirm создаёт Confirmed Change event | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-CC-02](#inv-cc-02) | Confirmed Change неизменяем (append-only) | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-CC-03](#inv-cc-03) | Confirm → ровно один event на difference | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-CC-04](#inv-cc-04) | Event содержит обязательные поля аудита | ✓ | ✓ | ✓ | ✓ | — |
| [INV-CC-05](#inv-cc-05) | Event + MRD update — одна транзакция | — | ✓ | ✓ | — | ✓ |
| [INV-VER-01](#inv-ver-01) | Версия MRD не растёт при confirm | ✓ | ✓ | ✓ | — | ✓ |
| [INV-VER-02](#inv-ver-02) | Новая версия — только явный fork-version | — | ✓ | ✓ | ✓ | ✓ |
| [INV-VER-03](#inv-ver-03) | Fork-period из выбранной версии источника | — | ✓ | ✓ | ✓ | ✓ |
| [INV-VER-04](#inv-ver-04) | Fork только из подтверждённого состояния | — | ✓ | ✓ | ✓ | ✓ |
| [INV-VER-05](#inv-ver-05) | После fork новый период независим | — | ✓ | ✓ | — | ✓ |
| [INV-IMP-01](#inv-imp-01) | Import не изменяет MRD напрямую | — | ✓ | ✓ | ✓ | ✓ |
| [INV-IMP-02](#inv-imp-02) | Import влияет на MRD только через difference→confirm | — | ✓ | ✓ | — | ✓ |
| [INV-IMP-03](#inv-imp-03) | Удаление import не затрагивает MRD | — | ✓ | ✓ | — | ✓ |
| [INV-ORG-01](#inv-org-01) | Difference Origin обязателен | ✓ | ✓ | ✓ | ✓ | ✓ |
| [INV-ORG-02](#inv-org-02) | origin_code из активного справочника | ✓ | ✓ | ✓ | ✓ | — |
| [INV-ORG-03](#inv-org-03) | Origin denormalized в Confirmed Change | ✓ | ✓ | ✓ | — | ✓ |

---

## 5. Инварианты по доменам

### MRD

<a id="inv-mrd-01"></a>
#### INV-MRD-01 — Один ACTIVE MRD на период

**Правило:** для каждого `report_period` существует **не более одной** версии MRD со статусом `ACTIVE`.

**Пояснение:** `ACTIVE(06.2026)` и `ACTIVE(07.2026)` — независимые указатели; внутри одного периода — единственная редактируемая версия.

**Обеспечение:** `DB` partial unique index `(report_period) WHERE status='ACTIVE'`; `DOM` MRD registry; `SVC` fork/activate; **`CT`/`IT`** concurrent activate.

---

<a id="inv-mrd-02"></a>
#### INV-MRD-02 — MRD изменяется только через Confirmed Change

**Правило:** мутация `hr_monthly_reference_entries` (create/update/delete атрибута) допустима **только** как следствие успешного **Confirmed Change** event (confirm handler).

**Исключение:** **fork-version** / **fork-period** — копирование подтверждённого состояния в новую версию/период (не confirm path, но только read confirmed → write new version snapshot).

**Пояснение:** Import, compare, reject, staging — **не** пишут в MRD.

**Обеспечение:** `DOM` MRD aggregate — единственный entry mutator; `SVC` — все пути через confirm/fork services; **`CT`/`IT`** попытка прямой записи → denied.

---

<a id="inv-mrd-03"></a>
#### INV-MRD-03 — MRD содержит только подтверждённые данные

**Правило:** каждая entry и каждый атрибут в ACTIVE MRD имеет provenance через **Confirmed Change** (или fork-copy от версии, полностью собранной из confirms).

**Пояснение:** «сырые» import-данные, pending differences, rejected candidates **не** попадают в MRD.

**Обеспечение:** `DB` optional `last_confirmed_change_id` на entry; `DOM`/`SVC` запрет bulk load from import; **`IT`** bootstrap только через confirm chain или fork from confirmed.

---

<a id="inv-mrd-04"></a>
#### INV-MRD-04 — CLOSED MRD неизменяем

**Правило:** версия MRD в статусе `CLOSED` — entries и metadata **не изменяются** (no confirm, no entry mutation, no reconcile target for new confirms).

**Пояснение:** CLOSED — исторический срез и источник для fork.

**Обеспечение:** `DB` CHECK trigger or service guard on entry FK → closed mrd; `DOM`/`SVC`; **`CT`** confirm against CLOSED → 409.

---

<a id="inv-mrd-05"></a>
#### INV-MRD-05 — Confirm привязан к ACTIVE MRD периода

**Правило:** Confirmed Change и entry mutation применяются к **`ACTIVE(report_period)`** difference, где `difference.report_period` = `mrd.report_period`.

**Пояснение:** нельзя confirm difference июля в MRD июня.

**Обеспечение:** `DOM`/`SVC` validate `difference.mrd_id = ACTIVE(period)`; **`CT`/`IT`** mismatch → error.

---

<a id="inv-mrd-06"></a>
#### INV-MRD-06 — Entry mutation только в ACTIVE версии

**Правило:** `hr_monthly_reference_entries.mrd_id` при confirm/fork-target update MUST reference MRD with `status='ACTIVE'`.

**Обеспечение:** `DB` FK + CHECK via trigger or deferred constraint; `DOM`/`SVC`; **`IT`**.

---

### Detected Difference

<a id="inv-dd-01"></a>
#### INV-DD-01 — Confirm только для DETECTED

**Правило:** операция confirm допустима **только** если `lifecycle_status = 'DETECTED'`.

**Пояснение:** CONFIRMED, REJECTED, SUPERSEDED — терминальные для confirm.

**Обеспечение:** `DB` CHECK on state transition table or optimistic lock; `DOM`/`SVC`; **`CT`/`IT`** double confirm → 409.

---

<a id="inv-dd-02"></a>
#### INV-DD-02 — Detected Difference не удаляется физически

**Правило:** записи Detected Difference **не DELETE**; история сохраняется (soft lifecycle only).

**Пояснение:** аудит, supersession chain, анализ решений HR.

**Обеспечение:** `DB` revoke DELETE grants / no DELETE in repos; `DOM`/`SVC`; **`IT`** admin purge forbidden.

---

<a id="inv-dd-03"></a>
#### INV-DD-03 — CONFIRMED и REJECTED необратимы

**Правило:** из `CONFIRMED` или `REJECTED` **нет** перехода обратно в `DETECTED` или другой non-terminal без создания **нового** difference (новый surrogate id).

**Обеспечение:** `DB` CHECK on allowed transitions; `DOM` state machine; **`CT`/`IT`**.

---

<a id="inv-dd-04"></a>
#### INV-DD-04 — SUPERSEDED образует корректную цепочку замещения

**Правило:**

1. Если `lifecycle_status = 'SUPERSEDED'`, то `supersedes_difference_id` **NULL** (это «голова», заменённая другим).
2. Если difference создан при supersession, `supersedes_difference_id` MUST reference существующий difference, переведённый в `SUPERSEDED` в той же reconcile-операции.
3. Цепочка **acyclic**; `supersedes_difference_id` ≠ self.

**Пояснение:** можно восстановить «какое различие заменило какое».

**Обеспечение:** `DB` FK self-ref + CHECK; `DOM`/`SVC` reconcile; **`IT`** chain integrity after multi-import.

---

<a id="inv-dd-05"></a>
#### INV-DD-05 — Не более одного open DETECTED на logical key

**Правило:** для комбинации `(report_period, active_mrd_id, logical_key)` существует **не более одной** записи со `lifecycle_status = 'DETECTED'`.

**Пояснение:** dedup очереди HR; reconcile обновляет существующее, а не плодит дубликаты.

**Обеспечение:** `DB` partial unique index; `SVC` reconcile; **`IT`**.

---

<a id="inv-dd-06"></a>
#### INV-DD-06 — Reconcile не пересоздаёт CONFIRMED / REJECTED

**Правило:** Automatic Comparison / любой producer при reconcile **не создаёт** новый Detected Difference, если для `logical_key` уже есть terminal `CONFIRMED` или `REJECTED` с тем же scope (unless explicit new business event — новый surrogate, новый origin).

**Обеспечение:** `SVC` reconcile algorithm; `DOM`; **`IT`** repeat import after confirm.

---

<a id="inv-dd-07"></a>
#### INV-DD-07 — UNCHANGED не материализуется

**Правило:** технически `UNCHANGED` compare-result **не** создаёт Detected Difference.

**Обеспечение:** `SVC` comparison materialization; **`IT`** identical re-import → zero new DETECTED.

---

### Confirmed Change

<a id="inv-cc-01"></a>
#### INV-CC-01 — Каждый Confirm создаёт Confirmed Change

**Правило:** успешный confirm **всегда** создаёт ровно одну запись Confirmed Change event.

**Обеспечение:** `DB` FK difference_id NOT NULL; `DOM`/`SVC`; **`CT`/`IT`**.

---

<a id="inv-cc-02"></a>
#### INV-CC-02 — Confirmed Change неизменяем

**Правило:** после INSERT event **запрещены** UPDATE и DELETE (append-only Event Log).

**Обеспечение:** `DB` permissions + optional trigger; `DOM`; **`CT`/`IT`**.

---

<a id="inv-cc-03"></a>
#### INV-CC-03 — Один confirm — один event на difference

**Правило:** для каждого `detected_difference_id` существует **не более одного** Confirmed Change event (1:1).

**Обеспечение:** `DB` UNIQUE(`detected_difference_id`); `SVC` idempotency key; **`CT`/`IT`**.

---

<a id="inv-cc-04"></a>
#### INV-CC-04 — Обязательные поля event

**Правило:** каждый Confirmed Change MUST содержать не-null:

`detected_difference_id`, `report_period`, `mrd_id`, `entity_scope`, `attribute`, `old_value`, `new_value`, `confirmed_by`, `confirmed_at`, `difference_origin_code`.

`basis`, `origin_context` — optional / origin-dependent per ADR-058.

**Обеспечение:** `DB` NOT NULL columns; `DOM` value object; **`CT`**.

---

<a id="inv-cc-05"></a>
#### INV-CC-05 — Event и MRD update — одна транзакция

**Правило:** insert Confirmed Change, transition difference → CONFIRMED, MRD entry mutation — **atomic** (commit или rollback всех трёх).

**Обеспечение:** `SVC` transaction boundary; **`IT`** failure mid-flight leaves no partial state.

---

### Versioning / Fork

<a id="inv-ver-01"></a>
#### INV-VER-01 — Версия MRD не увеличивается при confirm

**Правило:** confirm **не** меняет `mrd.version` и **не** создаёт новую версию MRD.

**Обеспечение:** `SVC`/`DOM`; **`IT`**.

---

<a id="inv-ver-02"></a>
#### INV-VER-02 — Новая версия только через fork-version

**Правило:** появление `vN+1` в том же `report_period` **только** через явную операцию **fork-version** (не confirm, не import, не compare).

**Обеспечение:** `SVC` dedicated command; **`CT`/`IT`**.

---

<a id="inv-ver-03"></a>
#### INV-VER-03 — Fork-period из выбранной версии

**Правило:** создание `MM.YYYY v1` для нового периода MUST specify `source_mrd_id` (любая версия любого периода — по выбору HR); default recommendation **не** override explicit choice.

**Обеспечение:** `SVC` fork-period; **`CT`/`IT`**.

---

<a id="inv-ver-04"></a>
#### INV-VER-04 — Fork только из подтверждённого состояния

**Правило:** fork-version и fork-period копируют **только** entries подтверждённого состояния source MRD (полный snapshot confirmed entries). **Не** копировать staging import, **не** DETECTED differences, **не** unconfirmed candidates.

**Пояснение:** минимально должно быть отражено требование пользователя.

**Обеспечение:** `SVC` fork reads entries only; `DOM`; **`CT`/`IT`** fork with pending DETECTED on source → target has no pending data.

---

<a id="inv-ver-05"></a>
#### INV-VER-05 — Новый период развивается независимо

**Правило:** после fork-period confirms и differences нового периода scoped to **`ACTIVE(new_period)`** only; reconcile/import другого периода **не** mutates чужой MRD.

**Обеспечение:** `SVC` period scoping; **`IT`**.

---

### Import

<a id="inv-imp-01"></a>
#### INV-IMP-01 — Import не изменяет MRD напрямую

**Правило:** операции import pipeline (upload, parse, normalize, compare, delete batch) **не** выполняют INSERT/UPDATE/DELETE на `hr_monthly_reference_entries`.

**Обеспечение:** `SVC` module boundaries; **`CT`/`IT`** import end-to-end without confirm → MRD unchanged.

---

<a id="inv-imp-02"></a>
#### INV-IMP-02 — Влияние import на MRD только через confirm chain

**Правило:** единственный путь import → MRD: Import → `IMPORT_COMPARE` → Detected Difference → Confirm → Confirmed Change → MRD.

**Обеспечение:** `SVC`/`DOM`; **`IT`**.

---

<a id="inv-imp-03"></a>
#### INV-IMP-03 — Удаление import не затрагивает MRD

**Правило:** delete import batch **не** rollback MRD entries, Confirmed Changes, или terminal differences.

**Обеспечение:** `SVC`; **`IT`**.

---

### Difference Origin

<a id="inv-org-01"></a>
#### INV-ORG-01 — Difference Origin обязателен

**Правило:** каждый Detected Difference MUST have non-null `difference_origin_code` и `origin_context` (JSON object, possibly `{}`).

**Обеспечение:** `DB` NOT NULL; `DOM`/`SVC`; **`CT`/`IT`**.

---

<a id="inv-org-02"></a>
#### INV-ORG-02 — origin_code из активного справочника

**Правило:** `difference_origin_code` MUST FK → `hr_difference_origin_types` where `is_active = true`.

**Пояснение:** расширяемый справочник без изменения схемы difference.

**Обеспечение:** `DB` FK; `SVC` registration; **`CT`**.

---

<a id="inv-org-03"></a>
#### INV-ORG-03 — Origin фиксируется в Confirmed Change

**Правило:** при confirm `difference_origin_code` и snapshot `origin_context` **denormalized** into Confirmed Change event and **immutable** thereafter (even if difference later only readable historically).

**Обеспечение:** `DB` NOT NULL on event; `SVC` confirm handler; **`IT`**.

---

## 6. Дополнительные инварианты (рекомендуемые для WP-MRD-001)

| ID | Правило | DB | SVC | IT |
|----|---------|:--:|:---:|:--:|
| INV-DD-08 | Reject не создаёт Confirmed Change | ✓ | ✓ | ✓ |
| INV-DD-09 | CONFLICT block confirm until resolved (policy TBD) | — | ✓ | ✓ |
| INV-CC-06 | Idempotent confirm: повторный POST → same event or 409 | — | ✓ | CT |
| INV-VER-06 | fork-version: prior ACTIVE → CLOSED atomically | ✓ | ✓ | ✓ |
| INV-ORG-04 | Reconcile не меняет origin открытого DETECTED при том же candidate | — | ✓ | ✓ |

---

## 7. Contract / integration test matrix (обязательный минимум)

Перед завершением WP-MRD-001 должны существовать тесты:

| Test ID | Инварианты | Сценарий |
|---------|------------|----------|
| **IT-MRD-01** | INV-MRD-01, INV-VER-06 | Два ACTIVE same period → second fails |
| **IT-MRD-02** | INV-MRD-02, INV-IMP-01 | Full import without confirm → MRD entries count unchanged |
| **IT-MRD-03** | INV-MRD-04 | Mutate CLOSED entry → rejected |
| **IT-CC-01** | INV-CC-01..05, INV-DD-01 | Confirm DETECTED → event + CONFIRMED + MRD updated atomically |
| **IT-CC-02** | INV-CC-02, INV-CC-03 | Double confirm → 409; event count = 1 |
| **IT-CC-03** | INV-DD-01, INV-DD-03 | Confirm REJECTED / CONFIRMED → 409 |
| **IT-DD-01** | INV-DD-04, INV-DD-06 | Re-import changes candidate → SUPERSEDED chain |
| **IT-DD-02** | INV-DD-06, INV-DD-07 | Re-import after confirm → no new DETECTED for same key |
| **IT-VER-01** | INV-VER-01, INV-VER-02 | N confirms → version unchanged; fork-version → v+1 |
| **IT-VER-02** | INV-VER-04 | fork copies only confirmed entries |
| **IT-ORG-01** | INV-ORG-01..03 | Missing origin → reject; confirm preserves origin in event |
| **CT-API-01** | INV-DD-01, INV-MRD-04 | API error codes for illegal confirm |

---

## 8. Связь с work packages

| WP | Инварианты (primary) |
|----|---------------------|
| **WP-MRD-001** | INV-MRD-01,03,04,06; INV-DD-02,05; INV-CC-02,04; INV-ORG-01,02; INV-VER-01 |
| **WP-MRD-002** | INV-MRD-02,05; INV-DD-01,03,04,06,07; INV-CC-01,03,05; INV-IMP-01,02; INV-ORG-03 |
| **WP-MRD-003** | INV-MRD-01,04; INV-VER-02,03,04,05,06 |
| **WP-MRD-004** | CT matrix; INV-ORG-01 display |
| **WP-MRD-006** | INV-IMP-01,03 regression |

---

## 9. History

| Date | Version | Change |
|------|---------|--------|
| 2026-07-19 | 1.0 | Initial specification aligned with ADR-058 v4 |
