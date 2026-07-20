"""Complete Import Review — transition IN_REVIEW → APPLY_PENDING (ADR-038 Screen 5, ADR-059 Phase 1)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import (
    BATCH_STATUS_APPLIED,
    BATCH_STATUS_APPLY_PENDING,
    BATCH_STATUS_CANCELLED,
    BATCH_STATUS_FAILED,
    BATCH_STATUS_IN_REVIEW,
    BATCH_STATUS_PARSED,
    BATCH_STATUS_PARTIALLY_APPLIED,
    BATCH_STATUS_UPLOADED,
)
from app.services.hr_import_analytics_service import BatchNotFoundError
from app.services.hr_import_diff_removal_decision_service import count_pending_diff_removals
from app.services.hr_import_normalized_record_service import (
    REVIEW_STATUS_PENDING,
    normalized_records_available,
)
from app.services.hr_import_review_exception_service import (
    BLOCKER_UNRESOLVED_EXCEPTIONS,
    count_unresolved_exceptions,
)
from app.services.security_audit_service import write_security_event

EVENT_TYPE_IMPORT_REVIEW_COMPLETED = "HR_IMPORT_REVIEW_COMPLETED"

COMPLETE_REVIEW_ALLOWED_PRIOR_STATUSES = frozenset({BATCH_STATUS_IN_REVIEW})

COMPLETE_REVIEW_ALREADY_DONE_STATUSES = frozenset(
    {
        BATCH_STATUS_APPLY_PENDING,
        BATCH_STATUS_APPLIED,
        BATCH_STATUS_PARTIALLY_APPLIED,
    }
)

BLOCKER_BATCH_STATUS = "BATCH_STATUS"
BLOCKER_ERROR_ROWS = "ERROR_ROWS"
BLOCKER_PENDING_REMOVED_DECISIONS = "PENDING_REMOVED_DECISIONS"


class CompleteImportReviewError(RuntimeError):
    def __init__(self, message: str, *, blockers: Optional[list[dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.blockers = list(blockers or [])


def _blocker(
    *,
    code: str,
    message: str,
    batch_id: int,
    count: Optional[int] = None,
    resolve_kind: str,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code,
        "message": message,
        "batch_id": batch_id,
        "resolve_kind": resolve_kind,
    }
    if count is not None:
        item["count"] = count
    return item


def _load_batch_by_import_code(conn: Connection, import_code: str) -> dict[str, Any]:
    code = str(import_code or "").strip()
    if not code:
        raise BatchNotFoundError(import_code)
    row = conn.execute(
        text(
            """
            SELECT batch_id, import_code, status, error_rows
            FROM public.hr_import_batches
            WHERE import_code = :import_code
            """
        ),
        {"import_code": code},
    ).mappings().first()
    if row is None:
        raise BatchNotFoundError(import_code)
    return dict(row)


def _load_batch_by_id(conn: Connection, batch_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT batch_id, import_code, status, error_rows
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        raise BatchNotFoundError(batch_id)
    return dict(row)


def _count_pending_normalized(conn: Connection, batch_id: int) -> int:
    if not normalized_records_available(conn):
        return 0
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND review_status = :pending
                """
            ),
            {"batch_id": batch_id, "pending": REVIEW_STATUS_PENDING},
        ).scalar_one()
        or 0
    )


def build_review_progress(conn: Connection, batch: dict[str, Any]) -> dict[str, Any]:
    batch_id = int(batch["batch_id"])
    pending_normalized = _count_pending_normalized(conn, batch_id)
    unresolved_exceptions = count_unresolved_exceptions(conn, batch_id)
    error_rows = int(batch.get("error_rows") or 0)
    pending_removals = count_pending_diff_removals(conn, batch_id)
    status = str(batch.get("status") or "")
    already_completed = status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES
    ready = already_completed or (
        status == BATCH_STATUS_IN_REVIEW
        and unresolved_exceptions == 0
        and error_rows == 0
        and pending_removals == 0
    )
    return {
        "pending_normalized": pending_normalized,
        "unresolved_exceptions": unresolved_exceptions,
        "error_rows": error_rows,
        "pending_removals": pending_removals,
        "ready": ready,
    }


