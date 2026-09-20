# Личная карточка сотрудника: исследование и проект self-service

Статус: проектирование, без реализации.  Основание: руководящий документ
`docs/implementation/employee-self-service-personal-card-design-brief.md` и
`docs-work/source-materials/employee/Руководство пользователя.docx`.

## Итоговое решение

Заменить верхнюю вкладку «Образование» отдельным self-service маршрутом
`/profile/personal-card`. Карточка определяется только на сервере по цепочке
`authenticated User → users.employee_id → employees.person_id → Person/PPR`.
Клиент не получает и не передаёт идентификатор для выбора субъекта. Это не
вариант кадровой карточки с урезанной видимостью: self-service не использует
`personnel_visibility_assignments`, `PERSONNEL_CARD_EDIT`, ни HR person-scoped
маршруты.

Рекомендуемый MVP: self-read для каждого активного User с однозначной активной
связью с Employee и Person; прямое self-edit только контактов, образования и
языков. Bootstrap Person и correction workflow для HR-owned данных — отдельные
явные этапы, а не побочный эффект первого GET.

## Изученные источники

### Руководящий документ и текущая вкладка

Пользовательское руководство описывает личный кабинет как закрытый контур
аутентифицированного пользователя с верхними вкладками. Оно не задаёт кадровую
видимость для рядового сотрудника. В codebase текущая вкладка определяется в
`corpsite-ui/lib/positionCabinetNav.ts` как `education → /education`; её
рендерит `components/PositionCabinetNav.tsx` внутри `components/AppShell.tsx`.

`app/education/page.tsx` выводит `EducationPageClient`, который сейчас является
заглушкой «Раздел в подготовке»: он не читает Employee/PPR и не хранит данных.
Следовательно, функциональной миграции данных нет. Однако route и ссылки уже
могли попасть в закладки или документы, поэтому `/education` нельзя удалять в
MVP. Он должен делать безопасный permanent/temporary redirect на
`/profile/personal-card` (с решением product-owner о сохранении query/hash) и
иметь regression-тест. Обновить также `positionCabinetNav.ts`,
`PositionCabinetNav.tsx`, `positionCabinetNav.test.ts` и ветку `/education` в
`personnelNav.ts::resolveDirectoryOrgTreeBasePath`.

### Фактическая identity-цепочка

| Шаг | Фактический источник | Наблюдение |
|---|---|---|
| Аутентификация | `app.auth.get_current_user`, таблица `users` | JWT даёт server-side `user_id`; user должен быть active. |
| User → Employee | `users.employee_id` | Административный route создания User проверяет один User на Employee. Это нужная, но не достаточная гарантия для self resolver. |
| Employee → Person | `employees.person_id` | Nullable link; Person — canonical root PPR. |
| Person → PPR | PPR query UoW, `persons`, `personnel_record_metadata`, section repositories | Read model собирается по `person_id`, с employee context только как дополнительным источником/assignment. |

Локальная read-only проверка после provisioning: `user_id=1245` активен, связан
с `employee_id=228`; Employee активен, operational status `active`, но
`person_id=NULL`. Это нормальное поддерживаемое состояние, а не повод
автоматически искать Person по Ф.И.О. или создавать дубликат. Для него
`GET /api/ppr/me` возвращает явный bootstrap-state, а не 404 чужой карточки.

Текущие `GET /api/ppr/persons/{person_id}` и
`GET /api/ppr/employees/{employee_id}` не подходят self-service: они вызывают
`assert_ppr_read_allowed_for_*` из `app/services/ppr_query_access_service.py`,
который требует `compute_scope()` и общую personnel visibility. Existing
employee-scoped endpoints оставляются только legacy/HR-адаптерами.

## Целевой self resolver

Новый сервис, например `app/services/self_personal_card_access_service.py`,
должен за одну read transaction:

1. получить `user_id` исключительно из `get_current_user`;
2. lock/read `users` и проверить `is_active`;
3. получить единственный `users.employee_id`; отсутствие — self state
   `NO_EMPLOYEE_LINK`;
4. получить этот Employee прямым запросом по ID, проверить active/lifecycle;
5. взять только его `person_id`; `NULL` — `PERSON_NOT_LINKED`;
6. при Person проверить, что link не неоднозначен среди active Employee;
   неоднозначность — контролируемый `409 SELF_CARD_IDENTITY_AMBIGUOUS`;
7. вернуть внутренний resolution object. `employee_id`/`person_id` не входят в
   browser request, URL, query или command body.

