--------------------------------------------------

Document Status

Document:
WP-HR-CARD-002

Title:
Unified Personnel Record Card — User-Facing Consolidation

Type:
Architecture Work Package

Status:
Approved — Ready for Implementation

Revision:
5

Date:
2026-09-06

Approval date:
2026-09-06

Parent program:
WP-HR-CARD (Employee Card UX unification)

Depends on:
ARCH-002, ADR-054 (Accepted — normative priority), ADR-045, ADR-050

Related (context only):
ADR-047, ADR-055, ADR-061, ADR-065

Purpose:
Fix the implemented baseline and define the target user-facing structure of the unified
personnel record card, including photo, controlled corrections and an internal printable
PDF representation.

Normative priority:
[ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) (Accepted) takes
precedence over this document. On any conflict, ADR-054 and ARCH-002 normative
sections govern. Existing-card repair remains governed separately by
[ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md).

--------------------------------------------------

# WP-HR-CARD-002 — Unified Personnel Record Card

## Decision Summary

| Topic | Decision |
|-------|----------|
| **Domain object (unchanged)** | **Personnel Personal Record (PPR)** = **Личный листок по учёту кадров** — самостоятельный предметный объект кадрового контура. |
| **Stable PPR identifier** | **`person_id`** — устойчивый идентификатор PPR. **`employee_id` не является идентификатором PPR.** |
| **Canonical UI route** | Каноническая карточка строится по Person и открывается по `/directory/personnel/persons/{personId}/card`. |
| **Employee compatibility route** | `/directory/personnel/employees/{employeeId}/card` разрешает `employees.person_id` и перенаправляет на Person-карточку. Он не создаёт отдельную Employee-карточку. |
| **Primary UI representation** | **Личная карточка по учёту кадров** — составное интерактивное представление PPR и связанных кадровых проекций; не master-storage. |
| **Card layout** | В верхней части карточки фото располагается рядом с основными сведениями; рядом доступны действия **«Редактировать»** и **«Печать личной карточки»**. Ниже располагаются утверждённые самостоятельные разделы карточки. |
| **Photo** | Используется существующая person-owned модель `person_photos` и person-scoped файловое хранилище. |
| **Printed representation v1** | **Внутренняя печатная копия электронной личной карточки формата A4**, сформированная из той же Person/PPR-модели. Первая страница содержит фото и основные сведения. Полная государственная/унифицированная форма сейчас не заявляется. |
| **Corrections** | Разделяются непосредственное HR-редактирование разрешённых полей и предложение сотрудником исправления с последующим HR-review/apply. |
| **Existing-card repair** | `EXISTING_CARD_REPAIR` из ADR-065 не является обычным редактированием Person: он исправляет связи Person/Employee и назначения. |

Этот документ не создаёт второй кадровый aggregate и не переносит authority из PPR,
Employment, Personnel Orders, Documents или других исходных bounded contexts в UI-карточку.

---

## 1. Architectural Principle (PPR-REP-001)

Проект различает:

1. **domain object** — Personnel Personal Record / Личный листок по учёту кадров;
2. **interactive representation** — Личная карточка по учёту кадров;
3. **derived document representation** — печатная PDF-копия или другой экспорт.

| Representation | Layer | Aggregate? |
|----------------|-------|------------|
| Personnel Personal Record | Domain | **Да** — единый PPR aggregate, Person-root в текущей фазе |
| Личная карточка | UI / Composite View | **Нет** — projection и interaction shell |
| PDF / export / snapshot | Document | **Нет** — производный артефакт |

Следствия:

- экран и PDF читают канонические данные, но не становятся их владельцами;
- `person_id` остаётся идентичностью карточки независимо от кадровых эпизодов Employee;
- Employment Relationship и Employee остаются соседними bounded contexts;
- добавление UI, печати или workflow исправлений не создаёт параллельный реестр кадровых данных;
- любой write должен использовать утверждённый writer соответствующего источника истины.

---

## 2. Текущее состояние (implemented baseline)

### 2.1. Person-rooted card and navigation

Каноническая страница:

```text
/directory/personnel/persons/{personId}/card
    → PPR composite read by person_id
```

Совместимый Employee-маршрут:

```text
/directory/personnel/employees/{employeeId}/card
    → resolve employees.person_id
    → redirect to /directory/personnel/persons/{personId}/card
```

