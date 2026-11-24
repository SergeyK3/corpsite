"""Isolated projection checks; no database writes or production fixtures."""
from datetime import datetime, timedelta, timezone

import app.services.access_people_view_service as view


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, user, grants, audits=()):
        self.user, self.grants, self.audits = user, grants, audits

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM public.users u" in sql and "WHERE u.user_id" in sql:
            return _Rows([self.user])
        if "FROM public.access_grants g" in sql:
            return _Rows(self.grants)
        if "FROM public.security_audit_log a" in sql:
            return _Rows(self.audits)
        raise AssertionError(sql)


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        connection = self.connection

        class Context:
            def __enter__(self):
                return connection

            def __exit__(self, *_args):
                return False

        return Context()


def _grant(grant_id, *, target_type="USER", target_id=7, scope_type="GLOBAL", scope_id=None, active=True, code="PERSONNEL_CARD_EDIT"):
    now = datetime.now(timezone.utc)
    return {
        "grant_id": grant_id, "target_type": target_type, "target_id": target_id,
        "resource_key": None, "scope_type": scope_type, "scope_id": scope_id,
        "include_subtree": False, "active_flag": active,
        "starts_at": now - timedelta(days=10), "ends_at": None,
        "created_at": now - timedelta(days=12), "granted_by_user_id": 25,
        "reason": "test fixture", "revoked_at": now - timedelta(days=1) if not active else None,
        "revoked_by_user_id": 25 if not active else None,
        "code": code, "name": code, "access_level": "MANAGER", "permission_active": True,
        "source_role_name": "Кадры" if target_type == "ROLE" else None,
        "source_role_code": "HR" if target_type == "ROLE" else None,
        "grantor_login": "admin", "grantor_name": "Администратор",
        "revoker_login": "admin" if not active else None,
        "revoker_name": "Администратор" if not active else None,
        "scope_unit_name": "Терапия" if scope_id == 10 else None,
    }


def test_personal_role_duplicate_scope_and_revoked_are_distinct(monkeypatch):
    user = {"user_id": 7, "employee_id": 20, "person_id": 30, "role_id": 14,
            "is_active": True, "role_name": "Кадры", "role_code": "HR"}
    grants = [
        _grant(1), _grant(2, target_type="ROLE", target_id=14),
        _grant(3, target_type="ROLE", target_id=14, scope_type="ORG_UNIT", scope_id=10),
        _grant(4, active=False, code="PERSONNEL_EVENTS_READ"),
    ]
    monkeypatch.setattr(view, "engine", _Engine(_Connection(user, grants)))
    monkeypatch.setattr(view, "_collect_subject_ids", lambda *_args, **_kwargs: {"USER": {7}, "ROLE": {14}})
    current = view.get_access_person(7)
    assert len(current["items"]) == 2
    global_right = next(item for item in current["items"] if item["scope_type"] == "GLOBAL")
    assert len(global_right["sources"]) == 2
    assert {source["source_type"] for source in global_right["sources"]} == {"personal", "role"}
    assert next(source for source in global_right["sources"] if source["source_type"] == "role")["role_assigned_at"] is None
    assert next(item for item in current["items"] if item["scope_type"] == "ORG_UNIT")["scope_id"] == 10
    with_revoked = view.get_access_person(7, show_revoked=True)
    assert len(with_revoked["items"]) == 3
    assert next(item for item in with_revoked["items"] if item["code"] == "PERSONNEL_EVENTS_READ")["active"] is False


def test_unlinked_admin_account_has_explicit_external_source(monkeypatch):
    user = {"user_id": 25, "employee_id": None, "person_id": None, "role_id": 2,
            "is_active": True, "role_name": "Администратор", "role_code": "ADMIN"}
    monkeypatch.setattr(view, "engine", _Engine(_Connection(user, [])))
    monkeypatch.setattr(view, "_collect_subject_ids", lambda *_args, **_kwargs: {"USER": {25}, "ROLE": {2}})
    result = view.get_access_person(25)
    assert result["items"] == []
    assert "ADMIN" in result["implicit_sources"][0]
    assert "не является полным" in result["coverage_note"]


def test_roster_keeps_missing_assignment_fields_and_unlinked_account(monkeypatch):
    employee = {"id": "20", "fio": "Сотрудник без должности", "position": None,
                "org_unit": None}
    monkeypatch.setattr(view, "list_employees", lambda **_kwargs: {"items": [employee]})

    class RosterConnection:
        def execute(self, statement):
            if "FROM public.users u" in str(statement):
                return _Rows([
                    {"user_id": 7, "employee_id": 20, "login": "linked", "full_name": None,
                     "role_id": None, "role_code": None, "role_name": None, "is_active": True},
                    {"user_id": 8, "employee_id": None, "login": "technical", "full_name": None,
                     "role_id": None, "role_code": None, "role_name": None, "is_active": True},
                ])
            return _Rows([])

    monkeypatch.setattr(view, "engine", _Engine(RosterConnection()))
    result = view.list_access_people()
    assert result["items"][0]["position_name"] is None
    assert result["items"][0]["org_unit_name"] is None
    assert result["items"][0]["users"][0]["login"] == "linked"
    assert result["unlinked_accounts"][0]["login"] == "technical"


def test_roster_card_unit_remains_filterable_without_person_assignment(monkeypatch):
    monkeypatch.setattr(view, "list_employees", lambda **_kwargs: {"items": [{
        "id": "138", "fio": "Макибаева Акмарал Сабитовна",
        "has_current_assignment": False,
        "position": {"id": 86, "name": "Руководитель отдела кадров"},
        "org_unit": {"unit_id": 73, "name": "Отдел кадров"},
    }]})

    class RosterConnection:
        def execute(self, statement):
            if "FROM public.users u" in str(statement):
                return _Rows([{
                    "user_id": 361, "employee_id": 138, "login": "makibaeva.as",
                    "full_name": "Макибаева Акмарал Сабитовна", "role_id": None,
                    "role_code": None, "role_name": None, "is_active": True,
                }])
            return _Rows([(73, 3)])

    monkeypatch.setattr(view, "engine", _Engine(RosterConnection()))
    result = view.list_access_people()
    row = result["items"][0]
    assert row["has_current_assignment"] is False
    assert (row["org_group_id"], row["org_unit_id"], row["position_id"]) == (3, 73, 86)
    assert row["users"][0]["login"] == "makibaeva.as"
    assert result["unlinked_accounts"] == []
