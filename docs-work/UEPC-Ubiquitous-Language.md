# UEPC — Ubiquitous Language (Единый язык предметной области)

**Document:** UEPC-Ubiquitous-Language  
**Title:** Единый словарь кадрового контура (DDD Ubiquitous Language)  
**Type:** Domain Language Reference  
**Status:** Draft — Ready for HR & Architecture Review  
**Revision:** 1  
**Date:** 2026-07-21  
**Set:** UEPC document set (4 of 4)

**Purpose:** Зафиксировать **единые бизнес-термины** проекта Corpsite для UEPC / Person Master Data, устранить неоднозначности между смежными понятиями и обеспечить согласованность будущих ADR, API, UI и документации.

**Explicit non-goals:** код, миграции, ADR, commit, deploy.

---

## 0. Правила использования словаря

1. **Официальное название** — единственный нормативный термин в ADR, API, UI labels (если не указан отдельный user-facing синоним).
2. **Запрещённые синонимы** — помечены явно; не использовать в новой документации.
3. **Сущность vs проекция** — каждый термин классифицирован по DDD-роли.
4. **Bounded Context (BC)** — владелец данных и правил мутации.
5. Маркер **⚠️ TBD** — требует решения кадровиков или архитектуры.

---

## 1. Ключевые термины (разбор неоднозначностей)

Для каждого термина: официальное название, определение, назначение, тип (сущность / проекция), BC, жизненный цикл, автономность, отличия от похожих терминов.

---

### 1.1 Person (Персона)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Person** (Персона) |
| **Краткое определение** | Устойчивая юридико-идентификационная сущность физического лица в системе (`person_id`, ИИН, ФИО, merge chain). |
| **Назначение** | Якорь идентичности для всех кadровых и смежных контуров; не хранит биографические разделы листка. |
| **Тип** | **Самостоятельная сущность** (aggregate root Identity BC) |
| **Bounded Context** | **Identity** |
| **Жизненный цикл** | `created` → `active` → (optional) `merged` / `inactive`; не зависит от приёма на работу. |
| **Может существовать самостоятельно** | **Да** — Person может существовать без активированного PPR и без Employee. |
| **Отличия** | **≠ Employee** (операционная оболочка); **≠ Applicant** (роль, не сущность); **≠ Canonical PPR** (Person — identity root, не кadровый листок); **≠ Person Master Data** (PMD — биографические факты, не legal identity). |

**Запрещённые синонимы:** «сотрудник» (для Person), «кандидат» (для Person).

---

### 1.2 Employee (Сотрудник)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Employee** (Сотрудник) |
| **Краткое определение** | Операционная оболочка трудовых отношений: доступ, задачи, текущее размещение (`employee_id`, связь с `person_id`). |
| **Назначение** | Контур Employment: текущая должность, подразделение, ставка, operational events, UI-навигация по `employee_id`. |
| **Тип** | **Самостоятельная сущность** (в составе Employment BC; snapshot placement — часть operational state) |
| **Bounded Context** | **Employment** |
| **Жизненный цикл** | Создаётся при HIRE → `active` → TRANSFER / POSITION_CHANGE → `terminated`; один Person может иметь несколько Employee-эпизодов во времени (rehire). |
| **Может существовать самостоятельно** | **Нет** без Person; **да** без полного PPR (edge case — operational-only, не целевой). |
| **Отличия** | **≠ Person** (identity vs operational); **≠ Applicant** (Applicant — до HIRE); **≠ Canonical PPR** (Employee не хранит образование, послужной список); **≠ Personnel Event** (Employee — текущее состояние, Event — факт изменения). |

**User-facing:** «Сотрудник» — корректно для Employee; не использовать для Person без employment.

---

### 1.3 Applicant (Претендент)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Applicant** (Претендент) |
| **Краткое определение** | **Роль** физического лица до оформления трудовых отношений; бизнес-процесс представлен агрегатом **Personnel Application**. |
| **Назначение** | Первичный сбор анкеты, intake link, gate перед HIRE; declared data до HR approve. |
| **Тип** | **Роль**, не отдельная persistence-сущность; процесс — **Personnel Application** (сущность) |
| **Bounded Context** | **Application** |
| **Жизненный цикл** | Регистрация → intake fill → HR review → transfer/approve → **HIRE** → роль трансформируется в **Employee** (тот же `person_id`). |
| **Может существовать самостоятельно** | Роль — **нет** без Person; Application — **да** как pre-hire aggregate. |
| **Отличия** | **≠ Person** (Person — постоянная identity); **≠ Employee** (Employee — после HIRE); **≠ Change Proposal** (intake — pre-hire channel; proposal — post-hire изменения). |

**Запрещено:** моделировать Applicant как отдельный aggregate root наряду с Person.

---

### 1.4 Personnel Personal Record / Canonical PPR

| Аспект | Описание |
|--------|----------|
| **Официальное название (EN)** | **Personnel Personal Record (PPR)** — domain object; **Canonical PPR** — нормативное состояние aggregate |
| **Официальное название (RU)** | **Личный листок по учёту кадров** |
| **Краткое определение** | Person-owned aggregate биографических и профессиональных **фактов**: envelope + секции `person_*` + audit; идентификатор Phase 1 — `person_id`. |
| **Назначение** | Единственный **System of Record** биографических данных человека в организации. |
| **Тип** | **Самостоятельная сущность** (aggregate **PersonnelPersonalRecord**) |
| **Bounded Context** | **Person Master Data (PMD)** |
| **Жизненный цикл** | Materialize (CANDIDATE) → section commits (supersede-only) → `EMPLOYED` context → `FORMER` → archive; **не копируется** при rehire (INV-3). |
| **Может существовать самостоятельно** | **Нет** без Person; **да** без Employee (Candidate path). |
| **Отличия** | **≠ Person** (identity anchor vs кadровый листок); **≠ UEPC** (PPR — domain SoT, UEPC — продукт/UI); **≠ Личная карточка** (UI projection); **≠ MRD/CL** (monthly/report projections); **≠ Staging/Proposal** (non-canonical). |

