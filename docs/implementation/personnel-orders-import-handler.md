# Обработчик подготовленных приказов

Сценарий `PERSONNEL_ORDERS_REVIEW_IMPORT` принимает только
`PERSONNEL_ORDERS_XLSX_V1`. Он проверяет листы/поля, formula cells, PDF hash,
безопасность относительных путей, employee_id и точное контрольное ФИО.
Ненайденные и неоднозначные строки блокируют пакет.

Apply создаёт только `personnel_order_import_review_records`. Официальные
`personnel_orders`, события, Person, Employee и assignments не изменяются.
Причина: реальная модель currently поддерживает ограниченный набор типов и не
позволяет без утверждённой модели безопасно представлять все архивные действия.
Продвижение review-записи в официальный приказ — отдельная кадровая процедура.

Отдельный `PERSONNEL_VACATION_REGISTER_REVIEW_IMPORT` хранит исключения
отпускного реестра только как evidence для review. Неподтверждённые правки,
`UNCLASSIFIED` и связанные действия без исходного отпуска остаются заблокированы.

Пакет проходит upload → preview → dry-run → echoed confirmation → one
transaction apply. Повторный upload SHA распознаётся, повторное apply запрещено.