Таким образом, Employee URL является только compatibility/navigation adapter. После
разрешения идентичности пользователь работает с одной Person-карточкой. Redirect должен
сохранять поддерживаемые deep-link и return-to параметры и не должен подменять
`employee_id` значением `person_id`.

Карточка формируется составным PPR read API:

```text
GET /api/ppr/persons/{person_id}
GET /api/ppr/persons/{person_id}/summary
GET /api/ppr/employees/{employee_id}       # compatibility read
```

Доступ к чтению определяется кадровой visibility и организационным scope. Отдельный
self-service доступ сотрудника только к собственной Person-карточке пока не реализован.

### 2.2. Уже работающие разделы и режимы доступа

| Раздел на текущем экране | Что отображается | Текущий режим |
|--------------------------|------------------|---------------|
| **Общие сведения** | ФИО, раздельные части имени, ИИН с учётом права доступа, дата рождения, статус карточки и кадровая связь | **Только чтение** |
| **Образование** | Действующие, заменённые и аннулированные записи; организация, вид, специальность, квалификация, период | **Только чтение** |
| **Обучение и повышение квалификации** | Название, вид, организация, период и сводные показатели | **Только чтение** |
| **Родственники** | Степень родства, ФИО, дата/место рождения, организация, адрес и примечание | **Только чтение** |
| **Знание иностранных языков** | Существующие сведения о владении иностранными языками | **Только чтение** |
| **Дополнительные сведения** | Награды, учёные степени и звания, а также структурированные факты «Примечания»: пенсионный статус и инвалидность | **Только чтение**; чувствительные факты выдаются только при действующем кадровом доступе |
| **Трудовая биография** | Внешние трудовые эпизоды и история версий | **Редактирование уполномоченным HR** через create/void/supersede PPR-команды; для остальных — чтение |
| **Воинский учёт** | Статус и категория учёта, состав, звание, годность, ВУС, военкомат, даты и ограниченные реквизиты | **Редактирование уполномоченным HR** через create/void/supersede PPR-команды; чувствительные поля выдаются отдельно по праву |
| **Предполагаемое трудоустройство** | Планируемые группа, подразделение, должность и ставка претендента | **Редактирование уполномоченным HR**, только в candidate-контексте |
| **Текущее назначение** | Группа подразделений, подразделение, должность, operational enrollment status | **Кадровая корректировка доступна уполномоченному HR**; текущая реализация изменяет разрешённые поля существующего Employee и пишет событие `CORRECTION` |
| **Кадровые приказы** | Связанные приказы сотрудника | **Только чтение в карточке**; команды приказа принадлежат отдельному workflow |
| **Кадровые обращения** | История Personnel Application для Person | **Только чтение в карточке**; lifecycle обращения ведётся отдельно |
| **Адаптация** | Связанный onboarding сотрудника | **Связанный operational workflow**, не редактирование PPR-полей карточки |
| **История изменений** | Краткая хронология PPR/кадровых событий | **Только чтение** |

Текущий экран не содержит фото/аватар, канонический раздел контактов, раздел документов
или кнопку печати всей личной карточки.

### 2.3. Граница существующего редактирования

Текущая возможность «Исправить ошибку в назначении» не является универсальным editor
личной карточки. Она ограничена разрешёнными полями существующего Employee: ФИО,
подразделение, должность, ставка, даты и operational status. Операция требует причины и
комментария и сохраняет before/after в кадровом событии.

Общие сведения Person, образование, обучение, родственники и дополнительные сведения
пока не имеют editor в канонической карточке. Наличие writer в intake/import контурах не
означает автоматического разрешения прямого редактирования этих полей из карточки.

### 2.4. Импортированные записи обучения в staging

Вкладка «Обучение и повышение квалификации» может показывать отдельную staging-таблицу
**«Из контрольного списка — требуется проверка»**. Это не часть `person_training`: записи
остаются в HR-import staging до отдельного утверждённого promotion-процесса. Одна строка
соответствует одному распознанному курсу и показывает название, даты начала и окончания,
часы, организацию, качество даты, текстовый review-статус и разрешённые действия кадровика.
Канонические и импортированные записи отображаются раздельно.

