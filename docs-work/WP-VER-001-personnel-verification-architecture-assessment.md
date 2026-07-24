# WP-VER-001 — Архитектурное обследование перед реализацией ADR-060

**Дата:** 2026-07-24
**Статус:** Assessment complete — код не изменялся; архитектурные блокеры обследования закрыты обновлением ADR-060
**Источник требований:** [ADR-060](../docs/adr/ADR-060-personnel-record-verification.md) (`Accepted`)
**Связанные решения:** ADR-056 (Employment Biography), ADR-059 (Import Review-by-Exception), Canonical PPR

---

## 1. Executive summary

ADR-060 принят как целевая архитектура **управляемой кадровой верификации** (политика → задание → неизменяемое свидетельство). В коде сегодня есть:

- полноценный контур **электронной анкеты → секционный приём кадровиком → transfer в Canonical PPR**;
- на секциях PPR — поле `verification_status` и lifecycle `active/superseded/voided`;
- очередь **import review-by-exception** (ADR-059) как близкий UX-паттерн, но с другой семантикой.

**Не реализованы** сущности ADR-060: каталог точек контроля, версии политики с `decision_basis`, `verification_task`, `verification_attestation`, dual-модель `verified`+`pending`, состояние расчёта «Недостаточно подтверждённых данных».

Обследование первоначально выявило **три архитектурных вопроса**. После обследования они **уже разрешены** обновлением ADR-060 (решения 2.1.7–2.1.9):

1. `medical_category` получает отдельный **typed canonical home** в PPR (не generic section / intake payload / computed view).
2. `verified` и `pending` **физически сосуществуют**; supersede выполняется **только при подтверждении** новой редакции.
3. `verification_status` **не является SSoT** и допускается только как **производная проекция**, обновляемая единым доменным сервисом.

**Оставшиеся риски реализации (код ещё не соответствует ADR):**

1. Путать `INTAKE_SECTION_REVIEW_ACCEPTED` / transfer с кадровой верификацией.
2. Обновлять колонку `verification_status` вне доменного сервиса attestation/policy.
3. Использовать текущий `supersede_pair` как замену dual-версии (в коде старая версия сразу уходит в `superseded`).

**Первая очередь ADR-060** (`employment_episode`, `medical_category`): episode уже живёт в `person_external_employment`; **typed medical category в PPR в коде отсутствует** (архитектурно обязательна; реализация таблицы — WP-VER-004, фундамент — WP-VER-002).

---

## 2. Карта существующих компонентов

### 2.1. Электронная анкета: заполнение, отправка, приём

| Слой | Путь | Назначение |
|---|---|---|
| Domain статусы ссылки/черновика | `app/personnel_intake/domain/status.py` | Link: `issued`, `opened`, `submitted`, `expired`, `revoked`; Draft: `editable`, `submitted` |
| Domain секционного review | `app/personnel_intake/domain/review_status.py` | Section: `pending`, `accepted`, `rework_requested`, `skipped`; коды секций включая `employment_biography` |
| Domain модели | `app/personnel_intake/domain/models.py` | Snapshots draft/link/review/transfer; `empty_intake_draft_payload()` |
| Application intake | `app/personnel_intake/application/intake_service.py` | Issue, autosave, `submit_intake_draft` |
| Application review | `app/personnel_intake/application/review_service.py` | `accept_intake_section`, `rework_intake_section`, `skip_intake_section` |
| Application transfer | `app/personnel_intake/application/transfer_service.py` | `transfer_intake_to_ppr` |
| Mapper | `app/personnel_intake/application/intake_mapper.py` | `map_employment_records`, military/education/… |
| ORM | `app/db/models/personnel_intake.py` | `PersonnelIntakeLink`, `PersonnelIntakeDraft`, `PersonnelIntakeSectionReview`, `PersonnelIntakeTransfer` |
| Public API | `app/api/personnel_intake_public_router.py` | Публичная отправка анкеты |
| HR API | `app/directory/personnel_intake_routes.py` | Review/accept/rework/skip/transfer |
| Application aggregate | `app/personnel_applications/domain/status.py` | Жизненный цикл кадрового обращения |
| UI претендента | `corpsite-ui/app/intake/` | Форма анкеты |
| UI кадровика | `corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeReviewDrawer.tsx` | Секционный приём |
| API client | `corpsite-ui/app/directory/personnel/_lib/personnelApplicationsApi.client.ts` | `acceptIntakeSection`, `transferIntakeToPpr` |

