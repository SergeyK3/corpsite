"""Scoped, in-app rehearsal of the electronic-hire path.

Every mutation resolves the application from an owned first-lesson attempt.
No caller-supplied personnel ID or external address is accepted.  The normal
personnel services still enforce their business gates.
"""
from __future__ import annotations

import json
import os
import re
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, insert, select, text

from app.db.engine import engine
from app.learning import expert_service, hire_path_link, service
from app.learning.hire_path import STEP_BY_CODE
from app.learning.model import (
    attempts, hire_acknowledgements, hire_applications, hire_messages,
    hire_recipients, hire_signatures, hire_step_links,
)
from app.personnel_applications.application.electronic_hire_service import (
    load_electronic_hire, mark_candidate_checked, missing_card_fields,
    record_visa, resolve_unit_head,
)
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application.application_apply_service import orchestrate_hire_apply_for_application
from app.personnel_intake.application.hr_link_access_service import get_hr_intake_link_display
from app.personnel_intake.application.intake_service import issue_intake_link
from app.personnel_intake.application.review_service import (
    accept_intake_section, load_intake_review_state, skip_intake_section,
)
from app.personnel_intake.application.transfer_service import transfer_intake_to_ppr
from app.personnel_intake.domain.review_status import INTAKE_REVIEW_SECTIONS
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository
from app.services.personnel_orders_command_service import (
    mark_personnel_order_ready_for_signature, register_personnel_order_tx,
    update_personnel_order_draft,
)
from app.services.personnel_orders_editorial_service import generate_editorial, get_editorial_state, patch_editorial_block
from app.services.personnel_orders_query_service import get_personnel_order