def _collect_review_queue_blockers(conn: Connection, batch: dict[str, Any]) -> list[dict[str, Any]]:
    """Blockers from review queues only (ignores batch-status gate)."""
    batch_id = int(batch["batch_id"])
    import_code = str(batch.get("import_code") or "").strip() or f"batch {batch_id}"
    blockers: list[dict[str, Any]] = []

    error_rows = int(batch.get("error_rows") or 0)
    if error_rows > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_ERROR_ROWS,
                message=f"Импорт {import_code} содержит {error_rows} строк с ошибками парсинга.",
                batch_id=batch_id,
                count=error_rows,
                resolve_kind="import_analytics",
            )
        )

    pending_removals = count_pending_diff_removals(conn, batch_id)
    if pending_removals > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_PENDING_REMOVED_DECISIONS,
                message=f"Импорт {import_code} содержит {pending_removals} removals без решения.",
                batch_id=batch_id,
                count=pending_removals,
                resolve_kind="removed_review",
            )
        )

    unresolved_exceptions = count_unresolved_exceptions(conn, batch_id)
    if unresolved_exceptions > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_UNRESOLVED_EXCEPTIONS,
                message=(
                    f"Импорт {import_code} содержит {unresolved_exceptions} "
                    "необработанных исключений review-by-exception."
                ),
                batch_id=batch_id,
                count=unresolved_exceptions,
                resolve_kind="hr_review",
            )
        )

    return blockers


def _collect_complete_review_blockers(conn: Connection, batch: dict[str, Any]) -> list[dict[str, Any]]:
    batch_id = int(batch["batch_id"])
    import_code = str(batch.get("import_code") or "").strip() or f"batch {batch_id}"
    status = str(batch.get("status") or "")
    blockers: list[dict[str, Any]] = []

    if status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES:
        return blockers

    if status not in COMPLETE_REVIEW_ALLOWED_PRIOR_STATUSES:
        if status == BATCH_STATUS_FAILED:
            msg = f"Импорт {import_code} завершился с ошибкой (FAILED). Повторите загрузку Excel."
        elif status == BATCH_STATUS_CANCELLED:
            msg = f"Импорт {import_code} архивирован (CANCELLED)."
        elif status in {BATCH_STATUS_UPLOADED, BATCH_STATUS_PARSED}:
            msg = (
                f"Импорт {import_code} ещё не готов к завершению проверки (статус {status}). "
                "Дождитесь окончания stage-import."
            )
        else:
            msg = (
                f"Импорт {import_code} имеет статус {status}. "
                "Завершение проверки доступно только для импортов в статусе IN_REVIEW."
            )
        blockers.append(
            _blocker(
                code=BLOCKER_BATCH_STATUS,
                message=msg,
                batch_id=batch_id,
                resolve_kind="import_list",
            )
        )
        return blockers

    error_rows = int(batch.get("error_rows") or 0)
    if error_rows > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_ERROR_ROWS,
                message=(
                    f"Импорт {import_code} содержит {error_rows} строк с ошибками парсинга. "
                    "Исправьте Excel и выполните повторный stage-import."
                ),
                batch_id=batch_id,
                count=error_rows,
                resolve_kind="import_analytics",
            )
        )

    pending_removals = count_pending_diff_removals(conn, batch_id)
    if pending_removals > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_PENDING_REMOVED_DECISIONS,
                message=(
                    f"Импорт {import_code} содержит {pending_removals} записей, "
                    "отсутствующих в новом файле без решения. "
                    "Выберите «Восстановить запись» или «Подтвердить удаление»."
                ),
                batch_id=batch_id,
                count=pending_removals,
                resolve_kind="removed_review",
            )
        )

    unresolved_exceptions = count_unresolved_exceptions(conn, batch_id)
    if unresolved_exceptions > 0:
        blockers.append(
            _blocker(
                code=BLOCKER_UNRESOLVED_EXCEPTIONS,
                message=(
                    f"Импорт {import_code} содержит {unresolved_exceptions} "
                    "необработанных исключений (CHANGED / CONFLICT / eligible NEW). "
                    "Подтвердите или отклоните их в HR review."
                ),
                batch_id=batch_id,
                count=unresolved_exceptions,
                resolve_kind="hr_review",
            )
        )

    return blockers