**Фактический поток:**

```text
editable draft → submit → draft=submitted, link=submitted
  → HR accept/rework/skip по секциям
  → transfer_intake_to_ppr (gate: required accepted, no rework)
  → записи в Canonical PPR (обычно verification_status=pending)
```

Приём секции = «можно переносить в PPR», **не** = «кадрово подтверждено для расчётов».

### 2.2. Перенос сведений анкеты в Canonical PPR

| Шаг | Где |
|---|---|
| Gate готовности transfer | `transfer_service._evaluate_can_transfer` |
| Материализация/активация PPR | `PprLifecycleApplicationService.materialize_ppr` / `activate_ppr` (внутри transfer используется `AllowAllAuthorizationPort` после route-level personnel admin check) |
| Personal/contacts | прямой SQL на `persons` / `personnel_applications` |
| Секции | `PprSectionApplicationService.add_*` / `create_military_service` |
| Employment biography | `map_employment_records` → `add_external_employment`; `metadata.source = "personnel_intake"` |
| Additional profile | `app/ppr/read/additional_reader.py` (`save_person_additional_profile`) |

`verification_status` при transfer **не выставляется в `verified`** — остаётся default `pending`.

### 2.3. Послужной список (employment episodes)

| Артефакт | Путь |
|---|---|
| ADR модели | `docs/adr/ADR-056-employment-biography-in-ppr.md` |
| Domain record | `ExternalEmploymentRecord` в `app/ppr/domain/section_models.py` |
| ORM / enums | `PersonExternalEmployment` + `EXTERNAL_EMPLOYMENT_*` в `app/db/models/personnel_migration.py` |
| Команды | `AddExternalEmploymentRecord`, `VoidExternalEmploymentRecord`, `SupersedeExternalEmploymentRecord` в `app/ppr/application/command_models.py` |
| Handlers | `app/ppr/domain/section_handlers.py` |
| Repository supersede | `app/ppr/infrastructure/section_repository.py` → `supersede_pair` |
| Section code | `PPR-EMPLOYMENT-BIOGRAPHY` |

**Статусы строки:**

- `verification_status`: `pending` \| `verified` \| `disputed`
- `lifecycle_status`: `active` \| `superseded` \| `voided` (без `draft` на строке)
- `record_kind`: `episode` \| `narrative_summary` \| `attestation_none`

Intake всегда мапит в `episode`. Поля ADR-060 material set (организация, должность, даты, вид занятости) покрыты **частично**: `employment_type` в mapper intake **не заполняется**; даты приходят из `year_from`/`year_to`.

### 2.4. Медицинские категории

| Что есть | Путь | Ограничение |
|---|---|---|
| Парсинг import `QUALIFICATION_CATEGORY` | `app/services/hr_import_document_parser.py`, `hr_import_analytics_service.py` | Staging/аналитика, не typed PPR |
| Employee documents lifecycle | `app/services/employee_documents_service.py`, `app/directory/employee_documents_routes.py` | Документы сотрудника, не ADR-060 control point |
| Control-list vocabulary | `app/control_list_import/domain/vocabulary.py` (`qualification.category`) | Import semantics |
| UI фильтры import | `corpsite-ui/.../importCategoryUtils.ts` | Review UI |
| Сценарий будущей секции | `docs-work/PPR-Telegram-Intake-Scenario.md` (`PPR-QUALIFICATIONS`) | Не реализовано |
| Roadmap | `docs/architecture/WP-PR-012-ppr-implementation-roadmap.md` — `person_qualifications` EPIC-4+ | Нет таблицы |