Исходный текст XLSX, лист, строка, batch и прочая provenance сохраняются в staging/audit
metadata, но не повторяются на экране карточки. Точные исходные даты имеют качество
`EXACT`; даты, рассчитанные из известного года и часов, — `CALCULATED` («Расчётная»).
Редактирование staging-записи не является редактированием канонической карточки и после
сохранения переводит её в «Требуется проверка». Подтверждение и отклонение — отдельные
кадровые решения с версией записи и историей действий. Сотрудник может предложить изменение
только собственной записи; кадровик рассматривает «было / предложено». Таблица показывает
подтверждённые и предварительные часы за пять лет. Статус и качество даты всегда передаются
текстом, не только цветом. Подробные правила review, дат и срока часов определены в
[WP-PPR-MIG-004A](../implementation/WP-PPR-MIG-004A-training-staging-review-and-validity.md);
canonical Stage 3 — в [WP-PPR-MIG-004](../implementation/WP-PPR-MIG-004-training-migration-plan.md).

---

## 3. Целевая структура Личной карточки

### 3.1. Верхняя часть карточки

В верхней части карточки формируется единый профильный блок:

- действующее фото сотрудника располагается рядом с основными сведениями Person/PPR;
- при отсутствии фото на его месте отображается явное текстовое пустое состояние;
- основные сведения содержат разрешённые вызывающему пользователю identity и профильные
  поля;
- рядом с фото и основными сведениями доступны действия **«Редактировать»** и
  **«Печать личной карточки»**;
- «Редактировать» открывает только действия и поля, разрешённые текущему пользователю, и
  не означает наличие общего unrestricted editor;
- «Печать личной карточки» формирует PDF по правилам §5.

На узком экране блок может перестраиваться вертикально, но фото, основные сведения и оба
действия должны оставаться однозначно связанными с одной Person-карточкой.

### 3.2. Утверждённые самостоятельные разделы

Ниже верхнего профильного блока располагаются утверждённые самостоятельные разделы
карточки в следующем порядке:

| Порядок | Раздел | Источник / назначение |
|---------|--------|-----------------------|
| 1 | **Контакты** | Канонически связанный contact projection; не копия данных в UI |
| 2 | **Текущее назначение** | Employment/Employee projection |
| 3 | **Образование и обучение** | `person_education`, `person_training` и относящиеся профессиональные сведения |
| 4 | **Трудовая биография** | `person_external_employment` и история версий |
| 5 | **Воинский учёт** | `person_military_service` с field-level ограничениями |
| 6 | **Родственники** | `person_relatives` |
| 7 | **Документы** | Связанный реестр документов и их реквизиты |
| 8 | **Приказы, обращения и история** | Personnel Orders, Personnel Applications, onboarding и event projections |

Существующие дополнительные сведения — языки, награды, учёные степени и звания — не
теряются при переходе к целевой структуре и отображаются внутри самостоятельного раздела
«Образование и обучение» как связанные профессиональные сведения, без изменения source
of truth.

Фото и основные сведения являются верхним профильным блоком, а не повторяются как
самостоятельные разделы ниже. Каждый самостоятельный раздел должен явно обозначать:

- источник данных и актуальность проекции;
- доступность только для чтения либо конкретное разрешённое действие;
- пустое состояние точным текстом **«Сведения отсутствуют»**, а не отсутствующим блоком;
- историю версий/изменений, когда она предусмотрена доменной моделью;
- field-level masking чувствительных данных.

---

## 4. Фото сотрудника

### 4.1. Source of truth and storage

Фото в личной карточке должно использовать существующие:

- таблицу `person_photos` для person-owned версий и метаданных;
- append-only provenance `person_photo_sources`;
- person-scoped файловое хранилище;
- существующие проверки JPEG, размера и SHA-256 checksum.

Нельзя создавать вторую avatar/photo таблицу, хранить байты в Person/PPR JSON или
использовать application-scoped intake-файл как постоянный URL карточки.

### 4.2. Read contract

- Карточка показывает не более одной действующей версии (`is_active=true`) для Person.
- При отсутствии действующего фото отображается текстовое пустое состояние.
- Байты выдаются только через авторизованный backend/API после проверки доступа к Person.
- Публичный файловый URL, прямой путь к filesystem или бессрочная публичная ссылка
  запрещены.
- Ответ должен использовать private/no-store cache policy и безопасный content type.

### 4.3. Upload and replacement

- Загрузка и замена канонического фото разрешены только уполномоченному HR.
- Замена создаёт новую версию и деактивирует/замещает прежнюю; историческая запись не
  перезаписывается.
