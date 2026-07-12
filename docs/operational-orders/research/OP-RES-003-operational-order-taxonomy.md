# OP-RES-003 — Operational Order Taxonomy

WP: **OP-RES-003** — Operational Order Taxonomy  
Date: **2026-07-12**  
Mode: **research-only** (read-only classification; no runtime changes)  
Corpus: `order_samples/Производственные приказы/` — **193 documents**  
Prior work: [OP-RES-001](./OP-RES-001-corpus-passport.md), [OP-RES-002](./OP-RES-002-structural-pattern-analysis.md)

---

## 1. Executive Summary

На основе реального корпуса выведена **8-доменная типология** производственных приказов, отражающая **бизнес-смысл управленческих решений**, а не имена папок-источников.

| Domain (research code) | RU label | Docs | Share |
|---|---|---:|---:|
| **CLINICAL** | Клинико-операционные | 40 | 20.7% |
| **ORGANIZATION** | Организационные | 39 | 20.2% |
| **OPERATIONS** | Операционная мобильность | 33 | 17.1% |
| **FINANCE** | Финансовые | 33 | 17.1% |
| **SAFETY** | Безопасность и охрана | 17 | 8.8% |
| **GOVERNANCE** | Управление и нормотворчество | 14 | 7.3% |
| **DEVELOPMENT** | Развитие персонала | 10 | 5.2% |
| **HR_OPERATIONS** | Кадрово-организационные (дисциплина) | 6 | 3.1% |
| **ADMINISTRATIVE** | Общие административные | 1 | 0.5% |

**Три доминирующих типа приказов (order type):**

1. `clinical_operations` — 35 (клиническая организация процессов)
2. `business_travel` — 33 (командировки)
3. `commission_create` — 28 (создание / переформирование комиссий)

**Универсальные управленческие намерения** (встречаются в разных доменах):

- **контролировать** (165 docs) — почти всегда как meta-intent
- **делегировать / возложить** (81)
- **создать** (71) — комиссии, режимы, органы
- **направить** (60) — командировки, обучение
- **утвердить** (51) — планы, положения, составы

**Главные управляемые объекты:** контроль (как связь), сотрудники, подразделения, процессы, документы, финансы, комиссии.

**Критический вывод:** папки корпуса (`Командировка`, `Ахч`, `Б.Мустафина`) **не совпадают** с доменами. Таксономия должна строиться по **business purpose**, а папка — только provenance.

Диаграммы: [`diagrams/operational-order-taxonomy.svg`](diagrams/operational-order-taxonomy.svg), [`diagrams/operational-order-domain-map.svg`](diagrams/operational-order-domain-map.svg), [`diagrams/operational-order-intents.svg`](diagrams/operational-order-intents.svg), [`diagrams/operational-order-managed-objects.svg`](diagrams/operational-order-managed-objects.svg)

Machine-readable: [`data/OP-RES-003-order-taxonomy-summary.csv`](data/OP-RES-003-order-taxonomy-summary.csv)

---

## 2. Методика исследования

### 2.1 Принципы

1. **Corpus-first** — категории выведены из частот и содержания документов, не из заранее заданного списка «организационный / финансовый / …».
2. **Business purpose over folder** — `thematic_source_folder` использована как слабый сигнал; финальная метка — по тексту заголовка и первых абзацев.
3. **No implementation** — не проектируются классы, БД, API, DSL, UI.
4. **Structural orthogonality** — таксономия ортогональна структурному каркасу OP-RES-002 (shell vs semantics).

### 2.2 Процесс

| Step | Action |
|---|---|
| 1 | Загрузка реестра OP-RES-001 (193 files) |
| 2 | Извлечение первых ~45 абзацев DOCX (read-only OOXML) |
| 3 | Правила классификации по устойчивым лексическим паттернам (заголовок + преамбула) |
| 4 | Присвоение: `domain → category → order_type → business_purpose` |
| 5 | Детекция `primary_intent`, `detected_objects`, `scenario` |
| 6 | Ручная валидация выборки 60 docs + исправление ложных срабатываний (напр. «информацион*» ≠ IT) |
| 7 | Агрегация в CSV + отчёт |

