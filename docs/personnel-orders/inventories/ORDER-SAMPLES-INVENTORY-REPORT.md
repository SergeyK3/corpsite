# ORDER-SAMPLES Inventory Report

WP: WP-PO-000 — Personnel Orders Document Repository Preparation  
Date: 2026-07-10  
Mode: read-only metadata inventory (no operational copies)

## 1. Purpose

Подготовить управляемую структуру документного репозитория внутри проекта и провести read-only инвентаризацию внешнего каталога образцов/приказов без копирования реальных кадровых документов с персональными данными в Git.

## 2. Source Location

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\
```

Локальный legacy-источник. Не production storage. Не Git. Не runtime path backend.

## 3. Scan Method

- Рекурсивный обход файловой системы (только чтение метаданных).
- Для каждого файла собраны: relative path, filename, extension, size, modified time, parent folder.
- Классификация выполнена по имени файла, расширению, размеру и положению в дереве каталогов.
- Содержимое документов массово не извлекалось.
- ФИО и иные персональные данные в отчёт не сохранялись.
- Исходные файлы не перемещались, не копировались и не изменялись.

CSV: полный file-level инвентарь `order-samples-inventory.csv` остаётся **локальным** (не для Git).  
Агрегированный summary без перечисления файлов: [`order-samples-inventory-summary.csv`](order-samples-inventory-summary.csv)

## 4. Inventory Summary

| Metric | Value |
|---|---|
| Files scanned | **252** |
| Total size | ~21.2 MB (22,276,113 bytes) |
| `.docx` | 238 |
| `.doc` | 9 |
| `.zip` | 2 |
| `.pdf` | 2 |
| `.txt` | 1 |
| Root-level files | 16 |
| Under `2026 ПРИКАЗ Прием/` | 43 |
| Under `Производственные приказы/` | 193 |

Top-level structure observed:

- `2026 ПРИКАЗ Прием/` — годовой архив кадровых приказов по приёму и смежным действиям
- `Производственные приказы/` — архив производственных приказов (много тематических подпапок)
- Root-level mix: short form-like Word files, ZIP archives, specialty/compensation docs, notes

## 5. Classification Counts

| Classification | Count |
|---|---|
| `OPERATIONAL_DOCUMENT` | 237 |
| `TEMPLATE_CANDIDATE` | 9 |
| `ARCHIVE_CONTAINER` | 3 |
| `AUXILIARY_FILE` | 2 |
| `REFERENCE_SAMPLE` | 1 |
| `UNKNOWN` | 0 |
| **Total** | **252** |

Personal-data flag (`contains_possible_personal_data`):

| Value | Count |
|---|---|
| `yes` | 240 |
| `unknown` | 11 |
| `no` | 1 |

## 6. Candidate Templates

Автоматически **не копировались**. Только помечены для ручного review.

### 6.1 ПРИЕМ.docx

- **source path:** `d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\ПРИЕМ.docx`
- **filename:** `ПРИЕМ.docx`
- **why it may be a template:** короткое типовое имя формы «Прием» на корне источника; небольшой размер (~12.8 KB)
- **why manual review is still required:** содержимое не проверялось; возможны заполненные поля/ПДн
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.2 Ауыстыру.docx

- **source path:** `...\order_samples\Ауыстыру.docx`
- **filename:** `Ауыстыру.docx`
- **why it may be a template:** типовое имя формы перевода/перемещения; небольшой размер (~12.8 KB)
- **why manual review is still required:** не подтверждено отсутствие конкретных ФИО/дат/номеров
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.3 Ауыстыру временно 2026.docx

- **source path:** `...\order_samples\Ауыстыру временно 2026.docx`
- **filename:** `Ауыстыру временно 2026.docx`
- **why it may be a template:** имя похоже на форму временного перевода
- **why manual review is still required:** в имени есть год; может быть заполненным экземпляром 2026
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.4 СТАВКА алу.docx

- **source path:** `...\order_samples\СТАВКА алу.docx`
- **filename:** `СТАВКА алу.docx`
- **why it may be a template:** типовое имя формы по ставке
- **why manual review is still required:** содержимое не анализировалось
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.5 Еңбек шартын бұзу.docx

- **source path:** `...\order_samples\Еңбек шартын бұзу.docx`
- **filename:** `Еңбек шартын бұзу.docx`
- **why it may be a template:** типовое имя формы расторжения трудового договора
- **why manual review is still required:** возможны персональные данные
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.6 Бала күтімінен жұмысқа шығу.docx

- **source path:** `...\order_samples\Бала күтімінен жұмысқа шығу.docx`
- **filename:** `Бала күтімінен жұмысқа шығу.docx`
- **why it may be a template:** типовое имя формы возврата из отпуска по уходу за ребёнком
- **why manual review is still required:** leave-related forms often contain employee identity fields
- **target template folder:** `docs/personnel-orders/templates/leave`

### 6.7 Коса аткару 2026.docx

- **source path:** `...\order_samples\Коса аткару 2026.docx`
- **filename:** `Коса аткару 2026.docx`
- **why it may be a template:** имя соответствует форме совместительства
- **why manual review is still required:** год в имени; размер больше типичного бланка (~53 KB)
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.8 Біліктілік санаты туралы мәліметіне.docx

- **source path:** `...\order_samples\Біліктілік санаты туралы мәліметіне.docx`
- **filename:** `Біліктілік санаты туралы мәліметіне.docx`
- **why it may be a template:** имя похоже на типовую форму по квалификационной категории
- **why manual review is still required:** может быть заполненным кадровым документом
- **target template folder:** `docs/personnel-orders/templates/personnel`

### 6.9 Приказ об утвержд. типовой формы ТД.docx

- **source path:** `...\order_samples\Приказ об утвержд. типовой формы ТД.docx`
- **filename:** `Приказ об утвержд. типовой формы ТД.docx`
- **why it may be a template:** прямо указывает на утверждение типовой формы
- **why manual review is still required:** сам приказ об утверждении может содержать реквизиты/подписи; нужна проверка перед Git
- **target template folder:** `docs/personnel-orders/templates/shared`

## 7. Operational Documents

**237 files** classified as `OPERATIONAL_DOCUMENT`.

Основные зоны:

- почти все файлы внутри `2026 ПРИКАЗ Прием/` (подпапки по типам действий и помесячные/персональные экземпляры);
- почти все файлы внутри `Производственные приказы/` (~26 тематических/персональных подпапок);
- root-level specialty docs: `группа А лучевая 2026год.doc`, `по ЛД КТиМРТ ежемес.оплата.docx`.

Рекомендация: **KEEP_EXTERNAL** / позднее **IMPORT_LATER** в серверное storage.  
В Git не копировать. Имена сотрудников в этот отчёт не выносятся.

## 8. Archive Containers

| File | Size | Reason | Action |
|---|---|---|---|
| `2026 ПРИКАЗ Прием.zip` | ~572 KB | ZIP-архив годового набора приказов | `IMPORT_LATER` |
| `Производственные приказы.zip` | ~9.3 MB | ZIP-архив производственных приказов | `IMPORT_LATER` |
| `ПРИКАЗЫ НА ДОПЛАТУ  - 2026.docx` | ~315 KB | крупный сводный Word-документ по доплатам | `IMPORT_LATER` |

Папки `2026 ПРИКАЗ Прием/` и `Производственные приказы/` также являются archive trees; в CSV учтены входящие файлы, не сами каталоги.

## 9. Reference Samples

| File | Size | Notes | Action |
|---|---|---|---|
| `образцы приказов.docx` | ~15 KB | полезен как reference для разработки; не подтверждён как безопасный шаблон | `ANONYMIZE_BEFORE_COPY` → `docs/personnel-orders/samples/anonymized` |

## 10. Auxiliary Files

| File | Notes | Action |
|---|---|---|
| `вопросы.txt` | вспомогательные заметки/вопросы | `MANUAL_REVIEW` |
| `2026 ПРИКАЗ Прием/АУЫСТЫРУ/~$Апрель.docx` | временный lock-файл Word | `IGNORE` |

## 11. Unknown Items

`UNKNOWN`: **0**

На текущих эвристиках все файлы получили рабочую классификацию. Это не означает юридическую/кадровую достоверность — только metadata-based triage.

## 12. Personal Data Risks

- Большинство файлов находится внутри operational archive trees и с высокой вероятностью содержит ФИО, должности, даты, кадровые решения.
- ZIP и крупные сводные DOC/DOCX особенно рискованны: один файл может содержать много приказов.
- Даже root-level «короткие формы» могут быть заполненными экземплярами — поэтому `TEMPLATE_CANDIDATE` ≠ safe for Git.
- PDF внутри archive trees трактуются как вероятные сканы/подписанные копии.
- В отчёт и CSV **не** включались извлечённые ФИО/ИИН/тексты приказов.

## 13. Recommended Repository Actions

1. Сохранить созданную структуру `docs/personnel-orders/{templates,samples/anonymized,storage-design,inventories,implementation}`.
2. Не копировать operational documents автоматически.
3. Провести ручной review 9 `TEMPLATE_CANDIDATE` файлов.
4. При подтверждении безопасности — копировать только очищенные бланки в соответствующий `templates/*`.
5. `образцы приказов.docx` — только после анонимизации в `samples/anonymized/`.
6. Зафиксировать storage concept и README (сделано в WP-PO-000).
7. Whitelist `docs/personnel-orders/` в `.gitignore` выполнен в WP-PO-000A; полный file-level CSV остаётся локальным.

## 14. Recommended External Storage Actions

1. Оставить `order_samples` как локальный legacy import source.
2. Не использовать путь как production storage root backend.
3. Не синхронизировать каталог в GitHub.
4. Сохранить ZIP-архивы как import packages для будущего pipeline.
5. Рассмотреть отдельный controlled external operational storage вне репозитория.

## 15. Recommended Import Actions

| Class | Action |
|---|---|
| `ARCHIVE_CONTAINER` | `IMPORT_LATER` в server storage + metadata rows |
| `OPERATIONAL_DOCUMENT` | `KEEP_EXTERNAL` сейчас; позже controlled import |
| `TEMPLATE_CANDIDATE` | `REVIEW_FOR_TEMPLATE` (не import в production storage как шаблон Git) |
| `REFERENCE_SAMPLE` | `ANONYMIZE_BEFORE_COPY` |
| `AUXILIARY_FILE` | `MANUAL_REVIEW` / `IGNORE` |

Импорт в БД/storage на этом WP **не выполняется**.

## 16. Files Safe to Review for Git Inclusion

Только после ручной проверки содержимого (сейчас — кандидаты, не approved):

1. `ПРИЕМ.docx`
2. `Ауыстыру.docx`
3. `Ауыстыру временно 2026.docx`
4. `СТАВКА алу.docx`
5. `Еңбек шартын бұзу.docx`
6. `Бала күтімінен жұмысқа шығу.docx`
7. `Коса аткару 2026.docx`
8. `Біліктілік санаты туралы мәліметіне.docx`
9. `Приказ об утвержд. типовой формы ТД.docx`
10. `образцы приказов.docx` — только в anonymized samples, не как template

Также безопасны для Git артефакты WP-PO-000/000A: README, storage concept, inventory Markdown report, aggregated inventory summary CSV.  
Полный `order-samples-inventory.csv` **не** считается безопасным для Git (см. Appendix A).

## 17. Files Explicitly Not Safe for Git

- все файлы внутри `2026 ПРИКАЗ Прием/` (кроме временного `~$...`, который просто игнорируется);
- все файлы внутри `Производственные приказы/`;
- `2026 ПРИКАЗ Прием.zip`;
- `Производственные приказы.zip`;
- `ПРИКАЗЫ НА ДОПЛАТУ  - 2026.docx`;
- `группа А лучевая 2026год.doc`;
- `по ЛД КТиМРТ ежемес.оплата.docx`;
- любые PDF/сканы подписанных приказов;
- любые документы с ФИО/ИИН/конкретными кадровыми решениями.

## 18. Open Questions

1. Являются ли root-level short forms действительно пустыми бланками или заполненными экземплярами?
2. Нужен ли отдельный template type для «приказ об утверждении типовой формы» vs сама типовая форма ТД?
3. Следует ли производственные шаблоны выделять в `templates/production/` уже на этапе review, или сначала только personnel/leave/shared?
4. Где физически будет production storage root (`/opt/corpsite-storage` vs иной mount)?
5. Нужен ли controlled quarantine folder вне Git для кандидатов до anonymization?
6. Полный file-level CSV содержит имена/пути рабочих документов с возможными ФИО — оставлять локальным; в Git только aggregated summary.

---

## Appendix A — Git visibility (WP-PO-000A)

### A.1 Decision on full inventory CSV

`order-samples-inventory.csv` содержит:

- реальные имена рабочих документов;
- относительные пути внутри legacy-архива;
- имена подпапок и файлов, в которых встречаются ФИО сотрудников (например, командировки, наказания, выплаты).

**Рекомендация (принята для visibility):**

- полный CSV оставить локальным / ignored;
- в Git хранить только агрегированный [`order-samples-inventory-summary.csv`](order-samples-inventory-summary.csv) без перечисления файлов.

Решение не копирует и не публикует file-level inventory.

### A.2 Markdown report PII check

`ORDER-SAMPLES-INVENTORY-REPORT.md` проверен:

- ФИО сотрудников — отсутствуют;
- ИИН — отсутствуют;
- тексты приказов — отсутствуют;
- полные перечни operational-файлов — отсутствуют (только агрегаты, кандидаты на шаблоны и root-level archive/specialty имена без персональных списков).

Дополнительная редакция на удаление ФИО не требуется.

### A.3 Applied `.gitignore` changes

```gitignore
!docs/personnel-orders/
!docs/personnel-orders/**

docs/personnel-orders/operational/
docs/personnel-orders/import-source/
docs/personnel-orders/private/

# after global *.csv:
!docs/personnel-orders/inventories/order-samples-inventory-summary.csv
*.personnel-order-source.zip
```

Полный `order-samples-inventory.csv` остаётся ignored через глобальное правило `*.csv`.

Не используются широкие запреты `*.docx` / `*.doc` / `*.pdf`.

## Appendix B — Repository structure created/confirmed

Created or confirmed empty/safe dirs:

- `docs/personnel-orders/implementation/`
- `docs/personnel-orders/templates/personnel/`
- `docs/personnel-orders/templates/leave/`
- `docs/personnel-orders/templates/production/`
- `docs/personnel-orders/templates/shared/`
- `docs/personnel-orders/samples/anonymized/`
- `docs/personnel-orders/storage-design/`
- `docs/personnel-orders/inventories/`

Pre-existing (not deleted): `architecture/`, `diagrams/`, `review/`, `work-packages/`, `samples/`.

`.gitkeep` не добавлялись: в `docs/` репозитория такая практика не используется.