В intake есть `fitness_category` (военная годность), это **не** медицинская квалификационная категория ADR-060.

**Вывод (факт кода):** для `medical_category` нет canonical typed record в PPR.

**Статус после ADR-060:** архитектурно обязателен отдельный typed canonical home; точная таблица проектируется в WP-VER-002/реализуется в WP-VER-004 (больше не открытый архитектурный блокер).

### 2.5. Статусы verification и lifecycle сегодня

| Контур | Статусы | Роль |
|---|---|---|
| Intake section review | `pending` / `accepted` / `rework_requested` / `skipped` | Приём секции анкеты |
| Intake transfer | `pending` / `completed` / `failed` | Операция переноса |
| PPR envelope | `CREATED`…`ACTIVE`… (`app/ppr/domain/models.py`) | Жизненный цикл карточки PPR |
| PPR section row lifecycle | `draft`? / `active` / `superseded` / `voided` | Версия строки (employment без draft) |
| PPR row `verification_status` | education/training/…: `pending`/`verified`/`needs_attention`/`rejected`; employment: `pending`/`verified`/`disputed` | Флаг строки **без** attestation workflow |
| ADR-059 MRD | `DETECTED`/`CONFIRMED`/`REJECTED`/`SUPERSEDED` | Import differences |
| ADR-060 (target) | `not_required`/`pending`/`verified`/`disputed`/`rejected`/`expired` + расчётное «Недостаточно подтверждённых данных» | **Нет кода** |

### 2.6. Версионирование, supersede/void, аудит

| Механизм | Путь | Поведение |
|---|---|---|
| Supersede | `section_repository.supersede_pair` | Старая → `lifecycle_status=superseded`, новая insert (обычно `active` + `verification_status=pending`) |
| Void | handlers `MUTATION_KIND_VOID` | `voided` |
| Optimistic concurrency | `updated_at` CAS | Конфликт при stale token |
| Event journal | `personnel_record_events` via `app/ppr/application/event_builder.py`, `section_service.py` | Append-only audit мутаций |
| Event read | `app/ppr/read/event_summary_reader.py` | Сводка |
| Aggregation read | `app/ppr/read/section_aggregation.py` | Берёт **active** по lifecycle; **не** фильтрует по `verified` |

**Dual verified+pending:** в коде не поддержан (история есть, параллельно действующая verified при новой pending-редакции — нет).

**Статус после ADR-060:** целевая модель зафиксирована — физическое сосуществование `verified`+`pending`, supersede только при успешном подтверждении; физическая схема — задача WP-VER-002/WP-VER-003.

### 2.7. Идентификация кадровика (user / employee)

| Сегодня | Где |
|---|---|
| `reviewed_by_user_id` | `PersonnelIntakeSectionReview` |
| `transferred_by_user_id` | `PersonnelIntakeTransfer` |
| PPR actor | `actor_id = f"user:{user_id}"` в `personnel_intake_routes.py` |
| ADR-060 target | `verifier_user_id` + `verifier_employee_id` + display `verifier_code` |

На intake review **нет** `employee_id` и кадрового кода вида `HR-014`. Связка user→employee для verifier display потребует отдельного разрешения в фундаменте.

### 2.8. RBAC и административные настройки

