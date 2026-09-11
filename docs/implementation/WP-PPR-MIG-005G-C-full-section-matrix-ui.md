# WP-PPR-MIG-005G-C — интерфейс общей матрицы из десяти разделов

| Параметр | Значение |
|---|---|
| Статус | **Completed** |
| Родительский пакет | [WP-PPR-MIG-005G](WP-PPR-MIG-005G-full-section-matrix-plan.md) |
| Зависимости | WP-005G-A persisted projection, WP-005G-B read API |
| Экран | `/directory/personnel/migration-status` |

## Реализация

Существующая `MigrationStatusMatrixPageClient` расширена без замены экрана. Матрица
показывает ровно десять ячеек в server/API order:

1. `general` — «Общие сведения»;
2. `education` — «Образование»;
3. `training` — «Обучение и повышение квалификации»;
4. `relatives` — «Родственники»;
5. `military` — «Воинский учёт»;
6. `employment_biography` — «Трудовая биография»;
7. `employment_history` — «Трудовая деятельность / послужной список»;
8. `foreign_languages` — «Знание иностранных языков»;
9. `awards` — «Награды»;
10. `academic_degrees_titles` — «Учёные степени и звания».

Контейнер таблицы использует постоянную горизонтальную прокрутку (`overflow-x: scroll`), а таблица имеет фиксированную читаемую ширину `2200px`.
а колонка «Сотрудник» закреплена (`sticky left-0`) в заголовке и строках. Каждая
ячейка показывает переданные API `status_label` и `reason_label`; frontend не
создаёт собственный словарь отображаемых статусов.

Под таблицей, перед pagination, расположен постоянно доступный range scrollbar, синхронизированный с `scrollLeft` таблицы. Существующие «Набор миграции», поиск, фильтры, pagination, permission gate и
выбор из нескольких universe сохранены. Фильтр разделов строится из общего
десятиколоночного списка.

## Навигация из ячеек

Все ссылки используют существующий безопасный `buildPprMigrationCardHref` и
сохраняют `migration_universe_id` и относительный `return_to` со всеми URL
фильтрами и страницей:

| Matrix code | Card section |
|---|---|
| `general` | `general` |
| `education` | `education` |
| `training` | `training` |
| `relatives` | `family` |
| `military` | `military` |
| `employment_biography` | `employment_biography` |
| `employment_history` | `assignment` |
| `foreign_languages`, `awards`, `academic_degrees_titles` | `additional` |

Последние три колонки намеренно используют один существующий раздел
«Дополнительные сведения»: новые вкладки карточки в scope не входят.

## Проверки

Целевой frontend-тест проверяет порядок десяти заголовков, десять ячеек строки,
горизонтальный контейнер, sticky-колонку сотрудника, текстовые `NOT_STARTED` и
`NOT_APPLICABLE`, все требуемые карточные маршруты, сохранение universe/return
URL, фильтры и выбор universe. Backend, БД, migration и API не изменялись.
