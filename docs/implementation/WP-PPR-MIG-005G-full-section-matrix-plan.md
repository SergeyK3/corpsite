# WP-PPR-MIG-005G — полный каталог разделов и макет общей матрицы

| Параметр | Значение |
|---|---|
| Статус | **Completed — десятиколоночная projection, API и matrix UI готовы** |
| Родительский контур | [WP-PPR-MIG-005](WP-PPR-MIG-005-migration-status-matrix-plan.md) |
| Зависимости | [WP-005A — semantics](WP-PPR-MIG-005A-status-semantics.md), [WP-005B — projection](WP-PPR-MIG-005B-status-projection-read-model.md), [WP-005C — report API](WP-PPR-MIG-005C-report-api-and-authorization.md) |
| Цель | Показать полный утверждённый набор миграционных разделов личной карточки в одной matrix, не выдавая неподключённые обработчики за выполненную миграцию. |
| Не входит в scope | Изменения UI, API, БД, projection, миграций, permissions и данных. |

## 1. Источник и границы каталога

Исходный навигационный реестр — `corpsite-ui/lib/pprCardSections.ts`, экспорт `PPR_CARD_SECTIONS`.
`PprPersonalCardPageClient` подтверждает, что `additional` — контейнер для языков,
наград, учёных степеней и званий; `assignment` — текущая трудовая деятельность;
`employment_biography` — биография до поступления в организацию.

Матрица не повторяет контейнер `additional`: его три самостоятельных кадровых набора
показаны отдельными колонками. Их переход временно ведёт в `section=additional`.

Из миграционного каталога намеренно исключены `orders`, `applications`, `onboarding`
и `changes`. Это операционные или системные разделы (кадровые действия, обращения,
адаптационный процесс и журнал), а не самостоятельные PPR-наборы кадровых фактов
для migration matrix. Они могут оставаться вкладками карточки, но не получают
колонку migration status.

WP-005G-A расширил persisted projection/rebuild до всех десяти codes.
[WP-005G-B](WP-PPR-MIG-005G-B-full-section-report-api.md) расширил read-only
matrix и person-status API до тех же десяти persisted cells.
[WP-005G-C](WP-PPR-MIG-005G-C-full-section-matrix-ui.md) расширил существующую
страницу матрицы до десяти колонок с горизонтальной прокруткой и sticky-колонкой
сотрудника; API labels и существующие безопасные переходы в карточку сохранены.

## 2. Утверждённый каталог из десяти колонок

| № | Matrix section code | Отображаемое имя | Соответствие существующей карточке | Самостоятельная колонка | Обработка сейчас |
|---:|---|---|---|---|---|
| 1 | `general` | Общие сведения | `general` | Да | Stage 1 / projection |
| 2 | `education` | Образование | `education` | Да | Stage 2 / projection |
| 3 | `training` | Обучение и повышение квалификации | `training` | Да | Stage 3 / projection |
| 4 | `relatives` | Родственники | `family` | Да | Нет |
| 5 | `military` | Воинский учёт | `military` | Да | Нет |
| 6 | `employment_biography` | Трудовая биография | `employment_biography` | Да | Нет |
| 7 | `employment_history` | Трудовая деятельность / послужной список | `assignment` (текущее назначение) | Да | Нет |
| 8 | `foreign_languages` | Знание иностранных языков | подраздел `additional` | Да | Нет |
| 9 | `awards` | Награды | подраздел `additional` | Да | Нет |
| 10 | `academic_degrees_titles` | Учёные степени и звания | подраздел `additional` | Да | Нет |

`employment_history` — migration-facing code для трудовой деятельности/послужного списка.
В текущем UI ближайшая реальная вкладка — `assignment`; её нельзя смешивать с
`employment_biography`, поскольку это разные наборы фактов и будущие fingerprints.
Когда карточка получит самостоятельный раздел послужного списка, route может быть
уточнён без переименования matrix section code.

## 3. Утверждённые правила projection и статусов

Для каждого `person_id` в active universe projection хранит по одной строке для
каждого из десяти section codes: уникальность — `(universe_id, person_id, section_code)`.
`employee_id` остаётся необязательным кадровым контекстом. ИИН не является ключом
матрицы и не хранится/не возвращается. Несвязанные CSV-строки без `person_id` не
получают строк projection и не появляются в matrix.

