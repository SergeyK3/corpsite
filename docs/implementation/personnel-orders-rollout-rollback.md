# Внедрение и откат

1. Применить Alembic migration `dxe001framework01` на test environment.
2. Выдать явно необходимые data-exchange grants; они не выдаются автоматически.
3. Выполнить synthetic workbook acceptance и экспорт эталона.
4. Провести локальный OCR/dry-run реальных документов, ручную сверку конфликтов
   и employee_id; в сервер загружается только review-ready workbook.
5. После отдельного HR решения о канонической модели реализовать контролируемое
   продвижение из review staging; до этого официальные приказы не импортируются.

Аналитический отпускной реестр допускается применять только в review-staging;
отсутствующий исходный реестр и неподтверждённые решения кадровика блокируют
официальный импорт.

Откат migration удаляет только `data_exchange_*` и review-staging. До удаления
любого applied package необходимо сохранить его audit/report; official HR
tables эта migration не изменяет.
