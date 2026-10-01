# Excel для подготовленных приказов

Версия: `PERSONNEL_ORDERS_XLSX_V1`.

Лист `Orders` содержит фиксированные поля: `schema_version`, `source_row_id`,
`employee_id`, `employee_full_name`, `order_number_raw`, `order_number`,
`order_date_raw`, `order_date`, `order_kind`, `action_type`, `pdf_source`,
`pdf_sha256`, `word_source`, `word_sha256`, `source_text`,
`recognition_confidence`, `recognition_status`, `matching_method`,
`review_status`, `note`.

`source_row_id` уникален внутри файла. Номер и дата сохраняются одновременно в
исходном и нормализованном виде; дата — ISO `YYYY-MM-DD`. Путь — только
относительный к внешнему source root, hash — SHA-256. `word_*` могут быть
пустыми только когда нет доказанной пары; PDF evidence обязательна.

Дополнительные листы: `UnmatchedEmployees`, `AmbiguousMatches`,
`DocumentConflicts`, `Metadata`, `Diagnostics`, `SourceManifest`. Пользователь
не должен добавлять формулы: Corpsite блокирует formula cells, а CLI экранирует
строки с `=`, `+`, `-`, `@`.

Бизнес-ключ review-staging: employee_id + order_kind + нормализованные номер,
дата, действие + SHA PDF/DOCX. Это не ключ официального `personnel_orders`.

Аналитический отпускной реестр использует отдельную схему
`PERSONNEL_VACATION_REGISTER_ANALYSIS_XLSX_V1`: source row, block/event,
исходные, предложенные, исправленные и подтверждённые HR значения передаются
раздельно. Пустая правка не очищает исходное значение.