**Canonical PPR** = подмножество PPR: только **verified** active records + envelope; pending/rejected исключены из расчётов.

**Запрещённые синонимы:** «employee card data», «import profile» (как SoT), «HR dossier» (как SoT).

---

### 1.5 Person Master Data (PMD)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Person Master Data (PMD)** |
| **Краткое определение** | Архитектурное имя bounded context и stored-facts слоя: Canonical PPR + Change Proposals + PPR Snapshots + mutation audit. |
| **Назначение** | «Цифровой паспорт человека» в кadровом контуре — долговременные person-owned факты, не привязанные к одному `employee_id`. |
| **Тип** | **Bounded Context** (не отдельный business object; синоним контекста вокруг Canonical PPR) |
| **Bounded Context** | **Person Master Data** |
| **Жизненный цикл** | См. конвейер L0–L8 в [UEPC-Business-Lifecycle.md](./UEPC-Business-Lifecycle.md). |
| **Может существовать самостоятельно** | Контекст — да; данные — только через Person + materialized PPR. |
| **Отличия** | **≠ Person Identity BC** (IIN, merge); **≠ Employment BC** (assignments, orders); **≠ Employee operational shell**; **= Canonical PPR** на уровне stored facts. |

---

### 1.6 UEPC (Unified Electronic Personal Card)

| Аспект | Описание |
|--------|----------|
| **Официальное название (EN)** | **UEPC** — Unified Electronic Personal Card |
| **Официальное название (RU)** | **Единая электронная личная карточка** |
| **Краткое определение** | Целевой **продукт** и UX-концепция единой электронной карточки человека на базе Canonical PPR, включая self-service proposals, evidence, trust tiers. |
| **Назначение** | Объединить каналы (intake, employee LC, HR card, Telegram delivery) вокруг одного person-owned досье. |
| **Тип** | **Продукт / capability** — не aggregate; read/write через PMD BC |
| **Bounded Context** | Cross-cutting presentation над **Person Master Data** |
| **Жизненный цикл** | Roadmap capability; не имеет собственного persistence root. |
| **Может существовать самостоятельно** | **Нет** — всегда проецирует/мутирует Canonical PPR через commands. |
| **Отличия** | **≠ Canonical PPR** (UEPC — продукт; PPR — SoT); **≠ Личная карточка** (UEPC шире — включает intake, proposals, Telegram); **≠ MRD/CL** (downstream projections). |

---

### 1.7 Личная карточка

| Аспект | Описание |
|--------|----------|
| **Официальное название (RU)** | **Личная карточка по учёту кадров** |
| **Официальное название (EN, technical)** | **Personnel Record Card** / **PPR Composite View** |
| **Краткое определение** | Основное **интерактивное UI-представление** PPR: composite read + HR/employee actions (PPR-REP-001). |
| **Назначение** | Просмотр и редактирование (через proposals/direct HR) биографических данных; навигация EMP-NAV-001. |
| **Тип** | **Проекция** (Composite View; INV-5) |
| **Bounded Context** | Presentation layer; данные — **Person Master Data** + read-only Employment projection |
| **Жизненный цикл** | UI session; данные следуют lifecycle PPR. |
| **Может существовать самостоятельно** | **Нет** — всегда привязана к `person_id` / transitional `employee_id` nav. |
| **Отличия** | **≠ PPR** (domain object vs UI); **≠ Кадровое досье** (legacy term); **≠ печатная форма** (derived document); **≠ Employee Card** (technical ARCH-002 term — converge под «Личная карточка»). |

---

### 1.8 Кадровое досье

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **HR Dossier** (legacy) — пользовательский термин «Кадровое досье» |
| **Краткое определение** | **Устаревшее** composite UI + service: PPR sections + Employment + import staging. |
| **Назначение** | Transitional HR view; постепенно заменяется термином **Личная карточка**. |
| **Тип** | **Проекция** (legacy composite) |
| **Bounded Context** | Presentation (transitional) |
| **Жизненный цикл** | Deprecated terminology; route `/card` — transitional. |
| **Может существовать самостоятельно** | **Нет** |
| **Отличия** | **≠ PPR / UEPC** (не SoT); **≠ Личная карточка** (target term, тот же intent); **запрещено** использовать в новых ADR как domain object. |

---

### 1.9 Электронная личная карточка

| Аспект | Описание |
|--------|----------|
| **Официальное название (RU)** | **Электронная личная карточка** = синоним **Единой электронной личной карточки (UEPC)** |
| **Краткое определение** | Русскоязычное product name для UEPC. |
| **Назначение** | User-facing / regulatory wording. |
| **Тип** | **Продукт** (не domain entity) |
| **Bounded Context** | Cross-cutting над PMD |
| **Жизненный цикл** | См. UEPC |
| **Может существовать самостоятельно** | **Нет** |
| **Отличия** | **≠ бумажная личная карточка** (Source Document / digitization input); **≠ Личная карточка (UI)** — «электронная» подчёркивает продукт UEPC целиком, UI — один из каналов. |

---

### 1.10 Контрольный список (Control List, CL)