| Механизм | Путь |
|---|---|
| Personnel admin gate | `app/security/personnel_admin_guard.py` — ADMIN / `HR_ENROLLMENT_MANAGER` |
| Permissions | `app/security/admin_permissions.py` |
| Directory helper | `app/directory/rbac.py` — `require_personnel_admin_or_403` |
| PPR auth adapter | `app/ppr/application/authorization.py` |
| Role `HR_HEAD` | seed / `app/security/platform_role_classification.py` — **не** основной grant personnel-admin |
| Versioned publish pattern | `ControlListMappingProfile` — `app/db/models/control_list_mapping.py` (`draft`/`active`/`archived`) |
| `decision_basis` analogue | `hr_import_diff_removal_decision_service.py` + migration `alembic/versions/i0j1k2l3m4n5_hr_import_diff_removal_decisions.py` |

Отдельного кабинета «Кадровая верификация» и permission split «публикация политики ≠ attestation» **нет**.

### 2.9. Очереди и близкие механизмы

| Очередь | Путь | Близость к ADR-060 |
|---|---|---|
| Import Review-by-Exception | ADR-059; `app/mrd/application/hr_review_service.py`; UI `ImportReviewByExceptionBanner`, `PersonnelImportReviewPageClient` | UX employee-centric exceptions; семантика **field-level import**, не whole-record attestation |
| Enrollment queue | `app/services/enrollment_service.py`, admin `/enrollment/queue` | Другой процесс |
| Intake HR drawer | per-application section review | Приём анкеты, не verification_task |
| ADR-060 `verification_task` | только в ADR | Не реализовано |

### 2.10. Потребители стажа / зарплаты

| Потребитель | Путь | Использует неподтверждённые данные? |
|---|---|---|
| Intake tenure helper | `app/personnel_intake/domain/employment_tenure.py`, `app/api/personnel_intake_tenure_router.py` | **Да** — даты из payload анкеты без verification gate |
| UI «Общий стаж» | `corpsite-ui/app/intake/_lib/employmentTenureFormat.ts`, `EmploymentTenureSummary*.tsx` | Да (тот же helper) |
| PPR card / composite | `section_aggregation` active rows | Показывает active независимо от `verification_status` |
| Payroll / salary engine | — | **Не найден** в `app/` |

---

## 3. Ответы на контрольные вопросы ADR-060

| Вопрос | Факт сегодня |
|---|---|
| Можно ли хранить старую `verified` действующей одновременно с новой `pending`-редакцией? | **В коде — нет** (`supersede_pair` сразу supersede-ит). **По ADR-060 — да:** физическое сосуществование; supersede только при подтверждении новой редакции. |
| Подтверждается целостная запись или отдельные поля? | Intake: **секция**. Import/MRD: **поле/diff**. PPR flag: **строка**, без workflow. ADR-060: **целостная запись** control point — не реализовано. |
| Отделено ли принятие анкеты от кадровой верификации? | **Частично по статусам** (accept ≠ `verified`), но **нет** отдельного attestation pipeline. Риск терминологической путаницы высокий. |
| Какие изменения повторно открывают проверку? | **Никакие по правилам ADR-060.** Есть только supersede/void/add; material-field reopen + сохранение действующей verified — нет. |
| Есть ли потребители неподтверждённых сведений для стажа/зарплаты/критичных процессов? | Стаж UI/API intake — **да**. Payroll — нет. Active PPR rows участвуют в чтениях без verified-only фильтра. |

---

## 4. Таблица соответствия требованиям ADR-060

Легенда: **R** = reuse as-is / pattern; **P** = partial; **N** = missing; **X** = contradiction / second-SSoT risk.