Внешние состояния bootstrap response:

| state | HTTP | UI |
|---|---:|---|
| `READY` | 200 | composite и разрешённые действия |
| `PERSON_NOT_LINKED` | 200 | «Личная карточка ещё не создана»; безопасная CTA согласно rollout-policy |
| `NO_EMPLOYEE_LINK` | 409 | «Карточка пока недоступна. Обратитесь к кадровику» |
| `IDENTITY_AMBIGUOUS` | 409 | та же нейтральная ошибка, correlation id |
| inactive/disabled | 403 | без раскрытия технических ID |

Ни одно из этих состояний не выполняет поиск Person по имени, ИИН из клиента,
intake draft или `intended_employment`.

## Контракт API

Все endpoints требуют authenticated active User и вызывают self resolver первым.
Ни один не объявляет `person_id`/`employee_id` как path/query/body parameter.

| Endpoint | Назначение | MVP |
|---|---|---|
| `GET /api/ppr/me` | self composite + identity state + read-only assignment | да |
| `POST /api/ppr/me/bootstrap` | идемпотентно создать/link Person только после отдельного решения о data governance | нет, вернуть state без CTA mutation |
| `GET/PUT /api/ppr/me/contacts` | canonical `person_contacts`, fallback только на чтение | да |
| `POST /api/ppr/me/education/records`, `.../{record_id}/supersede`, `.../void` | versioned education | да |
| `GET/PUT /api/ppr/me/foreign-languages` | narrow key `additional_profile.foreign_languages` | да |
| `POST /api/ppr/me/correction-requests` | HR-owned/sensitive correction proposal | этап 2 |
| `GET /api/ppr/me/history` | только собственные allowed audit events | этап 2 |
| `GET /api/ppr/me/card/pdf` | собственный PDF | да, после self read |

`GET /api/ppr/me` должен адаптировать существующий
`PprQueryApplicationService` и `composite_to_response`, но с отдельной self
read-policy и маскированием. Нельзя просто вызвать `/persons/{id}` из browser.
Server-side adapter может передать resolved Person во внутренний query service,
не публикуя его в contract. Для self response надо ввести отдельную schema,
чтобы полное ИИН, restricted military facts, import/provenance metadata и
HR-only status не появились по ошибке при расширении HR response.

## Владение разделами

| Раздел | Self read | Self write MVP | Правило |
|---|---:|---:|---|
| Фото | да | нет в MVP | позже переиспользовать storage/validation, но отдельный `/me/photo` |
| Контакты | да | да | `person_contacts`; full-section contract, version/CAS |
| Общие сведения, ИИН, Ф.И.О., дата рождения | маскированно | нет | только correction request/HR |
| Образование | да | да | `person_education`, create/supersede/void, lineage |
| Обучение | да | нет MVP | HR-owned до отдельного решения |
| Квалификационная категория | да | нет | HR-owned |
| Внешняя биография | да | нет MVP | этап 2, после provenance policy |
| Работа в текущей организации | да | нет | только trusted operational assignment |
| Воинский учёт | policy-limited | нет | restricted/HR workflow |
| Родственники | да | нет MVP | третьи лица; отдельная privacy review |
| Иностранные языки | да | да | меняется только key `foreign_languages` |
| Примечание, инвалидность, пенсионный статус, награды | policy-limited | нет | sensitive/HR-owned |
| Приказы, обращения, адаптация, история | own read позже | нет | отдельные bounded projections/workflows |
| Расчёт стажа | UI read только при необходимости | нет | derived, не PDF |

Canonical source map: contacts — `person_contacts`; versioned sections —
`person_education`, `person_training`, `person_relatives`,
`person_external_employment`, `person_military_*`; additional profile —
`personnel_record_metadata.additional_profile`; photo — canonical Person photo
repository; change journal — `personnel_record_events`. Current organisation
must come from trusted active Employee/primary assignment projection, never
from `intended_employment`.

## Write, CAS и аудит

Existing HR editors demonstrate reusable mechanics, not reusable authorization:
`app/api/ppr_card_command_router.py` already implements contacts versioning,
education/training/relative section commands, narrow language replacement and
events. Their guards call `require_personnel_card_edit_for_person`, therefore
they must not be exposed or weakened for employees.

New `/me` command handlers reuse only domain services/repositories:

- every body uses `extra=forbid`, `command_id`, optional correlation id and
  `expected_version`/`expected_updated_at`;
- resolve self Person server-side before validation/mutation;
- use one transaction and existing command-id repository for idempotent
  replay; duplicate command with different fingerprint is `409`;