| Аспект | Описание |
|--------|----------|
| **Официальное название (RU)** | **Контрольный список** |
| **Официальное название (EN)** | **Control List (CL)** |
| **Краткое определение** | Ежемесячный **import/compare** контур: подмножество полей UEPC; staging + reconcile, не полная карточка. |
| **Назначение** | Bootstrap, сверка с verified PPR, генерация **Control List Row Projection** для отчётности. |
| **Тип** | **Проекция + временный import staging** (не SoT) |
| **Bounded Context** | **Integrations** (import) → **Reporting** (export projection) |
| **Жизненный цикл** | Monthly import → normalize → compare → Detected Difference → optional promote via approve → export projection. |
| **Может существовать самостоятельно** | Staging rows — временно; export row — derived, не автономен. |
| **Отличия** | **≠ Canonical PPR** (CL never write-back без Confirmed Change / approve path); **≠ MRD** (CL — operational compare; MRD — confirmed monthly reference); **≠ Control Output (target)** — future derived export from PPR+Employment. |

---

### 1.11 MRD (Monthly Reference Dataset)

| Аспект | Описание |
|--------|----------|
| **Официальное название (RU)** | **Месячный эталонный набор данных** |
| **Официальное название (EN)** | **MRD** — Monthly Reference Dataset |
| **Краткое определение** | Aggregate **MonthlyReferenceDataset**: версии по `report_period`, entries только из **Confirmed Change**, immutable when CLOSED. |
| **Назначение** | Регуляторный/управленческий **monthly lock** подтверждённых кadровых атрибутов. |
| **Тип** | **Самостоятельная сущность** (aggregate в MRD BC); entries — confirmed projection of PPR snapshot |
| **Bounded Context** | **MRD** |
| **Жизненный цикл** | Create version → `ACTIVE` → reconcile Detected Differences → Confirmed Changes → `CLOSED` (immutable) → fork to new period/version. |
| **Может существовать самостоятельно** | **Да** как aggregate; entries не автономны без person key. |
| **Отличия** | **≠ Canonical PPR** (live SoT vs frozen monthly slice); **≠ Snapshot** (PPR snapshot — input; MRD — regulatory store); **≠ CL import** (import → difference → confirm, не direct MRD write). |

---

### 1.12 Proposal (Change Proposal)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Change Proposal** (Предложение изменения) |
| **Краткое определение** | Aggregate **желаемого** состояния секции PPR до HR approve; state machine: draft → submitted → under_hr_review → approved/rejected/returned. |
| **Назначение** | Self-service path (Applicant/Employee) без прямой мутации Canonical PPR (INV-UEPC-02). |
| **Тип** | **Самостоятельная сущность** (aggregate **ChangeProposal**) |
| **Bounded Context** | **Person Master Data** |
| **Жизненный цикл** | Create → submit → HR review → approve (atomic PPR commit) / reject / return → terminal. |
| **Может существовать самостоятельно** | **Да** (привязан к `person_id`); не влияет на расчёты до approve. |
| **Отличия** | **≠ Verified Data** (proposal — intent T0–T1); **≠ Staging** (import-specific); **≠ Personnel Application intake** (pre-hire process aggregate). |

**Краткая форма «Proposal»** — допустима **только** как сокращение **Change Proposal** в контексте PMD.

---

### 1.13 Verified Data (Подтверждённые данные)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Verified Data** / **Verified value** |
| **Краткое определение** | Canonical PPR value с `verification_status = verified` (trust tier **T2+**); участвует в CL/MRD/tenure/payroll projections. |
| **Назначение** | Gate между declared и operational/regulatory use (INV-UEPC-04). |
| **Тип** | **Классификация stored fact**, не отдельная сущность |
| **Bounded Context** | **Person Master Data** (attribute on canonical rows) |
| **Жизненный цикл** | Устанавливается при HR approve / direct HR entry; снимается supersede/void, не «un-verify» silently. |
| **Может существовать самостоятельно** | **Нет** — always part of canonical section record. |
| **Отличия** | **≠ declared** (T1, proposal); **≠ document_confirmed** (T3, + evidence); **≠ MRD entry** (frozen monthly copy of verified slice). |

---

### 1.14 Staging (Промежуточный слой)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Staging** |
| **Краткое определение** | **Временное** pre-validation хранилище: intake drafts, import rows, OCR candidates, PMF items, normalized import records. |
| **Назначение** | Изолировать внешние каналы от Canonical PPR до HR reconcile/approve. |
| **Тип** | **Временное состояние** (не aggregate SoT) |
| **Bounded Context** | **Integrations**, **Application** (intake), **PMF** |
| **Жизненный цикл** | Ingest → review → promote (approve/transfer/commit) **или** discard; не append-only regulatory store. |
| **Может существовать самостоятельно** | **Да** временно; **не** authoritative. |
| **Отличия** | **≠ Proposal** (proposal — domain aggregate с lifecycle); **≠ Snapshot** (snapshot — immutable copy of verified facts); **≠ Import Profile** (structured staging view, still TEMPORARY). |

---

### 1.15 Snapshot (Снимок)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **PPR Snapshot** (`PprSnapshot`); контекстно — MRD frozen version, signed document snapshot |
| **Краткое определение** | **Неизменяемый** point-in-time срез verified PPR (whole-card payload) на `effective_at`. |
| **Назначение** | Audit, as-of read, MRD close input, legal export, payroll boundary. |
| **Тип** | **Immutable read artifact** (entity `PprSnapshot` в PMD BC для card; отдельные snapshot types в других BC) |
| **Bounded Context** | **Person Master Data** (PPR Snapshot); **MRD** (CLOSED version); **HR Documents** (signed order snapshot) |
| **Жизненный цикл** | Capture (on_approve \| on_mrd_close \| periodic \| manual \| pre_hire) → **immutable** → archive. |
| **Может существовать самостоятельно** | **Да** как stored artifact; всегда ссылается на `person_id`. |
| **Отличия** | **≠ live Canonical PPR** (mutable via supersede); **≠ event log** (per-mutation vs whole-card); **≠ Projection** (snapshot stored; projection computed on read); **≠ Staging** (staging mutable). |