| # | Требование ADR-060 | Статус | Комментарий |
|---|---|---|---|
| 1 | Canonical PPR — единственный кадровый SSoT | **R/P** | PPR есть; рядом employee_documents / MRD / intake payload как источники предложений |
| 2 | Анкета = предложение, не verified fact | **P** | Семантически верно в ADR; UI/tenure уже считают по intake |
| 3 | Приём ≠ верификация | **P/X** | Статусы разные, но нет attestation; риск смешения в языке/UI |
| 4 | Политика контроля (версии, `decision_basis`) | **N** | Есть аналоги publish profile / `decision_basis` в import removals |
| 5 | Каталог точек контроля (programmatic) | **N** | |
| 6 | `employment_episode` whole-record control | **P** | Typed episode есть; material fields/reopen/attestation нет |
| 7 | `medical_category` whole-record control | **N** | В коде нет typed PPR; ADR-060 требует typed canonical home (реализация WP-VER-004) |
| 8 | Dual `verified` effective + `pending` revision | **X/N** | Код: supersede-as-replace; ADR-060: сосуществование, supersede только при confirm |
| 9 | Неизменяемое свидетельство | **N** | Есть mutation events, не attestation |
| 10 | Задание кадровику (`verification_task`) | **N** | Ближайший UX — ADR-059 / intake drawer |
| 11 | Статусы `not_required`…`expired` | **P/X** | Пересечение имён `pending`/`verified`/`disputed` с другой семантикой |
| 12 | Verifier = user_id + employee_id + code | **P** | Есть только `user_id` на intake review |
| 13 | Сотруднику: статус + дата; код/ФИО по правам | **N** | |
| 14 | Критичный расчёт не берёт pending; «Недостаточно подтверждённых данных» | **N/X** | Tenure берёт неподтверждённое; payroll нет |
| 15 | Политику утверждает руководство/`HR_HEAD`; admin публикует | **N** | `HR_HEAD` существует как роль; workflow публикации политики нет |
| 16 | Права настройки ≠ права подтверждения | **N** | Personnel admin сейчас общий gate |
| 17 | Four-eyes не в v1, модель расширяема | **N** (ok for v1) | Нужно заложить в attestation schema |
| 18 | Документы-основания — отдельный справочник | **N** (deferred ADR §20) | Не блокер фундамента |
| 19 | Интеграция с зарплатой | **N** (deferred) | Не блокер фундамента |
| 20 | Аудит решений и политик | **P** | Mutation audit есть; attestation/policy audit нет |
| 21 | Массовое подтверждение без просмотра запрещено | **N** | Нечего массово подтверждать в ADR-060 sense |

---

## 5. Пробелы и риски

### 5.1. Пробелы (must-have для ADR-060)

1. Сущности: `verification_control_definition`, `verification_policy` (+versions), `verification_task`, `verification_attestation`.
2. Dual-version storage относительно lifecycle PPR.
3. Canonical home для `medical_category`.
4. Query API: текущее состояние верификации объекта/версии; расчётное состояние недостаточности данных.
5. Permission model: publish policy vs attest; sysadmin без auto-attest.
6. Отображение verifier code / FIO rules.
7. Material-field diff + reopen rules для `employment_episode`.
8. Отдельный read-model / projection для verified tenure (даже до payroll).

### 5.2. Риски второго SSoT и терминологические ловушки

| Риск | Почему опасно | Митигация |
|---|---|---|
| `verification_status` на строке PPR как «подтверждено» | Дублирует attestation без политики/снимка/проверяющего | По ADR-060: attestation + policy + version = канон; колонка только derived projection через единый сервис |
| Intake `accepted` = verified | Нарушает ADR §5/§19 | Явные имена в API/UI: «принято в PPR» vs «подтверждено кадровиком» |
| Supersede заменяет действующую verified при создании pending | Ломает инвариант ADR §2.1.8 / §3.4 | Dual-path: создать pending рядом; supersede только при успешном подтверждении |
| Import CONFIRM / MRD | Field-level trust другого контура | Не переиспользовать как attestation employment/medical |
| Tenure на intake payload | Критичный UX уже считает «как будто правда» | Пометить UI как предварительный; verified projection — отдельный пакет |
| Два enum vocabulary (`needs_attention` vs `disputed`/`expired`) | Путаница статусов | ADR vocabulary только в verification domain; mapping layer |

### 5.3. Частичные активы для переиспользования

