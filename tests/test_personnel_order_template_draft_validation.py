from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import admin_router
from app.main import app
from app.security.admin_guard import require_sysadmin_api
from app.services import personnel_order_template_draft_service as draft_service
from app.db.models.personnel_orders import ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE
from app.services.personnel_order_template_draft_service import EDITABLE_TYPE, TemplateDraftError, _validate, preview_draft
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_initial_data import INITIAL_TEXTS_BY_TYPE


def _initial_texts(item_type_code: str = EDITABLE_TYPE) -> dict[str, str]:
    return dict(get_personnel_order_template_spec(item_type_code).initial_texts)


def test_readable_initial_texts_match_the_ten_type_golden_snapshot() -> None:
    expected_hashes = {
        "HIRE": "96444278a247538672dfb544559359d08cc3b54e0de182d2d3fb0617320658fa",
        "TRANSFER": "3a6d711e7484839479a98697da7e91a6a2f27b5fab315ad38c3f295722005995",
        "TERMINATION": "bc34ed5af9bbc3e3e1fd7dd874aeebecc9b2d2b918692526c59abaabfc2c78a2",
        "CONCURRENT_DUTY_START": "6d3af87099855f0270cc9c015e24fa44dfc98bcd8ea7f7ebccb2848dd77fcdce",
        "CONCURRENT_DUTY_END": "6f9dc6cd6a6424d061d1d154142e18a4f02bdaaaa581f2d3fb96370bade07fc0",
        "LEAVE.ANNUAL.GRANT": "9ac3b1e220d4f174350626cb65d97949abcdce9ddadb6ba02c4846242e7bb96d",
        "LEAVE.UNPAID.GRANT": "df3b6b2c648e392e99cba29ce45ed9f15272f50e253420d4a37f0b62f13a3eed",
        "LEAVE.CHILDCARE.GRANT": "ae26f701f695f8b5e92f1ff613463656098ad7bad746791ad617978c4df5d088",
        "SUPPLEMENTARY_PAY": "bc5b0cfcb36a7bd4606ac327c896268ab020bc959a4ccdeb8ebde5d9a1cbad54",
        "RETURN_FROM_CHILDCARE_LEAVE": "bf6c0f6daf69edbf77df33015aedc20d253e15d68c84ad9f6c743edb41c7c3e3",
    }
    expected_fields = {"title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk"}
    assert set(INITIAL_TEXTS_BY_TYPE) == set(expected_hashes)
    assert all(set(values) == expected_fields for values in INITIAL_TEXTS_BY_TYPE.values())
    actual_hashes = {
        item_type_code: hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for item_type_code, values in INITIAL_TEXTS_BY_TYPE.items()
    }
    assert actual_hashes == expected_hashes
    registry_source = Path("app/services/personnel_order_template_specs.py").read_text(encoding="utf-8")
    assert all(token not in registry_source for token in ("_INITIAL_TEXTS_B85", "b85decode", "base64"))


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
                **{key: values[key] for key in _initial_texts()},
                "based_on_built_in": True,
                "created_at": now,
                "updated_at": now,
                "created_by_user_id": values["actor"],
                "updated_by_user_id": values["actor"],
            }
            return _Result(self.row)
        assert sql.lstrip().startswith("UPDATE")
        assert self.row is not None
        self.row.update({key: values[key] for key in _initial_texts()})
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
    values = _initial_texts()
    _validate(values)
    preview = preview_draft(EDITABLE_TYPE, values)
    assert preview["ru"]["directive"] == "ПРИКАЗЫВАЮ:"
    assert preview["kk"]["directive"] == "БҰЙЫРАМЫН:"
    assert "{{" not in preview["ru"]["body"]


def test_unpaid_template_rejects_unknown_and_missing_required_variables() -> None:
    values = _initial_texts()
    values["body_template_ru"] += " {{unknown.value}}"
    with pytest.raises(TemplateDraftError, match="Неизвестная"):
        _validate(values)
    values = _initial_texts()
    values["body_template_ru"] = values["body_template_ru"].replace("{{leave.days}}", "")
    with pytest.raises(TemplateDraftError, match="обязательные"):
        _validate(values)