**Disambiguation:** всегда квалифицировать: **PPR Snapshot**, **MRD Snapshot (CLOSED)**, **Signed Document Snapshot**.

---

### 1.16 Projection (Проекция)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Projection** (Проекция) |
| **Краткое определение** | **Read-only** производное представление из одного или более SoT без права прямой authoritative write-back. |
| **Назначение** | UI composite views, CL rows, MRD building blocks, tenure input assembly, internal HR section in card. |
| **Тип** | **Паттерн / класс артефактов** — не business aggregate SoT |
| **Bounded Context** | **Reporting**, Presentation, **Tenure** (input assembly), Employment→PMD UI |
| **Жизненный цикл** | Rebuilt on read or async refresh; invalidates on upstream domain events. |
| **Может существовать самостоятельно** | Materialized projections — да как cache; **не** SoT. |
| **Отличия** | **≠ Snapshot** (snapshot intentionally frozen at T); **≠ Computed indicator** (projection assembles facts; computed applies rules); **≠ Canonical PPR**. |

**Примеры:** Личная карточка, HR Dossier, ControlListRowProjection, Internal Employment History view, VerifiedTenureTimeline input.

---

### 1.17 Source Document (Документ-источник / основание)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Source Document** / **Basis Document** (`basis_document_ref`) |
| **Краткое определение** | Внешний или внутренний **юридический/нормативный** документ, на котором основан факт или кadровое действие (приказ, диплом, выписка из ТК). |
| **Назначение** | Lineage и trust T3; legal traceability. |
| **Тип** | **Reference** — может быть Personnel Order (Employment BC) или external doc via Evidence |
| **Bounded Context** | **HR Documents**, **Employment** (orders), **Person Master Data** (lineage pointer) |
| **Жизненный цикл** | Registration → (optional) signing → immutable; ссылка из FieldLineage / order item. |
| **Может существовать самостоятельно** | **Да** (Personnel Order, uploaded scan metadata). |
| **Отличия** | **≠ Evidence** (Evidence — person-owned scan registry + links; Source Document — semantic/legal notion); **≠ Snapshot** (export copy); **≠ Proposal attachment** (staging until approve). |

---

### 1.18 Evidence (Подтверждающий документ / Evidence)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Evidence** / **PPR-EVIDENCE** |
| **Краткое определение** | Person-owned реестр файлов (`person_evidence_documents`) + many-to-many links к полям/записям PPR; `scan_verification_status`. |
| **Назначение** | Повышение trust до **T3** (document_confirmed); gate для tenure-critical fields. |
| **Тип** | **Самостоятельная сущность** (aggregate **EvidenceDocument** в HR Documents BC) |
| **Bounded Context** | **HR Documents** (storage + verification); links target **Person Master Data** |
| **Жизненный цикл** | Upload (proposal or direct) → pending scan verify → verified/rejected → archived ⚠️ TBD retention. |
| **Может существовать самостоятельно** | **Да** (file entity); semantic value — только через link to PPR field. |
| **Отличия** | **≠ Source Document** (Evidence — artifact + scan workflow); **≠ Personnel Order PDF** (Employment DERIVED); **≠ employee_documents** (legacy employee-scoped — OUT, migrate to person-owned). |

---

### 1.19 Tenure (Стаж)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Tenure** / **Tenure Calculation** |
| **Краткое определение** | **Вычисляемый** показатель трудового стажа (общий, специальный, стажевые группы) по verified timeline + rule set. |
| **Назначение** | Payroll, льготы, отчётность; **никогда** не SoT в PPR (INV-UEPC-13). |
| **Тип** | **Computed indicator** (stateless **TenureCalculation** service) |
| **Bounded Context** | **Tenure** |
| **Жизненный цикл** | On-demand or event-triggered recalc; optional cache with `{rule_set_id, input_snapshot_id}`. |
| **Может существовать самостоятельно** | **Нет** как authoritative fact; cache — derivable. |
| **Отличия** | **≠ Employment Episode** (episode — stored/projected fact); **≠ verified_period** (stored HR-attested interval); **≠ MRD entry** (frozen attribute snapshot). |

---

### 1.20 Employment Episode (Эпизод трудовой деятельности)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Employment Episode** |
| **Краткое определение** | Один период работы: **External** — stored in `person_external_employment` (PPR); **Internal** — projection from `person_assignments` / personnel orders. |
| **Назначение** | Послужной список (Service Record); input для TenureEngine. |
| **Тип** | **External: stored fact (IN PPR)**; **Internal: projection (Employment BC)** |
| **Bounded Context** | **Person Master Data** (external); **Employment** (internal) |
| **Жизненный цикл** | External: create → verify → supersede; Internal: append-only via Personnel Events/Orders. |
| **Может существовать самостоятельно** | External episode — **да** in PPR without current Employee; Internal — **нет** без Employment relationship. |
| **Отличия** | **≠ Personnel Event** (Event — discrete HR act changing state); **≠ Employee** (current shell); **≠ Tenure** (computed sum over episodes). |

---

### 1.21 Personnel Record — disambiguation