- use active-record `supersede`/`void`, preserve record_id and lineage; void
  requires a reason;
- contacts CAS returns `409`; languages update only the one JSON key and
  preserve null/provenance/sibling keys;
- emit append-only `personnel_record_events` with actor User, resolved Employee
  context, Person, section, action, server-side before/after, command id,
  correlation id and source `EMPLOYEE_SELF_SERVICE`.

The current event names have HR suffixes (for example
`PPR_CONTACTS_HR_CORRECTED`); self writes need distinct event types/source, so
HR history cannot be mistaken for employee confirmation. Do not put PII into
application/technical logs.

## Correction workflow and bootstrap

No generic employee self correction-request model was found. Create it as a
separate workflow rather than writing HR-owned canonical data directly:
request holds only allowed proposed fields, reason, source User/Employee/Person,
status, reviewer and decision event. The actual canonical mutation is an HR
command after approval; the employee sees a redacted proposal/status.

Existing `app/services/adr065_person_link_service.py` is an HR identity-link
operation: it can adopt/create Person, depends on normalized identity inputs,
locks Employee/Person and invokes migration first-pass. It must **not** be
called directly by employee browser bootstrap. Before enabling bootstrap,
choose one of:

1. HR request only (recommended initial path); or
2. a narrowly audited server bootstrap with no client identity input, explicit
   policy for required canonical identity values, idempotency and an HR review
   flag.

## Self PDF

Reuse the pure view model/HTML/CSS layers:
`personCardPdfViewModel.ts`, `personCardPdfDocumentHtml.ts`,
`personalCardSections.ts` and `intakePdfRouteHandler.ts`. The existing route
`/directory/personnel/persons/[personId]/card/pdf` and loader are HR-only:
they expose a path Person ID and call PPR endpoints that require personnel
visibility. Do not proxy it from self UI.

Implement `/api/ppr/me/card/pdf` (or Next route `/profile/personal-card/pdf`)
with the self resolver and a self PDF loader. It uses the same canonical
composite, contacts and photo under self policy plus server-resolved
operational assignment. Keep the existing order from `PERSONAL_CARD_PDF_SECTIONS`;
the registry already excludes `tenure_calculation`. The PDF shares screen
masking and never grants a separate HR read right.

## Isolation of PERSONNEL_EVENTS_READ

`PERSONNEL_EVENTS_READ` plus `personnel_event_visibility_assignments` remains
an independent event-only capability. It must neither set
`has_personnel_visibility` nor be considered by the self resolver. Conversely,
self-card access must not add event scope/capability, expose the personnel
journal, `/directory/employees`, PPR person routes, orders, intake or HR
write routes. UI hiding is supplementary; every backend route retains its own
guard.

## File and API change map

| Area | Likely files | Change |
|---|---|---|
| self identity | new `app/services/self_personal_card_access_service.py`, `app/api/ppr_self_router.py`, `app/api/ppr_self_schemas.py`, `app/main.py` | resolver and `/api/ppr/me` namespace |
| PPR reuse | `app/ppr/read/query_service.py`, mappers/schemas, section service/repositories | internal adapters; no HR guard weakening |
| audit/idempotency | `personnel_record_event_service.py`, PPR event/idempotency repos | source-aware self events |
| photo/PDF | new self loader/route under `corpsite-ui/app/profile/personal-card`, existing person PDF VM/HTML | self wrapper, no person ID URL |
| UI | new `app/profile/personal-card/page.tsx` and client/editor components; `positionCabinetNav.ts`, `PositionCabinetNav.tsx`, `AppShell.tsx` | tab rename and self states |
| legacy education | `app/education/page.tsx`, `EducationPageClient.tsx`, nav tests | redirect compatibility |
| tests | new backend API/security tests and Vitest route/nav/editor/PDF tests | see acceptance matrix |

No migration is required for read-only self-card MVP if bootstrap and correction
requests are deferred. A durable correction workflow, bootstrap idempotency or
new self event taxonomy may require separate migrations. They must continue
from the committed personnel migration chain and not merge local Data Exchange
heads opportunistically.

## MVP phases and acceptance tests

1. **Read/navigation:** rename tab; `/education` redirect; `GET /api/ppr/me`;
   READY/no Employee/no Person/ambiguous states. Test that body/query/path IDs
   cannot select another employee.
2. **Read-only card/PDF:** screen and own PDF with assignment projection,
   shared section order and no tenure; test masked fields and no visibility
   requirement.