def assess_complete_import_review(conn: Connection, import_code: str) -> dict[str, Any]:
    """Return complete-review readiness (no writes)."""
    batch = _load_batch_by_import_code(conn, import_code)
    batch_id = int(batch["batch_id"])
    status = str(batch.get("status") or "")
    blockers = _collect_complete_review_blockers(conn, batch)
    already_completed = status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES
    complete_allowed = already_completed or not blockers
    review_progress = build_review_progress(conn, batch)
    return {
        "import_code": str(batch.get("import_code") or import_code),
        "batch_id": batch_id,
        "batch_status": status,
        "already_completed": already_completed,
        "complete_allowed": complete_allowed,
        "blockers": blockers,
        "review_progress": review_progress,
    }


def assess_import_review_progress_by_batch(conn: Connection, batch_id: int) -> dict[str, Any]:
    batch = _load_batch_by_id(conn, batch_id)
    assessment = assess_complete_import_review(conn, str(batch["import_code"]))
    return assessment


def _transition_batch_to_apply_pending(
    conn: Connection,
    *,
    batch_id: int,
    import_code: str,
    actor_user_id: int,
    trigger: str = "auto",
) -> dict[str, Any]:
    updated = conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET status = :target_status
            WHERE batch_id = :batch_id
              AND status = :source_status
            RETURNING batch_id, import_code, status
            """
        ),
        {
            "batch_id": batch_id,
            "target_status": BATCH_STATUS_APPLY_PENDING,
            "source_status": BATCH_STATUS_IN_REVIEW,
        },
    ).mappings().first()

    if updated is None:
        current = conn.execute(
            text(
                """
                SELECT batch_id, import_code, status
                FROM public.hr_import_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().one()
        current_status = str(current.get("status") or "")
        if current_status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES:
            return {
                "import_code": str(current.get("import_code") or import_code),
                "batch_id": batch_id,
                "batch_status": current_status,
                "completed": True,
                "already_completed": True,
                "blockers": [],
                "auto_completed": False,
            }
        blockers = _collect_complete_review_blockers(conn, dict(current))
        message = "Завершение проверки импорта заблокировано:\n" + "\n".join(
            f"- {item['message']}" for item in blockers
        )
        raise CompleteImportReviewError(message, blockers=blockers)

    write_security_event(
        event_type=EVENT_TYPE_IMPORT_REVIEW_COMPLETED,
        actor_user_id=int(actor_user_id),
        metadata={
            "batch_id": batch_id,
            "import_code": str(updated.get("import_code") or import_code),
            "previous_status": BATCH_STATUS_IN_REVIEW,
            "new_status": BATCH_STATUS_APPLY_PENDING,
            "trigger": trigger,
            "auto_completed": trigger == "auto",
        },
        conn=conn,
    )

    return {
        "import_code": str(updated.get("import_code") or import_code),
        "batch_id": batch_id,
        "batch_status": str(updated.get("status") or BATCH_STATUS_APPLY_PENDING),
        "completed": True,
        "already_completed": False,
        "blockers": [],
        "auto_completed": True,
    }


def maybe_auto_complete_import_review(
    conn: Connection,
    batch_id: int,
    *,
    actor_user_id: int,
) -> dict[str, Any]:
    """When all review blockers are cleared, idempotently move IN_REVIEW → APPLY_PENDING."""
    batch = _load_batch_by_id(conn, batch_id)
    status = str(batch.get("status") or "")
    import_code = str(batch.get("import_code") or "").strip()

    if status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES:
        return {
            "import_code": import_code,
            "batch_id": batch_id,
            "batch_status": status,
            "auto_completed": False,
            "already_completed": True,
            "blockers": [],
        }

    if status != BATCH_STATUS_IN_REVIEW:
        blockers = _collect_complete_review_blockers(conn, batch)
        return {
            "import_code": import_code,
            "batch_id": batch_id,
            "batch_status": status,
            "auto_completed": False,
            "already_completed": False,
            "blockers": blockers,
        }

    blockers = _collect_complete_review_blockers(conn, batch)
    if blockers:
        return {
            "import_code": import_code,
            "batch_id": batch_id,
            "batch_status": status,
            "auto_completed": False,
            "already_completed": False,
            "blockers": blockers,
        }

    return _transition_batch_to_apply_pending(
        conn,
        batch_id=batch_id,
        import_code=import_code,
        actor_user_id=actor_user_id,
    )