- Для каждой версии сохраняются `person_id`, file ID/path, MIME type, byte size, checksum,
  источник, автор, время создания и provenance операции.
- Клиент не выбирает `person_id`, source или audit author в обход server-owned context.
- Ошибка публикации файла или записи метаданных не должна оставлять новую версию
  действующей без подтверждённого файла и checksum.

---

## 5. Печатная PDF-копия

### 5.0. Раздел «Примечание»

Печатное представление включает самостоятельный раздел **«Примечание»** только для
пользователя, которому разрешено чтение соответствующих кадровых данных. В нём
отображаются пенсионный статус и дата его наступления, а для инвалидности — дата
присвоения, группа и код МКБ-10. Отсутствующие значения не заменяются вычисленными
или предполагаемыми; они остаются предметом кадровой проверки. Свободный текст XLSX,
лист, строка и прочее provenance в печатной форме не показываются.

### 5.1. Product definition v1

На карточке добавляется действие **«Печать личной карточки»**.

PDF первой версии является **внутренней печатной копией электронной карточки** для
кадровой работы формата **A4**. Полная государственная/унифицированная форма сейчас не
заявляется: PDF не объявляется формой Т-2, официальным государственным бланком,
юридически самостоятельным оригиналом или заменой документов кадрового дела.

### 5.2. Data and layout contract

- Формат страницы — **A4**.
- PDF строится из той же канонической Person/PPR read-модели и тех же связанных кадровых
  проекций, что используются экраном; отдельная PDF-база или параллельный snapshot
  master-data запрещены.
- Первая страница PDF содержит действующее фото при наличии и основные сведения Person/PPR.
- В документе указываются дата/время формирования и версия PDF-шаблона.
- Действующее фото включается только при наличии и разрешённом доступе.
- Каждый пустой раздел сохраняет своё место и выводится с точным текстом
  **«Сведения отсутствуют»**.
- Порядок и названия разделов согласуются с целевой структурой §3.
- Значения форматируются для печати без изменения исходной семантики и точности дат.

### 5.3. Authorization and audit

- Полный ИИН включается только если вызывающий пользователь имеет соответствующее право
  на чувствительные identity fields. Иначе применяется та же маскировка, что и в
  канонической экранной проекции.
- Field-level ограничения, включая закрытые реквизиты воинского учёта, применяются до
  рендеринга HTML.
- Каждое успешное формирование PDF записывается в аудит как минимум с `person_id`, actor,
  временем, версией шаблона и результатом; содержимое PDF и полные персональные данные в
  audit payload не сохраняются.
- Ошибка авторизации или формирования не должна возвращать частичный PDF.

### 5.4. Rendering approach

Следует переиспользовать существующий проектный подход:

```text
canonical Person/PPR ViewModel
    → versioned HTML/CSS template
    → headless Chromium / Playwright
    → PDF A4
```

Переиспользуются общая browser lifecycle infrastructure, безопасная загрузка шрифтов,
настройки печатной страницы и обработка ошибок, уже применяемые для intake и Personnel
Order PDF. Шаблон личной карточки остаётся отдельным versioned template.

---

## 6. Режимы исправления данных

### 6.1. Непосредственное HR-редактирование

Уполномоченный HR может непосредственно изменить только поля из утверждённого allowlist.

Обязательные свойства:

- отдельное permission на действие и проверка организационного scope;
- server-owned выбор writer/source of truth для каждого поля;
- optimistic concurrency или эквивалентная stale-state защита;
- обязательная причина для существенных кадровых исправлений;
- неизменяемый audit с actor, временем, полем, старым и новым значением и результатом;
- version/void/supersede вместо потери истории там, где раздел имеет версионную модель;
- отсутствие создания второго Person или Employee при обычном исправлении поля.

### 6.2. Предложение исправления сотрудником

Сотрудник не редактирует официальную Person/PPR-запись напрямую. Он может предложить
исправление только собственных данных после однозначного server-side разрешения:

```text
authenticated User → own Employee → own Person
```

Целевой workflow:

```text
employee proposal
    → HR review
    → approve / reject / request information
    → explicit HR apply through the canonical writer
```