### 2.3 Ограничения метода

- **183 DOCX** — полный текстовый анализ; **8 DOC** — только имя файла (medium/low confidence); **2 PDF** — не классифицированы по содержанию.
- Правила **не ML**; пограничные случаи требуют human review в OP-RES-004.
- Один документ = **один primary order type**; мульти-тематические приказы (редко) получают доминантную метку.

---

## 3. Общая типология производственных приказов

### 3.1 Иерархия (research model)

```text
Domain
  └── Category
        └── Order Type
              └── Business Purpose (one-line management outcome)
```

### 3.2 Полное дерево типов (corpus-derived)

#### CLINICAL — Клинико-операционные (40)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| clinical_ops | clinical_operations | 35 | Organize clinical department work, staffing modes, group activities |
| pharmacy | pharmaceutical_control | 5 | Govern pharmacy, narcotic/psychotropic substance rules |

#### ORGANIZATION — Организационные (39)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| governance_body | commission_create | 28 | Create, reappoint, or constitute a commission |
| events | institutional_event | 3 | Organize institutional outreach / holiday work mode |
| events | conference_support | 3 | Support scientific conference participation logistics |
| responsibility | responsibility_assignment | 5 | Assign functional responsibility to role / unit |

#### OPERATIONS — Операционная мобильность (33)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| mobility | business_travel | 33 | Authorize business travel and related conditions |

#### FINANCE — Финансовые (33)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| accounting | accounting_procedure | 18 | Accounting, fixed assets, inventory commissions |
| revenue | paid_services | 10 | Paid services, ОППВ, tariffs, penalties |
| allocation | funds_allocation | 3 | Allocate / transfer funds |
| planning | economic_plan | 2 | Approve economic or execution plans |

#### SAFETY — Безопасность и охрана (17)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| infection_control | infection_control | 11 | Epidemiological and sanitary regimes |
| facility | transport_access | 3 | Vehicle assignment and facility access |
| emergency_preparedness | emergency_drill | 2 | Safety drills (штабные тренировки) |
| radiation | radiation_safety | 1 | Radiation safety commission / checks |

#### GOVERNANCE — Управление и нормотворчество (14)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| procurement | procurement_procedure | 8 | Public procurement method / procedure |
| regulation | document_approval | 5 | Approve internal regulation / rules |
| compliance | compliance_program | 1 | Anti-corruption / compliance measures |

#### DEVELOPMENT — Развитие персонала (10)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| training | training_assignment | 10 | Assign staff to training, practice, education |

#### HR_OPERATIONS — Кадрово-организационные (6)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| discipline | disciplinary_action | 6 | Impose or process disciplinary sanctions |

#### ADMINISTRATIVE — Общие (1)

| Category | Order Type | n | Business Purpose |
|---|---|---:|---|
| general | operational_directive | 1 | Unparsed legacy DOC (КИЛИ) |

### 3.3 Соответствие примерам из задания

| Пример из WP | Подтверждение в корпусе |
|---|---|
| организационный | **ORGANIZATION** (39) |
| кадрово-организационный | **HR_OPERATIONS** (6) + overlap с Personnel |
| финансовый | **FINANCE** (33) |
| обучение | **DEVELOPMENT** (10) |
| командировка | **OPERATIONS** (33) |
| комиссии | **ORGANIZATION/governance_body** (28) |
| утверждение документов | **GOVERNANCE/regulation** (5) + внутри комиссий |
| планы | **FINANCE/planning** (2) + планы в accounting |
| безопасность / охрана труда | **SAFETY** (17) |
| платные услуги | **FINANCE/revenue** (10) |
| закупки | **GOVERNANCE/procurement** (8) |
| информационные системы | **1 doc** — слабый сигнал, не выделять домен |
| административный | Рассеян по ORGANIZATION/responsibility, SAFETY/facility |
| хозяйственный | Частично SAFETY/facility + FINANCE/accounting |
| проверки / инвентаризация | Внутри accounting_procedure, infection_control, radiation |

