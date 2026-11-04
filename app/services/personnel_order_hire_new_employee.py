"""HIRE name snapshots and deferred enrollment; caller owns the apply transaction."""
from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import text


def normalize_new_employee(value: Any) -> dict[str, str]:
    from app.services.personnel_orders_query_service import PersonnelOrderValidationError

    if not isinstance(value, Mapping) or set(value) - {"last_name", "first_name", "middle_name"}:
        raise PersonnelOrderValidationError("Укажите фамилию и имя нового сотрудника.")
    result = {}
    for key in ("last_name", "first_name", "middle_name"):
        raw = value.get(key, "")
        if not isinstance(raw, str) or len(raw) > 100:
            raise PersonnelOrderValidationError("Поля ФИО должны содержать не более 100 символов.")
        result[key] = " ".join(raw.split())
    if not result["last_name"] or not result["first_name"]:
        raise PersonnelOrderValidationError("Укажите фамилию и имя нового сотрудника. Отчество необязательно.")
    return result


def new_employee_full_name(value: Mapping[str, str]) -> str:
    return " ".join(value[key] for key in ("last_name", "first_name", "middle_name") if value.get(key))


def assert_no_hire_name_duplicate(conn, value: Mapping[str, str], *, lock: bool = False) -> None:
    """Conservative name match including inactive/unlinked employees; never auto-link."""
    from app.services.personnel_orders_query_service import PersonnelOrderValidationError

    # The lock key excludes patronymic, so concurrent variants of the same name
    # cannot both enroll before seeing the other transaction's person row.
    stem = f"{value['last_name']} {value['first_name']}".lower().replace("ё", "е")
    if lock:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"hire-name:{stem}"})
    rows = conn.execute(text(r"""
        SELECT kind, id, full_name FROM (
            SELECT 'person' AS kind, person_id AS id, full_name FROM public.persons
            UNION ALL
            SELECT 'employee', employee_id, full_name FROM public.employees
        ) candidates
        WHERE regexp_replace(translate(lower(btrim(full_name)), 'ё', 'е'), '\s+', ' ', 'g') = :stem
           OR starts_with(regexp_replace(translate(lower(btrim(full_name)), 'ё', 'е'), '\s+', ' ', 'g'), :prefix)
        ORDER BY kind, id LIMIT 10
    """), {"stem": stem, "prefix": stem + " "}).mappings().all()
    if rows:
        matches = "; ".join(f"{row['full_name']} ({row['kind']} #{row['id']})" for row in rows)
        raise PersonnelOrderValidationError(
            f"Возможный дубликат сотрудника: {matches}. Проверьте карточки и выберите существующего сотрудника или заявителя."
        )


def prepare_hire_new_employee_payload(payload: Mapping[str, Any], employee_id, subject) -> dict[str, Any]:
    from app.services.personnel_orders_query_service import PersonnelOrderValidationError

    out = dict(payload)
    value = normalize_new_employee(out["new_employee"])
    if employee_id is not None or out.get("person_id"):
        raise PersonnelOrderValidationError("Новый сотрудник не должен содержать employee_id или person_id.")
    name = new_employee_full_name(value)
    if subject is None or str(subject.get("full_name") or "").strip() != name:
        raise PersonnelOrderValidationError("ФИО нового сотрудника не совпадает с ФИО в приказе.")
    out["new_employee"] = value
    return out


def materialize_hire_new_employee_tx(conn, item: dict[str, Any], *, created_by: int) -> None:
    """Create only the applicant identity; existing HIRE apply creates the employee."""
    if item.get("item_type_code") != "HIRE" or item.get("employee_id") is not None:
        return
    payload = dict(item.get("payload") or {})
    if "new_employee" not in payload or payload.get("person_id"):
        return
    value = normalize_new_employee(payload["new_employee"])
    assert_no_hire_name_duplicate(conn, value, lock=True)
    from app.personnel_applications.application.registration_service import _insert_person, _materialize_ppr_participating
    from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE

    person_id = _insert_person(conn, full_name=new_employee_full_name(value), iin=None, birth_date=None)
    conn.execute(text("""
        UPDATE public.persons SET last_name=:last_name, first_name=:first_name,
            middle_name=NULLIF(:middle_name, '') WHERE person_id=:person_id
    """), {**value, "person_id": person_id})
    _materialize_ppr_participating(conn, person_id=person_id,
                                 hr_relationship_context=HR_RELATIONSHIP_CANDIDATE, actor_id=str(created_by))
    payload["person_id"] = person_id
    if isinstance(payload.get("unresolved_subject"), dict):
        payload["unresolved_subject"] = {**payload["unresolved_subject"], "needs_employee_link": False}
    conn.execute(text("UPDATE public.personnel_order_items SET payload=CAST(:payload AS jsonb) WHERE item_id=:id"),
                 {"payload": json.dumps(payload, ensure_ascii=False), "id": item["item_id"]})
    item["payload"] = payload