def test_childcare_return_uses_its_typed_catalog_variables_and_renders_neutral_rate_and_return_date() -> None:
    values = _initial_texts(ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE)
    _validate(values, ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE)
    preview = preview_draft(ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE, values)

    assert "{{" not in " ".join(str(value) for locale in preview.values() for value in locale.values())
    preview_text = " ".join(str(item) for locale in preview.values() for item in locale.values())
    assert all(value in preview["ru"]["body"] for value in ("[[ФИО сотрудника]]", "[[Должность]]", "[[Подразделение]]", "[[Дата выхода]]", "[[Ставка]]"))
    assert all(value in preview["kk"]["body"] for value in ("[[Қызметкердің аты-жөні]]", "[[Лауазым]]", "[[Бөлімше]]", "[[Жұмысқа шығу күні]]", "[[Мөлшерлеме]]"))
    assert all(value not in preview_text for value in ("1.0", "15 января 2026", "2026 жылғы 15 қаңтар", "««", "»»"))
    invalid = dict(values)
    invalid["body_template_ru"] += " {{specialty}}"
    with pytest.raises(TemplateDraftError) as error:
        _validate(invalid, ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE)
    assert error.value.code == "TEMPLATE_VARIABLE_UNKNOWN"


def test_unpaid_leave_draft_preview_uses_unquoted_technical_placeholders() -> None:
    preview = preview_draft(EDITABLE_TYPE, _initial_texts(EDITABLE_TYPE))
    preview_text = " ".join(str(item) for locale in preview.values() for item in locale.values())

    assert all(value in preview["ru"]["body"] for value in ("[[ФИО сотрудника в дательном падеже]]", "[[Должность в именительном падеже]]", "[[Подразделение]]", "7 июля 2026 года", "[[Количество дней]]"))
    assert all(value in preview["kk"]["body"] for value in ("[[Бөлімшенің құжаттық нысаны]]", "[[Лауазымның құжаттық нысаны]]", "[[Қызметкердің барыс септігі]]", "2026 жылғы 7 шілде күніне"))
    assert "[[Қызметкердің ілік септігі]]" in preview["kk"]["basis"]
    assert "[[Дата заявления]]" in preview["ru"]["basis"]
    assert all(value not in preview_text for value in ("1.0", "15 января 2026", "2026 жылғы 15 қаңтар", "««", "»»"))


def test_childcare_return_create_load_save_noop_and_conflict_do_not_touch_personnel_data(draft_store: _DraftStore) -> None:
    item_type = ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE
    created = draft_service.create_draft_from_working_copy(item_type, "INITIAL", None, None, _initial_texts(item_type), actor_user_id=77)
    assert created["item_type_code"] == item_type
    assert draft_service.get_draft(item_type)["template_version_id"] == created["template_version_id"]
    assert draft_store.insert_count == 1

    changed = _initial_texts(item_type)
    changed["title_ru"] += " Проверка"
    assert draft_service.save_draft(item_type, 1, changed, actor_user_id=99)["revision"] == 2
    assert draft_service.save_draft(item_type, 2, changed, actor_user_id=100)["revision"] == 2
    with pytest.raises(TemplateDraftError) as conflict:
        draft_service.save_draft(item_type, 1, changed, actor_user_id=101)
    assert conflict.value.code == "TEMPLATE_REVISION_CONFLICT"
    statements = "\n".join(draft_store.statements).lower()
    assert "personnel_order_template_versions" in statements
    assert not any(name in statements for name in ("personnel_orders", "personnel_order_items", "employee_events", "assignments"))


def test_termination_save_uses_safe_required_lookup_and_succeeds(draft_store: _DraftStore) -> None:
    """Regression: TERMINATION was absent from _REQUIRED_BY_TYPE and save raised KeyError."""
    item_type = "TERMINATION"
    created = draft_service.create_draft_from_working_copy(item_type, "INITIAL", None, None, _initial_texts(item_type), actor_user_id=77)
    values = _initial_texts(item_type)
    values["body_template_ru"] += "\nПроверка сохранения."

    saved = draft_service.save_draft(item_type, created["revision"], values, actor_user_id=77)

    assert saved["revision"] == created["revision"] + 1
    assert draft_service.get_draft(item_type)["body_template_ru"] == values["body_template_ru"]


