# OP-RES-002 — Structural Pattern Analysis

WP: **OP-RES-002** — Structural Pattern Analysis  
Date: **2026-07-12**  
Mode: **research-only** (read-only content probe; no runtime changes)  
Corpus: `order_samples/Производственные приказы/` — **193 files** (183 DOCX analyzed in depth)  
Prior work: [OP-RES-001 — Corpus Passport](./OP-RES-001-corpus-passport.md)

---

## 1. Executive Summary

Производственные приказы корпуса **не образуют набор разрозненных «типовых форм по темам»** на уровне внутренней структуры. Независимо от папки-источника (командировки, закупки, АХЧ, дисциплина, комиссии) документы повторяют **единый распорядительный каркас** — тот же, что уже зафиксирован для кадровых приказов в [PO-EDIT-001](../../personnel-orders/architecture/PO-EDIT-001-editorial-document-model.md):

```text
Header → Preamble/Basis → Order Formula → Numbered Items → [Attachments] → Signature → [Agreement] → [Acknowledgement]
```

**Ключевой вывод для Document Engine:** Operational Orders и Personnel Orders должны быть **двумя специализациями одного механизма документов**, а не двумя параллельными модулями. Различаются:

- **семантика пунктов** (кадровое решение vs операционное распоряжение);
- **structured payload** (сотрудник/отпуск vs комиссия/закупка/мероприятие);
- **типичная длина** (операционные приказы чаще 4–10 пунктов, но встречаются регламенты на 30–120 пунктов).

**Обязательный минимум каркаса** (по частоте в 183 DOCX):

| Block | Presence |
|---|---|
| Заголовок / предмет | ~97% |
| Формула «ПРИКАЗЫВАЮ» / «БҰЙЫРАМЫН» | ~97% |
| ≥1 нумерованный распорядительный пункт | ~97% |
| Подпись директора / уполномоченного | ~99% |
| Контроль исполнения | ~92% |

**Высокая вариативность** сосредоточена не в каркасе, а в: (a) длине и вложенности пунктов, (b) двуязычной компоновке, (c) способе записи исполнителей, (d) наличии комиссионного блока, (e) позиции основания (преамбула vs хвост).

Диаграммы: [`diagrams/operational-order-structure.svg`](diagrams/operational-order-structure.svg), [`diagrams/operational-order-blocks.svg`](diagrams/operational-order-blocks.svg), [`diagrams/operational-order-structure.drawio`](diagrams/operational-order-structure.drawio).

---

## 2. Методика исследования

### 2.1 Scope

| Included | Excluded |
|---|---|
| 183 DOCX (OOXML `word/document.xml`, read-only) | 8 legacy DOC (stream probe only in OP-RES-001; текст не извлекался) |
| Стратифицированная выборка 60 файлов (2 per folder + edge cases) | 2 PDF (сканы, OCR не применялся) |
| Полный корпусный regex-frequency pass по 183 DOCX | Программная классификация типов приказов (→ OP-RES-003) |
| Сопоставление с PO-EDIT-001 (Personnel Orders) | Проектирование API / БД / UI / Document Engine |