3. **Direct self edits:** contacts, education, languages only; test CAS 409,
   replay, before/after audit, no adjacent JSON loss and unsaved-change UX.
4. **Governed changes:** correction requests and optionally bootstrap after
   governance decision.

Security regression matrix: ordinary linked employee succeeds without generic
visibility; employee 228 receives `PERSON_NOT_LINKED`; event observer stays
event-only; HR visibility APIs retain current access; self user receives 403 on
`/directory/employees`, `/api/ppr/persons/*`, order/intake/assignment writes;
public token receives 401/403 on `/api/ppr/me*`; stale CAS is 409; duplicate
command is an idempotent replay; direct route/body IDs are rejected by schema.

## Open decisions and risks

- Who may trigger Person bootstrap, and which verified identity data may seed
  it? This is the largest provenance/duplicate-identity risk.
- Does employee education write directly to canonical records or require HR
  review? Decide before Phase 3.
- Define redaction policy for self IIN, military facts, relatives and history.
- Decide retention/consent and reviewer SLA for third-party/sensitive data.
- Ensure a self PDF cannot reveal broader data than self screen.
- Add rate/file limits before enabling photo/doc uploads.
- Audit enum/version differences between the legacy card UI and canonical
  section models before reusing editor controls.

Until these decisions are approved, no application code, schema, migrations or
access grants should be changed for self-service.

## APPROVED — границы MVP

Следующие решения утверждены для планирования MVP.

| Решение | Статус | Утверждённый вариант |
|---|---|---|
| Точка входа | APPROVED | Верхняя вкладка «Личная карточка» и маршрут `/profile/personal-card`; не кадровый список. |
| Старый маршрут | APPROVED | Сохранить `/education` как compatibility redirect на новый маршрут; не удалять в MVP. |
| Доступ | APPROVED | Встроенный identity-based self-read только для active User с однозначной server-side связью User → Employee → Person. Общая personnel visibility и `PERSONNEL_CARD_EDIT` не используются. |
| Employee без Person | APPROVED | Не создавать Person/PPR автоматически. Показывать `PERSON_NOT_LINKED` и нейтральное сообщение; bootstrap и HR request — отдельное решение следующего этапа. |
| Self-write MVP | APPROVED | Только контакты, образование и иностранные языки; каждое изменение — narrow command, CAS, idempotency и append-only audit. |
| HR/sensitive fields | APPROVED | ИИН, Ф.И.О., дата рождения, current assignment, категория, воинский учёт, статусы, приказы, стаж и история — read-only; correction workflow не входит в MVP. |
| PDF | APPROVED | Собственный защищённый PDF без client-supplied ID; использовать existing Person-card view model/HTML/CSS, но отдельный self loader/policy. |
| Event journal | APPROVED | `PERSONNEL_EVENTS_READ` и event-only scope остаются изолированными: self-card не даёт журнал, журнал не даёт card access. |
| Миграции | APPROVED | В read/edit MVP не планировать migration; отдельные migrations допускаются только для будущих bootstrap/correction workflow. |

## Поэтапный план реализации MVP

### Этап 0 — контракт и security foundation

Цель: ввести self identity resolver и read-only endpoint, не меняя HR access
paths.

**Backend-файлы:**

- новый `app/services/self_personal_card_access_service.py`;
- новый `app/api/ppr_self_router.py` и `app/api/ppr_self_schemas.py`;
- `app/main.py` — регистрация router;
- при необходимости internal adapter в `app/ppr/read/query_service.py` и
  `app/api/ppr_mappers.py`, без изменения публичного HR response contract.

**API:** `GET /api/ppr/me` возвращает `READY` с self-safe composite или
`PERSON_NOT_LINKED`/`NO_EMPLOYEE_LINK`/`IDENTITY_AMBIGUOUS`. Ни URL, ни query,
ни body не содержат subject IDs.

**Тесты:**

- active linked User читает только собственный Person без generic visibility;
- `employee_id=228`/`user_id=1245` получает `PERSON_NOT_LINKED`;
- User без Employee, inactive User и multiple active Employee/Person links не
  получают чужую карточку;
- `PERSONNEL_EVENTS_READ` не влияет на self resolver;
- body/query/path с подставленными IDs отвергаются схемой либо игнорируются;
- existing `/api/ppr/persons/*`, `/directory/employees` и HR access matrix не
  меняются.

**Критерий приёмки:** self endpoint не вызывает `compute_scope()` или
`require_personnel_visibility_or_403`; в аудите/логах нет раскрытия чужих IDs.