def maybe_reopen_import_review(
    conn: Connection,
    batch_id: int,
    *,
    actor_user_id: int,
) -> dict[str, Any]:
    """When review blockers reappear, move APPLY_PENDING → IN_REVIEW (e.g. after revert)."""
    batch = _load_batch_by_id(conn, batch_id)
    status = str(batch.get("status") or "")
    import_code = str(batch.get("import_code") or "").strip()

    if status != BATCH_STATUS_APPLY_PENDING:
        return {
            "import_code": import_code,
            "batch_id": batch_id,
            "batch_status": status,
            "reopened": False,
            "blockers": _collect_review_queue_blockers(conn, batch),
        }

    blockers = _collect_review_queue_blockers(conn, batch)
    if not blockers:
        return {
            "import_code": import_code,
            "batch_id": batch_id,
            "batch_status": status,
            "reopened": False,
            "blockers": [],
        }

    updated = conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET status = :target_status
            WHERE batch_id = :batch_id
              AND status = :source_status
            RETURNING batch_id, import_code, status
            """
        ),
        {
            "batch_id": batch_id,
            "target_status": BATCH_STATUS_IN_REVIEW,
            "source_status": BATCH_STATUS_APPLY_PENDING,
        },
    ).mappings().first()

    if updated is None:
        current = _load_batch_by_id(conn, batch_id)
        return {
            "import_code": str(current.get("import_code") or import_code),
            "batch_id": batch_id,
            "batch_status": str(current.get("status") or status),
            "reopened": False,
            "blockers": blockers,
        }

    write_security_event(
        event_type=EVENT_TYPE_IMPORT_REVIEW_COMPLETED,
        actor_user_id=int(actor_user_id),
        metadata={
            "batch_id": batch_id,
            "import_code": str(updated.get("import_code") or import_code),
            "previous_status": BATCH_STATUS_APPLY_PENDING,
            "new_status": BATCH_STATUS_IN_REVIEW,
            "trigger": "reopen",
        },
        conn=conn,
    )

    return {
        "import_code": str(updated.get("import_code") or import_code),
        "batch_id": batch_id,
        "batch_status": str(updated.get("status") or BATCH_STATUS_IN_REVIEW),
        "reopened": True,
        "blockers": blockers,
    }


def complete_import_review(
    conn: Connection,
    import_code: str,
    *,
    completed_by: int,
) -> dict[str, Any]:
    """Explicit complete-review (legacy/manual). Prefer maybe_auto_complete_import_review."""
    batch = _load_batch_by_import_code(conn, import_code)
    batch_id = int(batch["batch_id"])
    status = str(batch.get("status") or "")

    if status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES:
        return {
            "import_code": str(batch.get("import_code") or import_code),
            "batch_id": batch_id,
            "batch_status": status,
            "completed": True,
            "already_completed": True,
            "blockers": [],
            "auto_completed": False,
        }

    locked = conn.execute(
        text(
            """
            SELECT batch_id, import_code, status, error_rows
            FROM public.hr_import_batches
            WHERE import_code = :import_code
            FOR UPDATE
            """
        ),
        {"import_code": str(import_code).strip()},
    ).mappings().one()
    locked_batch = dict(locked)
    locked_status = str(locked_batch.get("status") or "")

    if locked_status in COMPLETE_REVIEW_ALREADY_DONE_STATUSES:
        return {
            "import_code": str(locked_batch.get("import_code") or import_code),
            "batch_id": int(locked_batch["batch_id"]),
            "batch_status": locked_status,
            "completed": True,
            "already_completed": True,
            "blockers": [],
            "auto_completed": False,
        }

    blockers = _collect_complete_review_blockers(conn, locked_batch)
    if blockers:
        message = "Завершение проверки импорта заблокировано:\n" + "\n".join(
            f"- {item['message']}" for item in blockers
        )
        raise CompleteImportReviewError(message, blockers=blockers)

    if locked_status != BATCH_STATUS_IN_REVIEW:
        blockers = _collect_complete_review_blockers(conn, locked_batch)
        message = "Завершение проверки импорта заблокировано:\n" + "\n".join(
            f"- {item['message']}" for item in blockers
        )
        raise CompleteImportReviewError(message, blockers=blockers)

    result = _transition_batch_to_apply_pending(
        conn,
        batch_id=int(locked_batch["batch_id"]),
        import_code=str(locked_batch.get("import_code") or import_code),
        actor_user_id=int(completed_by),
        trigger="manual",
    )
    result["auto_completed"] = False
    return result
