# app/errors.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class ErrorKind(str, Enum):
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class ApiErrorSpec:
    http_status: int
    error: ErrorKind
    message: str
    reason: str
    hint: str

    def payload(self, *, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "error": self.error.value,
            "message": self.message,
            "reason": self.reason,
            "hint": self.hint,
        }
        if extra:
            data.update(extra)
        return data

    def http_exc(self, *, extra: Optional[Dict[str, Any]] = None) -> HTTPException:
        return HTTPException(status_code=self.http_status, detail=self.payload(extra=extra))


class ErrorCode(str, Enum):
    # meta
    META_FORBIDDEN_NOT_BOUND = "META_FORBIDDEN_NOT_BOUND"

    # tasks: list/view
    TASKS_FORBIDDEN_LIST = "TASKS_FORBIDDEN_LIST"
    TASKS_CONFLICT_PERIOD_NOT_SELECTED = "TASKS_CONFLICT_PERIOD_NOT_SELECTED"
    TASK_FORBIDDEN_VIEW = "TASK_FORBIDDEN_VIEW"

    # tasks: create/update/delete
    TASK_FORBIDDEN_CREATE = "TASK_FORBIDDEN_CREATE"
    TASK_CONFLICT_CREATE_EXISTS = "TASK_CONFLICT_CREATE_EXISTS"
    TASK_FORBIDDEN_PATCH = "TASK_FORBIDDEN_PATCH"
    TASK_CONFLICT_PATCH_STATUS = "TASK_CONFLICT_PATCH_STATUS"
    TASK_FORBIDDEN_DELETE = "TASK_FORBIDDEN_DELETE"
    TASK_CONFLICT_DELETE_STATUS = "TASK_CONFLICT_DELETE_STATUS"

    # tasks: actions/report/approve
    TASK_FORBIDDEN_ACTION = "TASK_FORBIDDEN_ACTION"
    TASK_CONFLICT_ACTION_STATUS = "TASK_CONFLICT_ACTION_STATUS"
    TASK_FORBIDDEN_REPORT = "TASK_FORBIDDEN_REPORT"
    TASK_CONFLICT_REPORT_ALREADY_SENT = "TASK_CONFLICT_REPORT_ALREADY_SENT"
    TASK_FORBIDDEN_APPROVE = "TASK_FORBIDDEN_APPROVE"
    TASK_CONFLICT_APPROVE_NO_REPORT = "TASK_CONFLICT_APPROVE_NO_REPORT"

    # task events
    TASK_EVENTS_FORBIDDEN = "TASK_EVENTS_FORBIDDEN"

    # tg bind
    TGBIND_FORBIDDEN_NOT_AUTH = "TGBIND_FORBIDDEN_NOT_AUTH"
    TGBIND_CONFLICT_CODE_EXISTS = "TGBIND_CONFLICT_CODE_EXISTS"
    TGBIND_FORBIDDEN_CONSUME = "TGBIND_FORBIDDEN_CONSUME"
    TGBIND_CONFLICT_CODE_INVALID = "TGBIND_CONFLICT_CODE_INVALID"
    # tg bind (additional conflicts for users.telegram_id source of truth)
    TGBIND_CONFLICT_TG_ALREADY_BOUND = "TGBIND_CONFLICT_TG_ALREADY_BOUND"
    TGBIND_CONFLICT_USER_ALREADY_BOUND = "TGBIND_CONFLICT_USER_ALREADY_BOUND"

    # periods
    PERIODS_FORBIDDEN_LIST = "PERIODS_FORBIDDEN_LIST"
    PERIODS_FORBIDDEN_CREATE = "PERIODS_FORBIDDEN_CREATE"
    PERIODS_CONFLICT_EXISTS = "PERIODS_CONFLICT_EXISTS"
    PERIODS_FORBIDDEN_GENERATE_TASKS = "PERIODS_FORBIDDEN_GENERATE_TASKS"
    PERIODS_CONFLICT_TASKS_ALREADY_GENERATED = "PERIODS_CONFLICT_TASKS_ALREADY_GENERATED"