### 2.2 Source

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы\
```

Исходники **не изменялись**. Тексты с ФИО **не цитируются** в отчёте; примеры обобщены или анонимизированы ([`samples/anonymized-structure-skeleton.txt`](samples/anonymized-structure-skeleton.txt)).

### 2.3 Method

1. Извлечение абзацев из OOXML (порядок абзацев = порядок блоков в печатной форме).
2. Детекция блоков по устойчивым маркерам: «ПРИКАЗЫВАЮ», «Контроль», «Приложение», «Келісілді», нумерация `1.` / `1)`.
3. Подсчёт частот по полному корпусу 183 DOCX.
4. Качественный разбор стратифицированной выборки по тематическим кластерам: командировки, комиссии, дисциплина, закупки, регламенты, мероприятия.

### 2.4 Limitations

- Анализ **текстовый**, не визуальный: выравнивание, печати, табличная вёрстка учтены частично (24 DOCX содержат `w:tbl`).
- 6 документов без формулы «ПРИКАЗЫВАЮ» — черновики, проекты или нестандартная подача.
- Казахский и русский тексты часто **дублируют** один документ; метрики языковых маркеров завышены для kk-бойлерплейта организации.

---

## 3. Общая структура производственных приказов

### 3.1 Каноническая последовательность блоков

```text
┌──────────────────┐
│ 1. Header        │  организация, город, тип документа, №, дата, заголовок
├──────────────────┤
│ 2. Preamble      │  нормативные и фактические основания; целевая формула
├──────────────────┤
│ 3. Order formula │  ПРИКАЗЫВАЮ / БҰЙЫРАМЫН / ПОСТАНОВЛЯЮ
├──────────────────┤
│ 4. Items 1..N    │  распорядительные + мета-пункты (контроль, вступление в силу)
├──────────────────┤
│ 5. Attachments   │  ссылка на приложения (опционально)
├──────────────────┤
│ 6. Trailing basis│  Основание:/Негіз: (вариант размещения)
├──────────────────┤
│ 7. Signature     │  должность + ФИО
├──────────────────┤
│ 8. Agreement     │  Келісілді / юрист (опционально)
├──────────────────┤
│ 9. Ack / distro  │  Танысу парағы, исп:, рассылка (опционально)
└──────────────────┘
```

### 3.2 Варианты компоновки (layout variants)

| Variant | Description | Frequency |
|---|---|---|
| **A — Classic RU** | Полный русский блок: header → preamble → items → sign | ~40% как доминирующий слой |
| **B — KK then RU mirror** | Сначала казахский полный текст, затем русский повтор | ~35% (командировки, дисциплина, часть АХЧ) |
| **C — Interleaved bilingual** | Пункты kk/ru чередуются или дублируются подряд | ~15% |
| **D — Title-first draft** | Предмет в начале; реквизиты №/дата заполнены пробелами | ~5% (проекты, шаблоны-заготовки) |
| **E — Regulatory mega-order** | 30–120 пунктов; преамбула-кодекс; мало «мета»-блоков в конце | ~5% (наркотические средства, комплаенс) |

### 3.3 Alignment with Personnel Orders (PO-EDIT-001)

| PO-EDIT-001 block | Operational corpus equivalent |
|---|---|
| `title` | Header title line («О создании…», «О командировании…») |
| `preamble` | Preamble / normative basis |
| Order formula | «ПРИКАЗЫВАЮ» (print chrome в PO-EDIT; здесь — явный абзац) |
| `item.body` | Numbered dispositive items |
| `item.basis` | Inline or trailing «Основание» / «Негіздеме» |
| Signature | Structured header fields в personnel; здесь — print block |
| Acknowledgement | «Танысу парағы», «ознакомить» — чаще в operational |

**Архитектурная рекомендация:** Document Engine должен оперировать **block kinds**, общими для обоих классов документов; class-specific generators заполняют payload и clause templates.

---

## 4. Повторяющиеся блоки

| Block | Corpus signal (183 DOCX) | Mandatory? |
|---|---|---|
| Header / title | 178 | **De facto mandatory** |
| City / org line | 134 | Optional requisites |
| Date | 170 | **Near-mandatory** |
| Number `№` | 93 | **Optional** (часто blank `№ ___`) |
| Preamble «В целях/В связи» | 112 (RU marker) | Common |
| Normative kk boilerplate | 153 (KK org/law text) | Common in bilingual |
| Order formula | 177 | **Mandatory** |
| Numbered items | 178 (≥1 detected) | **Mandatory** |
| Control clause | 168 | **Near-mandatory** (92%) |
| Effective-date item | ~60% (by pattern «вступает в силу») | Common in short orders |
| Attachment reference | 35 | Situational |
| Distribution / ack | 25 | Situational |
| Agreement «Келісілді» | 11 | Episodic |
| Preparer line `исп:` / `Орын.:` | ~70% (qualitative) | Common |

### 4.1 Распорядительная часть — структура нумерации

| Style | Occurrences (paragraph-level) | Notes |
|---|---|---|
| `1.` arabic dot | 2,123 | **Dominant** |
| `1)` arabic paren | 318 | Secondary |
| `1.1.` sub-numbering | frequent in АХЧ, регламентах | Hierarchical items |
| Bullet lists inside item | common in commission/regulatory | Not separate items |

**Распределение числа пунктов верхнего уровня (183 DOCX):**

| Items | Documents |
|---|---|
| 0 (no detected numbering) | 5 |
| 1–3 | 21 |
| 4–6 | 79 |
| 7–10 | 45 |
| 11–20 | 21 |
| 21+ | 12 |

Медиана: **5–6 пунктов**; длинные регламенты — хвост распределения.

### 4.2 Мета-пункты внутри распорядительной части

Часто **последние 1–2 пункта** не вводят нового действия, а закрывают документ:

1. **Контроль** — «возложить на…» / «оставляю за собой» (137 docs — final block; 33 — within body).
2. **Вступление в силу** — «со дня подписания».
3. **Признать утратившим силу** — редко, в изменениях к планам/регламентам.

---

## 5. Повторяющиеся реквизиты

### 5.1 Обязательные (для печатно-юридического образца)

| Requisite | Pattern | Notes |
|---|---|---|
| **Тип документа** | Приказ / Бұйрық | Иногда «Распоряжение» |
| **Предмет** | «О …» / «…туралы» | Может занимать 1–3 строки |
| **Распорядительная воля** | ПРИКАЗЫВАЮ | 6 docs без формулы — drafts |
| **Подпись** | Директор + ФИО | Единый подписант в корпусе |

### 5.2 Необязательные / часто пустые

| Requisite | Pattern | Frequency |
|---|---|---|
| **Номер** | `№ ___`, `№ ______` | ~51% filled pattern; остальное — blank placeholder |
| **Дата** | «__» _________ 2026 | Placeholder или полная дата |
| **Город** | г. Астана | ~73% |
| **Полное наименование org** | ГКП на ПХВ «ММЦ»… | В преамбуле чаще, чем в шапке |

### 5.3 Варианты оформления шапки

1. **Классическая тройка:** `Приказ №` + дата + заголовок (бухгалтерия, комиссии).
2. **Заголовок-first:** предмет → основание → пункты → шапка RU внизу (часть bilingual).
3. **Проект:** «Проект приказа…» без номера; реквизиты отсутствуют.

---

## 6. Повторяющиеся модели распорядительных пунктов

> **Важно:** ниже — **исследовательский словарь наблюдаемых глагольных моделей**, не taxonomy и не programmatic enum (OP-RES-003).

| Model (RU stem) | Approx. docs | Typical use |
|---|---|---|
| **возложить контроль** | 104 | Meta-item; финализация |
| **возложить / жүктелсін** | 70 | Delegation of duty |
| **назначить / тағайындау** | 44 | Person → role/responsibility |
| **утвердить / бекіту** | 44 | Plan, composition, regulation |
| **создать / құру** | 42 | Commission, working body |
| **обеспечить / қамтамасыз ету** | 32 | Resource, staffing, supply |
| **организовать / ұйымдастыру** | 30 | Event, cleanup day, training |
| **направить / жіберу** | 24 | Travel, secondment |
| **провести / өткізу** | 14 | Event, audit, training |
| **установить** | 11 | Rules, lists, modes |
| **обязать** | 7 | Duty binding (регламенты) |
| **принять к сведению** | 5 | Procedural (редко) |
| **признать утратившим силу** | 3 | Supersede prior order |
| **запретить / разрешить** | 3 | Access modes (АХЧ) |

### 6.1 Состав типичного пункта (item anatomy)

```text
[номер] + [глагол в повелительном/инфинитиве] + [адресат в дательном] + [содержание действия] + [срок/условие]
```

**Примеры обобщённых форм (анонимизировано):**

- «1. Заведующему отделением [X] обеспечить [режим работы] в период [даты].»
- «2. Создать комиссию по [предмет] в следующем составе: …»
- «3. Контроль за исполнением настоящего приказа возложить на [должность].»

### 6.2 Сложные пункты

- **Комиссионный:** пункт 1 создаёт комиссию; внутри — подблок «Председатель» / «Члены» без отдельной нумерации.
- **Регламентный:** пункт 1 устанавливает перечень; далее bullet-list отделений (не отдельные numbered items).
- **Пакетный:** один пункт — несколько unrelated действий (реже; в длинных приказах).

---

## 7. Исполнители

### 7.1 Наблюдаемые модели адресации

| Model | Corpus signal | Recording style |
|---|---|---|
| **Конкретный сотрудник** | Very common | «Иванову И.И.» + должность inline |
| **Должность без ФИО** | Common | «Заведующему отделением хирургии №3» |
| **Подразделение** | 102 docs (unit keywords) | «Отделу фармации», «Службе охраны» |
| **Комиссия** | 57 docs | Коллективный орган + roster |
| **Несколько исполнителей** | Common | Multi-address in one item or parallel items |
| **И.О. / врио** | In items | «Исполняющему обязанности заведующего…» |

### 7.2 Синтаксические паттерны

1. **Дательный падеж должности:** «Заведующему…», «Руководителю…», «Директору по…».
2. **Именной дательный:** «Нурбекову Б.Б.» (в финансовых/командировочных).
3. **Именительный подразделения:** «Отдел фармации обеспечить…» (реже).
4. **Казахский маркер:** «…жүктелсін», «…тағайындалсын».

### 7.3 Исполнитель документа (не путать с исполнителем поручения)

Строка **`исп:` / `Орын.:` / `Орынд.:`** — подготовивший приказ (часто HR/делопроизводитель). Это **не** operational executor, а document preparer metadata.

---

## 8. Контроль исполнения

### 8.1 Наличие

| Signal | Count (183 DOCX) |
|---|---|
| Control mentioned | 168 (92%) |
| No control | 13 (8%) |
| Position: **final block** | 137 |
| Position: **within body** | 33 |

### 8.2 Формулировки (research set)

| Formulation | Role |
|---|---|
| «Контроль за исполнением приказа возложить на [должность/ФИО]» | Delegated controller |
| «Контроль … оставляю за собой» | Self-control (директор) |
| «…взять на контроль работу сотрудников…» | Embedded ongoing control |
| «Бақылауды өзіме қалдырамын» | KK self-control |
| «Бақылау … жүктелсін» | KK delegated |

### 8.3 Кому поручается контроль

| Controller type | Examples (обобщённо) |
|---|---|
| Зам. директора по лечебной работе | Regulatory, clinical orders |
| Главный бухгалтер | Commission on fixed assets |
| Руководитель АХЧ | Transport, access modes |
| Директор (self) | Travel, finance allocation |
| Заведующий отделением | Disciplinary follow-up |

**Несколько контролирующих:** в дисциплинарных приказах — пункты 2–3 назначают разных «контролёров» по линиям (отдел + зам. директора).

---

## 9. Сроки

### 9.1 Варианты (research)

| Type | Pattern | Frequency |
|---|---|---|
| **Конкретная дата / период** | «11–13 марта 2026», «за апрель 2026» | Common in travel, payroll |
| **Относительный срок** | «в течение 3 рабочих дней» | 13 docs |
| **Периодический** | «ежемесячно», «ежедневно» | 12 docs |
| **Постоянно** | «на постоянной основе», «постоянно действующая комиссия» | 5 docs |
| **До/после события** | «по окончании конференции», «за 1 час до операции» | Qualitative |
| **Без срока** | Majority of operational duties | Default |
| **Вступление в силу** | «со дня подписания» | Meta-item |

Сроки чаще **внутри пункта действия**, а не в отдельном блоке «Сроки исполнения».

---

## 10. Комиссии

**Встречаются:** 60 / 183 DOCX (33%).

### 10.1 Типовая композиция

```text
1. Создать [вид] комиссию по [предмет].
   Председатель комиссии: [должность] – [ФИО].
   Члены комиссии:
   [должность] – [ФИО];
   …
