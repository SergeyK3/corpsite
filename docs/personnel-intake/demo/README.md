# PIF-2B — Demo Prototype: Анкета нового сотрудника

Демонстрационный HTML-прототип электронной анкеты для оформления на работу.

| Field | Value |
|-------|-------|
| Work package | PIF-2B |
| UX specification | [PIF-2A-electronic-intake-ux-specification.md](../PIF-2A-electronic-intake-ux-specification.md) |
| Type | Static demo — **not** production UI |
| Production | `corpsite-ui` — 9 шагов, preview-PDF на «Проверке»; фото **3×4 см** в PDF (см. [PIF-2A §1.4](../PIF-2A-electronic-intake-ux-specification.md#14-production-vs-this-specification)) |

---

## Быстрый старт

1. Откройте файл **`index.html`** в любом современном браузере (Chrome, Edge, Firefox).
2. Никаких зависимостей, сборки и сервера **не требуется**.

```text
docs/personnel-intake/demo/index.html  →  двойной щелчок или «Open with browser»
```

---

## Файлы

| File | Purpose |
|------|---------|
| `index.html` | Shell layout |
| `styles.css` | Corpsite-inspired light corporate theme |
| `app.js` | Wizard logic, validation, cards |
| `README.md` | This file |

---

## Demo navigation (optional)

For HR presentation you can jump to a step via URL hash:

```text
index.html#step=4   → Образование
index.html#step=10  → Проверка заполнения
index.html#step=11  → Анкета отправлена
```

Or in browser console: `pifGoToStep(4)`

---

## Быстрое заполнение для показа

Кнопка **«Заполнить демо-данными»** в верхней панели загружает тестовые данные во все основные поля (включая прикреплённые документы-заглушки). Это позволяет за минуту дойти до экранов «Проверка заполнения» и «Анкета отправлена» на встрече с отделом кадров.

Кнопка явно оформлена как demo-only и не предназначена для production.

---

## Сценарий demo для HR

1. Нажать **«Заполнить демо-данными»** (или заполнить вручную)
2. **Начало** → «Начать заполнение»
3. Пройти шаги 1–9 (или сразу перейти к проверке через hash `#step=10`)
4. **Проверка заполнения** → «Отправить в отдел кадров»
5. **Анкета отправлена** — при необходимости «Скачать лист предложений» для обратной связи от HR

Данные хранятся только в памяти браузера до перезагрузки страницы.

---

## Валидация (demo)

- Обязательные поля на текущем шаге
- ИИН — 12 цифр
- Email — формат (если заполнен)
- Телефон — минимум 10 цифр
- Блокировка «Далее» при ошибках на шаге
- На экране проверки — список незаполненных полей и блокировка отправки

---

## Ограничения

- Нет сервера и сохранения на диск — только демонстрация в браузере
- Не часть `corpsite-ui`
- HR-side экраны не реализованы