### Этап 1 — навигация и read-only self-card

Цель: заменить заглушку «Образование» полноценной собственной карточкой.

**Frontend-файлы:**

- новый `corpsite-ui/app/profile/personal-card/page.tsx` и
  `_components/PersonalCardSelfPageClient.tsx`;
- новый self API client/types рядом с `corpsite-ui/lib/api.ts`;
- `corpsite-ui/lib/positionCabinetNav.ts`;
- `corpsite-ui/components/PositionCabinetNav.tsx`;
- `corpsite-ui/app/education/page.tsx` — redirect only;
- удалить/не использовать content в `EducationPageClient.tsx` после redirect;
- `corpsite-ui/lib/personnelNav.ts` только для корректного route classification.

**UX:** загрузка, `PERSON_NOT_LINKED`, error state без technical IDs и READY
screen. Использовать обычную page scroll и существующий порядок
`PERSONAL_CARD_UI_SECTIONS`; HR-owned разделы объясняют причину read-only.

**Тесты:** Vitest для tab label/active state, redirect `/education`, no-card
state, read-only sections, absence of HR navigation and unsaved-state logic.

**Критерий приёмки:** рядовой пользователь видит «Личная карточка», но не
«Персонал»; URL `/education` не ведёт на удалённый экран; Employee без Person
не получает 404 или форму ручного ввода IDs.

### Этап 2 — own PDF

Цель: дать сотруднику PDF ровно той карточки и в том объёме, который доступен
на экране.

**Файлы:**

- новый route `corpsite-ui/app/profile/personal-card/pdf/route.ts` либо
  backend `GET /api/ppr/me/card/pdf`;
- новый self PDF loader рядом с
  `app/directory/personnel/_lib/personCardPdfData.server.ts`;
- reuse без копирования: `personCardPdfViewModel.ts`,
  `personCardPdfDocumentHtml.ts`, `personalCardSections.ts`,
  `intakePdfRouteHandler.ts`.

**Тесты:** self PDF не делает intake/application calls; section order совпадает
с registry; `tenure_calculation` отсутствует; current organisation берётся из
server-resolved assignment; masked/sensitive fields совпадают с `GET /me`;
без Person — controlled no-card response.

**Критерий приёмки:** PDF не имеет Person ID в browser route, не открывает
чужой документ и не повышает права пользователя.

### Этап 3 — narrow self-edit

Цель: безопасно добавить три утверждённых employee-owned раздела.

**Backend-файлы:**

- расширить `ppr_self_router.py` self-only handlers;
- self command schemas для contacts, education, foreign languages;
- reuse `PprSectionApplicationService`, section/idempotency repositories и
  `personnel_record_event_service` через self authorization adapter;
- отдельные event types/source `EMPLOYEE_SELF_SERVICE`; HR route
`ppr_card_command_router.py` не ослаблять.

**API:**

- `GET/PUT /api/ppr/me/contacts`;
- create/supersede/void education commands без subject ID;
- `GET/PUT /api/ppr/me/foreign-languages`.

**Frontend-файлы:** self-specific section editors, используя existing form
controls/adapters только как presentation layer; не импортировать HR API client
или intake writer.

**Тесты:**

- 403 inactive/unlinked user; self user cannot select another subject;
- contact create/update and stale version → 409;
- education create/supersede/void сохраняют record lineage; void reason
  required; replay command id is idempotent;
- language required/duplicate validation and preservation of unrelated
  `additional_profile` keys;
- audit has actor, server before/after, self source and command id;
- UI edit/save/cancel/unsaved warning/error 403/409/422 and card refresh.

**Критерий приёмки:** изменение одного раздела не очищает соседние records,
JSON keys, provenance или HR-owned fields; audit trail объясняет, что действие
совершил сотрудник.

### Этап 4 — rollout и regression gate

Цель: включить MVP только после проверки изоляции и обратной совместимости.

**Проверки:** адресные pytest на `corpsite_test`, relevant Vitest, ESLint
изменённых frontend files, `npm run build`, `compileall`, `git diff --check`.
Тестировать реальные state fixtures: linked Person, Employee 228 без Person,
observer с `PERSONNEL_EVENTS_READ`, HR reader и public intake token.

**Критерий приёмки:** все security regressions проходят; event observer по-
прежнему не видит PPR, self employee не видит кадровый журнал/реестр, HR PDF и
applicant PDF не меняют contract. Commit/deploy — только отдельным решением.