Предложение хранит field identity, исходное значение/версию, предлагаемое значение,
комментарий и разрешённые доказательства. Решение HR и фактическое применение являются
разными аудируемыми действиями. Одобрение не обходит повторную проверку current value,
permission, scope и доменных инвариантов перед apply.

### 6.3. Граница ADR-065

Обычное редактирование Person/PPR нельзя смешивать с `EXISTING_CARD_REPAIR` из ADR-065.

| Контур | Назначение |
|--------|------------|
| **Обычное редактирование карточки** | Изменение разрешённого значения существующей канонической записи через writer её bounded context |
| **Предложение сотрудника** | Запрос на исправление собственных данных с HR review/apply |
| **ADR-065 `EXISTING_CARD_REPAIR`** | Исправление разрывов и противоречий связей Person/Employee и lifecycle назначений, включая link/open/correct/replace assignment |

ADR-065 не должен использоваться как общий endpoint изменения ФИО, контакта, образования,
документа, родственника, фотографии или другого Person-owned поля.

---

## 7. Навигация и терминология

### 7.1. Navigation rule (EMP-NAV-001)

UI-элемент с известным `person_id` должен вести непосредственно в каноническую
Person-карточку. Если вызывающий контекст имеет только `employee_id`, используется
совместимый Employee-маршрут с server-backed identity resolution и redirect.

При невозможности разрешить Person интерфейс обязан показать явную причину и не открывать
похожую карточку по совпадению ФИО или другому неустойчивому признаку.

### 7.2. Terminology

| Термин | Значение |
|--------|----------|
| **Личный листок по учёту кадров / PPR** | Domain object |
| **Личная карточка по учёту кадров** | Основное интерактивное UI-представление PPR |
| **Внутренняя печатная копия личной карточки** | PDF v1, derived representation |
| **Employee Card** | Техническое название Composite View, не отдельный aggregate |
| **HR Dossier / Кадровое досье** | Legacy UI term; не отдельный источник данных |
| **Рабочая карточка** | Preview UI, не канонический PPR editor |

---

## 8. Этапы реализации

Этапы выполняются последовательно; каждый использует существующие источники истины и не
создаёт параллельного профиля сотрудника.

| Этап | Результат | Основная граница |
|------|-----------|------------------|
| **1. Просмотр фото в карточке** | Авторизованный read API активной `person_photos` версии, placeholder и отображение в Person-карточке | Без manual upload в первом read slice; без публичного URL |
| **2. Печатный PDF** | Кнопка «Печать личной карточки», A4 HTML/CSS → Playwright PDF, template version и аудит | Внутренняя копия, не государственная форма |
| **3. Контакты и документы** | Канонические read-проекции и разделы с явными empty states | Сначала определить authority и устойчивую Person-связь; не копировать данные в card storage |
| **4. HR-редактирование общих сведений** | Field allowlist, permissions, canonical writers, stale-state guard и audit | Не использовать legacy Employee correction как writer всех Person-полей |
| **5. Предложения сотрудника и согласование HR** | Own-data self-view, proposal/evidence model, HR review и отдельный apply | Нет прямого self-edit; решение и применение разделены |

Замена фото уполномоченным HR может быть реализована после read slice этапа 1 либо вместе
с этапом 4, но обязана соблюдать §4.3.

---

## 9. Implementation details to close

Утверждённая продуктовая структура не зависит от следующих технических деталей. Они
закрываются в соответствующих implementation work packages до включения функции:

| ID | Решение |
|----|---------|
| IMPL-1 | Точный состав и field-level visibility PDF v1, включая воинские реквизиты |
| IMPL-2 | Canonical authority и Person-link для контактов и существующих Employee Documents |
| IMPL-3 | Allowlist прямого HR-редактирования и writer для каждого поля общих сведений |
| IMPL-4 | Allowlist полей, по которым сотрудник может предлагать исправления, и допустимые evidence types |
| IMPL-5 | Retention generated PDF: stream-only в v1 или отдельный versioned artifact позднее |

IMPL-5 не блокирует stream-only PDF первой версии: сформированный файл может возвращаться
без постоянного хранения при обязательной audit-записи факта формирования.

---

## 10. Risks and controls