Все десять ячеек persisted: future sections не должны быть catalog-derived только
в API. Это даёт стабильные timestamps, counts, filtering, invalidation и audit
границы, но не разрешает подменять отсутствие обработки успешной миграцией.

| Условие | `status_code` | Текст статуса | `reason_code` | Текст причины |
|---|---|---|---|---|
| Section обработчик ещё не подключён и section применим к person | `NOT_STARTED` | Не начато | `SECTION_PROCESSING_NOT_CONNECTED` | Обработка раздела ещё не подключена |
| Section неприменим по утверждённому типу person/employee и policy | `NOT_APPLICABLE` | Не применимо | `POLICY_SECTION_NOT_APPLICABLE` | Раздел не применяется |
| Есть подтверждённые stage/source/canonical facts | По дереву WP-005A | Backend label | Reason из WP-005A | Backend label |

`NOT_APPLICABLE` требует policy-основания и не означает «пустой раздел». Пока
конкретное policy-rule не введено, default для подключённого к каталогу и применимого
section — `NOT_STARTED`.

Projection и API по-прежнему содержат только безопасные IDs, section/status/reason
codes, labels, timestamps и разрешённые evidence references. Кадровые значения,
ФИО в projection, ИИН, raw payload и документы туда не копируются. ФИО для строки
матрицы получает scoped report API существующим canonical join только после
permission и org-scope check.

## 4. Целевой read contract и переходы

Полный matrix API сохраняет инварианты WP-005C: обязательный `universe_id`,
server-side pagination, стабильную сортировку, org scope до pagination/counts,
section/status/reason filters и текстовые `status_label`/`reason_label`. Он отдаёт
все десять persisted cells на строку и считает aggregates по полному scoped набору.

Переход из ячейки использует существующий PPR-safe contract:

```text
/directory/personnel/persons/{person_id}/card
  ?section={general|education|training|family|military|employment_biography|assignment|additional}
  &migration_universe_id={universe_id}
  &return_to={encoded-relative-matrix-url}
```

Mapping колонок: `relatives → family`, `employment_history → assignment`,
`foreign_languages` / `awards` / `academic_degrees_titles → additional` до появления
гранулярных card anchors. `return_to` остаётся относительным и сохраняет universe,
фильтры и страницу.

## 5. Графический макет

Настоящий PNG-макет существующего тёмного визуального языка создан локально:

```text
D:\Temp\wp-ppr-mig-005g-full-section-matrix-mockup.png
```

Он показывает закреплённую колонку сотрудника, горизонтальную прокрутку и все десять
колонок: общие сведения, образование, обучение, родственники, воинский учёт,
трудовую биографию, трудовую деятельность, иностранные языки, награды, учёные
степени и звания. В ячейках явно видны текстовые `Не начато`, `Не применимо`,
`Согласовано` и `Требуется обновление` вместе с пояснениями; цвет используется лишь
как вспомогательный сигнал.

## 6. Последовательность реализации после утверждения

1. Завершено WP-005G-A: section constraint, migration projection schema/repository
   и initial persisted `NOT_STARTED` rows для полного каталога.
2. Добавить policy evaluator для `NOT_APPLICABLE` и
   точечную invalidation contract для будущих section handlers.
3. Завершено WP-005G-B: scoped report API, aggregation и filters используют
   десять persisted cells без N+1.
4. Завершено WP-005G-C: matrix UI показывает десять колонок, sticky employee
   column, horizontal scroll, доступные текстовые status/reason и указанный card mapping.
5. Подключать stage/source processors по одному section, заменяя только его
   `NOT_STARTED` на фактический результат согласно WP-005A.

## 7. Зафиксированные решения владельца продукта

| Решение | Утверждённый вариант | Последствие |
|---|---|---|
| Хранение ячеек будущих разделов | Все десять cells хранятся в projection | Требуется расширение schema/rebuild и unique invariant на полный каталог. |
| Неприменимость | Использовать `NOT_APPLICABLE` с policy reason | Нужен явный policy evaluator; пустой набор записей не равен неприменимости. |
| Additional details | `foreign_languages`, `awards`, `academic_degrees_titles` — три отдельные колонки | Для всех трёх понадобятся самостоятельные source/fingerprint/acceptance contracts. |
