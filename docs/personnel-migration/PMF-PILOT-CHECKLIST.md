# PMF Pilot Checklist — Education Domain

## Метаданные

| Поле | Значение |
|------|----------|
| Документ | PMF-PILOT-CHECKLIST |
| Дата | 2026-07-08 |
| Pilot domain | `education` (education + training normalized records) |
| Связанный review | [PMF-PILOT-READINESS-REVIEW.md](./PMF-PILOT-READINESS-REVIEW.md) |

---

## A. Preconditions (до начала пилота)

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| A1 | PMF-3B API доступен (domains, draft, items, commit) | ☐ | Smoke на dev/stage |
| A2 | Education domain `is_enabled=true` | ☐ | Admin |
| A3 | Pilot employee имеет `employees.person_id` | ☐ | Иначе person blocker |
| A4 | HR operator имеет права migration | ☐ | 403 → forbidden panel |
| A5 | Normalized records approved + employee bound | ☐ | Review prerequisite |

---

## B. User Flow — Happy Path

| # | Шаг | Ожидаемый результат | Статус |
|---|-----|---------------------|--------|
| B1 | Открыть `/directory/personnel/import/review` | Список normalized records | ☐ |
| B2 | Утвердить запись + привязать сотрудника | `review_status=approved`, `employee_id` set | ☐ |
| B3 | CTA «Перенести в кадровую карточку» виден | Только approved+bound+education/training | ☐ |
| B4 | Переход по CTA | URL `/migration/education/{id}?candidate_id=…&source=review` | ☐ |
| B5 | Session bootstrap | Draft run создан/возобновлён без ручных действий HR | ☐ |
| B6 | Candidate auto-select | Запись из `candidate_id` выбрана | ☐ |
| B7 | Add item | Item в draft run; фаза Review Summary | ☐ |
| B8 | Stepper | «Проверка» активен; «Готово» disabled | ☐ |
| B9 | Review Summary | Сотрудник, домен, источник, запись, «Готово к переносу» | ☐ |
| B10 | CTA «Перенести в кадровую карточку» | Открывает confirm dialog | ☐ |
| B11 | Confirm commit | POST commit успешен | ☐ |
| B12 | Success state | «Запись перенесена»; stepper «Готово» | ☐ |
| B13 | Verify data | `person_education` / `person_training` row exists | ☐ |
| B14 | personnel_record_events | `EDUCATION_MIGRATED` event emitted | ☐ |

---

## C. User Flow — Alternate Paths

| # | Сценарий | Ожидаемый результат | Статус |
|---|----------|---------------------|--------|
| C1 | Session без `candidate_id` | Список кандидатов; ручной выбор | ☐ |
| C2 | Resume draft (sessionStorage) | Banner «Продолжение незавершённого переноса» | ☐ |
| C3 | Resume committed run | Info «уже зафиксирован» (не Success replay) | ☐ |
| C4 | Пустой список кандидатов | Сообщение + ссылка на Review | ☐ |
| C5 | Отмена confirm dialog | Остаёмся на Review Summary | ☐ |

---

## D. Error Flow

| # | Сценарий | HR UI (не raw) | Статус |
|---|----------|----------------|--------|
| D1 | Network error при bootstrap | Понятное сообщение + «Повторить» | ☐ |
| D2 | person_id missing | Person blocker panel | ☐ |
| D3 | 403 forbidden | «Недостаточно прав» | ☐ |
| D4 | Commit validation 422 | «Данные записи не готовы к переносу…» | ☐ |
| D5 | Double commit 409 | «Перенос уже был завершён…» | ☐ |
| D6 | Raw error только в Technical Details | `<details>` свёрнут | ☐ |

---

## E. UX & Terminology

| # | Проверка | Статус |
|---|----------|--------|
| E1 | Нет «Commit Engine», «Migration Run», «payload», «item» в primary UI | ☐ |
| E2 | Confirm dialog — HR текст о кадровой карточке | ☐ |
| E3 | Success — понятный итог без технических ID | ☐ |
| E4 | Technical Details свёрнуты по умолчанию | ☐ |
| E5 | Person blocker без «Person» в заголовке | ☐ |
| E6 | Source panel: «Ключ записи», не `candidate_id` | ☐ |

---

## F. Architecture Invariants

| # | Инвариант | Статус |
|---|-----------|--------|
| F1 | HR не создаёт Draft Run вручную | ☐ |
| F2 | Commit Engine — единственная точка записи в personnel | ☐ |
| F3 | Frontend не дублирует lifecycle/event model | ☐ |
| F4 | Backend/API/Schema не изменялись для pilot UI | ☐ |
| F5 | Review не пишет в `person_*` tables | ☐ |

---

## G. Known Limitations (accept for pilot)

| # | Ограничение | Accept |
|---|-------------|--------|
| G1 | Нет split-view field mapping | ☐ |
| G2 | Нет Education tab verify UI | ☐ |
| G3 | Migration Home employee picker disabled | ☐ |
| G4 | Нет History / Void / Supersede UI | ☐ |
| G5 | Verify через staff card или DB, не Education tab | ☐ |

---

## H. Sign-off

| Роль | Имя | Дата | Подпись |
|------|-----|------|---------|
| HR Pilot Lead | | | |
| Engineering | | | |
| Product / Architecture | | | |

**Pilot entry path (mandatory):** Import Review → CTA → Session → Commit → Success

**Pilot NOT via:** Migration Home employee picker (disabled)