| Аспект | Описание |
|--------|----------|
| **Официальное название** | См. **Personnel Personal Record (PPR)** — единственный нормативный domain term |
| **Краткое определение** | **«Personnel Record» без квалификатора — неоднозначен и запрещён** в новой документации. |
| **Назначение** | — |
| **Разрешённое использование** | Только в составе: **Personnel Personal Record**, **Personnel Record Card** (UI), **personnel_record_events** (audit), **Personnel Record Event** (если явно audit event PMD). |
| **Отличия** | **≠ Personnel Event** (Employment BC); **≠ employee record** (legacy HRIS term). |

---

### 1.22 Personnel Event (Кадровое событие)

| Аспект | Описание |
|--------|----------|
| **Официальное название** | **Personnel Event** |
| **Краткое определение** | **Primary business entity** Employment BC: дискретное изменение Personnel State (HIRE, TRANSFER, TERMINATION, …) с Change Set; регистрируется Personnel Order. |
| **Назначение** | Legal/operational truth для assignments, position, rate; reconstruction Personnel State. |
| **Тип** | **Самостоятельная сущность** (Employment / Personnel Orders domain) |
| **Bounded Context** | **Employment** / **HR Documents** (Personnel Orders) |
| **Жизненный цикл** | Created from Order Item → applied → (optional) void/reverse → immutable audit. |
| **Может существовать самостоятельно** | **Да** (linked to `employee_id` / person context). |
| **Отличия** | **≠ personnel_record_events** (PMD section audit, not employment act); **≠ Change Proposal** (biographical intent); **≠ Employment Episode** (timeline segment vs discrete event); **≠ Domain Event** (technical messaging — may correspond but not identical). |

---

## 2. Сводная таблица неоднозначностей (quick reference)

| Термин A | Термин B | Ключевое различие |
|----------|----------|-------------------|
| Person | Employee | Identity vs operational employment shell |
| Person | Applicant | Permanent identity vs pre-hire role |
| Applicant | Employee | До HIRE vs после HIRE (same `person_id`) |
| Canonical PPR | UEPC | Domain SoT vs product/UI concept |
| Canonical PPR | Person Master Data | Aggregate vs BC name (same stored facts) |
| Canonical PPR | Личная карточка | Domain object vs UI projection |
| Личная карточка | Кадровое досье | Target term vs legacy HR Dossier |
| Электронная личная карточка | Личная карточка (UI) | UEPC product vs primary UI shell |
| Canonical PPR | Контрольный список | SoT vs import/compare projection |
| Canonical PPR | MRD | Live verified facts vs CLOSED monthly reference |
| Proposal | Verified Data | Non-canonical intent vs approved canonical |
| Staging | Snapshot | Mutable pre-validation vs immutable as-of copy |
| Snapshot | Projection | Stored frozen payload vs derived read model |
| Projection | Computed (Tenure) | Assembled facts vs rule engine output |
| Source Document | Evidence | Legal/basis notion vs scan registry + links |
| Employment Episode | Personnel Event | Timeline segment vs discrete state change |
| Personnel Personal Record | Personnel Event | Biographical SoT vs employment act |
| personnel_record_events | Personnel Event | PMD audit journal vs Employment primary entity |

---

## 3. Каталог агрегатов

| Aggregate | Root / ID | Bounded Context | Responsibility | Consistency boundary |
|-----------|-----------|-----------------|----------------|----------------------|
| **PersonIdentity** | Person / `person_id` | Identity | IIN, legal identity, merge, `person_status` | One person per IIN policy |
| **PersonnelPersonalRecord** | PPR Envelope / `person_id` | Person Master Data | Person-owned sections, lifecycle, completeness | One PPR per Person; supersede-only mutations |
| **ChangeProposal** | `proposal_id` | Person Master Data | Desired state until HR approve | Proposal + evidence refs; approve → atomic PPR commit |
| **PersonnelApplication** | `application_id` | Application | Pre-hire intake, hire gate | One active application per person policy |
| **EmploymentRelationship** | Assignment context / `employee_id` | Employment | Current placement, enrollment | Orders apply → employee snapshot |
| **PersonnelOrder** | `order_id` | HR Documents | Legal HR acts wrapper | Order + items; links to Personnel Events |
| **PersonnelEvent** | `event_id` | Employment | Change Set, Personnel State mutation | One event → one Change Set |
| **EvidenceDocument** | `evidence_id` | HR Documents | File metadata + PPR field links | Scan verification independent per file |
| **ImportBatch** | `batch_id` | Integrations | Staging import, normalization | Batch rows; promote via ACL |
| **DetectedDifference** | `difference_id` | MRD | Compare CL/MRD vs live | One open DETECTED per logical key |
| **MonthlyReferenceDataset** | `mrd_id` / version | MRD | Monthly confirmed entries | One ACTIVE per report_period |
| **PprSnapshot** | `snapshot_id` | Person Master Data | Immutable whole-card capture | Append-only snapshot history |
| **TenureCalculation** | — (stateless) | Tenure | Rule application | Pure function; no aggregate store |

**Note:** **UEPC**, **Личная карточка**, **Control List export row** — **не агрегаты**.

---

## 4. Каталог Value Objects

