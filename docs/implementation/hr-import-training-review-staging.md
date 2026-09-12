# Проверка импортированных записей обучения в staging

## Назначение

Это implementation note фактически реализованного локального review-механизма для
нормализованных `training` записей контрольного списка. Нормативные требования определяет
[WP-PPR-MIG-004A](WP-PPR-MIG-004A-training-staging-review-and-validity.md); при противоречии
приоритет имеет он. Архитектурный контекст карточки описан в
[WP-HR-CARD-002](../architecture/WP-HR-CARD-002-unified-personnel-record-card.md), а перенос в
канонический `person_training` регулирует [WP-PPR-MIG-004](WP-PPR-MIG-004-training-migration-plan.md).

## Границы

- Данные остаются в `hr_import_normalized_records` и его `review_override_json`.
- Канонические `Person`, `Employee` и `PersonTraining` не читаются для записи и не
  изменяются.
- Provenance (`batch_id`, исходная строка, лист, исходный текст) сохраняется в staging,
  но не выводится в таблице карточки.
- Повторный rebuild не должен удалять запись с review metadata или ручным override.

## Фактически реализованные состояния и права

Внутренние normalized состояния `pending`, `approved`, `rejected` выводятся соответственно
как «Требуется проверка», «Проверено», «Отклонено». Активное отдельное предложение
сотрудника выводится как «Предложено сотрудником» и не заменяет current values до решения
кадровика. Изменение и решение требуют `require_personnel_admin_or_403`; предложение
принимается только если `users.employee_id` точно совпадает с employee записи.

## Фактически реализованные даты и часы

Механизм сохраняет `EXACT`/`CALCULATED` date metadata и выдаёт summary из одной backend
формулы по дате окончания. Детальный алгоритм дат, рабочие дни, норматив и набор учитываемых
review-статусов нормативно определены в [WP-PPR-MIG-004A](WP-PPR-MIG-004A-training-staging-review-and-validity.md).

## Разделение staging-записи

Фактическая реализация хранит связь в private metadata
`_training_review_v1.split`: parent ID, `split_group_id`, child order, offsets,
raw provenance, actor и correlation ID. Дети создаются как
`training_manual_split`; endpoint-ы — `GET .../split-preview`, `POST .../split`
и `POST .../undo-split`; UI — `PprCardTrainingSection.tsx`. Это implementation
note: при конфликте нормативным источником является
[WP-PPR-MIG-004A](WP-PPR-MIG-004A-training-staging-review-and-validity.md).

## Конкурентность и аудит

Private member `_training_review_v1` existing `review_override_json` хранит version,
качество/расчёт дат, pending proposal и последовательную application-level историю с
before/after, ID normalised record/batch/source row, actor ID, снимком ФИО/логина,
снимком review-решения, действием, комментарием и временем. Update использует
compare-and-set по version; устаревшая форма получает HTTP 409. Повторное approve/reject
без нового состояния идемпотентно и не добавляет историю. История относится к staging
record; это не promotion и не замена канонического кадрового аудита.