2. [Опционально] Утвердить положение / график / состав (ссылка на приложение).
3. Контроль возложить на [ФИО/должность].
```

### 10.2 Роли

| Role | Presence |
|---|---|
| Председатель | ~95% commission orders |
| Члены комиссии | ~95% |
| Секретарь | ~15% (реже; в протокольных формах) |
| «Мүшелері» (kk) | Mirror of members block |

### 10.3 Приложения vs inline

- **Inline roster** — доминирует (бухгалтерия, ВЦРО, формулярная комиссия).
- **Attachment reference** — «состав согласно приложению 1» (формулярная комиссия: «1-қосымша»).

### 10.4 Acknowledgement после комиссии

Блок **«Танысу парағы»** с строками подписей председателя и всех членов — procedural extension после основного текста; встречается в комиссионных и регламентных приказах.

---

## 11. Ссылки (основания)

### 11.1 Виды оснований

| Kind | Corpus signal | Placement |
|---|---|---|
| **Законы / кодексы** | 110 | Preamble |
| **Приказы министров / ведомств** | 14 explicit + часть law block | Preamble |
| **Протоколы** | Disciplinary, production meetings | Preamble or trailing |
| **Служебные записки** | 34 | Preamble / «Негіздеме» |
| **Заявления / өтініш** | Travel, finance | Trailing «Основание» |
| **Технические регламенты** | Radiation, pharma rules | Preamble |
| **Протокол производственного совещания** | Clinical protocols | Preamble (project orders) |

### 11.2 Позиция в документе

| Position | When |
|---|---|
| **Preamble** (до «ПРИКАЗЫВАЮ») | Normative chain + «в целях» |
| **Trailing** (после пунктов) | «Основание:», «Негіздеме:» — командировки |
| **Per-item** | «на основании заявления…» внутри пункта 1 |

---

## 12. Приложения

| Metric | Value |
|---|---|
| Docs with attachment reference | 35 (19%) |
| Attachment count 0 | 158 |
| Attachment count 1 | 11 |
| Attachment count 2+ | 14 |

### 12.1 Способы ссылок

- «Приложение 1» / «1-қосымша» в тексте пункта.
- «Состав согласно приложению».
- **Inline table** в теле DOCX (24 docs with `w:tbl`) — фактическое приложение без отдельного файла.

### 12.2 Оформление

Приложения в корпусе **не выделены** в отдельные файлы в папке — они либо встроены в DOCX (таблицы/списки), либо referenced but not attached in sample folder.

---

## 13. Подписи

### 13.1 Варианты

| Variant | Frequency |
|---|---|
| **Один подписант** (Директор) | Dominant |
| **И.О. в пунктах** | Common (not signature block) |
| **Должность + ФИО в sign block** | ~99% |
| **Визирование «Келісілді»** | 11 docs (юрист) |
| **Multi-sign acknowledgement** | Commission / regulatory (Танысу парағы) |

### 13.2 Дополнительные строки

| Line | Purpose |
|---|---|
| `исп:` / `Орын.:` | Document preparer |
| `Келісілді:` | Legal vetting |
| `«Бұйрықпен таныстым»` | Acknowledgement of disciplinary orders |
| Multiple `_______` lines | Commission members sign-off |

**Несколько подписантов в sign block** как co-signers редки; чаще — один директор + многострочное **ознакомление** ниже.

---

## 14. Степень вариативности

| Layer | Variability | Impact on Engine |
|---|---|---|
| **Document shell** | **Low** | Stable block model |
| **Requisites formatting** | Medium | Placeholder vs filled; number/date optional |
| **Bilingual layout** | **High** | Renderer must support mirror/interleave |
| **Item count & depth** | **High** | 1–123 items; sub-numbering |
| **Executor syntax** | Medium | Parser needs dative/position patterns |
| **Control placement** | Low–medium | Final vs embedded |
| **Commission block** | Medium | Inline roster vs attachment |
| **Attachments** | Medium | Reference vs inline table |
| **Agreement/ack** | **High** | Optional tails differ by subtype |

**Итог:** формализовать следует **оболочку и item atom**; вариативность — в generators и optional blocks, не в разных document types на уровне engine core.

---

## 15. Выводы

1. **Единый каркас подтверждён** на 97% корпуса; операционные приказы структурно совместимы с editorial model кадровых приказов (PO-EDIT-001).
2. **Document Engine core** должен оперировать: `header`, `preamble`, `order_formula`, `items[]`, `attachment_refs`, `signature`, `agreement`, `acknowledgement` — как locale-aware blocks.
3. **Item atom** — универсальная единица: number + directive + actor + object + optional deadline + sub-items.
4. **Контроль** — почти стандартный meta-item; engine должен поддерживать `control_delegate` на уровне order или item.
5. **Комиссии** — составной шаблон внутри item, не отдельный document type.
6. **Двуязычие** — composition concern (kk+ru mirror), не дублирование document instance.
7. **8 DOC + 2 PDF** требуют отдельного ingestion path; структурный анализ по ним неполный.

---

## 16. Предварительные рекомендации для OP-RES-003

OP-RES-003 (типология приказов) должна **наслаиваться** на блоковую модель OP-RES-002, а не заменять её.

### 16.1 Предлагаемые оси классификации (для OP-RES-003)

| Axis | Examples from corpus folders |
|---|---|
| **Operational domain** | clinical, finance, procurement, HR-discipline, AХЧ, training |
| **Primary directive pattern** | commission / travel / regulation / event / allocation |
| **Actor model** | individual / unit / commission |
| **Control model** | self / delegated / multi |
| **Basis type** | legal / memo / protocol / application |
| **Attachment pattern** | none / inline / referenced |
| **Bilingual mode** | ru-only / kk+ru mirror / interleaved |

### 16.2 Не классифицировать на этапе OP-RES-003 как отдельные document types

- Каждая папка-источник (`Командировка`, `Бухгалтерия`) — **provenance**, не тип.
- «Приказ о наказании» и «кадровый приказ» близки по каркасу; различие — в payload и legal generator.

### 16.3 Shared engine primitives (candidate names for architecture track)

```text
DocumentShell
  ├── RequisitesBlock
  ├── PreambleBlock
  ├── OrderFormulaBlock
  ├── DispositiveSection
  │     └── OrderItem[]  { number, directive, actors[], object, deadline?, subitems[] }
  ├── AttachmentRefBlock
  ├── SignatureBlock
  ├── AgreementBlock
  └── AcknowledgementBlock