| Value Object | Bounded Context | Описание | Примеры полей / кодов |
|--------------|-----------------|----------|------------------------|
| **PersonId** | Shared Kernel | Stable identifier | `person_id` UUID/int |
| **EmployeeId** | Employment | Operational key | `employee_id` |
| **Iin** | Identity | Individual identification number | 12-digit validated |
| **FieldLineage** | Person Master Data | Provenance overlay | `source_type`, `actor_kind`, `event_id`, `evidence_ids[]` |
| **SourceType** | Person Master Data | Channel enum | INTAKE, EMPLOYEE, HR, IMPORT, INTEGRATION, SYSTEM |
| **TrustTier** | Person Master Data | T0–T4 classification | draft, declared, hr_verified, document_confirmed, blocked |
| **VerificationStatus** | Person Master Data | Row-level gate | pending, verified, rejected, needs_attention, disputed |
| **SectionCode** | Person Master Data | PPR section registry | PPR-GENERAL, PPR-EDUCATION, … |
| **ReportPeriod** | MRD | Monthly bucket | `YYYY-MM` |
| **LogicalDifferenceKey** | MRD | Stable compare key | person + attribute path |
| **DifferenceOrigin** | MRD | Source of detected diff | IMPORT_COMPARE, MANUAL, … |
| **ConfirmedChangeRef** | MRD | Audit pointer | `confirmed_change_id` |
| **EmploymentEpisodePeriod** | Person Master Data / Tenure | Date interval | `started_at`, `ended_at`, `verified_period` |
| **ChangeSet** | Employment | Atomic attribute changes | previous/new pairs |
| **EventType** | Employment | Personnel Event classifier | HIRE, TRANSFER, TERMINATION, … |
| **EvidenceKind** | HR Documents | Document taxonomy | diploma, workbook_extract, military_id, … |
| **SnapshotKind** | Person Master Data | Capture trigger | on_approve, on_mrd_close, periodic, manual, pre_hire |
| **Money / Rate** | Employment | Compensation VO | FTE, rate fraction |
| **OrgPlacement** | Employment | Unit + position snapshot | `org_unit_id`, `position_id` |
| **MatchKey** | Identity | Dedup key | normalized name + birth date hash |
| **IntakeToken** | Application | Opaque TTL token | hashed, revocable |

---

## 5. Каталог Domain Events

### 5.1 Person Master Data

| Event | Producer | Key consumers |
|-------|----------|---------------|
| `PprSectionRecordCommitted` | PersonnelPersonalRecord | Audit log, lineage, projections, snapshot triggers |
| `PprRecordSuperseded` | PersonnelPersonalRecord | Tenure recalc, audit |
| `ChangeProposalCreated` | ChangeProposal | — |
| `ChangeProposalSubmitted` | ChangeProposal | HR work queue |
| `ChangeProposalReturned` | ChangeProposal | Employee notification |
| `ChangeProposalApproved` | ChangeProposal | PPR commit, snapshots, tenure |
| `ChangeProposalRejected` | ChangeProposal | Employee notification |
| `PprSnapshotCaptured` | PprSnapshot | MRD, archive, as-of read |

### 5.2 Identity & Application

| Event | Producer | Key consumers |
|-------|----------|---------------|
| `PersonIdentityEnsured` | PersonIdentity | Application, PPR materialize |
| `PersonMerged` | PersonIdentity | Survivor PPR linkage |
| `ApplicantRegistered` | PersonnelApplication | Notifications |
| `IntakeLinkIssued` | PersonnelApplication | Delivery channels |
| `IntakeQuestionnaireSubmitted` | PersonnelApplication | HR inbox |

### 5.3 Employment & HR Documents

| Event | Producer | Key consumers |
|-------|----------|---------------|
| `PersonnelOrderIssued` | PersonnelOrder | Workflow |
| `PersonnelOrderApplied` | PersonnelOrder | Employment BC, internal HR projection |
| `PersonnelEventRecorded` | PersonnelEvent | Personnel State reconstruction |
| `EmployeeHired` | Employment | PPR context CANDIDATE→EMPLOYED |
| `EmployeeTerminated` | Employment | PPR context update |

### 5.4 Evidence & Integrations

| Event | Producer | Key consumers |
|-------|----------|---------------|
| `EvidenceUploaded` | EvidenceDocument | Proposal review |
| `EvidenceScanVerified` | EvidenceDocument | Trust T3 boost |
| `ImportBatchReceived` | ImportBatch | Normalization pipeline |
| `ImportDifferenceDetected` | Import / MRD | HR reconcile UI |
| `ImportDifferencePromoted` | HR command path | PPR via approve |
| `OcrExtractionCompleted` | Integrations | Proposal pre-fill |

### 5.5 MRD & Tenure

| Event | Producer | Key consumers |
|-------|----------|---------------|
| `ConfirmedChangeRecorded` | MRD | Entry mutation audit |
| `MrdsPeriodClosed` | MonthlyReferenceDataset | Reporting lock |
| `TenureRecalculated` | Tenure | Payroll projection (optional persist) |

**Disambiguation:** `PersonnelEvent` (entity) ≠ `PprSectionRecordCommitted` (PMD audit). Naming in code/API must preserve BC prefix where ambiguous.

---

## 6. Каталог Commands

### 6.1 Identity & Application

| Command | Actor | Target | Effect |
|---------|-------|--------|--------|
| `EnsurePersonIdentity` | HR, System | PersonIdentity | Create/resolve Person by IIN |
| `RegisterApplicant` | HR | PersonIdentity + PersonnelApplication | Pre-hire registration |
| `IssueIntakeLink` | HR | PersonnelApplication | Enable intake URL |
| `SubmitIntakeQuestionnaire` | Applicant | PersonnelApplication | Declared data → review |
| `TransferIntakeToPpr` | HR | PPR (+ Application) | Staging → canonical (transitional) |

### 6.2 Person Master Data

