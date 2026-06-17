# ADR-038-D.1. Sync Admin UI (Read-only)

Статус: Approved (D.1 implemented)  
Дата: 2026-06-17  
Родитель: [ADR-038-C.1](ADR-038-C-conflict-policy.md)

## Контекст

Phase B (export/import/preview) и Phase C.1 (conflict policy + apply gate) завершены и прошли server smoke-test.

Phase D.1 — первый пользовательский интерфейс для Sync Foundation **без записи в БД**.

## Реализация

| Слой | Путь |
|---|---|
| UI | `/admin/sync` — `corpsite-ui/app/admin/sync/` |
| API meta | `GET /directory/personnel/sync/meta` |
| API export | `POST /directory/personnel/sync/export` |
| API preview | `POST /directory/personnel/sync/preview` |

## UI (read-only)

- **Состояние Sync** — schema/package version; последний export/preview (in-memory на странице).
- **Экспорт** — форма (source instance, org, environment, notes) → summary + скачивание zip.
- **Загрузка + preview** — upload zip → summary counts + таблица записей.
- **Conflict visualization** — status `conflict`, action `review_required`, без кнопок resolution.

## Запрещено в D.1

- Apply package / force apply
- Conflict resolution UI
- POST `/sync/apply` или эквивалент
- История sync в БД

## Тесты

- `tests/test_hr_sync_api.py` — meta, export, preview, conflict/table contract

## Следующий шаг

**Phase D.2** — Apply UI с apply gate, dry-run vs apply, blocked conflicts summary.

## Ссылки

- [ADR-038-B](ADR-038-B-sync-foundation.md)
- [ADR-038-C](ADR-038-C-conflict-policy.md)
