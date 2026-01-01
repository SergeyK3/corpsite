# -*- coding: utf-8 -*-

STATUS_LABELS_RU = {
    "WAITING_REPORT": "Получено и ожидается отчёт",
    "WAITING_APPROVAL": "Отчёт на проверке",
    "DONE": "Выполнено",
    "ARCHIVED": "В архиве",
}

NOTIFICATIONS_RU = {
    # Исполнителю: назначена задача, ожидается отчёт
    "WAITING_REPORT_ASSIGNEE": (
        "Вам назначена задача: «{task_title}».\n"
        "Статус: {status_label}.\n"
        "Необходимо подготовить и отправить отчёт в установленный срок."
    ),
    # Исполнителю: напоминание
    "WAITING_REPORT_REMINDER": (
        "Напоминание: по задаче «{task_title}» ожидается отчёт.\n"
        "Статус: {status_label}."
    ),

    # Руководителю/проверяющему: поступил отчёт, нужна проверка
    "WAITING_APPROVAL_APPROVER": (
        "Поступил отчёт по задаче «{task_title}».\n"
        "Требуется проверка и принятие решения."
    ),
    # Исполнителю: отчёт на проверке
    "WAITING_APPROVAL_ASSIGNEE": (
        "Отчёт по задаче «{task_title}» отправлен и находится на проверке."
    ),

    # Исполнителю: отчёт принят, задача закрыта
    "DONE_ASSIGNEE": (
        "Отчёт по задаче «{task_title}» принят.\n"
        "Задача выполнена."
    ),
    # Инициатору/руководителю (если нужно)
    "DONE_INITIATOR": (
        "Задача «{task_title}» завершена и закрыта."
    ),

    # Архивирование (по необходимости)
    "ARCHIVED_INFO": (
        "Задача «{task_title}» переведена в архив.\n"
        "Дальнейшие действия не требуются."
    ),

    # Событие: возврат на доработку (не статус)
    "RETURN_FOR_REWORK_ASSIGNEE": (
        "Отчёт по задаче «{task_title}» возвращён на доработку.\n"
        "Комментарий: {comment}"
    ),
}


def status_label(code: str) -> str:
    return STATUS_LABELS_RU.get(code, code)


def render(template_key: str, **kwargs) -> str:
    """
    Формирует текст уведомления.
    Ожидаемые поля (по необходимости): task_title, status_label, comment.
    """
    tpl = NOTIFICATIONS_RU.get(template_key)
    if not tpl:
        raise KeyError(f"Unknown template: {template_key}")

    # автоподстановка label, если передан status_code
    if "status_code" in kwargs and "status_label" not in kwargs:
        kwargs["status_label"] = status_label(kwargs["status_code"])

    return tpl.format(**kwargs)