---

## 4. Категории приказов

### 4.1 Смысл доменов (управленческие классы решений)

| Domain | Какие решения принимает организация |
|---|---|
| **CLINICAL** | Как работают отделения, группы врачей, клинические процессы, фармконтроль |
| **ORGANIZATION** | Кто за что отвечает; какие комиссии и мероприятия существуют |
| **OPERATIONS** | Куда и на каких условиях направляется персонал (командировки) |
| **FINANCE** | Учёт, деньги, платные услуги, планы, активы |
| **SAFETY** | Риски: инфекции, транспорт, радиация, учения |
| **GOVERNANCE** | Закупки, нормативные документы, комплаенс |
| **DEVELOPMENT** | Обучение и профессиональное развитие |
| **HR_OPERATIONS** | Дисциплинарные решения (граница с Personnel Orders) |

### 4.2 Расхождение папок и доменов (примеры)

| Folder | Primary domain mix | Research note |
|---|---|---|
| Командировка (37) | 100% OPERATIONS | Редкий случай совпадения папки и домена |
| по платным услугам 2026 (23) | ~100% FINANCE/revenue | Тематически однородна |
| Бухгалтерия (21) | FINANCE + ORGANIZATION (комиссии) | Папка ≠ один домен |
| Ахч (12) | SAFETY + ORGANIZATION + FINANCE + CLINICAL | Смешанный админхоз |
| Б.Мустафина (9) | CLINICAL + ORGANIZATION | Персональная папка ≠ тип |
| ККМУ (11) | CLINICAL + GOVERNANCE | Клиника + нормативка |

---

## 5. Business Intent

### 5.1 Частота намерений (183 DOCX, multi-label)

| Intent | Docs | Typical domains |
|---|---:|---|
| контролировать | 165 | All — meta-intent |
| делегировать | 81 | ORGANIZATION, FINANCE, SAFETY |
| создать | 71 | ORGANIZATION (комиссии), GOVERNANCE |
| направить | 60 | OPERATIONS, DEVELOPMENT |
| утвердить | 51 | FINANCE, GOVERNANCE, CLINICAL |
| обеспечить | 47 | CLINICAL, SAFETY |
| организовать | 46 | CLINICAL, ORGANIZATION (events) |
| назначить | 25 | ORGANIZATION, SAFETY |
| провести | 22 | DEVELOPMENT, SAFETY (drills) |
| изменить | 20 | FINANCE (планы), GOVERNANCE |
| ввести | 16 | SAFETY (режимы), GOVERNANCE |
| установить | 9 | CLINICAL/pharma, SAFETY |
| разрешить / запретить | 6 | SAFETY/transport |
| признать / отменить | 4 | HR_OPERATIONS, plan changes |

### 5.2 Cross-domain intents (важно для Document Engine)

Следующие intents **не являются** типами приказов — это **универсальные глаголы** движка:

- **контролировать** — meta-item на уровне order (92% structural presence, OP-RES-002)
- **делегировать / возложить** — связь actor ↔ duty
- **утвердить** — binding approval act
- **обеспечить** — resource/process enablement

Один intent «утвердить» встречается в: утверждении состава комиссии, плана закупок, регламента, графика ОППВ.

### 5.3 Primary intent per order type (типичный)

| Order Type | Primary Intent |
|---|---|
| business_travel | направить |
| commission_create | создать |
| accounting_procedure | утвердить |
| clinical_operations | организовать / обеспечить |
| paid_services | утвердить |
| disciplinary_action | назначить (санкцию) |
| infection_control | утвердить / обеспечить |
| training_assignment | направить |
| procurement_procedure | утвердить / организовать |

---

## 6. Managed Objects

### 6.1 Частота объектов управления (multi-label per document)

