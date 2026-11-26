"""Permanently delete one unfinished electronic hire application and its DRAFT order."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


class ElectronicHireDeleteConflict(Exception):
    def __init__(self, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _locked_pair(conn: Connection, application_id: int) -> tuple[dict, dict | None]:
    app = conn.execute(text("""
        SELECT a.application_id, a.personnel_order_id, a.status, a.archived_at,
               COALESCE(CASE WHEN e.candidate_checked_at IS NULL AND e.preliminary_last_name IS NOT NULL
                        THEN CONCAT_WS(' ', e.preliminary_last_name, e.preliminary_first_name,
                                       NULLIF(e.preliminary_middle_name, '')) END,
                   p.full_name, e.preliminary_full_name) AS full_name
        FROM public.personnel_applications a
        JOIN public.electronic_hire_applications e USING (application_id)
        LEFT JOIN public.persons p ON p.person_id = a.person_id
        WHERE a.application_id=:id FOR UPDATE OF a, e
    """), {"id": application_id}).mappings().first()
    if app is None:
        raise ElectronicHireDeleteConflict("Заявление не найдено.", status_code=404)
    order = None
    if app["personnel_order_id"] is not None:
        order = conn.execute(text("""
            SELECT order_id, order_number, status, archived_at, deleted_at
            FROM public.personnel_orders WHERE order_id=:id FOR UPDATE
        """), {"id": app["personnel_order_id"]}).mappings().first()
        if order is None:
            raise ElectronicHireDeleteConflict("Связанный приказ не найден.")
    return dict(app), dict(order) if order else None


def _deletion_blocker(conn: Connection, app: dict, order: dict | None) -> str | None:
    application_id = int(app["application_id"])
    if app["archived_at"] is not None:
        return "Заявление уже находится в архиве и отсутствует в списке незавершённых."
    if app["status"] in {"completed", "cancelled", "withdrawn", "expired"}:
        return f"Заявление уже закрыто (статус {app['status']})."
    if conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.employee_onboardings WHERE application_id=:id)
    """), {"id": application_id}).scalar_one():
        return "По заявлению уже создано оформление сотрудника; удаление запрещено."
    if conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.personnel_intake_links other
          WHERE other.superseded_by_link_id IN
            (SELECT link_id FROM public.personnel_intake_links WHERE application_id=:id)
            AND other.application_id<>:id)
    """), {"id": application_id}).scalar_one():
        return "На ссылку кандидата ссылается другое заявление; удаление запрещено."
    if order is None:
        return None
    order_id = int(order["order_id"])
    if order["status"] != "DRAFT":
        return f"Связанный приказ ID {order_id} имеет статус {order['status']}; удаление запрещено."
    if order["archived_at"] is not None or order["deleted_at"] is not None:
        return f"Связанный приказ ID {order_id} уже удалён из рабочего списка."
    if conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.employee_events WHERE order_id=:id)
            OR EXISTS(SELECT 1 FROM public.personnel_order_lifecycle_audit
                      WHERE order_id=:id AND new_status IN ('SIGNED','REGISTERED'))
            OR EXISTS(SELECT 1 FROM public.personnel_order_acknowledgement_events WHERE order_id=:id)
    """), {"id": order_id}).scalar_one():
        return f"Приказ ID {order_id} уже подписывался или проводился; удаление запрещено."
    if conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.incoming_document_personnel_order_links
                      WHERE personnel_order_id=:id)
            OR EXISTS(SELECT 1 FROM public.personnel_applications
                      WHERE personnel_order_id=:id AND application_id<>:application_id)
    """), {"id": order_id, "application_id": application_id}).scalar_one():
        return f"Приказ ID {order_id} связан с другими документами; удаление запрещено."
    return None


def delete_preview(conn: Connection, application_id: int) -> dict:
    app, order = _locked_pair(conn, application_id)
    reason = _deletion_blocker(conn, app, order)
    return {
        "application_id": app["application_id"],
        "full_name": app["full_name"],
        "personnel_order_id": order["order_id"] if order else None,
        "order_number": order["order_number"] if order else None,
        "order_status": order["status"] if order else None,
        "can_delete": reason is None,
        "reason": reason,
    }


def delete_electronic_hire(conn: Connection, application_id: int) -> dict:
    """Delete application-owned rows and, when present, its draft order in one transaction.

    Caller owns the transaction. Foreign keys also fail closed if a new dependency
    is introduced without being included in this deletion plan.
    """
    preview = delete_preview(conn, application_id)
    if not preview["can_delete"]:
        raise ElectronicHireDeleteConflict(preview["reason"] or "Удаление заявления недоступно.")
    params = {"id": application_id}

    # Candidate links and intake data must go before the application. Removing
    # the link rows makes every previously issued public token unusable.
    for table in (
        "electronic_hire_link_deliveries",
        "personnel_intake_section_reviews",
        "personnel_intake_reconciliation_decisions",
        "personnel_intake_transfers",
        "personnel_intake_drafts",
    ):
        conn.execute(text(f"DELETE FROM public.{table} WHERE application_id=:id"), params)
    conn.execute(text("""
        UPDATE public.personnel_intake_links SET superseded_by_link_id=NULL
        WHERE application_id=:id
    """), params)
    conn.execute(text("DELETE FROM public.personnel_intake_links WHERE application_id=:id"), params)

    for table in (
        "electronic_hire_approval_tasks",
        "electronic_hire_notifications",
        "electronic_hire_paper_confirmations",
        "electronic_hire_position_requests",
        "electronic_hire_visas",
        "hire_approval_mode_audit",
        "electronic_hire_attachments",
    ):
        conn.execute(text(f"DELETE FROM public.{table} WHERE application_id=:id"), params)
    conn.execute(text("DELETE FROM public.electronic_hire_applications WHERE application_id=:id"), params)

    for table in (
        "personnel_application_lifecycle_audit",
        "personnel_application_resolution_audit",
        "personnel_application_blockers",
    ):
        conn.execute(text(f"DELETE FROM public.{table} WHERE application_id=:id"), params)
    deleted_app = conn.execute(text("DELETE FROM public.personnel_applications WHERE application_id=:id"), params)
    if deleted_app.rowcount != 1:
        raise ElectronicHireDeleteConflict("Заявление изменилось во время удаления.")

    order_id = preview["personnel_order_id"]
    if order_id is not None:
        order_params = {"id": order_id}
        # Existing physical draft deletion uses this transaction-local switch
        # for append-only template and audit rows.
        conn.execute(text("SELECT set_config('corpsite.allow_personnel_order_physical_delete', 'on', true)"))
        for table in ("personnel_order_item_bases", "personnel_order_item_editorial_blocks"):
            conn.execute(text(f"""
                DELETE FROM public.{table} WHERE order_item_id IN
                    (SELECT item_id FROM public.personnel_order_items WHERE order_id=:id)
            """), order_params)
        for table in (
            "personnel_order_template_applications",
            "personnel_order_attachments",
            "personnel_order_editorial_blocks",
            "personnel_order_evidence_scopes",
            "personnel_order_lifecycle_audit",
            "personnel_order_localized_texts",
            "personnel_order_prints",
        ):
            conn.execute(text(f"DELETE FROM public.{table} WHERE order_id=:id"), order_params)
        conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), order_params)
        deleted_order = conn.execute(text("""
            DELETE FROM public.personnel_orders WHERE order_id=:id AND status='DRAFT'
        """), order_params)
        if deleted_order.rowcount != 1:
            raise ElectronicHireDeleteConflict("Статус черновика изменился во время удаления.")
    return {**preview, "deleted": True}