def test_legacy_termination_without_unused_leave_days_still_previews() -> None:
    """Existing DRAFT text may predate the optional settlement paragraph."""
    values = _initial_texts("TERMINATION")
    values["body_template_ru"] = values["body_template_ru"].split("\n\n", 1)[0]
    values["body_template_kk"] = values["body_template_kk"].split("\n\n", 1)[0]

    preview = preview_draft("TERMINATION", values)

    assert "termination_unused_leave_days" not in values["body_template_ru"]
    assert "termination_unused_leave_days" not in values["body_template_kk"]
    assert "Количество дней неиспользованного отпуска" not in preview["ru"]["body"]
    assert "Пайдаланылмаған демалыс күндерінің саны" not in preview["kk"]["body"]


def test_termination_draft_body_uses_contract_termination_wording_without_basis_or_leave_settlement() -> None:
    values = _initial_texts("TERMINATION")
    values.update({
        "title_ru": "О расторжении трудового договора",
        "title_kk": "Еңбек шартын бұзу туралы",
        "body_template_ru": (
            "Уволить сотрудника {{employee.full_name}}, должность: {{position.title_ru}}, "
            "отделение: {{org_unit.title_ru}}, с {{effective_date_local}}. "
            "Причина увольнения: {{termination.reason}}."
        ),
        "body_template_kk": (
            "Қызметкер {{employee.full_name}}, лауазымы: {{position.title_kk}}, "
            "бөлімшесі: {{org_unit.title_kk}}, {{effective_date_local}} бастап жұмыстан босатылсын. "
            "Жұмыстан босату себебі: {{termination.reason}}."
        ),
        "basis_template_ru": "Личное заявление",
        "basis_template_kk": "Жеке өтініш",
    })

    _validate(values, "TERMINATION")
    preview = preview_draft("TERMINATION", values)

    assert "уволить сотрудника" in preview["ru"]["body"].casefold()
    assert "Основание:" not in preview["ru"]["body"]
    assert "Личное заявление" not in preview["ru"]["body"]
    assert "жұмыстан босатылсын" in preview["kk"]["body"]
    assert "Негіздеме:" not in preview["kk"]["body"]
    assert "Жеке өтініш" not in preview["kk"]["body"]
    assert "пайдаланылмаған" not in preview["kk"]["body"].casefold()
    assert preview["ru"]["basis"] == "Личное заявление"
    assert preview["kk"]["basis"] == "Жеке өтініш"


def test_termination_draft_http_save_reload_noop_conflict_and_preview(draft_store: _DraftStore) -> None:
    """Exercise the real router/service path that previously returned a KeyError/500."""
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    client = TestClient(app)
    path = "/admin/personnel-order-templates/TERMINATION/draft"
    try:
        # Existing persisted DRAFTs continue through the PUT revision contract;
        # first working-copy creation has its own typed POST contract.
        initial = draft_service.create_draft_from_working_copy("TERMINATION", "INITIAL", None, None, _initial_texts("TERMINATION"), actor_user_id=2)
        payload = _initial_texts("TERMINATION")
        for field in tuple(payload):
            payload[field] += f"\nПроверка полного снимка {field}."
        payload["expected_revision"] = initial["revision"]

        saved = client.put(path, json=payload)
        assert saved.status_code == 200
        assert saved.json()["revision"] == initial["revision"] + 1
        assert set(payload) == {*_initial_texts("TERMINATION"), "expected_revision"}
        loaded = client.get(path)
        assert loaded.status_code == 200
        assert all(loaded.json()[field] == payload[field] for field in _initial_texts("TERMINATION"))

        payload["expected_revision"] = saved.json()["revision"]
        no_op = client.put(path, json=payload)
        assert no_op.status_code == 200
        assert no_op.json()["revision"] == saved.json()["revision"]

        payload["expected_revision"] = initial["revision"]
        conflict = client.put(path, json=payload)
        assert conflict.status_code == 409
        assert all(client.get(path).json()[field] == saved.json()[field] for field in _initial_texts("TERMINATION"))

        revision_before_preview = client.get(path).json()["revision"]
        preview = client.post(f"{path}/preview", json=_initial_texts("TERMINATION"))
        assert preview.status_code == 200
        assert client.get(path).json()["revision"] == revision_before_preview
        ru, kk = preview.json()["previews"].values()
        assert all(token in ru["body"] for token in ("[[ФИО сотрудника]]", "[[Должность]]", "[[Подразделение]]", "[[Дата увольнения]]", "[[Количество дней неиспользованного отпуска]]"))
        assert all(token in kk["body"] for token in ("[[Лауазым]]", "[[Бөлімше]]", "[[Жұмыстан босату күні]]", "[[Пайдаланылмаған демалыс күндерінің саны]]", "еңбек шарты", "бұзылсын"))
        assert "29" not in f"{ru['body']} {kk['body']}"
        assert "Основание:" not in ru["body"]
        assert "Негіздеме:" not in kk["body"]
        assert ru["basis"].count("Основание:") == 1
        assert kk["basis"].count("Негіз:") == 1
    finally:
        app.dependency_overrides.clear()