def require_rehearsal(user: dict, *roles: str) -> None:
    database = engine.url.database or ""
    isolated_database = database == "corpsite_learn" or (
        database.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1")
    if (not user.get("training_enabled") or not isolated_database
            or os.getenv("TRAINING_SERVER_ENABLED") != "1"
            or os.getenv("HIRE_PATH_REHEARSAL") != "1"):
        raise HTTPException(503, "Учебный маршрут недоступен в этом экземпляре")
    if user.get("role_code") not in roles:
        raise HTTPException(403, "Недостаточно прав для учебного действия")


def _root(conn, user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    attempt = service.owned_attempt(conn, user, root_attempt_id)
    link = conn.execute(select(hire_applications).where(
        hire_applications.c.attempt_id == root_attempt_id)).mappings().first()
    if link is None or attempt["lesson_code"] in STEP_BY_CODE:
        raise HTTPException(404, "Заявление занятия 1 не найдено")
    app = load_electronic_hire(conn, int(link["application_id"]))
    if int(app["person_id"]) != int(link["person_id"]):
        raise HTTPException(409, "Нарушена связь учебного заявления")
    return {"attempt": attempt, "link": link, "application": app}


def _step(conn, root_attempt_id: str, step: int) -> dict:
    row = conn.execute(select(hire_step_links, attempts.c.status, attempts.c.lesson_code)
        .join(attempts, attempts.c.id == hire_step_links.c.attempt_id)
        .where(and_(hire_step_links.c.root_attempt_id == root_attempt_id,
                    hire_step_links.c.step == step))
        .order_by(attempts.c.created_at.desc())).mappings().first()
    if row is None:
        raise HTTPException(409, f"Сначала начните занятие {step}")
    return dict(row)


def validate_step_submission(conn, user: dict, attempt_id: str) -> None:
    """Require the saved business result before screenshots can be submitted."""
    require_rehearsal(user, "LEARN_HR")
    link = conn.execute(select(hire_step_links).where(
        hire_step_links.c.attempt_id == attempt_id)).mappings().first()
    if link is None:
        raise HTTPException(404, "Занятие маршрута не найдено")
    root_id, step = link["root_attempt_id"], int(link["step"])
    root = _root(conn, user, root_id)
    app = root["application"]
    if step == 2:
        recipient = conn.execute(select(hire_recipients).where(
            hire_recipients.c.root_attempt_id == root_id)).mappings().first()
        notice = conn.execute(select(hire_messages.c.id).where(and_(
            hire_messages.c.root_attempt_id == root_id,
            hire_messages.c.kind == "intake_link"))).scalar_one_or_none()
        transfer = SqlAlchemyPersonnelIntakeReviewRepository(conn).get_transfer(int(app["application_id"]))
        if (not recipient or not notice or not transfer
                or transfer.status != "completed" or not app["candidate_checked_at"]
                or missing_card_fields(conn, int(app["person_id"]), int(app["application_id"]))):
            raise HTTPException(422, "Сначала получите заполненную карточку кандидата и подтвердите её проверку")
    elif step == 3:
        order = _order_row(conn, app)
        editorial = get_editorial_state(int(order["order_id"]))
        blocks = [block for item in editorial.get("items", [])
                  for block in item.get("blocks", []) if block.get("block_type") == "body"]
        locales = {block.get("locale") for block in blocks if (block.get("effective_text") or "").strip()}
        if not {"ru", "kk"}.issubset(locales):
            raise HTTPException(422, "Сначала сформируйте и проверьте русский и казахский тексты приказа")
    elif step == 4:
        order = _order_row(conn, app)
        signature = conn.execute(select(hire_signatures).where(
            hire_signatures.c.root_attempt_id == root_id)).mappings().first()
        if (order["status"] != "REGISTERED" or not order["order_number"]
                or not order["order_date"] or not signature
                or int(signature["order_id"]) != int(order["order_id"])):
            raise HTTPException(422, "Сначала подпишите и зарегистрируйте связанный приказ с номером и датой")
    elif step == 5:
        order = _order_row(conn, app)
        notice = conn.execute(select(hire_messages).where(and_(
            hire_messages.c.root_attempt_id == root_id,
            hire_messages.c.kind == "order_notice"))).mappings().first()
        acknowledgement = conn.execute(select(hire_acknowledgements).where(
            hire_acknowledgements.c.root_attempt_id == root_id)).mappings().first()
        if (order["status"] != "REGISTERED" or not notice or not acknowledgement
                or int(notice["order_id"]) != int(order["order_id"])
                or int(acknowledgement["order_id"]) != int(order["order_id"])):
            raise HTTPException(422, "Сначала отправьте учебное уведомление и получите отдельное ознакомление")


def roots(conn, user: dict) -> dict:
    require_rehearsal(user, "LEARN_HR")
    rows = conn.execute(select(hire_applications.c.attempt_id, hire_applications.c.application_id,
                               attempts.c.attempt_no, attempts.c.created_at)
        .join(attempts, attempts.c.id == hire_applications.c.attempt_id)
        .where(and_(attempts.c.participant_id == int(user["user_id"]),
                    attempts.c.unit_id == service.unit(user)))
        .order_by(attempts.c.created_at.desc())).mappings().all()
    return {"items": [{"root_attempt_id": r["attempt_id"], "application_id": r["application_id"],
                       "attempt_no": r["attempt_no"], "created_at": r["created_at"].isoformat()}
                      for r in rows]}


def start_step(conn, user: dict, root_attempt_id: str, lesson_code: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    step = STEP_BY_CODE.get(lesson_code)
    if step is None:
        raise HTTPException(404, "Неизвестное занятие маршрута")
    requirement = _start_requirement(conn, root_attempt_id, root["application"], step)
    if not requirement["ready"]:
        raise HTTPException(409, requirement["reason"])
    app = root["application"]
    if step >= 3:
        if missing_card_fields(conn, int(app["person_id"]), int(app["application_id"])) or not app["candidate_checked_at"]:
            raise HTTPException(409, "Сначала проверьте и подтвердите личную карточку в занятии 2")
    if step >= 4 and app["personnel_order_id"] is None:
        raise HTTPException(409, "Сначала создайте проект приказа в занятии 3")
    if step >= 5:
        order = _order_row(conn, app)
        if order["status"] != "REGISTERED":
            raise HTTPException(409, "Сначала зарегистрируйте приказ в занятии 4")
    previous = conn.execute(select(hire_step_links.c.attempt_id, attempts.c.status, attempts.c.attempt_no)
        .join(attempts, attempts.c.id == hire_step_links.c.attempt_id)
        .where(and_(hire_step_links.c.root_attempt_id == root_attempt_id,
                    hire_step_links.c.step == step))
        .order_by(attempts.c.created_at.desc())).mappings().first()
    if previous and previous["status"] == "draft":
        return {"id": previous["attempt_id"], "attempt_no": previous["attempt_no"], "status": "draft"}
    if previous and previous["status"] == "manual_review":
        raise HTTPException(409, "Предыдущая попытка ожидает проверки")
    lesson = next((item for item in expert_service.assigned_lessons(
        conn, int(user["user_id"]), service.unit(user), user.get("role_code"))
        if item["code"] == lesson_code), None)
    if lesson is None:
        raise HTTPException(404, "Учебное занятие не назначено")
    record = service.record_action(conn, user, f"LEARN-HIRE-{app['application_id']}", "submitted")
    attempt_id = str(uuid4())
    # Attempt numbers are unique per participant, unit and lesson across all
    # source applications. A new candidate starts a new root, not a new counter.
    last_no = conn.execute(select(func.max(attempts.c.attempt_no)).where(and_(
        attempts.c.participant_id == int(user["user_id"]),
        attempts.c.unit_id == service.unit(user),
        attempts.c.lesson_code == lesson_code))).scalar_one()
    attempt_no = int(last_no or 0) + 1
    conn.execute(insert(attempts).values(
        id=attempt_id, participant_id=int(user["user_id"]), unit_id=service.unit(user),
        lesson_code=lesson_code, record_id=record["id"], attempt_no=attempt_no,
        status="draft", lesson_snapshot_json=json.dumps(lesson, ensure_ascii=False)))
    conn.execute(insert(hire_step_links).values(attempt_id=attempt_id,
        root_attempt_id=root_attempt_id, step=step))
    return {"id": attempt_id, "attempt_no": attempt_no, "status": "draft"}


def _order_row(conn, app: dict) -> dict:
    order_id = app["personnel_order_id"]
    if order_id is None:
        raise HTTPException(409, "Связанный приказ ещё не создан")
    row = conn.execute(text("""
        SELECT order_id, order_number, order_date, status, signed_by_employee_id
        FROM public.personnel_orders WHERE order_id=:id AND deleted_at IS NULL
    """), {"id": int(order_id)}).mappings().first()
    if row is None:
        raise HTTPException(409, "Связанный приказ недоступен")
    return dict(row)


def _start_requirement(conn, root_attempt_id: str, app: dict, step: int,
                       intake_state: str | None = None) -> dict:
    """Explain the same saved-record gates enforced when a stage is started."""
    ready = {"ready": True, "reason": None, "return_to_step": None,
             "requires_submission": False, "requires_pass": False}
    if step <= 2:
        return ready
    previous = conn.execute(select(hire_step_links.c.attempt_id).where(and_(
        hire_step_links.c.root_attempt_id == root_attempt_id,
        hire_step_links.c.step == step - 1))).first()
    if previous is None:
        return {**ready, "ready": False, "reason": f"Сначала начните этап {step - 1}.",
                "return_to_step": step - 1}
    missing = missing_card_fields(conn, int(app["person_id"]), int(app["application_id"]))
    if step >= 3 and (missing or not app["candidate_checked_at"]):
        if intake_state is None:
            intake_state = get_hr_intake_link_display(conn, int(app["application_id"])).display_state
        if intake_state in {"not_issued", "reissue_required", "revoked", "expired"}:
            reason = "На этапе 2 выдайте кандидату ссылку на анкету."
        elif intake_state != "submitted":
            reason = "Кандидат ещё не отправил анкету. Вернитесь на этап 2 и передайте ему ссылку."
        elif missing:
            reason = "Анкета отправлена, но личная карточка ещё не заполнена: проверьте разделы и перенесите данные на этапе 2."
        else:
            reason = "Личная карточка заполнена. Подтвердите её проверку кадровиком на этапе 2."
        return {**ready, "ready": False, "reason": reason, "return_to_step": 2}
    if step >= 4 and app["personnel_order_id"] is None:
        return {**ready, "ready": False,
                "reason": "На этапе 3 создайте проект приказа из проверенного заявления.",
                "return_to_step": 3}
    if step >= 5 and _order_row(conn, app)["status"] != "REGISTERED":
        return {**ready, "ready": False,
                "reason": "На этапе 4 подпишите и зарегистрируйте приказ с номером и датой.",
                "return_to_step": 4}
    return ready


def state(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    linked = hire_path_link.linked_records(conn, user, root_attempt_id)
    app = root["application"]
    recipient = conn.execute(select(hire_recipients).where(
        hire_recipients.c.root_attempt_id == root_attempt_id)).mappings().first()
    step_rows = conn.execute(select(hire_step_links.c.step, hire_step_links.c.attempt_id,
                                    attempts.c.status, attempts.c.attempt_no,
                                    attempts.c.score, attempts.c.review_source)
        .join(attempts, attempts.c.id == hire_step_links.c.attempt_id)
        .where(hire_step_links.c.root_attempt_id == root_attempt_id)
        .order_by(hire_step_links.c.step, attempts.c.created_at, attempts.c.id)).mappings().all()
    messages = conn.execute(select(hire_messages.c.kind, hire_messages.c.created_at)
        .where(hire_messages.c.root_attempt_id == root_attempt_id)
        .order_by(hire_messages.c.created_at)).mappings().all()
    signature = conn.execute(select(hire_signatures).where(
        hire_signatures.c.root_attempt_id == root_attempt_id)).mappings().first()
    acknowledgement = conn.execute(select(hire_acknowledgements).where(
        hire_acknowledgements.c.root_attempt_id == root_attempt_id)).mappings().first()
    link_display = get_hr_intake_link_display(conn, int(app["application_id"]))
    result = {**linked,
              "source_attempt": {"status": root["attempt"]["status"], "score": root["attempt"]["score"],
                                 "review_source": root["attempt"]["review_source"]},
              "intake_link": {"status": link_display.display_state,
                              "url_path": link_display.intake_url_path if link_display.display_state in {"active", "submitted"} else None,
                              "expires_at": link_display.expires_at.isoformat() if link_display.expires_at else None},
              "steps": [{"step": r["step"], "attempt_id": r["attempt_id"],
                          "status": r["status"], "attempt_no": r["attempt_no"],
                          "score": r["score"], "review_source": r["review_source"]} for r in step_rows],
              "messages": [{"kind": r["kind"], "at": r["created_at"].isoformat()} for r in messages],
              "candidate_login": _candidate_login(conn, recipient["candidate_user_id"]) if recipient else None,
              "employee_id": recipient["employee_id"] if recipient else None,
              "signed_at": signature["signed_at"].isoformat() if signature else None,
              "acknowledgement": {"method": acknowledgement["method"], "evidence": acknowledgement["evidence"],
                                  "at": acknowledgement["acknowledged_at"].isoformat()} if acknowledgement else None}
    result["start_requirements"] = {str(step): _start_requirement(
        conn, root_attempt_id, app, step, link_display.display_state) for step in range(2, 6)}
    if app["personnel_order_id"] is not None:
        result["numbering"] = numbering(conn, int(app["personnel_order_id"]))
    return result


def _candidate_login(conn, user_id: int) -> str:
    return str(conn.execute(text("SELECT login FROM public.users WHERE user_id=:id"), {"id": user_id}).scalar_one())


def issue_link(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 2)
    login = {"learn.hr.a": "learn.candidate.a", "learn.hr.b": "learn.candidate.b"}.get(user.get("login"))
    if login is None:
        raise HTTPException(403, "Для кадровика не назначен учебный кандидат")
    candidate = conn.execute(text("SELECT user_id FROM public.users WHERE login=:login AND is_active"),
                             {"login": login}).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(409, "Учебная учётная запись кандидата не подготовлена")
    recipient = conn.execute(select(hire_recipients).where(
        hire_recipients.c.root_attempt_id == root_attempt_id)).mappings().first()
    if recipient and int(recipient["candidate_user_id"]) != int(candidate):
        raise HTTPException(409, "Кандидат уже закреплён за заявлением")
    if not recipient:
        conn.execute(insert(hire_recipients).values(root_attempt_id=root_attempt_id,
                                                    candidate_user_id=int(candidate)))
    display = get_hr_intake_link_display(conn, int(root["application"]["application_id"]))
    if display.display_state == "submitted":
        raise HTTPException(409, "Анкета уже отправлена кандидатом")
    if display.display_state == "active" and display.link_id:
        link_id = int(display.link_id)
        url_path = display.intake_url_path
        expires_at = display.expires_at
    else:
        result = issue_intake_link(conn, application_id=int(root["application"]["application_id"]),
                                   issued_by_user_id=int(user["user_id"]),
                                   reissue=display.link_id is not None)
        link_id = int(result.link_id)
        url_path = result.intake_url_path
        expires_at = result.expires_at
    prior = conn.execute(select(hire_messages.c.id).where(and_(
        hire_messages.c.root_attempt_id == root_attempt_id,
        hire_messages.c.kind == "intake_link", hire_messages.c.link_id == link_id))).scalar_one_or_none()
    if prior is None:
        conn.execute(insert(hire_messages).values(id=str(uuid4()), root_attempt_id=root_attempt_id,
            recipient_user_id=int(candidate), kind="intake_link", link_id=link_id,
            created_by_user_id=int(user["user_id"])))
    return {"application_id": int(root["application"]["application_id"]), "link_id": link_id,
            "recipient_login": login, "delivered_in_training_inbox": True,
            "intake_url_path": url_path,
            "expires_at": expires_at.isoformat() if expires_at else None}


def review_state(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 2)
    review = load_intake_review_state(conn, int(root["application"]["application_id"]))
    return {"sections": [{"code": s.section_code, "status": s.status} for s in review.sections],
            "can_transfer": review.can_transfer,
            "blocked_reason": review.transfer_blocked_reason,
            "draft_status": review.draft.status,
            "payload": review.draft.payload}


def review_section(conn, user: dict, root_attempt_id: str, section: str, decision: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 2)
    if section not in INTAKE_REVIEW_SECTIONS or decision not in {"accept", "skip"}:
        raise HTTPException(422, "Неизвестный раздел или решение")
    kwargs = {"application_id": int(root["application"]["application_id"]),
              "section_code": section, "reviewed_by_user_id": int(user["user_id"])}
    result = accept_intake_section(conn, **kwargs) if decision == "accept" else skip_intake_section(conn, **kwargs)
    return {"section": section, "status": result.section.status, "can_transfer": result.review_state.can_transfer}


def transfer_card(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 2)
    result = transfer_intake_to_ppr(conn, application_id=int(root["application"]["application_id"]),
                                    transferred_by_user_id=int(user["user_id"]),
                                    actor_id=f"user:{user['user_id']}")
    return {"application_id": result.application_id, "idempotent_replay": result.idempotent_replay,
            "status": result.transfer.status}


def check_card(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 2)
    app = root["application"]
    missing = missing_card_fields(conn, int(app["person_id"]), int(app["application_id"]))
    if missing:
        raise HTTPException(422, {"code": "PERSONAL_CARD_INCOMPLETE", "missing_fields": missing})
    mark_candidate_checked(conn, int(app["application_id"]), int(user["user_id"]))
    return {"candidate_checked": True, "application_id": int(app["application_id"])}


def draft_order(conn, user: dict, root_attempt_id: str) -> dict:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, 3)
    app = root["application"]
    if missing_card_fields(conn, int(app["person_id"]), int(app["application_id"])) or not app["candidate_checked_at"]:
        raise HTTPException(409, "Личная карточка не проверена")
    result = create_hire_order_draft_for_application(conn, application_id=int(app["application_id"]),
                                                       created_by_user_id=int(user["user_id"]))
    return {"application_id": result.application_id, "order_id": result.personnel_order_id,
            "idempotent_replay": result.idempotent_replay}


def configure_signatory(user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    with engine.connect() as conn:
        _, order = _linked_order(conn, user, root_attempt_id, 3)
        signatory = conn.execute(text("""
            SELECT u.employee_id,u.full_name,p.name AS position_name
            FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id
            JOIN public.positions p ON p.position_id=e.position_id
            WHERE u.login='learn.signatory' AND u.is_active AND e.is_active
        """)).mappings().first()
    if signatory is None:
        raise HTTPException(409, "Учебный подписант не подготовлен")
    if order["signed_by_employee_id"] == int(signatory["employee_id"]):
        return {"order_id": int(order["order_id"]), "signatory": signatory["full_name"]}
    if order["status"] != "DRAFT":
        raise HTTPException(409, "Подписанта можно назначить только в проекте")
    update_personnel_order_draft(order_id=int(order["order_id"]),
        signed_by_employee_id=int(signatory["employee_id"]),
        signed_by_name=str(signatory["full_name"]),
        signed_by_position=str(signatory["position_name"]))
    return {"order_id": int(order["order_id"]), "signatory": signatory["full_name"]}


def numbering(conn, order_id: int) -> dict:
    order = conn.execute(text("SELECT order_date,order_number FROM public.personnel_orders WHERE order_id=:id"),
                         {"id": order_id}).mappings().one()
    year = int(order["order_date"].year)
    rows = conn.execute(text("""
        SELECT order_number,order_date,status FROM public.personnel_orders
        WHERE EXTRACT(YEAR FROM order_date)=:year AND deleted_at IS NULL
          AND order_number IS NOT NULL AND BTRIM(order_number)<>'' AND order_id<>:id
        ORDER BY order_date DESC,order_id DESC
    """), {"year": year, "id": order_id}).mappings().all()
    registered = next((r for r in rows if r["status"] == "REGISTERED"), None)
    numeric = [int(match.group(1)) for r in rows
               if (match := re.fullmatch(r"(\d+)(?:/\d+)?", str(r["order_number"]).strip()))]
    suggestion = str(max(numeric, default=0) + 1)
    return {"year": year, "last_registered_number": registered["order_number"] if registered else None,
            "last_registered_date": registered["order_date"].isoformat() if registered else None,
            "suggested_number": suggestion, "current_number": order["order_number"]}


def _linked_order(conn, user: dict, root_attempt_id: str, step: int) -> tuple[dict, dict]:
    root = _root(conn, user, root_attempt_id)
    _step(conn, root_attempt_id, step)
    return root, _order_row(conn, root["application"])


def order_detail(conn, user: dict, root_attempt_id: str) -> dict:
    _, order = _linked_order(conn, user, root_attempt_id, 3)
    return {"detail": get_personnel_order(int(order["order_id"])),
            "editorial": get_editorial_state(int(order["order_id"]))}


def approve_as_head(conn, user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "TRAINING_HEAD_LOCAL")
    row = conn.execute(select(hire_applications.c.application_id)
        .where(hire_applications.c.attempt_id == root_attempt_id)).first()
    if row is None:
        raise HTTPException(404, "Учебное заявление не найдено")
    app = load_electronic_hire(conn, int(row.application_id))
    if app["personnel_order_id"] is None or resolve_unit_head(conn, int(app["intended_org_unit_id"])) != int(user["user_id"]):
        raise HTTPException(403, "Заявление не направлено этому руководителю")
    return record_visa(conn, int(app["application_id"]), actor_user_id=int(user["user_id"]),
                       decision="approved", explanation=None)


def pending_approvals(conn, user: dict) -> dict:
    require_rehearsal(user, "TRAINING_HEAD_LOCAL")
    rows = conn.execute(select(hire_applications.c.attempt_id, hire_applications.c.application_id)
        .order_by(hire_applications.c.created_at.desc())).mappings().all()
    items = []
    for row in rows:
        app = load_electronic_hire(conn, int(row["application_id"]))
        if app["personnel_order_id"] is not None and resolve_unit_head(conn, int(app["intended_org_unit_id"])) == int(user["user_id"]):
            items.append({"root_attempt_id": row["attempt_id"], "application_id": row["application_id"],
                          "order_id": app["personnel_order_id"], "candidate": app["full_name"]})
    return {"items": items}


def pending_signatures(conn, user: dict) -> dict:
    require_rehearsal(user, "LEARN_SIGNATORY")
    rows = conn.execute(text("""
        SELECT h.attempt_id AS root_attempt_id,h.application_id,o.order_id,o.order_number,o.status
        FROM public.learning_hire_applications h
        JOIN public.personnel_applications a ON a.application_id=h.application_id
        JOIN public.personnel_orders o ON o.order_id=a.personnel_order_id
        WHERE o.signed_by_employee_id=:employee AND o.deleted_at IS NULL
        ORDER BY o.order_id DESC
    """), {"employee": int(user.get("employee_id") or 0)}).mappings().all()
    return {"items": [dict(r) for r in rows]}


def role_order(conn, user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_SIGNATORY", "LEARN_CANDIDATE")
    application_id = conn.execute(select(hire_applications.c.application_id).where(
        hire_applications.c.attempt_id == root_attempt_id)).scalar_one_or_none()
    if application_id is None:
        raise HTTPException(404, "Учебный приказ не найден")
    app = load_electronic_hire(conn, int(application_id))
    order = _order_row(conn, app)
    if user["role_code"] == "LEARN_SIGNATORY":
        if int(order["signed_by_employee_id"] or 0) != int(user.get("employee_id") or 0):
            raise HTTPException(404, "Учебный приказ не найден")
    else:
        recipient = conn.execute(select(hire_recipients).where(and_(
            hire_recipients.c.root_attempt_id == root_attempt_id,
            hire_recipients.c.candidate_user_id == int(user["user_id"])))).mappings().first()
        bound_employee = conn.execute(text("""
            SELECT employee_id FROM public.users WHERE user_id=:id AND is_active
        """), {"id": int(user["user_id"])}).scalar_one_or_none()
        notice = conn.execute(select(hire_messages.c.id).where(and_(
            hire_messages.c.root_attempt_id == root_attempt_id,
            hire_messages.c.kind == "order_notice",
            hire_messages.c.recipient_user_id == int(user["user_id"])))).scalar_one_or_none()
        if (notice is None or order["status"] != "REGISTERED" or not recipient
                or not recipient["employee_id"] or bound_employee != recipient["employee_id"]):
            raise HTTPException(404, "Учебный приказ не найден")
    return {"detail": get_personnel_order(int(order["order_id"])),
            "editorial": get_editorial_state(int(order["order_id"]))}


def save_number(user: dict, root_attempt_id: str, number: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    with engine.connect() as conn:
        _, order = _linked_order(conn, user, root_attempt_id, 4)
    if order["status"] != "DRAFT":
        raise HTTPException(409, "Номер закреплён после подготовки к подписи")
    return update_personnel_order_draft(order_id=int(order["order_id"]), order_number=number.strip())


def generate_text(user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    with engine.connect() as conn:
        _, order = _linked_order(conn, user, root_attempt_id, 3)
    return generate_editorial(int(order["order_id"]), user_id=int(user["user_id"]))


def save_editorial_body(user: dict, root_attempt_id: str, locale: str, body: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    if locale not in {"ru", "kk"} or not body.strip() or len(body) > 5000:
        raise HTTPException(422, "Укажите текст пункта приказа на русском или казахском языке")
    with engine.connect() as conn:
        _, order = _linked_order(conn, user, root_attempt_id, 3)
        if order["status"] != "DRAFT":
            raise HTTPException(409, "Текст можно исправить только до подписи")
        order_id = int(order["order_id"])
    editorial = get_editorial_state(order_id)
    blocks = [block for item in editorial["items"] for block in item["blocks"]
              if block["locale"] == locale and block["block_type"] == "body"]
    if len(blocks) != 1:
        raise HTTPException(409, "Пункт приказа не найден")
    block = blocks[0]
    return patch_editorial_block(order_id, int(block["block_id"]),
        user_id=int(user["user_id"]), override_text=body.strip(),
        expected_revision=int(block["revision"]), scope="item")


def ready(user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    with engine.connect() as conn:
        _, order = _linked_order(conn, user, root_attempt_id, 4)
    return mark_personnel_order_ready_for_signature(order_id=int(order["order_id"]))


def sign(conn, user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_SIGNATORY")
    row = conn.execute(select(hire_applications.c.application_id)
        .where(hire_applications.c.attempt_id == root_attempt_id)).first()
    if row is None:
        raise HTTPException(404, "Учебное заявление не найдено")
    app = load_electronic_hire(conn, int(row.application_id))
    order = _order_row(conn, app)
    if order["status"] != "READY_FOR_SIGNATURE":
        raise HTTPException(409, "Приказ ещё не готов к подписи")
    if not user.get("employee_id") or int(order["signed_by_employee_id"] or 0) != int(user["employee_id"]):
        raise HTTPException(403, "Вы не указаны подписантом приказа")
    register_personnel_order_tx(conn, order_id=int(order["order_id"]), target_status="SIGNED")
    conn.execute(insert(hire_signatures).values(root_attempt_id=root_attempt_id,
        order_id=int(order["order_id"]), signatory_user_id=int(user["user_id"])))
    return {"order_id": int(order["order_id"]), "status": "SIGNED"}


def register(conn, user: dict, root_attempt_id: str) -> dict:
    root, order = _linked_order(conn, user, root_attempt_id, 4)
    signed = conn.execute(select(hire_signatures).where(
        hire_signatures.c.root_attempt_id == root_attempt_id)).mappings().first()
    if not signed or int(signed["order_id"]) != int(order["order_id"]):
        raise HTTPException(409, "Сначала требуется подпись указанного подписанта")
    if order["status"] != "SIGNED":
        raise HTTPException(409, "Приказ не находится на этапе регистрации")
    register_personnel_order_tx(conn, order_id=int(order["order_id"]), target_status="REGISTERED",
                                allow_training_signed_transition=True)
    return {"application_id": root["application"]["application_id"], "order_id": int(order["order_id"]),
            "number": order["order_number"], "date": order["order_date"].isoformat(), "status": "REGISTERED"}


def apply_registered_order(user: dict, root_attempt_id: str) -> dict:
    require_rehearsal(user, "LEARN_HR")
    with engine.connect() as conn:
        root, order = _linked_order(conn, user, root_attempt_id, 5)
        if order["status"] != "REGISTERED":
            raise HTTPException(409, "Сначала зарегистрируйте приказ")
        application_id = int(root["application"]["application_id"])
        recipient = conn.execute(select(hire_recipients).where(
            hire_recipients.c.root_attempt_id == root_attempt_id)).mappings().first()
        if recipient is None:
            raise HTTPException(409, "Получатель учебного уведомления не найден")
        current_employee = conn.execute(text("""
            SELECT employee_id FROM public.users WHERE user_id=:id AND is_active
        """), {"id": int(recipient["candidate_user_id"])}).scalar_one_or_none()
        if current_employee and current_employee != recipient["employee_id"]:
            raise HTTPException(409, "Учебная учётная запись уже связана с другим сотрудником")
    result = orchestrate_hire_apply_for_application(
        application_id=application_id, created_by_user_id=int(user["user_id"]))
    with engine.begin() as conn:
        recipient = conn.execute(select(hire_recipients).where(
            hire_recipients.c.root_attempt_id == root_attempt_id)).mappings().first()
        if recipient is None:
            raise HTTPException(409, "Получатель учебного уведомления не найден")
        if recipient["employee_id"] and int(recipient["employee_id"]) != int(result.employee_id):
            raise HTTPException(409, "Учебный получатель связан с другим сотрудником")
        conn.execute(text("""
            UPDATE public.users SET employee_id=:employee
            WHERE user_id=:user AND is_active AND (employee_id IS NULL OR employee_id=:employee)
        """), {"employee": int(result.employee_id), "user": int(recipient["candidate_user_id"])})
        conn.execute(hire_recipients.update().where(
            hire_recipients.c.root_attempt_id == root_attempt_id)
            .values(employee_id=int(result.employee_id)))
    return {"application_id": application_id, "order_id": int(result.personnel_order_id),
            "employee_id": int(result.employee_id), "idempotent_replay": result.idempotent_replay}


def inbox(conn, user: dict) -> dict:
    require_rehearsal(user, "LEARN_CANDIDATE")
    rows = conn.execute(select(hire_messages, hire_applications.c.application_id)
        .join(hire_applications, hire_applications.c.attempt_id == hire_messages.c.root_attempt_id)
        .where(hire_messages.c.recipient_user_id == int(user["user_id"]))
        .order_by(hire_messages.c.created_at.desc())).mappings().all()
    items = []
    for row in rows:
        item = {"id": row["id"], "kind": row["kind"], "root_attempt_id": row["root_attempt_id"],
                "created_at": row["created_at"].isoformat(), "application_id": row["application_id"]}
        if row["kind"] == "intake_link":
            display = get_hr_intake_link_display(conn, int(row["application_id"]))
            item["intake_url_path"] = display.intake_url_path if (
                display.display_state == "active" and display.link_id == row["link_id"]) else None
        else:
            order = conn.execute(text("SELECT order_number,order_date,status FROM public.personnel_orders WHERE order_id=:id"),
                                 {"id": row["order_id"]}).mappings().first()
            if order:
                item.update(order_id=row["order_id"], number=order["order_number"],
                            date=order["order_date"].isoformat() if order["order_date"] else None,
                            status=order["status"])
            ack = conn.execute(select(hire_acknowledgements).where(
                hire_acknowledgements.c.root_attempt_id == row["root_attempt_id"])).mappings().first()
            item["acknowledged_at"] = ack["acknowledged_at"].isoformat() if ack else None
        items.append(item)
    return {"items": items}


def notified_recipient(conn, user: dict, root_attempt_id: str) -> dict:
    root, order = _linked_order(conn, user, root_attempt_id, 5)
    if order["status"] != "REGISTERED":
        raise HTTPException(409, "Уведомить можно только о зарегистрированном приказе")
    recipient = conn.execute(select(hire_recipients).where(
        hire_recipients.c.root_attempt_id == root_attempt_id)).mappings().first()
    if not recipient or not recipient["employee_id"]:
        raise HTTPException(409, "Сначала примените приказ и создайте учебную запись сотрудника")
    bound_employee = conn.execute(text("""
        SELECT employee_id FROM public.users WHERE user_id=:id AND is_active
    """), {"id": int(recipient["candidate_user_id"])}).scalar_one_or_none()
    if bound_employee != recipient["employee_id"]:
        raise HTTPException(409, "Учебная учётная запись сотрудника не привязана")
    prior = conn.execute(select(hire_messages).where(and_(
        hire_messages.c.root_attempt_id == root_attempt_id,
        hire_messages.c.kind == "order_notice"))).mappings().first()
    if prior is None:
        conn.execute(insert(hire_messages).values(id=str(uuid4()), root_attempt_id=root_attempt_id,
            recipient_user_id=int(recipient["candidate_user_id"]), kind="order_notice",
            order_id=int(order["order_id"]), created_by_user_id=int(user["user_id"])))
    return {"order_id": int(order["order_id"]), "recipient_login": _candidate_login(conn, recipient["candidate_user_id"]),
            "delivered_in_training_inbox": True}


def acknowledge(conn, user: dict, root_attempt_id: str, method: str, evidence: str) -> dict:
    require_rehearsal(user, "LEARN_CANDIDATE")
    recipient = conn.execute(select(hire_recipients).where(and_(
        hire_recipients.c.root_attempt_id == root_attempt_id,
        hire_recipients.c.candidate_user_id == int(user["user_id"])))).mappings().first()
    notice = conn.execute(select(hire_messages).where(and_(
        hire_messages.c.root_attempt_id == root_attempt_id,
        hire_messages.c.kind == "order_notice",
        hire_messages.c.recipient_user_id == int(user["user_id"])))).mappings().first()
    bound_employee = conn.execute(text("""
        SELECT employee_id FROM public.users WHERE user_id=:id AND is_active
    """), {"id": int(user["user_id"])}).scalar_one_or_none()
    if (not recipient or not notice or not recipient["employee_id"]
            or bound_employee != recipient["employee_id"]):
        raise HTTPException(404, "Уведомление сотруднику не найдено")
    if method != "training_cabinet" or evidence.strip() != "Подтверждаю ознакомление с приказом":
        raise HTTPException(422, "Требуется личное подтверждение в учебном кабинете")
    order = conn.execute(text("SELECT status FROM public.personnel_orders WHERE order_id=:id"),
                         {"id": int(notice["order_id"])}).scalar_one_or_none()
    if order != "REGISTERED":
        raise HTTPException(409, "Приказ не зарегистрирован")
    existing = conn.execute(select(hire_acknowledgements).where(
        hire_acknowledgements.c.root_attempt_id == root_attempt_id)).mappings().first()
    if existing:
        return {"acknowledged_at": existing["acknowledged_at"].isoformat(), "idempotent_replay": True}
    return {"order_id": int(notice["order_id"]), "employee_id": int(recipient["employee_id"]),
            "recipient_user_id": int(user["user_id"]), "method": method, "evidence": evidence.strip()}


def save_acknowledgement(conn, root_attempt_id: str, validated: dict) -> dict:
    conn.execute(insert(hire_acknowledgements).values(root_attempt_id=root_attempt_id,
        order_id=validated["order_id"], employee_id=validated["employee_id"],
        recipient_user_id=validated["recipient_user_id"], method=validated["method"],
        evidence=validated["evidence"]))
    saved = conn.execute(select(hire_acknowledgements).where(
        hire_acknowledgements.c.root_attempt_id == root_attempt_id)).mappings().one()
    return {"acknowledged_at": saved["acknowledged_at"].isoformat(), "idempotent_replay": False}
