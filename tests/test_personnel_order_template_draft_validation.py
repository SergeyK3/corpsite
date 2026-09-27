from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import admin_router
from app.main import app
from app.security.admin_guard import require_sysadmin_api
from app.services import personnel_order_template_draft_service as draft_service
from app.services.personnel_order_template_draft_service import EDITABLE_TYPE, TemplateDraftError, _built_in, _validate, preview_draft


class _Result:
    def __init__(self, row: dict[str, Any] | None):
        self.row = row

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict[str, Any] | None:
        return self.row

    def one(self) -> dict[str, Any]:
        assert self.row is not None
        return self.row


class _DraftStore:
    """Small SQL boundary double: it exposes only the draft table to the service."""

    def __init__(self) -> None:
        self.row: dict[str, Any] | None = None
        self.statements: list[str] = []
        self.insert_count = 0

    def connect(self) -> "_DraftStore":
        return self

    def begin(self) -> "_DraftStore":
        return self

    def __enter__(self) -> "_DraftStore":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, statement: object, values: dict[str, Any] | None = None) -> _Result:
        sql = str(statement)
        self.statements.append(sql)
        values = values or {}
        if sql.lstrip().startswith("SELECT"):
            return _Result(self.row)
        if sql.lstrip().startswith("INSERT"):
            self.insert_count += 1
            now = datetime.now(timezone.utc)
            self.row = {
                "template_version_id": 101,
                "item_type_code": values["type"],
                "version_number": 1,
                "status": "DRAFT",
                "revision": 1,
                **{key: values[key] for key in _built_in()},
                "based_on_built_in": True,
                "created_at": now,
                "updated_at": now,
                "created_by_user_id": values["actor"],
                "updated_by_user_id": values["actor"],
            }
            return _Result(self.row)
        assert sql.lstrip().startswith("UPDATE")
        assert self.row is not None
        self.row.update({key: values[key] for key in _built_in()})
        self.row["revision"] += 1
        self.row["updated_by_user_id"] = values["actor"]
        self.row["updated_at"] = datetime.now(timezone.utc)
        return _Result(self.row)


@pytest.fixture
def draft_store(monkeypatch: pytest.MonkeyPatch) -> _DraftStore:
    store = _DraftStore()
    monkeypatch.setattr(draft_service, "engine", store)
    return store


def test_unpaid_template_builtin_is_safe_and_has_bilingual_preview() -> None:
    values = _built_in()
    _validate(values)
    preview = preview_draft(EDITABLE_TYPE, values)
    assert preview["ru"]["directive"] == "ПРИКАЗЫВАЮ:"
    assert preview["kk"]["directive"] == "БҰЙЫРАМЫН:"
    assert "{{" not in preview["ru"]["body"]


def test_unpaid_template_rejects_unknown_and_missing_required_variables() -> None:
    values = _built_in()
    values["body_template_ru"] += " {{unknown.value}}"
    with pytest.raises(TemplateDraftError, match="Неизвестная"):
        _validate(values)
    values = _built_in()
    values["body_template_ru"] = values["body_template_ru"].replace("{{leave.days}}", "")
    with pytest.raises(TemplateDraftError, match="обязательные"):
        _validate(values)


def test_template_editor_is_unavailable_for_other_type() -> None:
    with pytest.raises(TemplateDraftError) as error:
        preview_draft("HIRE", _built_in())
    assert error.value.code == "TEMPLATE_EDITOR_NOT_AVAILABLE"


def test_draft_create_load_save_noop_and_conflict_are_isolated_to_template_versions(draft_store: _DraftStore) -> None:
    created = draft_service.create_draft(EDITABLE_TYPE, actor_user_id=77)
    repeated = draft_service.create_draft(EDITABLE_TYPE, actor_user_id=88)
    loaded = draft_service.get_draft(EDITABLE_TYPE)

    assert created["template_version_id"] == repeated["template_version_id"] == loaded["template_version_id"]
    assert draft_store.insert_count == 1
    assert draft_store.row is not None
    assert draft_store.row["created_by_user_id"] == draft_store.row["updated_by_user_id"] == 77

    changed = _built_in()
    changed["preamble_ru"] += " Проверка."
    saved = draft_service.save_draft(EDITABLE_TYPE, 1, changed, actor_user_id=99)
    no_op = draft_service.save_draft(EDITABLE_TYPE, 2, changed, actor_user_id=100)
    assert saved["revision"] == no_op["revision"] == 2
    assert draft_store.row["updated_by_user_id"] == 99

    with pytest.raises(TemplateDraftError) as conflict:
        draft_service.save_draft(EDITABLE_TYPE, 1, changed, actor_user_id=101)
    assert conflict.value.code == "TEMPLATE_REVISION_CONFLICT"
    assert conflict.value.conflict is True
    assert admin_router._template_draft_error(conflict.value).status_code == 409
    assert all("personnel_order_template_versions" in sql for sql in draft_store.statements)
    assert not any(word in "\n".join(draft_store.statements).lower() for word in ("personnel_orders", "employee_events", "assignments"))


def test_template_text_rejects_html_script_and_expressions() -> None:
    for unsafe in ("<script>alert(1)</script>", "javascript:alert(1)", "{{if(test)}}", "value => value"):
        values = _built_in()
        values["title_ru"] = unsafe
        with pytest.raises(TemplateDraftError) as rejected:
            _validate(values)
        assert rejected.value.code == "TEMPLATE_TEXT_UNSAFE"


def test_router_derives_actor_from_admin_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int]] = []
    monkeypatch.setattr(admin_router, "create_draft", lambda item_type_code, actor_user_id: seen.append((item_type_code, actor_user_id)) or {"ok": True})

    assert admin_router.admin_create_personnel_order_template_draft(EDITABLE_TYPE, {"user_id": 42}) == {"ok": True}
    assert seen == [(EDITABLE_TYPE, 42)]


def test_preview_endpoint_accepts_the_complete_built_in_draft_shape() -> None:
    """The actual HTTP endpoint accepts the same eight typed fields as a new DRAFT."""
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    try:
        response = TestClient(app).post(f"/admin/personnel-order-templates/{EDITABLE_TYPE}/draft/preview", json=_built_in())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()["previews"]) == {"ru", "kk"}
