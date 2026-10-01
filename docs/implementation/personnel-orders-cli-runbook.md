# Запуск внешнего инструмента приказов

CLI расположен в `tools/order_preparation/prepare_personnel_orders.py` и
запускается вне server runtime. Сначала в Corpsite экспортируйте эталонный
список сотрудников, затем выполните dry-run:

## Ограниченный исследовательский пилот PDF ↔ Word

До массового OCR следует запускать отдельный read-only пилот. Он выбирает
только первую, среднюю и последнюю страницы каждого PDF, не открывает БД и не
изменяет ни исходные документы, ни таблицы Corpsite:

```powershell
python tools/order_preparation/research_pdf_word_linking.py `
  '…\order_samples' `
  --output C:\safe-work\pdf_word_pilot.xlsx --include-full-text
```

`--include-full-text` создаёт локальный лист `OCRFullText_LOCAL_PII` с
персональными данными исключительно для ручной сверки. Такой файл нельзя
передавать или загружать на сервер. Без флага в книге остаются только
обезличенные фрагменты и SHA-256. Совпадение номера и даты формирует только
кандидата; оно не подтверждает связь PDF с Word и не разрешает импорт.

```powershell
python tools/order_preparation/prepare_personnel_orders.py `
  --pdf-root '…\Журнал кадровых приказов' `
  --word-root '…\2026 ПРИКАЗ Прием' `
  --employee-reference C:\safe-work\corpsite_employee_reference.xlsx `
  --output C:\safe-work\personnel_orders.xlsx --dry-run
```

После проверки локального OCR и листов diagnostics повторите без `--dry-run`.
Не размещайте output внутри source folders. Инструмент рекурсивно читает PDF и
DOCX, вычисляет SHA-256 и не меняет исходные файлы. Для сканов требуется
локально установленный Tesseract с языками минимум `rus+eng` (для полного
казахского OCR дополнительно требуется `kaz`); при его ошибке
строка остаётся review-required, а не заполняется догадкой.

Аналитический отпускной реестр запускается отдельным data-exchange сценарием;
не пропускайте его через OCR/Word schema и не загружайте без кадрового решения.