| Managed Object | Docs | % of 183 DOCX |
|---|---:|---:|
| контроль | 164 | 90% |
| сотрудники | 134 | 73% |
| подразделения | 124 | 68% |
| процессы | 121 | 66% |
| документы | 92 | 50% |
| финансы | 84 | 46% |
| комиссии | 54 | 30% |
| услуги | 39 | 21% |
| мероприятия | 27 | 15% |
| сроки | 22 | 12% |
| имущество | 21 | 11% |
| проекты | 19 | 10% |
| оборудование | 18 | 10% |
| закупки | 16 | 9% |
| планы | 6 | 3% |
| помещения | 4 | 2% |
| информационные системы | 1 | менее 1% |

### 6.2 Кластеры объектов (для будущих сущностей движка)

```text
People & Org     → сотрудники, подразделения, комиссии
Governance       → документы, контроль, планы, закупки
Resources        → финансы, имущество, оборудование, услуги
Operations       → процессы, мероприятия, сроки, помещения
```

### 6.3 Наблюдения

- **«процессы»** — самый универсальный объект; почти каждый приказ регулирует процедуру или режим.
- **«контроль»** — одновременно объект и **отношение** (controller → controlled action).
- **«сотрудники»** в operational orders — адресация исполнения, **не** кадровый SoT (в отличие от Personnel Orders).
- **«комиссии»** — часто composite object: председатель + члены + предмет полномочий.
- **ИТ-системы** — практически отсутствуют в корпусе; не строить домен вокруг IT на этом этапе.

---

## 7. Responsible Parties

### 7.1 Роли, извлечённые из корпуса

| Role | Function in orders | Frequency |
|---|---|---|
| **Директор** | Подписант, self-control, highest authority | ~99% sign block |
| **Зам. директора** (лечебная / экономика) | Controller, clinical oversight | Very common |
| **Заведующий отделением** | Item-level executor | Very common in CLINICAL |
| **Руководитель службы** | АХЧ, охрана, экономика, закупки | Common |
| **Ответственный исполнитель** | Named accountable person | 44% docs (OP-RES-002) |
| **Комиссия** (председатель + члены) | Collective decision body | 30% object signal |
| **Секретарь комиссии** | Episodic | Rare |
| **Главный бухгалтер** | Controller for accounting commissions | Common in FINANCE |
| **Отдел кадров / HR** | Ознакомление, подготовка (`исп:`) | Discipline + travel |
| **Юрист** | «Келісілді» vetting | ~6% |
| **Исполнитель документа** | `исп:` / `Орын.:` line | ~70% qualitative |

### 7.2 Паттерны участия

1. **Signatory ≠ executor** — директор подписывает, исполняют заведующие / службы.
2. **Controller ≠ executor** — контроль часто у зам. директора или главбуха, не у исполнителя пункта.
3. **Commission = multi-party actor** — отдельная модель состава, не один `employee_id`.
4. **Acknowledgement parties** — ознакомление комиссии / дисциплинарных приказов (Танысу парағы).

---

## 8. Повторяющиеся сценарии