- PPR section command/event model и optimistic concurrency.
- External employment typed record + void/supersede history.
- Intake transfer как producer «proposed revision» (после доработки dual-version).
- ADR-059 employee-centric queue UX patterns (не data model).
- Control List mapping profile versioning (`draft`/`active`) как паттерн публикации политики.
- `decision_basis` в import removal decisions как прецедент обязательного основания.
- `personnel_record_events` как образец append-only journal (attestation — отдельная сущность).

---

## 6. Рекомендуемая целевая архитектура (без кода)

### 6.1. Разделение слоёв

```text
[Intake / Import / Manual edit]  →  proposed revision (PPR-linked)
                                      │
                                      ▼
                         verification_task (queue)
                                      │
                                      ▼
                      verification_attestation (immutable)
                                      │
                                      ▼
              effective verified projection for critical reads
                                      │
                                      ▼
                     tenure / future payroll consumers
```

- **Canonical PPR** остаётся хранилищем кадровых фактов/редакций.
- **Verification domain** владеет политикой, заданиями и свидетельствами.
- Intake accept/transfer **не** пишет attestation.

### 6.2. Размещение компонентов

| Компонент | Рекомендуемое размещение | Примечание |
|---|---|---|
| Каталог точек контроля | `app/personnel_verification/domain/control_catalog.py` (+ code constants); опционально read-only table `verification_control_definitions` | Только programmatic codes; v1: `employment_episode`, `medical_category` |
| Политика + версии + `decision_basis` | `verification_policies` / `verification_policy_versions` в DB; application `app/personnel_verification/application/policy_service.py` | Publish создаёт новую immutable version; admin UI позже |
| Задания | `verification_tasks`; `app/personnel_verification/application/task_service.py` | Производные; SSoT решения — attestation |
| Свидетельство | `verification_attestations` append-only; hash/snapshot версии объекта | Связь на `object_type` + `object_id` + `object_version_id` |
| Связь с PPR employment | `person_external_employment` как object; version_id = record id (или явный revision id после dual-model) | Material fields из ADR-060 §15.1 |
| Связь с medical category | Typed canonical home в PPR (ADR-060 §2.1.7); таблица — WP-VER-002/WP-VER-004 | Не мапить на `fitness_category`; WP-VER-002 не создаёт фиктивную medical-запись |
| Derived status API | `GET` текущего verification state (не путать с intake review) | По ADR-060: `verification_status` только derived projection, не SSoT |
| Admin API | тонкий publish/disable policy; требует `decision_basis` URL/ref | SYSADMIN publish; approve authority = leadership/`HR_HEAD` вне системы или role check |
| HR queue API/UI | позже; employee-centric как ADR-059 | Не в первом реализационном пакете |
| Employee-facing status | status + decided_at; code/FIO по ACL | После attestation exists |

### 6.3. Dual-version strategy (зафиксировано ADR-060)

Не использовать текущий `supersede_pair` как путь создания `pending`-редакции поверх действующей `verified`-версии.

Целевое поведение для критичных объектов (ADR-060 §2.1.8):

1. Действующая **verified revision** остаётся **effective for critical calc**.
2. Новая редакция создаётся как **separate pending revision** (отдельная строка или revision slot) и **физически сосуществует** с verified; при создании supersede **не** выполняется.
3. Только успешное подтверждение **атомарно** делает новую версию действующей и supersede-ит прежнюю; отклонённая редакция остаётся в аудите и не становится действующей.
4. `supersede`/`void` lifecycle PPR сохраняются для не-verification сценариев, но verification-aware mutation path должен соблюдать ADR §2.1.8 / §3.4.

Конкретный физический вариант (вторая строка с role flag vs отдельный revision status vs side-table) проектируется и проверяется в **WP-VER-002 / WP-VER-003** согласно ADR-060; текущий код **ни один вариант не реализует**.

### 6.4. Границы первой версии

**Входит:**