```

Personnel Orders = same shell + `PersonnelItemPayload`.  
Operational Orders = same shell + `OperationalItemPayload`.

### 16.4 Open questions for OP-RES-003

1. Сколько **top-level order classes** нужно продукту (10? 20? 40?) vs clause-level generators?
2. Как отделить **disciplinary** operational orders от **personnel** discipline в журнале?
3. Нужен ли отдельный class для **regulatory mega-orders** (30+ items) или parameter `item_density`?
4. Как кодировать **bilingual mirror** — one document two locales vs one locale composed at render?

---

## Appendix A — Research artifacts

| Artifact | Path |
|---|---|
| This report | `OP-RES-002-structural-pattern-analysis.md` |
| Block sequence diagram | `diagrams/operational-order-structure.svg` |
| Engine decomposition | `diagrams/operational-order-blocks.svg` |
| Draw.io source | `diagrams/operational-order-structure.drawio` |
| Anonymized skeleton | `samples/anonymized-structure-skeleton.txt` |
| Corpus inventory | [OP-RES-001-corpus-inventory.csv](./data/OP-RES-001-corpus-inventory.csv) (local; may contain PII paths) |

## Appendix B — Corpus frequency table (183 DOCX)

| Block marker | Documents |
|---|---|
| header_prikaz | 178 |
| order_part (ПРИКАЗЫВАЮ) | 177 |
| sign_director | 181 |
| sign_io (и.о. in text) | 181 |
| header_date | 170 |
| control | 168 |
| preamble_kk markers | 153 |
| header_city | 134 |
| preamble_v (В целях…) | 112 |
| basis_law | 110 |
| header_number | 93 |
| executor keywords | 81 |
| commission | 60 |
| deadline keywords | 36 |
| basis_memo | 34 |
| attachment | 35 |
| distribution | 25 |
| basis_order | 14 |
| agreement | 11 |

---

*OP-RES-002 complete. Research documentation only. No source files modified.*
