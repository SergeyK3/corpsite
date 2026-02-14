ADR-023 — RBAC v2: Lean RBAC (roles + dept scope + approvals fallback)
Status

Accepted

Context

В Corpsite реализованы:

FSM задач (report/approve/reject/archive)

события и доставки (task_events / task_event_deliveries) с backend как source of truth

Directory/Org Units и режимы RBAC (dept/groups/off)

Для масштабируемости и предсказуемости требуется закрепить RBAC-модель, отвечающую на три ключевых вопроса:

Кто видит задачу?

Кто может менять статус (actions)?

Кому уходят уведомления (recipients/deliveries)?

При этом модель должна:

работать сразу в реальной структуре “директор/замы/руководители/исполнители”

не превращаться в “enterprise-лабиринт”

оставаться расширяемой (новые роли, новые отделы, новые каналы доставки)

Decision

Принята модель Lean RBAC: минимальная по сущностям, строгая по принципам.

1) Роли и назначение задач

Инициатор задачи: initiator_user_id — конкретный пользователь (директор/зам/руководитель/и др.), который поставил задачу и является контролирующей стороной.

Исполнитель по умолчанию задаётся ролью, а не человеком: executor_role_id.

Это обеспечивает масштабируемость: смена сотрудников не ломает маршрутизацию задач.

Позднее допускается расширение до assignee_user_id (точечное назначение) без смены модели.

2) Approve/Reject: кто принимает отчёт

Базовое правило:

Primary approver: initiator_user_id (инициатор согласует/отклоняет результат).

Fallback-правило:

Fallback approver: руководитель (или уполномоченное лицо) в scope инициатора в зависимости от DIRECTORY_RBAC_MODE.

Override-правило:

Privileged override: пользователи/роли из DIRECTORY_PRIVILEGED_ROLE_IDS и/или DIRECTORY_PRIVILEGED_USER_IDS могут выполнять approve/reject в пределах заданного режима.

3) Visibility: кто видит задачу

По умолчанию задачу видят:

initiator_user_id

пользователи, соответствующие executor_role_id (исполнители по роли)

руководитель/уполномоченные лица в dept-scope инициатора (если включён DIRECTORY_RBAC_MODE=dept)

privileged пользователи/роли (override)

4) Assignment scope

Поле assignment_scope фиксируется как:

admin — административные задачи (орг/кадровые/регламентные/документооборот)

functional — производственные/профильные задачи (экспертиза/качество/отчёты/основные процессы)

assignment_scope влияет на:

видимость задач

маршрутизацию и набор доступных действий (can_* правила)

правила согласования (при необходимости)

5) События и уведомления

Уведомления по ключевым событиям (REPORT_SUBMITTED, APPROVED, REJECTED) формируются backend’ом и доставляются через delivery-queue.

Recipients базово включают:

инициатора

исполнителей (по роли / по назначению)

при необходимости — руководителя инициатора (dept-mode)

privileged (override, если требуется политикой)

Telegram-бот остаётся delivery-agent:

не формирует бизнес-события

не является источником истины

только доставляет pending deliveries и подтверждает статус доставки

Consequences
Плюсы

Модель сразу соответствует реальной структуре управления.

Масштабируется (смена исполнителей, добавление ролей, добавление каналов доставки).

Не требует “permission matrix” на сотни правил.

Единые принципы для backend/UI/notifications.

Минусы / ограничения

Требуется корректно поддерживать связи “руководитель ↔ подчинённые” (dept-scope).

В режиме groups/off fallback/visibility могут отличаться и должны быть явно описаны политикой режима.

Operational rules (summary)

initiator_user_id — владелец контроля, по умолчанию согласует результат.

executor_role_id — исполнение по роли (масштабируемо).

DIRECTORY_RBAC_MODE=dept включает dept-scope видимости/фолбэков.

DIRECTORY_PRIVILEGED_* дают override-способности.

assignment_scope разделяет admin vs functional.

Implementation checklist

Backend:

 can_report_or_update: разрешить репорт пользователям, подпадающим под executor_role_id (и/или assignee_user_id в будущем)

 can_approve / can_reject: инициатор + privileged + fallback (dept-scope инициатора)

 Query scoping: фильтрация задач по visibility-правилам

 События: recipients/deliveries формируются только backend’ом

UI:

 Показывать задачу только если она видима по backend-фильтру

 Действия (approve/reject/report/archive) показывать из allowed_actions

Config:

 DIRECTORY_RBAC_MODE (dept/groups/off)

 DIRECTORY_PRIVILEGED_ROLE_IDS

 DIRECTORY_PRIVILEGED_USER_IDS (опционально)

Notes / Future extensions

Добавление assignee_user_id как опции точечного назначения (не ломает модель).

Мульти-каналы доставок (Email, Push) поверх delivery-queue.

Расширение scope: dept + groups гибрид (если понадобится).

Next steps

Прогнать e2e сценарий с разными ролями (director → executor, deputy → supervisor и т.п.)

Зафиксировать режим DIRECTORY_RBAC_MODE=dept как дефолт для текущей организации

Довести правила can_* и фильтры directory/tasks до полного соответствия этому ADR