- каталог control points `employment_episode` и `medical_category` (оба разрешены ADR-060);
- schema + domain services фундамента (без фиктивной medical-category записи в WP-VER-002);
- получение verification state;
- permissions skeleton;
- audit attestations/policies;
- запрет auto-verify при publish policy / intake transfer;
- правила derived `verification_status` и dual-version contracts.

**Не входит в v1 foundation:**

- полный UI очереди кадровика;
- кабинет admin publish UI (допустим API/fixtures для тестов);
- payroll integration;
- справочник документов-оснований (достаточно `requires_evidence` + refs);
- four-eyes;
- сертификаты / military как control points.

---

## 7. Декомпозиция рабочих пакетов

### WP-VER-001 (этот документ)

Обследование — **выполнено**.

### WP-VER-002 — минимальный фундамент (первый реализационный пакет)

Цель: схема + domain без UI очереди и без admin UI.

- таблицы policy/version/attestation (+ optional task stub или без task);
- каталог **обоих** разрешённых control points (`employment_episode`, `medical_category`) на уровне verification foundation;
- **не** создавать фиктивную medical-category запись/таблицу в этом пакете — typed home реализуется в WP-VER-004;
- спроектировать и проверить contracts dual-version и derived `verification_status` согласно ADR-060;
- command: record attestation / reject / dispute (API-level, без rich UI) хотя бы для employment object;
- query: verification state for object version;
- invariants tests: intake transfer ≠ attestation; policy publish ≠ auto-verify; `verification_status` не SSoT;
- **не** строить очередь и admin кабинет.

### WP-VER-003 — dual-version для `employment_episode`

- mutation path: keep effective verified revision + create pending revision без supersede при создании;
- атомарный supersede только при успешном подтверждении;
- material-field detection;
- reopen → task creation (если task введён) / state transition;
- согласование с существующим `supersede_pair` / void для не-verification путей.

### WP-VER-004 — typed canonical `medical_category` + control point wiring

- реализовать typed PPR home (таблица/модель по проекту из WP-VER-002);
- intake/import producers как proposed revisions;
- подключить к verification foundation (без изменения архитектурных решений ADR-060).

### WP-VER-005 — очередь кадровика (employee-centric)

- `verification_task` lifecycle;
- compare current verified vs pending;
- actions Confirm / Fix&Confirm / Reject / Dispute;
- UI по мотивам ADR-059 drawer/list, отдельный namespace.

### WP-VER-006 — кабинет admin политик

- publish/disable с обязательным `decision_basis`;
- rollout strategy + queue volume estimate;
- RBAC: publish ≠ attest; `HR_HEAD`/leadership basis.

### WP-VER-007 — verified tenure projection

- read API «стаж из verified episodes»;
- состояние «Недостаточно подтверждённых данных»;
- разметить/ограничить intake tenure UI как preliminary.

### WP-VER-008+ — payroll / evidence catalog / more control points

По ADR-060 §20 — отдельные пакеты после бизнес-утверждений.

---

## 8. Вопросы реализации после закрытия архитектурных блокеров

Отложенные ADR §20 (перечень документов, payroll rules) и исправление intake tenure **не** блокируют старт фундамента.

Три принципиальных решения, которые обследование первоначально выявило как архитектурные вопросы, **больше не являются открытыми блокерами** — они зафиксированы в ADR-060 §2.1.7–2.1.9:

| Бывший вопрос обследования | Решение ADR-060 |
|---|---|
| Canonical home для `medical_category` | Отдельный typed canonical home в PPR обязателен |
| Dual `verified`+`pending` vs `supersede_pair` | Физическое сосуществование; supersede только при подтверждении новой редакции |
| Роль колонки `verification_status` | Не SSoT; только производная проекция через единый доменный сервис |

**Что остаётся спроектировать внутри реализации (не до старта WP-VER-002):**