| Risk | Control |
|------|---------|
| Появление второго профиля данных внутри карточки | Composite View only; canonical writer per field |
| Ошибочная трактовка PDF как официальной формы | Явная маркировка v1 как внутренней печатной копии |
| Утечка ИИН или закрытых воинских данных в PDF | Field-level authorization before ViewModel/rendering |
| Публичный доступ к фото | Только авторизованный API; no public file URL; private/no-store |
| Потеря истории при замене фото или записи | Новая версия + supersede/void, checksum и provenance |
| Прямое self-edit официальных данных | Proposal workflow; HR review и отдельный guarded apply |
| Использование ADR-065 для обычного Person edit | Явная граница §6.3 и разные application services |
| Рассинхронизация экрана и PDF | Общая каноническая Person/PPR read-модель |

---

## 11. Backward Compatibility

| Artifact | Policy |
|----------|--------|
| `/directory/personnel/persons/{personId}/card` | **Canonical and retained** |
| `/directory/personnel/employees/{employeeId}/card` | **Retained as compatibility redirect** |
| `GET /api/ppr/employees/{employee_id}` | Transitional compatibility read; canonical identity remains Person |
| Existing PPR section reads and commands | Retained; access rules remain server-owned |
| Legacy import-card | Retained as a separate transitional/rollback route; not merged into canonical card implicitly |
| ADR-054 | Not amended |
| ADR-065 | Not amended and not reused for ordinary Person editing |

---

## 12. References and implementation evidence

| Document / component | Role |
|----------------------|------|
| [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) | Normative PPR aggregate and Person-root identity |
| [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md) | Master architecture; card as Composite View |
| [WP-PR-002](./WP-PR-002-aggregate-boundary-specification.md) | PPR section boundaries |
| [ADR-047](../adr/ADR-047-appendix-service-record-and-pdf-export.md) | Earlier personal-file/PDF analysis; PDF v1 in this WP remains internal |
| [ADR-061](../adr/ADR-061-canonical-person-photo-and-test-application-deletion-policy.md) | Canonical Person photo ownership and storage |
| [ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md) | Separate Person/Employee link and assignment repair protocol |
| `corpsite-ui/app/directory/personnel/persons/[personId]/card/page.tsx` | Canonical Person-card route |
| `corpsite-ui/app/directory/personnel/employees/[employeeId]/card/page.tsx` | Employee compatibility route |
| `corpsite-ui/app/directory/personnel/_components/PprPersonalCardPageClient.tsx` | Current composite card UI |
| `app/api/ppr_router.py`, `app/api/ppr_command_router.py` | Current read and section-command API |
| `app/db/models/person_photos.py`, `app/person_photos/` | Existing canonical photo model and storage |
| `corpsite-ui/app/intake/_lib/intakePdfRenderer.ts` | Existing HTML/CSS → Playwright PDF approach |
| `corpsite-ui/app/directory/personnel/_lib/personnelOrderPdfRenderer.ts` | Existing A4 Playwright PDF infrastructure |

---

## Imported training split

The separate staging table on the Training tab gives an authorised HR user a
textual **Split** action.  Confirming a split hides the merged parent row and
shows two child rows with the normal review actions; **Undo split** restores
the parent without physically deleting either history or children.  This never
changes canonical `PersonTraining`, `Person`, or `Employee`.  The normative
algorithm and audit rule are in
[WP-PPR-MIG-004A](../implementation/WP-PPR-MIG-004A-training-staging-review-and-validity.md).

## Revision history

| Rev | Date | Changes |
|-----|------|---------|
| 1 | 2026-07-15 | Initial draft |
| 2 | 2026-07-15 | Terminology alignment with ADR-054: PPR = Личный листок (domain); Личная карточка (UI); печатная форма (document); person_id vs employee_id; HR Dossier legacy status; ADR-055 demoted to Related |
| 3 | 2026-07-15 | Added normative Architectural Principle PPR-REP-001 (representations are not independent aggregates) |
| 4 | 2026-09-06 | Recorded the implemented Person-rooted card and Employee redirect; classified current sections by editability; defined target card structure, canonical photo requirements, internal A4 PDF, direct HR edit versus employee proposal workflow, ADR-065 boundary and staged delivery plan. Status set to Draft — Ready for Product Review. |
| 5 | 2026-09-06 | Product decisions approved: photo and main details form the upper card block with «Редактировать» and «Печать личной карточки» actions; standalone sections follow below; PDF v1 is an internal A4 copy whose first page contains photo and main details, with explicit empty-section text and no claim of a state/unified official form. Status set to Approved — Ready for Implementation. |