| Command | Actor | Target | Effect |
|---------|-------|--------|--------|
| `MaterializePprEnvelope` | HR, System | PersonnelPersonalRecord | Create envelope CANDIDATE |
| `CreateChangeProposal` | Applicant, Employee | ChangeProposal | Draft proposal |
| `SubmitChangeProposal` | Applicant, Employee | ChangeProposal | → under_hr_review |
| `ReturnProposalForClarification` | HR | ChangeProposal | Rework loop |
| `ApproveChangeProposal` | HR | ChangeProposal + PPR | **Atomic** canonical commit + verified |
| `RejectChangeProposal` | HR | ChangeProposal | Terminal reject |
| `DirectAmendPprSection` | HR | PPR | Bypass proposal ⚠️ policy + audit |
| `SupersedePprRecord` | HR | PPR section row | New version, old superseded |
| `CapturePprSnapshot` | HR, System | PprSnapshot | Immutable whole-card capture |

### 6.3 Employment & Orders

| Command | Actor | Target | Effect |
|---------|-------|--------|--------|
| `IssuePersonnelOrder` | HR | PersonnelOrder | Legal act created |
| `ApplyPersonnelOrder` | HR, System | Employment | Mutate assignments/employee |
| `VoidPersonnelOrder` | HR | PersonnelOrder + Events | Rollback path |

### 6.4 Evidence & Integrations

| Command | Actor | Target | Effect |
|---------|-------|--------|--------|
| `AttachEvidence` | Applicant, Employee, HR | EvidenceDocument | Link file to proposal/record |
| `VerifyEvidenceScan` | HR | EvidenceDocument | T3 boost |
| `ImportPersonnelData` | System | ImportBatch | Staging only |
| `ReconcileImportDifference` | HR | Import + Proposal | Promote or reject |
| `ProcessOcrDocument` | System | Import / Proposal | Candidates only |

### 6.5 MRD & Tenure

| Command | Actor | Target | Effect |
|---------|-------|--------|--------|
| `ConfirmDetectedDifference` | HR | MRD + DetectedDifference | Confirmed Change → entry update |
| `RejectDetectedDifference` | HR | DetectedDifference | Terminal reject |
| `ForkMrdsVersion` | HR | MRD | New version from confirmed state |
| `CloseMrdsPeriod` | System, HR | MRD | Freeze ACTIVE → CLOSED |
| `ComputeTenure` | System | TenureCalculation | Derived read; **no PPR write** |

---

## 7. Каталог Projections

| Projection | Producer inputs | Consumer | Mutable? | SoT? |
|------------|-----------------|----------|----------|------|
| **PprCompositeReadModel** | Canonical PPR + envelope | HR card API, Личная карточка | No | No |
| **PprEmployeeSelfView** | PPR + open proposals overlay | Employee self-service | No | No |
| **InternalEmploymentHistoryView** | Personnel Events, assignments, orders | PPR card PPR-INTERNAL-HR section | No | No |
| **ControlListRowProjection** | Verified PPR + assignment | CL Excel export | No | No |
| **HrDossierView** (legacy) | PPR + Employment + import staging | Transitional `/card` | No | No |
| **EmployeeCardWorkingView** | Employment + partial PPR | Operational quick view | No | No |
| **MrdWorkspaceSnapshot** | ACTIVE MRD + differences | MRD UI | No | No (MRD aggregate is SoT for monthly entries) |
| **VerifiedTenureTimeline** | Verified external episodes + internal projection | TenureEngine input | No | No |
| **PayrollPersonProjection** | Tenure + qualification computed + MRD slice | Payroll ⚠️ TBD | No | No |
| **PprRegistryList** | PPR envelope metadata | HR registry browse | No | No |
| **ImportProfileView** | hr_import_rows normalized | Import UI | Staging edit | No |
| **PersonnelStateSnapshot** | Sequence of Personnel Events | Employment drawer | Rebuilt | No (Events are SoT) |

---

## 8. Каталог вычисляемых показателей

| Indicator | Canonical read key | Verified inputs | Engine | Min trust |
|-----------|-------------------|-----------------|--------|-----------|
| **Общий трудовой стаж** | `computed.tenure.total` | External + internal episodes | TenureEngine | T2/T3 ⚠️ policy |
| **Специальный стаж** | `computed.tenure.special.*` | Episodes + rule buckets | TenureEngine | T3 for strict fields |
| **Стажевая группа** | `computed.tenure.group` | Total + thresholds | TenureEngine | T2+ |
| **Дата следующей стажевой границы** | `computed.tenure.next_milestone_date` | Timeline + catalog | TenureEngine | T2+ |
| **Стаж в организации** | `computed.internal.tenure` | Personnel orders / assignments | InternalTenure ⚠️ TBD | T2 |
| **Effective qualification** | `computed.qualification.effective` | `qualification[]` active rows | QualificationEngine ⚠️ TBD | T2/T3 |
| **Проф. надбавка %** | `computed.pay.allowance_percent` | Category + tenure rules | PayrollProjection ⚠️ TBD | T2+ |
| **Completeness score** | `computed.card.completeness` | Required fields matrix | CompletenessEngine | N/A |
| **Возраст** | `computed.general.age` | `birth_date`, `as_of` | Display derive | T2 for display |
| **Full name display** | `general.full_name` | Name parts | SYSTEM derive on commit | T2 |

**Cache policy:** optional materialization **only** with `{rule_set_id, computed_at, input_snapshot_id}` (INV-UEPC-14).

---

## 9. Классификация: SoT / Projection / Computed / Temporary

| Класс | Что входит | Примеры | Правило мутации |
|-------|------------|---------|-----------------|
| **System of Record (SoT)** | Authoritative domain facts | Canonical PPR (`person_*`), Person Identity, Personnel Events (applied), Personnel Orders (legal), CLOSED MRD entries, Evidence metadata (file entity), Confirmed Change event log | Только через domain commands + invariants |
| **Projection** | Read-only derived views | Личная карточка, PprCompositeReadModel, Internal Employment History, ControlListRowProjection, CL export, MRD workspace UI, PersonnelStateSnapshot, Payroll read assembly | Rebuild from SoT; no authoritative write-back |
| **Computed value** | Rule engine output | Tenure totals, allowance %, completeness score, age, effective qualification | Never write to PPR; optional invalidatable cache |
| **Temporary state** | Pre-validation / transitional | Staging import rows, intake drafts, OCR candidates, PMF items, Import Profile, Change Proposal (until approve), Detected Difference (open), ACTIVE MRD editing session, intake tokens, initial baseline source selection | Promote → SoT or discard; not regulatory archive |