def test_template_editor_is_unavailable_for_composite_header_type() -> None:
    with pytest.raises(TemplateDraftError) as error:
        preview_draft("COMPOSITE", _initial_texts())
    assert error.value.code == "TEMPLATE_EDITOR_NOT_AVAILABLE"


def test_draft_create_load_save_noop_and_conflict_are_isolated_to_template_versions(draft_store: _DraftStore) -> None:
    created = draft_service.create_draft_from_working_copy(EDITABLE_TYPE, "INITIAL", None, None, _initial_texts(), actor_user_id=77)
    loaded = draft_service.get_draft(EDITABLE_TYPE)

    assert created["template_version_id"] == loaded["template_version_id"]
    assert draft_store.insert_count == 1
    assert draft_store.row is not None
    assert draft_store.row["created_by_user_id"] == draft_store.row["updated_by_user_id"] == 77

    changed = _initial_texts()
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


@pytest.mark.parametrize("item_type", (EDITABLE_TYPE, "HIRE"))
def test_common_draft_flow_has_the_same_load_save_preview_and_revision_contract_for_each_type(
    draft_store: _DraftStore, item_type: str,
) -> None:
    created = draft_service.create_draft_from_working_copy(item_type, "INITIAL", None, None, _initial_texts(item_type), actor_user_id=77)
    values = _initial_texts(item_type)
    values["title_ru"] += " Проверка общего потока."

    assert draft_service.get_draft(item_type)["template_version_id"] == created["template_version_id"]
    assert set(preview_draft(item_type, values)) == {"ru", "kk"}
    saved = draft_service.save_draft(item_type, created["revision"], values, actor_user_id=78)
    assert saved["revision"] == created["revision"] + 1
    assert draft_service.save_draft(item_type, saved["revision"], values, actor_user_id=79)["revision"] == saved["revision"]
    with pytest.raises(TemplateDraftError) as conflict:
        draft_service.save_draft(item_type, created["revision"], values, actor_user_id=80)
    assert conflict.value.code == "TEMPLATE_REVISION_CONFLICT"


def test_template_text_rejects_html_script_and_expressions() -> None:
    for unsafe in ("<script>alert(1)</script>", "javascript:alert(1)", "{{if(test)}}", "value => value"):
        values = _initial_texts()
        values["title_ru"] = unsafe
        with pytest.raises(TemplateDraftError) as rejected:
            _validate(values)
        assert rejected.value.code == "TEMPLATE_TEXT_UNSAFE"


def test_router_derives_actor_from_admin_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int, int, int]] = []
    values = _initial_texts()
    monkeypatch.setattr(admin_router, "create_draft_from_working_copy", lambda item_type_code, source, base_id, base_revision, payload, actor: seen.append((item_type_code, base_id, base_revision, actor)) or {"ok": True})
    from app.api.admin_schemas import PersonnelOrderTemplateWorkingCopySave
    body = PersonnelOrderTemplateWorkingCopySave(**values, base_source="PUBLISHED", base_published_template_version_id=7, base_published_revision=3)
    assert admin_router.admin_create_personnel_order_template_draft(EDITABLE_TYPE, body, {"user_id": 42}) == {"ok": True}
    assert seen == [(EDITABLE_TYPE, 7, 3, 42)]


def test_preview_endpoint_accepts_the_complete_initial_texts_draft_shape() -> None:
    """The actual HTTP endpoint accepts the same eight typed fields as a new DRAFT."""
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    try:
        response = TestClient(app).post(f"/admin/personnel-order-templates/{EDITABLE_TYPE}/draft/preview", json=_initial_texts())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()["previews"]) == {"ru", "kk"}