1. **Точная таблица / ORM для `medical_category`** — проектируется и проверяется в WP-VER-002 (контракты/границы), реализуется в **WP-VER-004**. Выбор конкретной схемы **не должен предшествовать** началу WP-VER-002: это часть задачи пакетов, а не отдельный pre-gate.
2. **Физическая схема dual-version** относительно текущего lifecycle/`supersede_pair` — проектируется и проверяется в **WP-VER-002 / WP-VER-003** согласно ADR-060.
3. **Механизм derived projection `verification_status`** — проектируется и проверяется в **WP-VER-002** согласно ADR-060 (единый доменный сервис + инварианты).

**Scope WP-VER-002 закрыт:**

- фундамент должен поддерживать **оба** разрешённых control point (`employment_episode`, `medical_category`) на уровне каталога/контрактов verification domain;
- typed medical_category **реализуется отдельным WP-VER-004**;
- WP-VER-002 **не должен** создавать фиктивную medical-category запись.

Не блокируют старт фундамента (но нужны до UI/prod rollout):

- формат кадрового кода verifier и источник `employee_id` для HR user;
- точный список material fields для intake dates (`year_from` vs day-precision) — можно зафиксировать в control definition v1;
- полный admin UI (достаточно API/tests).

---

## 9. Рекомендуемый порядок немедленных действий

1. Review обновлённых ADR-060 и WP-VER-001 с владельцем PPR/HR.
2. Документационный commit: ADR-060 вместе с WP-VER-001.
3. После commit — подготовка **WP-VER-002** (минимальный фундамент: schema/domain/tests, без очереди и без admin UI).
4. Далее по декомпозиции: WP-VER-003 (dual-version employment), WP-VER-004 (typed medical home).

---

## 10. Индекс ключевых файлов

```text
docs/adr/ADR-060-personnel-record-verification.md
docs/adr/ADR-056-employment-biography-in-ppr.md
docs/adr/ADR-059-employee-centric-import-review.md
docs/architecture/WP-PR-012-ppr-implementation-roadmap.md
docs-work/PPR-Telegram-Intake-Scenario.md
docs-work/UEPC-Ubiquitous-Language.md

app/personnel_intake/domain/status.py
app/personnel_intake/domain/review_status.py
app/personnel_intake/domain/employment_tenure.py
app/personnel_intake/application/intake_service.py
app/personnel_intake/application/review_service.py
app/personnel_intake/application/transfer_service.py
app/personnel_intake/application/intake_mapper.py
app/db/models/personnel_intake.py
app/db/models/personnel_migration.py
app/directory/personnel_intake_routes.py

app/ppr/domain/section_models.py
app/ppr/domain/section_handlers.py
app/ppr/application/section_service.py
app/ppr/application/lifecycle_service.py
app/ppr/infrastructure/section_repository.py
app/ppr/read/section_aggregation.py
app/ppr/application/event_builder.py

app/security/personnel_admin_guard.py
app/security/admin_permissions.py
app/security/platform_role_classification.py
app/mrd/application/hr_review_service.py
app/db/models/control_list_mapping.py
app/services/hr_import_diff_removal_decision_service.py

corpsite-ui/app/intake/
corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeReviewDrawer.tsx
corpsite-ui/app/directory/personnel/_components/ImportReviewByExceptionBanner.tsx
```

---

## 11. Заключение

Текущий код даёт **сильный фундамент PPR + intake accept/transfer + section versioning**, но **не реализует** управляемую кадровую верификацию ADR-060. Фактические риски кода — ложные эквивалентности (`accepted`/`verification_status`/`supersede` ≈ attestation) и отсутствие dual-version / typed medical home.

Архитектурные вопросы обследования по medical home, dual-version и роли `verification_status` **закрыты** обновлением ADR-060. Первый реализационный пакет (**WP-VER-002**) закладывает минимальный фундамент verification domain по этим решениям, без очереди, без admin UI и без фиктивной medical-category записи; typed medical и полная dual-version employment доводятся в WP-VER-004 / WP-VER-003.