| ID | Scenario | Domain(s) | n | Краткое описание |
|---|---|---|---:|---|
| **S_TRAVEL** | Направить в командировку | OPERATIONS | 33 | Направление 1+ сотрудников; условия расходов; сохранение ЗП; основание-заявление |
| **S_COMMISSION** | Создать комиссию | ORGANIZATION | 28 | Создание органа; председатель + члены; контроль главбуха/зама |
| **S_CLINICAL** | Организовать клинический процесс | CLINICAL | 35 | Режим работы отделения, группы, штатные задачи, ДОД |
| **S_ACCOUNTING** | Бухучёт / основные средства | FINANCE | 18 | Комиссии по списанию/приёмке; учётная политика; отчётность |
| **S_EPID** | Инфекционный контроль | SAFETY | 11 | Санитарно-эпидемиологический режим; ВИЧ; дезинфекция |
| **S_TRAINING** | Направить на обучение | DEVELOPMENT | 10 | Обучение, практика врачей, списки на курсы |
| **S_PAID_SERVICES** | Платные услуги / ОППВ | FINANCE | 10 | Тарифы, начисления, штрафы неустойки |
| **S_PROCUREMENT** | Закупка | GOVERNANCE | 8 | Конкурс, единый источник, процедура |
| **S_DISCIPLINE** | Дисциплинарное взыскание | HR_OPERATIONS | 6 | Выговор; ознакомление; контроль руководителей |
| **S_PHARMA** | Фармконтроль | CLINICAL | 5 | Наркотические средства, формулярная комиссия |
| **S_RESPONSIBILITY** | Назначить ответственного | ORGANIZATION | 5 | Дежурства, кураторы, функциональные обязанности |
| **S_REGULATION** | Утвердить регламент | GOVERNANCE | 5 | Внутренние правила, инструкции |
| **S_FUNDS** | Выделить средства | FINANCE | 3 | Перечисление, аванс, финансирование мероприятия |
| **S_EVENT** | Праздничный / outreach | ORGANIZATION | 3 | Режим работы в праздники, ДОД |
| **S_CONFERENCE** | Поддержка конференции | ORGANIZATION | 3 | Организация участия, ответственные, финансы |
| **S_TRANSPORT** | Транспорт и доступ | SAFETY | 3 | Закрепление авто, пропускной режим |
| **S_DRILL** | Штабная тренировка | SAFETY | 2 | Учения по ЧС |
| **S_PLAN** | Утвердить план | FINANCE | 2 | План закупок, исполнение плана |
| **S_RADIATION** | Радиационная безопасность | SAFETY | 1 | Внутренняя комиссия ВЦРО |
| **S_COMPLIANCE** | Комплаенс | GOVERNANCE | 1 | Антикоррупционная программа |
| **S_GENERAL** | Неклассифицированный DOC | ADMINISTRATIVE | 1 | Требует ручного разбора |

---

## 9. Предварительная Domain Model

> **Research primitives only** — не классы, не схема БД.

```text
OperationalOrder (research aggregate)
│
├── TaxonomyRef
│     ├── domain: CLINICAL | ORGANIZATION | OPERATIONS | FINANCE | SAFETY | GOVERNANCE | DEVELOPMENT | HR_OPERATIONS
│     ├── category
│     ├── order_type
│     └── business_purpose
│
├── BusinessIntent
│     ├── primary_intent
│     └── secondary_intents[]        # per item
│
├── ManagedObjects[]                 # multi-tag: сотрудники + процессы + …
│
├── ResponsibleParties[]
│     ├── role (director | head_of_unit | controller | commission | preparer | …)
│     ├── scope (order | item | commission)
│     └── reference (position | person — research: not normalized)
│
├── Control
│     ├── mode: self | delegated | embedded
│     └── controller_party
│
├── Deadlines[]                      # optional; item-level or order-level
│
├── Attachments[]                    # ref or inline (OP-RES-002)
│
├── SupportingDocuments[]            # law | order | memo | protocol | application
│
└── DocumentShell                    # OP-RES-002: header, preamble, items, signature…
```

### 9.1 Orthogonality: Shell × Taxonomy × Payload

| Layer | Question it answers |
|---|---|
| **DocumentShell** | *Как выглядит документ?* |
| **Taxonomy** | *Какое управленческое решение?* |
| **ManagedObjects + Parties** | *На что и на кого направлено?* |
| **Structured payload** (future) | *Какие machine-readable facts for apply/audit?* |

Personnel Orders share **DocumentShell** and editorial block model; differ in **Taxonomy** (HIRE, LEAVE, …) and **payload**.

---

## 10. Степень покрытия корпуса

| Metric | Value |
|---|---|
| Documents in registry | 193 |
| Classified with domain (all extensions) | 193 (100%) |
| DOCX full-text classification | 183 (94.8%) |
| DOC filename-only classification | 8 (4.1%) |
| PDF not content-classified | 2 (1.0%) |
| High/medium confidence | 192 |
| Low confidence (ADMINISTRATIVE/general) | 1 |
| Distinct domains | 9 |
| Distinct order types | 21 |
| Distinct scenarios | 21 |
| Unclassified «прочее» | 1 (0.5%) |

