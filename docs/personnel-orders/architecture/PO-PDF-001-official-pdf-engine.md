# PO-PDF-001 — Official Personnel Order PDF Engine

**Статус:** Implemented (MVP)  
**WP:** WP-PO-PDF-001  
**Код:** `corpsite-ui/app/directory/personnel/orders/[orderId]/pdf/`, `_lib/personnelOrderPdf*`

---

## 1. Цели

Серверное формирование кадрового приказа в PDF, полностью контролируемого системой:

- без браузерных колонтитулов (дата, URL, название сайта, номер страницы);
- формат A4;
- Times New Roman 14 pt (при наличии системного шрифта);
- языки `kk` / `ru` / `kk-ru`;
- те же заголовки, пункты, подпись, ознакомление и watermark, что у HTML-предпросмотра;
- источник данных — `PersonnelOrderPrintViewModel`;
- пригодно для просмотра, скачивания и печати;
- архитектурная заготовка под будущий snapshot / SHA-256 / ЭЦП.

HTML-маршрут `/print` сохраняется как **экранный предпросмотр**.

---

## 2. Архитектура renderer’а

```text
UI (Bearer) → GET /orders/{id}/pdf?language=…
  → auth + FastAPI detail (те же права)
  → PersonnelOrderPrintViewModel
  → shared print HTML template (server-safe string, no react-dom/server)
  → Playwright Chromium page.setContent()
  → page.pdf({ displayHeaderFooter: false, format: A4, … })
  → application/pdf
```

Разделение слоёв:

| Слой | Ответственность |
|---|---|
| Order data | FastAPI detail + directory lookups |
| Print view-model | `buildPersonnelOrderPrintViewModel` (общий с HTML) |
| Shared document HTML | `buildPersonnelOrderPrintDocumentHtml` (preview + PDF) |
| PDF document wrapper | `buildPersonnelOrderPdfHtmlDocument` |
| PDF transport/rendering | `PersonnelOrderPdfRenderer` / Playwright |

Интерфейс:

```ts
type PersonnelOrderPdfRenderer = {
  render(input: { model: PersonnelOrderPrintViewModel; language: … }): Promise<Buffer>;
};
```

HTTP Route Handler **не** связан с будущим immutable storage.

---

## 3. Security

- Нет `?url=` / `?html=` — только проверенный `orderId` + enum языка.
- Renderer работает с HTML, собранным на сервере (`page.setContent`), без открытия произвольных URL.
- Ответ: `Cache-Control: private, no-store`.
- Ошибки: 401 / 403 / 404 / 422 / 500 без stack trace.
- Аудит-лог: `order_id`, `language`, `requesting_user_id`, `result`, `duration_ms`, `error_code`.
- Не логируются: текст приказа, ИИН, cookies, Authorization, HTML, PDF bytes.

---

## 4. Auth

Текущая UI-модель: Bearer JWT в `localStorage` (не cookie).

Поэтому выбран **Variant B**:

1. Route Handler читает `Authorization: Bearer …` (и dev `X-User-Id` вне production).
2. Тот же токен проксируется в FastAPI для detail/org/positions.
3. HTML собирается в handler; Chromium **не** открывает `/print` и не получает cookies пользователя.

UI-открытие PDF:

```ts
fetch(pdfHref, { headers: Authorization… }) → blob → window.open(blobUrl, "_blank", "noopener,noreferrer")
```

Прямой `window.open(pdfHref)` без Authorization невозможен при текущей auth-модели — это ограничение зафиксировано, `/print` не ослаблялся.

---

## 5. Font policy

Требование: **Times New Roman, 14 pt**.

| Среда | Статус |
|---|---|
| Windows (dev) | `times.ttf` присутствует |
| VPS | **не проверено в WP** (SSH publickey denied с рабочей станции) |

Правила:

- не коммитить проприетарный файл шрифта без лицензии;
- на VPS проверить `fc-match "Times New Roman"` / `fc-list`;
- при отсутствии — установить допустимый пакет (`ttf-mscorefonts-installer`) **или** явно утвердить метрически совместимый fallback (Liberation Serif / Tinos) отдельным решением;
- не менять шрифт молча.

PDF должен встраивать/использовать серверный шрифт, чтобы результат не зависел от ПК кадровика.

---

## 6. Resource limits

| Параметр | Default | Env |
|---|---|---|
| Timeout | 30 s | `PERSONNEL_ORDER_PDF_TIMEOUT_MS` |
| Max concurrent | 2 | `PERSONNEL_ORDER_PDF_MAX_CONCURRENT` |
| Max response | 15 MiB | code constant |

Lifecycle:

- singleton Chromium browser process;
- новый browser context + page на запрос;
- гарантированный `page.close()` / `context.close()`;
- перезапуск browser после hard failure / timeout;
- слот-семафор против бесконтрольного параллелизма.

---

## 7. Deployment (VPS)

Сервис: `corpsite-frontend.service`, пользователь `ubuntu`.

Перед выкладкой:

1. `npm install` (зависимость `playwright`).
2. `npx playwright install chromium` (или `playwright install --with-deps chromium` на Linux).
3. Системные библиотеки Chromium (см. Playwright docs для Ubuntu).
4. Шрифты: Times New Roman или утверждённый fallback.
5. Оценить RAM: Chromium headless ≈ сотни МБ дополнительно; при необходимости добавить `MemoryMax` / лимиты в systemd.
6. Env (опционально): `BACKEND_URL=http://127.0.0.1:8000`, `PERSONNEL_ORDER_PDF_*`.

После deploy:

```bash
systemctl status corpsite-frontend.service
journalctl -u corpsite-frontend.service -n 100
ps aux | grep -E 'chromium|chrome'
```

Не запускать `sudo npm run build` вне принятого deploy-скрипта.

---

## 8. UI

Диалог языка:

- **Предпросмотр** → HTML `/print`
- **Открыть PDF** → официальный PDF

На HTML-toolbar:

- **PDF / Печать** — официальный канал;
- **Печать HTML** — браузерная печать предпросмотра;
- подсказка про колонтитулы браузера — только для HTML-сценария.

---

## 9. Watermark

| Статус | Watermark |
|---|---|
| DRAFT | ПРОЕКТ / ЖОБА |
| READY_FOR_SIGNATURE | НА ПОДПИСЬ / ҚОЛ ҚОЮҒА |
| SIGNED | нет |
| REGISTERED | нет |
| VOIDED | АННУЛИРОВАН / КҮШІ ЖОЙЫЛҒАН |

Watermark — часть PDF (`printBackground: true`), не зависит от viewer.

---

## 10. Future snapshot / hash / signature

MVP: PDF формируется динамически, **не** сохраняется в БД/архив.

Следующая фаза (вне WP):

```text
SIGNED / REGISTERED
  → frozen print snapshot
  → rendered PDF
  → SHA-256
  → immutable storage
  → digital signature
```

Хранение не привязывать к Route Handler — только к `PersonnelOrderPdfRenderer` + отдельный storage service.

---

## 11. Граница HTML preview vs official PDF

| | HTML `/print` | PDF `/pdf` |
|---|---|---|
| Назначение | экранный предпросмотр | официальный документ |
| Колонтитулы браузера | возможны при Print | отключены (`displayHeaderFooter: false`) |
| Auth | client Bearer → API | server Bearer → API |
| SoT | `PersonnelOrderPrintViewModel` | тот же |

---

## 12. Out of scope (WP)

ЭЦП, визирование, ознакомление в системе, сохранение PDF, immutable storage, хэш финального документа, QR/штрихкод, печать организации, изображение подписи, пакетная генерация, email, DOCX, физическое удаление.