### 9.1 Матрица по обязательным терминам

| Термин | System of Record | Projection | Computed | Temporary |
|--------|:----------------:|:----------:|:--------:|:---------:|
| Person | ✓ (Identity) | | | |
| Employee | ✓ (Employment) | | | |
| Applicant (role) | | ✓ (via Application UI) | | ✓ (pre-hire) |
| Canonical PPR | ✓ | | | |
| UEPC | | ✓ (product surfaces) | | |
| Person Master Data | ✓ (BC) | | | |
| Личная карточка | | ✓ | | |
| Кадровое досье | | ✓ (legacy) | | |
| Электронная личная карточка | | ✓ (UEPC) | | |
| Контрольный список | | ✓ (export) | | ✓ (import staging) |
| MRD | ✓ (when CLOSED) | ✓ (workspace) | | ✓ (ACTIVE edit) |
| Change Proposal | | | | ✓ |
| Verified Data | ✓ (attribute class) | | | |
| Staging | | | | ✓ |
| PPR Snapshot | ✓ (immutable artifact) | | | |
| Projection (pattern) | | ✓ | | |
| Source Document | ✓ (orders / ext refs) | | | |
| Evidence | ✓ (file entity) | | | |
| Tenure | | | ✓ | |
| Employment Episode (external) | ✓ | | | |
| Employment Episode (internal) | | ✓ | | |
| Personnel Personal Record | ✓ | | | |
| Personnel Event | ✓ | | | |

---

## 10. Bounded Contexts — официальный реестр

| Context | RU name | Owns (SoT) | Anti-patterns |
|---------|---------|------------|---------------|
| **Identity** | Идентичность | IIN, merge, legal person status | Biographical sections |
| **Person Master Data** | Кадровые факты человека | Canonical PPR, proposals, PPR snapshots | Orders, assignments |
| **Application** | Приём / анкета | Personnel Application, intake | Direct PPR hire data without review |
| **Employment** | Трудовые отношения | Assignments, employee snapshot, Personnel Events | Education, tenure storage |
| **HR Documents** | Кадровые документы | Orders, evidence files | Canonical field values |
| **Tenure** | Стаж | Rule sets only | Writing totals into PPR |
| **MRD** | Месячный эталон | MRD versions, confirmed entries | Direct import write |
| **Reporting** | Отчётность | Report definitions | Any canonical facts |
| **Integrations** | Интеграции | Import batches, OCR jobs | Direct Canonical PPR write |

---

## 11. Trust tiers — единые коды (UI / API / docs)

| Tier | Code | RU label | Canonical signal |
|------|------|----------|------------------|
| T0 | `draft` | Черновик | proposal draft / intake draft |
| T1 | `declared` | Заявлено | submitted proposal / pending |
| T2 | `hr_verified` | Проверено HR | `verification_status=verified` |
| T3 | `document_confirmed` | Подтверждено документом | T2 + evidence scan verified |
| T4 | `blocked` | Отклонено / спорное | rejected / disputed / needs_attention |

**Правило документации:** в API и UI использовать **tier code** + RU label; не смешивать «verified» (T2) и «document confirmed» (T3).

---

## 12. Naming conventions для downstream artifacts

| Artifact | Naming rule | Example |
|----------|-------------|---------|
| ADR / WP | Full English domain term first mention | «Personnel Personal Record (PPR)» |
| REST API paths | `ppr`, `persons`, `proposals`, `mrd` — не `dossier`, `card-data` | `/api/ppr/persons/{id}` |
| UI (RU) | **Личная карточка** для PPR view; **Единая электронная личная карточка** для program/UEPC | — |
| UI (legacy) | «Кадровое досье» — только migration notes | deprecate |
| Events | `{Aggregate}{PastTense}` | `ChangeProposalApproved` |
| Commands | `{Verb}{Noun}` imperative | `ApproveChangeProposal` |
| Projections | `{Noun}{Projection\|View\|ReadModel}` | `ControlListRowProjection` |
| DB tables | `person_*`, `ppr_*`, `hr_mrd_*` — не `employee_card_*` for PPR SoT | `person_education` |

---

## 13. Open terms (⚠️ TBD)

| ID | Term gap | Decision needed |
|----|----------|-----------------|
| OQ-UL-01 | Manager co-sign for proposals | HR policy |
| OQ-UL-02 | Min trust tier per field for payroll vs display | HR + Tenure |
| OQ-UL-03 | Retire «Personnel Record» in legacy code comments | Tech debt sweep |
| OQ-UL-04 | Unified Russian UI string for «Change Proposal» | «Предложение изменения» recommended |
| OQ-UL-05 | `employee_documents` → person_evidence migration naming | WP-UEPC-009 |

---

## 14. Document maintenance

| Action | Owner | Trigger |
|--------|-------|---------|
| Add term | Architecture + HR | New BC or aggregate |
| Deprecate synonym | Architecture | ADR ratification |
| Version bump | Architecture | Breaking ubiquitous language change |

**Revision history:**

| Rev | Date | Change |
|-----|------|--------|
| 1 | 2026-07-21 | Initial ubiquitous language catalog |

---

*End of document.*