**Покрытие таксономией:** корпус **практически полностью** раскладывается на 8 доменов + хвост из 12 редких order types (1–3 docs). Длинный хвост — нормальное ожидание для реальной организации.

---

## 11. Ограничения исследования

1. **Лексические правила** — не семантический NLP; возможны ошибки на пограничных документах.
2. **Один ярлык на документ** — мульти-тематические приказы упрощены.
3. **DOC/PDF gap** — 10 файлов без полного текстового разбора.
4. **HR boundary** — дисциплинарные приказы могут относиться к Personnel Orders по продуктовой классификации.
5. **IT underrepresented** — не выводить отдельный домен по одному документу.
6. **ПДн** — per-document CSV содержит пути с ФИО; хранить локально (см. OP-RES-001 git policy).
7. **Не проверялось** фактическое исполнение приказов — только текст документа.

---

## 12. Рекомендации для OP-RES-004 (Control & Execution Model)

OP-RES-004 должен опереться на связку **Intent × Object × Party × Control**, уже видимую в таксономии:

### 12.1 Приоритетные вопросы OP-RES-004

1. **Control model** — унифицировать `self | delegated | embedded` (92% docs имеют control; 75% в final block).
2. **Executor vs controller vs signatory** — три разные роли; не сливать в одно поле.
3. **Commission execution** — как отслеживать состав и срок полномочий комиссии.
4. **Deadline extraction** — сроки размазаны по пунктам; нужен item-level model.
5. **Scenario templates** — 21 scenario; top-8 покрывают ~75% корпуса (Pareto).
6. **Cross-link to Personnel** — `HR_OPERATIONS/discipline` vs `PersonnelOrder/TERMINATION`-class boundary.
7. **Acknowledgement workflow** — Танысу парағы / ознакомление как execution evidence.

### 12.2 Pareto scenarios для первой волны formalization

| Priority | Scenarios | Cumulative share |
|---|---|---|
| P0 | S_TRAVEL, S_COMMISSION, S_CLINICAL, S_ACCOUNTING | ~59% |
| P1 | S_EPID, S_TRAINING, S_PAID_SERVICES, S_PROCUREMENT | ~80% |
| P2 | Long tail (13 scenarios) | ~20% |

### 12.3 Не делать в OP-RES-004

- Проектировать таблицы БД или API.
- Фиксировать финальный enum `OrderType` без валидации с кадровиками/АХЧ.
- Объединять control и execution в одно понятие без различения meta-item vs operational duty.

---

## Appendix A — Artifacts

| File | Description |
|---|---|
| [`OP-RES-003-operational-order-taxonomy.md`](OP-RES-003-operational-order-taxonomy.md) | This report |
| [`data/OP-RES-003-order-taxonomy-summary.csv`](data/OP-RES-003-order-taxonomy-summary.csv) | Per-document taxonomy + aggregate section |
| [`diagrams/operational-order-taxonomy.svg`](diagrams/operational-order-taxonomy.svg) | Taxonomy tree |
| [`diagrams/operational-order-domain-map.svg`](diagrams/operational-order-domain-map.svg) | Domain map |
| [`diagrams/operational-order-intents.svg`](diagrams/operational-order-intents.svg) | Intent frequencies |
| [`diagrams/operational-order-managed-objects.svg`](diagrams/operational-order-managed-objects.svg) | Managed object frequencies |

## Appendix B — Git visibility

Per-document rows in `OP-RES-003-order-taxonomy-summary.csv` may contain **PII in paths** (same policy as OP-RES-001 full inventory). Aggregate rows (`section=aggregate`) are safe for summary statistics. Full CSV is subject to global `*.csv` ignore unless explicitly exempted.

---

*OP-RES-003 complete. Research documentation only. No source files modified.*
