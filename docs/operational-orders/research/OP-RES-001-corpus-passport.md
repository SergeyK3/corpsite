# OP-RES-001 — Corpus Passport: Production Orders

WP: **OP-RES-001** — Operational Orders Corpus Inventory and Baseline  
Date: **2026-07-12**  
Mode: **research-only** (read-only scan; source documents untouched)

## 1. Purpose

Создать проверяемый baseline корпуса реальных производственных приказов для последующих исследований:

- структурных шаблонов;
- типологии приказов;
- типов распорядительных пунктов;
- исполнителей, контроля, сроков, комиссий, приложений;
- генерации документов.

На этом этапе **не** проектируется финальная архитектура и **не** реализуется модуль приказов.

## 2. Source Location

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы\
```

- Локальный legacy-источник, предоставленный пользователем.
- Не production storage, не Git, не runtime path backend.
- Исходные файлы **не перемещались, не переименовывались и не изменялись**.

Связанный контекст: корневая инвентаризация `order_samples` описана в [`docs/personnel-orders/inventories/ORDER-SAMPLES-INVENTORY-REPORT.md`](../../personnel-orders/inventories/ORDER-SAMPLES-INVENTORY-REPORT.md); подпапка `Производственные приказы/` там отмечена как archive tree (193 файла).

## 3. Scan Method

| Step | Method |
|---|---|
| File metadata | Рекурсивный read-only обход; `stat` для size/mtime |
| DOCX | OOXML probe: `zipfile` + `word/document.xml`; подсчёт `w:p`, `w:t`, таблиц, media/embeddings |
| DOC | OLE magic + `olefile` stream probe (`WordDocument`, `1Table`); **без конвертации и перезаписи** исходников |
| PDF | `pypdf` text probe на первых страницах; OCR **не применялся** |
| Дубликаты | SHA-256 content hash + normalized stem + filename + size |
| Язык/год | Эвристики по имени файла (без извлечения текста тела) |

Скрипт (reproducible): [`scripts/op_res_001_inventory.py`](scripts/op_res_001_inventory.py)

## 4. Corpus Summary

| Metric | Value |
|---|---|
| Files scanned | **193** |
| Total size | **10.6 MB** (10,597,834 bytes) |
| Thematic top-level folders | **25** (+ 1 root-level file) |
| Extensions | `.docx` 183, `.doc` 8, `.pdf` 2 |
| XLS/XLSX | **0** (не встречены) |
| Other formats | **0** |

### 4.1 Presumed document year (from filename)

| Year in filename | Files |
|---|---|
| none / not detected | 148 |
| 2026 | 41 |
| 2025 | 4 |

Год в имени файла часто отсутствует; для dating baseline следует использовать дату изменения файла и содержимое на следующих этапах.

### 4.2 Presumed language (from filename)

| Language | Files | Share |
|---|---|---|
| `ru` | 184 | 95.3% |
| `kk` | 7 | 3.6% |
| `mixed` | 1 | 0.5% |
| `unknown` | 1 | 0.5% |

Казахскоязычные документы сконцентрированы в `Ахч/` (4 файла), `Командировка/` (2), `Праздничный приказ/` (1), `Эпидемиолог -Производ.приказы на 2026 год/` (1).

### 4.3 Text extraction suitability

| Suitability | Files | Notes |
|---|---|---|
| `good` | 183 | DOCX с извлекаемым OOXML-текстом (≥100 chars в `document.xml`) |
| `fair` | 8 | Legacy `.doc` с подтверждённым `WordDocument` stream |
| `poor_ocr_needed` | 2 | PDF без извлекаемого текстового слоя |

**DOCX OOXML stats (183 files):**

| Measure | Min | Median | Max |
|---|---|---|---|
| Paragraphs (`w:p`) | 23 | 88 | 1,118 |
| Text chars (`w:t`) | 298 | 2,218 | 26,304 |
| With tables | 24 | — | — |
| With images | 1 | — | — |
| With embeddings | 0 | — | — |

### 4.4 Duplicates and versions

| Signal | Count |
|---|---|
| No duplicate signal | 189 |
| Identical content hash (2 pairs) | 2 files |
| Same normalized stem (version siblings) | 2 files |
| Version/copy marker in filename | 12 |

**Подтверждённые идентичные копии (content hash):**

- `Бухгалтерия/по учетной политике.docx` ↔ `Бухгалтерия/по учетной политике 2026.docx` (различаются только именем; одинаковый mtime)

**Вероятные редакции одного документа (normalized stem):**

- `Гос.закуп/Приказ на открытый конкурс … (1).docx` ↔ `… (5).docx`

Маркеры версий: суффиксы `(1)`, `(2)`, `(5)`, слово `копия`, `— копия.doc`.

## 5. Thematic Folder Map

Папки верхнего уровня используются как **thematic_source_folder** (прокси подразделения/темы). Агрегат по числу файлов:

| Files | Folder | Research cluster (baseline) |
|---|---|---|
| 37 | Командировка | Командировки, служебные поездки |
| 23 | по платным услугам 2026 | Платные услуги / тарификация |
| 21 | Бухгалтерия | Учёт, ОППВ, финансовые процедуры |
| 16 | Обучение | Обучение персонала (вкл. вложенные подпапки) |
| 12 | Ахч | АХЧ: ОТ, ТБ, транспорт, комиссии (ru+kk) |
| 11 | ККМУ | Клинико-диагностическая деятельность |
| 10 | Экономисты | Экономический блок |
| 9 | Б.Мустафина | Персональные/кадровые приказы (ФИО в пути папки) |
| 9 | Эпидемиолог -Производ.приказы на 2026 год | Эпиднадзор, инфекционный контроль |
| 7 | приказ наказание | Дисциплинарные решения |
| 7 | Трансфузиология | Трансфузиология |
| 5 | Гос.закуп | Государственные закупки |
| 4 | Праздничный приказ | Праздничные/событийные приказы |
| 3 | Аптека | Фармация, наркотические средства |
| 3 | ВЦРО | ВЦРО |
| 3 | Главная медсестра | Сестринское управление |
| 2 | Лучевая | Лучевая диагностика |
| 2 | Нурбеков Б.Б | Персональные приказы (ФИО в пути) |
| 2 | О снятии испытательного срока | Кадровые решения |
| 1 | Альянс онкологов | Онкология |
| 1 | Инсульт | Инсультный центр |
| 1 | Комплаенс-офицер | Комплаенс |
| 1 | ОУЧР | ОУЧР |
| 1 | Практика врачей | Практика врачей |
| 1 | Приказы о снятии наказания | Снятие наказания |
| 1 | *(root)* | `Проект приказа по Антибиотикам.docx` |

**Наблюдение:** структура корпуса **тематически-фрагментирована** — папки отражают инициаторов/направления (отдел, ФИО, годовой проект), а не единую номенклатуру типов приказов.

## 6. Format-Specific Findings

### 6.1 DOCX (183) — primary corpus format

- Все 183 файла: валидный OOXML, `word/document.xml` присутствует.
- 24 документа содержат таблицы (`w:tbl`) — вероятные списки исполнителей, графики, перечни.
- 1 документ содержит изображения (`word/media/`) — возможна скан-подпись или логотип.
- Встроенных OLE-объектов (`word/embeddings/`) не обнаружено.

**Рекомендация для OP-RES-002+:** OOXML-парсинг достаточен для bulk text/structure extraction без OCR.

### 6.2 DOC (8) — legacy Word binary

| Relative path | Extraction |
|---|---|
| `Аптека/Приказ на спирт.doc` | fair |
| `Ахч/приказ - субботник-2026.doc` | fair |
| `Главная медсестра/по наркотических веществам ответственные.doc` | fair |
| `Гос.закуп/Приказ о внесении изменений в план каз рус 03.07.2026.doc` | fair |
| `Инсульт/группа А инсульт 2026год.doc` | fair |
| `ККМУ/3. Приказ по КИЛИ.doc  17.01.26г. — копия.doc` | fair (+ version marker) |
| `Лучевая/группа А лучевая 2026год.doc` | fair |
| `Эпидемиолог -…/приказ по ВИЧ ( СПИД)+.doc` | fair |

**Безопасный локальный способ извлечения текста (без перезаписи исходников):**

1. **Предпочтительно:** LibreOffice headless на **копии во временный каталог**  
   `soffice --headless --convert-to txt:Text --outdir <tmp> <source.doc>`
2. **Альтернатива:** `antiword <source.doc>` (read-only stdout)
3. **Структурная проверка:** `olefile` — подтверждение `WordDocument` stream (уже выполнено)

`antiword` и `soffice` в текущем PATH **не обнаружены**; для полнотекстового этапа потребуется установка или CI-side probe.

### 6.3 PDF (2) — auxiliary / non-standard

| File | Probe result |
|---|---|
| `Обучение/…/НАО «Медицинский Университет Астана» … ценовое предложение в.pdf` | `poor_ocr_needed` — похоже на скан/коммерческое приложение, не типовой приказ |
| `Обучение/…/WhatsApp Scan 2026-01-20 at 16.50.55.pdf` | `poor_ocr_needed` — мобильный скан |

PDF в корпусе **периферийны** (2 из 193); для baseline генерации приказов приоритет — DOCX.

## 7. Machine-Readable Artifacts

| Artifact | Path | Git visibility |
|---|---|---|
| Full file-level registry | [`data/OP-RES-001-corpus-inventory.csv`](data/OP-RES-001-corpus-inventory.csv) | **Local / ignored** — пути и имена могут содержать ФИО |
| Aggregated summary | [`data/OP-RES-001-corpus-inventory-summary.csv`](data/OP-RES-001-corpus-inventory-summary.csv) | Safe for Git (агрегаты без file list) |
| Repro script | [`scripts/op_res_001_inventory.py`](scripts/op_res_001_inventory.py) | Safe for Git |
| Generated stats (internal) | `data/OP-RES-001-passport-stats.json` | Local / ignored |

### CSV columns (full registry)

`relative_path`, `filename`, `parent_folder`, `extension`, `size_bytes`, `modified_utc`, `presumed_year`, `presumed_language`, `thematic_source_folder`, `possible_duplicate`, `version_or_copy`, `text_extraction_suitability`, `technical_notes`

## 8. Baseline Hypotheses for Next Research (not validated)

На основе имён папок/файлов и OOXML-структуры (без NLP по телу):

| Hypothesis | Evidence |
|---|---|
| H1: корпус ориентирован на **операционные распоряжения**, не кадровые | темы: закупки, обучение, ОТ, эпиднадзор, платные услуги |
| H2: значимая доля приказов содержит **табличные приложения** | 24/183 DOCX с `w:tbl` |
| H3: **комиссии** — частый паттерн | имена: «комиссия», «формулярная комиссия», «по гос символикам» |
| H4: **двуязычие** — edge case, не основной поток | 8/193 kk/mixed |
| H5: **версионность** хранится файлово (копии, суффиксы) | 12 version markers + 2 stem-sibling pairs |
| H6: часть «приказов» — **проекты/черновики** | `Проект приказа по Антибиотикам.docx` на root |

Эти гипотезы требуют OP-RES-002 (content/structure sampling).

## 9. Privacy and Git Safety

- Полный CSV перечисляет **реальные пути и имена**; в папках `Командировка/`, `Б.Мустафина/`, `Нурбеков Б.Б/` и отдельных файлах встречаются **ФИО**.
- Тексты приказов **не извлекались** в отчёт.
- Для Git рекомендуется: passport + summary CSV; полный inventory — локально или в ignored research data.

## 10. Open Questions

1. Нормализовать ли `thematic_source_folder` к справочнику подразделений Corpsite или оставить legacy-имена папок как provenance?
2. Как трактовать папки с ФИО (`Б.Мустафина`, `Нурбеков Б.Б`) — личный архив vs отдел?
3. Нужна ли миграция 8 `.doc` → reference DOCX для единого pipeline, или dual-parser?
4. Два PDF в `Обучение/` — включать в корпус приказов или вынести в attachments/quarantine?
5. Пара идентичных файлов в `Бухгалтерия/` — оставить оба в корпусе или дедупликация на этапе sampling?

## 11. Reproduction

```powershell
python docs/operational-orders/research/scripts/op_res_001_inventory.py
```

Ожидаемый результат: 193 строки в `OP-RES-001-corpus-inventory.csv`.

---

*OP-RES-001 complete. No source files modified. No runtime code changed.*