ERRORS: Dict[ErrorCode, ApiErrorSpec] = {
    # meta
    ErrorCode.META_FORBIDDEN_NOT_BOUND: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Доступ к справочнику статусов запрещён",
        reason="Пользователь не привязан к системе",
        hint="Выполните привязку аккаунта",
    ),
    # tasks list/view
    ErrorCode.TASKS_FORBIDDEN_LIST: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Просмотр задач запрещён",
        reason="Недостаточно прав для просмотра задач",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.TASKS_CONFLICT_PERIOD_NOT_SELECTED: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно получить список задач",
        reason="Отчётный период не выбран",
        hint="Выберите период и повторите запрос",
    ),
    ErrorCode.TASK_FORBIDDEN_VIEW: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Доступ к задаче запрещён",
        reason="Задача не относится к вашим полномочиям",
        hint="Запросите доступ у руководителя",
    ),
    # tasks create/patch/delete
    ErrorCode.TASK_FORBIDDEN_CREATE: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Создание задачи запрещено",
        reason="Создание задач доступно только руководителю",
        hint="Обратитесь к руководителю",
    ),
    ErrorCode.TASK_CONFLICT_CREATE_EXISTS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно создать задачу",
        reason="Задача для этого периода уже существует",
        hint="Проверьте существующие задачи",
    ),
    ErrorCode.TASK_FORBIDDEN_PATCH: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Изменение задачи запрещено",
        reason="У вас нет прав изменять эту задачу",
        hint="Обратитесь к руководителю",
    ),
    ErrorCode.TASK_CONFLICT_PATCH_STATUS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно изменить задачу",
        reason="Задача находится в статусе согласования или закрыта",
        hint="Завершите процесс или создайте новую задачу",
    ),
    ErrorCode.TASK_FORBIDDEN_DELETE: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Удаление задачи запрещено",
        reason="Удаление доступно только руководителю",
        hint="Обратитесь к руководителю",
    ),
    ErrorCode.TASK_CONFLICT_DELETE_STATUS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно удалить задачу",
        reason="Задача уже в работе или закрыта",
        hint="Удаление возможно только до начала выполнения",
    ),
    # task actions/report/approve
    ErrorCode.TASK_FORBIDDEN_ACTION: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Действие запрещено",
        reason="У вас нет прав выполнять это действие",
        hint="Проверьте свою роль",
    ),
    ErrorCode.TASK_CONFLICT_ACTION_STATUS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Действие невозможно",
        reason="Действие недопустимо в текущем статусе задачи",
        hint="Проверьте статус задачи",
    ),
    ErrorCode.TASK_FORBIDDEN_REPORT: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Отправка отчёта запрещена",
        reason="Отчёт может отправить только исполнитель задачи",
        hint="Проверьте назначение задачи",
    ),
    ErrorCode.TASK_CONFLICT_REPORT_ALREADY_SENT: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Отчёт уже отправлен",
        reason="Задача ожидает согласования",
        hint="Дождитесь решения руководителя",
    ),
    ErrorCode.TASK_FORBIDDEN_APPROVE: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Согласование запрещено",
        reason="Согласование доступно только руководителю",
        hint="Передайте задачу руководителю",
    ),
    ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно согласовать задачу",
        reason="Отчёт ещё не отправлен",
        hint="Дождитесь отчёта исполнителя",
    ),
    # task events
    ErrorCode.TASK_EVENTS_FORBIDDEN: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Доступ к событиям задачи запрещён",
        reason="У вас нет прав просматривать историю задачи",
        hint="Обратитесь к руководителю",
    ),
    # tg bind
    ErrorCode.TGBIND_FORBIDDEN_NOT_AUTH: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Создание кода привязки запрещено",
        reason="Пользователь не авторизован",
        hint="Выполните вход в систему",
    ),
    ErrorCode.TGBIND_CONFLICT_CODE_EXISTS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Код привязки уже создан",
        reason="Активный код ещё не использован",
        hint="Используйте существующий код",
    ),
    ErrorCode.TGBIND_FORBIDDEN_CONSUME: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Привязка запрещена",
        reason="Недостаточно прав для привязки",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.TGBIND_CONFLICT_CODE_INVALID: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно выполнить привязку",
        reason="Код недействителен или уже использован",
        hint="Создайте новый код привязки",
    ),
    ErrorCode.TGBIND_CONFLICT_TG_ALREADY_BOUND: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно выполнить привязку",
        reason="Этот Telegram уже привязан к другому пользователю",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.TGBIND_CONFLICT_USER_ALREADY_BOUND: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно выполнить привязку",
        reason="Этот пользователь уже привязан к другому Telegram",
        hint="Отвяжите старый Telegram и повторите привязку",
    ),
    # periods
    ErrorCode.PERIODS_FORBIDDEN_LIST: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Просмотр периодов запрещён",
        reason="Недостаточно прав для просмотра периодов",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.PERIODS_FORBIDDEN_CREATE: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Создание периода запрещено",
        reason="Создание периодов доступно только администратору",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.PERIODS_CONFLICT_EXISTS: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Период уже существует",
        reason="Период с такими датами уже создан",
        hint="Выберите другой диапазон дат",
    ),
    ErrorCode.PERIODS_FORBIDDEN_GENERATE_TASKS: ApiErrorSpec(
        http_status=status.HTTP_403_FORBIDDEN,
        error=ErrorKind.FORBIDDEN,
        message="Генерация задач запрещена",
        reason="Генерация доступна только администратору",
        hint="Обратитесь к администратору",
    ),
    ErrorCode.PERIODS_CONFLICT_TASKS_ALREADY_GENERATED: ApiErrorSpec(
        http_status=status.HTTP_409_CONFLICT,
        error=ErrorKind.CONFLICT,
        message="Невозможно сгенерировать задачи",
        reason="Задачи для этого периода уже созданы",
        hint="Проверьте список задач периода",
    ),
}


def raise_error(code: ErrorCode, *, extra: Optional[Dict[str, Any]] = None) -> None:
    """
    Raise HTTPException with a stable, UX-focused error contract.

    extra: optional fields to include into payload (e.g., task_id, current_status, allowed_actions, etc.)
    """
    spec = ERRORS.get(code)
    if spec is None:
        # Fail-safe: keep contract shape even if code missing
        fallback = ApiErrorSpec(
            http_status=status.HTTP_409_CONFLICT,
            error=ErrorKind.CONFLICT,
            message="Действие невозможно",
            reason="Непредвиденное состояние",
            hint="Повторите попытку позже",
        )
        raise fallback.http_exc(extra={"code": code.value, **(extra or {})})

    payload_extra = {"code": code.value}
    if extra:
        payload_extra.update(extra)
    raise spec.http_exc(extra=payload_extra)


def error_payload(code: ErrorCode, *, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build a payload without raising (useful for tests or non-exception flows).
    """
    spec = ERRORS.get(code)
    if spec is None:
        data = {
            "error": ErrorKind.CONFLICT.value,
            "message": "Действие невозможно",
            "reason": "Непредвиденное состояние",
            "hint": "Повторите попытку позже",
            "code": code.value,
        }
        if extra:
            data.update(extra)
        return data

    data = spec.payload(extra={"code": code.value, **(extra or {})})
    return data
