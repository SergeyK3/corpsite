"""Read-only, administrator-facing projection of employee access sources."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.services.access_resolver_service import _collect_subject_ids
from app.services.directory_service import list_employees


_LABELS = {
    "ACCESS_ADMIN": "Полное управление доступом",
    "ACCESS_MANAGER": "Управление доступом",
    "ACCESS_NONE": "Нет доступа",
    "ACCESS_OBSERVER": "Просмотр доступа",
    "CONTROL_LIST_EXPORT": "Выгрузка контрольного списка",
    "DATA_EXCHANGE_CONFIRM_APPLY": "Подтверждение обмена данными",
    "DATA_EXCHANGE_DRY_RUN": "Пробный запуск обмена данными",
    "DATA_EXCHANGE_EXPORT_REFERENCE": "Выгрузка справочника для обмена",
    "DATA_EXCHANGE_UPLOAD_PREVIEW": "Предпросмотр загрузки данных",
    "DATA_EXCHANGE_VIEW": "Просмотр обмена данными",
    "HR_ENROLLMENT_MANAGER": "Управление оформлением сотрудников",
    "INCOMING_INFO_ADMIN": "Администрирование входящей информации",
    "INCOMING_INFO_CONTROL": "Контроль входящей информации",
    "INCOMING_INFO_EXECUTE": "Исполнение входящей информации",
    "INCOMING_INFO_READ": "Просмотр входящей информации",
    "INCOMING_INFO_REGISTER": "Регистрация входящей информации",
    "INCOMING_INFO_RESOLVE": "Резолюции по входящей информации",
    "INCOMING_INFO_RESTRICTED_BYPASS": "Доступ к ограниченной входящей информации",
    "OPERATIONAL_ORDER_ARCHIVE_REVIEW": "Просмотр архива оперативных приказов",
    "OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY": "Назначение подписанта оперативных приказов",
    "OPERATIONAL_ORDERS_CONTENT_CONFIRM": "Подтверждение содержания оперативных приказов",
    "OPERATIONAL_ORDERS_EDITORIAL_READY": "Редакторская готовность оперативных приказов",
    "OPERATIONAL_ORDERS_INTAKE_CREATE": "Создание оперативных приказов",
    "OPERATIONAL_ORDERS_INTAKE_OPERATE": "Работа с оперативными приказами",
    "OPERATIONAL_ORDERS_INTAKE_READ": "Просмотр оперативных приказов",
    "OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE": "Передача оперативных приказов на подпись",
    "OPERATIONAL_ORDERS_PROMOTE": "Продвижение оперативных приказов",
    "OPERATIONAL_ORDERS_RECONCILE": "Сверка оперативных приказов",
    "OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE": "Возврат оперативных приказов с подписи",
    "OPERATIONAL_ORDERS_SIGN": "Подписание оперативных приказов",
    "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ": "Просмотр готовности оперативных приказов к подписи",
    "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN": "Назначение перевода оперативных приказов",
    "OPERATIONAL_ORDERS_TRANSLATION_WORK": "Перевод оперативных приказов",
    "PERSONNEL_CARD_EDIT": "Редактирование личных карточек",
    "PERSONNEL_EVENTS_READ": "Просмотр кадровых событий",
    "PERSONNEL_ORDERS_ARCHIVE": "Архив кадровых приказов",
    "PERSONNEL_ORDERS_AUDIT_READ": "Просмотр аудита кадровых приказов",
    "PERSONNEL_ORDERS_CANCEL_OWN": "Отмена своих кадровых приказов",
    "PERSONNEL_ORDERS_CANCEL_SCOPE": "Отмена кадровых приказов в своей области",
    "PERSONNEL_ORDERS_RESTORE": "Восстановление кадровых приказов",
    "PERSONNEL_ORDERS_VOID": "Аннулирование кадровых приказов",
    "PERSONNEL_ORDERS_VOID_APPLIED": "Аннулирование применённых кадровых приказов",
    "PERSONNEL_RECOVERY_ADMIN": "Управление восстановлением кадровых данных",
    "POSITION_RECONCILIATION_RESOLVE": "Сопоставление должностей",
    "PPR_MIGRATION_STATUS_READ": "Просмотр статуса миграции ППР",
    "SECURITY_AUDITOR": "Аудит безопасности",
    "SYSADMIN_CABINET": "Кабинет системного администратора",
    "TECHNICAL_PERSONNEL_ORDER_CLEANUP": "Техническая очистка кадровых приказов",
    "TEST_PERSONNEL_DELETION_APPROVE": "Согласование удаления тестовых сотрудников",
    "TEST_PERSONNEL_DELETION_AUDIT_READ": "Просмотр аудита удаления тестовых сотрудников",
    "TEST_PERSONNEL_DELETION_EXECUTE": "Выполнение удаления тестовых сотрудников",
    "TEST_PERSONNEL_DELETION_REQUEST": "Запрос удаления тестовых сотрудников",
    "TEST_SYSTEM_IDENTITY_DELETION_APPROVE": "Согласование удаления тестовых системных записей",
    "TEST_SYSTEM_IDENTITY_DELETION_AUDIT_READ": "Просмотр аудита удаления тестовых системных записей",
    "TEST_SYSTEM_IDENTITY_DELETION_EXECUTE": "Выполнение удаления тестовых системных записей",
    "TEST_SYSTEM_IDENTITY_DELETION_REQUEST": "Запрос удаления тестовых системных записей",
    "USER_ACCESS_ADMIN": "Управление доступами пользователей",
}


def _section(code: str) -> str:
    if code.startswith("PERSONNEL_CARD"):
        return "Личные карточки"
    if code.startswith("PERSONNEL_ORDERS"):
        return "Кадровые приказы"
    if code.startswith("INCOMING_INFO"):
        return "Документы"
    if code.startswith("OPERATIONAL_ORDER"):
        return "Оперативные приказы"
    if code.startswith("DATA_EXCHANGE"):
        return "Обмен данными"
    if code.startswith(("USER_ACCESS", "ACCESS_", "SYSADMIN", "SECURITY_", "TEST_SYSTEM_IDENTITY")):
        return "Администрирование"
    if code.startswith(("PERSONNEL_", "HR_", "PPR_", "TEST_PERSONNEL", "POSITION_")):
        return "Персонал"
    if code.startswith("CONTROL_LIST"):
        return "Документы"
    return "Другие разделы"


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def list_access_people() -> dict[str, Any]:
    """Use the Personnel roster projection for current position and unit."""
    roster = list_employees(
        status="all", q=None, department_id=None, position_id=None,
        limit=10000, offset=0, sort="fio", order="asc",
    )["items"]
    with engine.connect() as conn:
        users = [dict(row) for row in conn.execute(text("""
            SELECT u.user_id, u.employee_id, u.full_name, u.login, u.is_active,
                   u.role_id, r.code AS role_code, r.name AS role_name
            FROM public.users u LEFT JOIN public.roles r ON r.role_id=u.role_id
            ORDER BY u.user_id
        """)).mappings()]
        unit_groups = dict(conn.execute(text(
            "SELECT unit_id, group_id FROM public.org_units"
        )).all())
    by_employee: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for user in users:
        if user["employee_id"] is not None:
            by_employee[int(user["employee_id"])].append(user)
    people: list[dict[str, Any]] = []
    roster_ids: set[int] = set()
    for employee in roster:
        if employee.get("id") is None:
            continue
        employee_id = int(employee["id"])
        roster_ids.add(employee_id)
        unit = employee.get("org_unit") or {}
        position = employee.get("position") or {}
        has_current_assignment = bool(employee.get("has_current_assignment"))
        # The roster already selects the current assignment when one exists and
        # falls back to the employee card otherwise. Keep that card placement
        # available for filtering even when no person assignment exists.
        unit_id = unit.get("unit_id")
        people.append({
            "employee_id": employee_id,
            "full_name": employee.get("fio") or "ФИО не указано",
            "has_current_assignment": has_current_assignment,
            "position_id": position.get("id"),
            "position_name": position.get("name"),
            "org_unit_id": unit_id,
            "org_unit_name": unit.get("name"),
            "org_group_id": unit_groups.get(unit_id),
            "users": by_employee.get(employee_id, []),
        })
    unlinked = [user for user in users if user["employee_id"] is None or int(user["employee_id"]) not in roster_ids]
    return {"items": people, "unlinked_accounts": unlinked}


def get_access_person(user_id: int, *, show_revoked: bool = False) -> dict[str, Any]:
    """List grant sources using the same subject collection as the access resolver."""
    with engine.connect() as conn:
        user = conn.execute(text("""
            SELECT u.user_id, u.employee_id, u.role_id, u.is_active,
                   e.person_id, r.name AS role_name, r.code AS role_code
            FROM public.users u
            LEFT JOIN public.employees e ON e.employee_id=u.employee_id
            LEFT JOIN public.roles r ON r.role_id=u.role_id
            WHERE u.user_id=:user_id
        """), {"user_id": user_id}).mappings().first()
        if user is None:
            raise ValueError("Учётная запись не найдена")
        subjects = _collect_subject_ids(
            conn, user_id=user_id, employee_id=user["employee_id"],
            person_id=user["person_id"], role_id=user["role_id"],
        )
        clauses = []
        params: dict[str, Any] = {}
        for index, (target_type, ids) in enumerate(subjects.items()):
            if ids:
                clauses.append(f"(g.target_type=:type_{index} AND g.target_id=ANY(:ids_{index}))")
                params[f"type_{index}"] = target_type
                params[f"ids_{index}"] = sorted(ids)
        where = " OR ".join(clauses) or "FALSE"
        rows = [dict(row) for row in conn.execute(text(f"""
            SELECT g.grant_id, g.target_type, g.target_id, g.resource_key,
                   g.scope_type, g.scope_id, g.include_subtree,
                   g.active_flag, g.starts_at, g.ends_at, g.created_at,
                   g.granted_by_user_id, g.reason, g.revoked_at, g.revoked_by_user_id,
                   ar.code, ar.name, ar.access_level, ar.is_active AS permission_active,
                   role.name AS source_role_name, role.code AS source_role_code,
                   grantor.login AS grantor_login, grantor.full_name AS grantor_name,
                   revoker.login AS revoker_login, revoker.full_name AS revoker_name,
                   scope_unit.name AS scope_unit_name
            FROM public.access_grants g
            JOIN public.access_roles ar ON ar.access_role_id=g.access_role_id
            LEFT JOIN public.roles role ON g.target_type='ROLE' AND role.role_id=g.target_id
            LEFT JOIN public.users grantor ON grantor.user_id=g.granted_by_user_id
            LEFT JOIN public.users revoker ON revoker.user_id=g.revoked_by_user_id
            LEFT JOIN public.org_units scope_unit ON g.scope_type='ORG_UNIT' AND scope_unit.unit_id=g.scope_id
            WHERE ({where})
            ORDER BY g.grant_id DESC
        """), params).mappings()]
        grant_ids = [row["grant_id"] for row in rows]
        audits: dict[int, list[dict[str, Any]]] = defaultdict(list)
        if grant_ids:
            for audit in conn.execute(text("""
                SELECT a.event_type, a.happened_at, a.actor_user_id, a.metadata,
                       actor.login AS actor_login, actor.full_name AS actor_name
                FROM public.security_audit_log a
                LEFT JOIN public.users actor ON actor.user_id=a.actor_user_id
                WHERE a.event_type IN ('ACCESS_GRANTED','ACCESS_REVOKED')
                  AND CASE WHEN (a.metadata->>'grant_id') ~ '^[0-9]+$'
                           THEN (a.metadata->>'grant_id')::bigint
                           ELSE NULL END = ANY(:grant_ids)
                ORDER BY a.happened_at
            """), {"grant_ids": grant_ids}).mappings():
                audits[int(audit["metadata"]["grant_id"])].append({
                    "event_type": audit["event_type"], "happened_at": _iso(audit["happened_at"]),
                    "actor_user_id": audit["actor_user_id"],
                    "actor_label": audit["actor_name"] or audit["actor_login"],
                    "reason": audit["metadata"].get("reason"),
                })
    now = datetime.now().astimezone()
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        active = bool(row["active_flag"] and row["permission_active"]
                      and row["access_level"] != "NONE"
                      and row["starts_at"] <= now
                      and (row["ends_at"] is None or row["ends_at"] > now))
        if not active and not show_revoked:
            continue
        code = row["code"]
        key = (code, row["resource_key"], row["scope_type"], row["scope_id"], row["include_subtree"])
        item = grouped.setdefault(key, {
            "code": code,
            "label": _LABELS.get(code) or (row["name"] if any("А" <= c <= "я" for c in row["name"] or "") else code),
            "section": _section(code), "resource_key": row["resource_key"],
            "scope_type": row["scope_type"], "scope_id": row["scope_id"],
            "scope_unit_name": row["scope_unit_name"],
            "include_subtree": row["include_subtree"], "active": False, "sources": [],
        })
        item["active"] = item["active"] or active
        item["sources"].append({
            "grant_id": row["grant_id"], "active": active,
            "status": "действует" if active else ("отозвано" if not row["active_flag"] else "не действует"),
            "source_type": "role" if row["target_type"] == "ROLE" else "personal" if row["target_type"] == "USER" else "related",
            "target_type": row["target_type"], "target_id": row["target_id"],
            "role_name": row["source_role_name"], "role_code": row["source_role_code"],
            "role_assigned_at": None, "role_assignment_date_known": False,
            "grant_created_at": _iso(row["created_at"]),
            "starts_at": _iso(row["starts_at"]), "ends_at": _iso(row["ends_at"]),
            "granted_by_user_id": row["granted_by_user_id"],
            "grantor_label": row["grantor_name"] or row["grantor_login"],
            "reason": row["reason"], "revoked_at": _iso(row["revoked_at"]),
            "revoked_by_user_id": row["revoked_by_user_id"],
            "revoker_label": row["revoker_name"] or row["revoker_login"],
            "audit": audits.get(row["grant_id"], []),
        })
    return {
        "user_id": user_id, "is_active": user["is_active"],
        "role_name": user["role_name"], "role_code": user["role_code"],
        "implicit_sources": (["Роль ADMIN: отдельные административные допуски вне таблицы выдач"]
                             if user["role_code"] == "ADMIN" else []),
        "items": sorted(grouped.values(), key=lambda item: (item["section"], item["label"], item["code"])),
        "coverage_note": "Показаны выдачи, применимые по правилам access_grants. Другие допуски приложения могут предоставляться ролью или отдельным механизмом; этот перечень не является полным аудитом всех проверок доступа.",
    }
