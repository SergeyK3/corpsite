"""Rollback-only local checks using copies of existing published templates.

COMPOSITE_TEMPLATE_SOURCE_URL is an explicit, read-only local catalog source.
No template authoring/publication service, registration or HR apply is called.
"""
from contextlib import nullcontext
from datetime import date
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.services import personnel_order_add_item_service as additions
from app.services import personnel_order_manual_draft_service as manual
from app.services import personnel_order_template_application_service as applications
from app.services import personnel_orders_command_service as commands
from app.services import personnel_orders_query_service as queries
from app.services.personnel_orders_editorial import generation_service as generation, service as editorial
from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT, SAMPLE_REPLACEMENT, variant
from app.services.personnel_order_service_area_contract import SAMPLE_RECIPIENT, enabled


def local_test_url():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("requires explicit local corpsite_test")
    url = make_url(raw)
    assert url.host in ("localhost", "127.0.0.1") and url.database == "corpsite_test"
    return url


@pytest.fixture(autouse=True)
def _cleanup_orphan_hr_baseline_artifacts():
    # Override unrelated global cleanup: this suite must only roll back its work.
    yield


@pytest.fixture(scope="module")
def published_catalog():
    raw = os.environ.get("COMPOSITE_TEMPLATE_SOURCE_URL")
    if not raw:
        pytest.skip("requires an explicit read-only local published catalog")
    url = make_url(raw)
    assert url.host in ("localhost", "127.0.0.1") and url.database == "corpsite"
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = conn.execute(text("SELECT v.*,t.name_ru,t.name_kk FROM personnel_order_template_versions v JOIN personnel_order_templates t USING(template_id) WHERE (v.status='PUBLISHED' AND v.item_type_code IN ('TRANSFER','CONCURRENT_DUTY_START','SUPPLEMENTARY_PAY')) OR (v.status='ARCHIVED' AND v.item_type_code='TRANSFER' AND v.template_version_id=(SELECT max(template_version_id) FROM personnel_order_template_versions WHERE status='ARCHIVED' AND item_type_code='TRANSFER')) ORDER BY v.template_version_id")).mappings().all()
            for code in ("TRANSFER", "CONCURRENT_DUTY_START", "SUPPLEMENTARY_PAY"):
                assert any(row["item_type_code"] == code and row["status"] == "PUBLISHED" for row in rows), f"No existing published {code}; stop and resolve the catalog."
            return [dict(row) for row in rows]
    finally:
        engine.dispose()


@pytest.fixture
def database(monkeypatch, published_catalog):
    from app.services import personnel_order_document_header_service as headers
    engine = create_engine(local_test_url(), hide_parameters=True)
    protected = ("personnel_orders", "personnel_order_items", "personnel_order_template_versions", "personnel_order_templates", "personnel_order_template_applications", "personnel_order_editorial_blocks", "personnel_order_item_editorial_blocks", "employees", "employee_events", "person_assignments")

    def snapshot(conn):
        return {table: conn.execute(text(f"SELECT md5(COALESCE(string_agg(to_jsonb(t)::text, '' ORDER BY to_jsonb(t)::text), '')) FROM {table} t")).scalar_one() for table in protected}

    with engine.connect() as conn:
        before = snapshot(conn)
        conn.rollback()
        tx = conn.begin()
        try:
            actor = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
            employee = conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")).scalar_one()
            versions = []
            for source in published_catalog:
                # Transient copies of existing texts, never newly authored templates.
                identity = conn.execute(text("INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk,is_default) VALUES(:item_type_code,:name_ru,:name_kk,false) RETURNING template_id"), source).scalar_one()
                fields = applications._FIELDS
                params = {**{key: source[key] for key in fields}, "type": source["item_type_code"], "number": source["version_number"], "identity": identity, "status": source["status"]}
                version = conn.execute(text(f"INSERT INTO personnel_order_template_versions(template_id,item_type_code,version_number,status,{','.join(fields)}) VALUES(:identity,:type,:number,:status,{','.join(':'+key for key in fields)}) RETURNING template_version_id"), params).scalar_one()
                versions.append({**source, "template_version_id": version, "template_id": identity})

            class TransactionEngine:
                def begin(self): return nullcontext(conn)
                def connect(self): return nullcontext(conn)

            adapter = TransactionEngine()
            for module in (additions, manual, applications, commands, queries, generation, editorial, headers):
                monkeypatch.setattr(module, "engine", adapter)
            yield conn, actor, employee, versions
        finally:
            tx.rollback()
            assert snapshot(conn) == before, "Rollback must preserve existing orders, templates and HR data."
    engine.dispose()


def payload(code, template=None):
    if code == "TRANSFER":
        return {"transfer": {"position_ru": "врач", "position_kk": "дәрігер", "org_unit_ru": "Терапия", "org_unit_kk": "Терапия", "rate": 1, "basis_ru": "Заявление о переводе", "basis_kk": "Ауыстыру туралы өтініш"}}
    if code == "SUPPLEMENTARY_PAY":
        return {"allowance_recipient": dict(SAMPLE_RECIPIENT), "allowance": {"percent": 25, "employee_dative_ru": "Тестовому Сотруднику", "employee_dative_kk": "Сынақ Қызметкеріне", "basis_ru": "Личное заявление", "basis_kk": "Жеке өтініш"}}
    data = {"concurrent": {**SAMPLE_CONCURRENT, "rate": 0.25, "total_rate": 1.25}}
    if variant(template):
        data["replacement"] = {**SAMPLE_REPLACEMENT, "end_date": "2026-12-31"}
    if enabled(template):
        data.update(allowance_recipient=dict(SAMPLE_RECIPIENT), replacement={"term_type": "NONE", "allowance_percent": 25})
    return data


def create_draft(database, first_type="TRANSFER"):
    conn, actor, employee, versions = database
    template = next(row for row in versions if row["item_type_code"] == first_type and row["status"] == "PUBLISHED")
    order = manual.create_manual_draft(created_by=actor, template_version_id=template["template_version_id"], order_number="COMPOSITE-TEST-" + uuid4().hex, order_date=date(2026, 10, 21), source_title=template["title_ru"], source_title_locale="ru", item_type_code=first_type, employee_id=employee, effective_date=date(2026, 10, 21), item_payload=payload(first_type, template))
    return order["order_id"], template


def add(database, order_id, template):
    _, actor, employee, _ = database
    return commands.create_personnel_order_item(order_id=order_id, item_type_code=template["item_type_code"], template_version_id=template["template_version_id"], employee_id=employee, effective_date=date(2026, 10, 21), payload=payload(template["item_type_code"], template), actor_user_id=actor)


def saved_blocks(conn, order_id):
    return [dict(row) for row in conn.execute(text("SELECT 'ORDER' scope,NULL::bigint item_id,locale,block_type,generated_text,override_text,revision FROM personnel_order_editorial_blocks WHERE order_id=:id UNION ALL SELECT 'ITEM',b.order_item_id,b.locale,b.block_type,b.generated_text,b.override_text,b.revision FROM personnel_order_item_editorial_blocks b JOIN personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id ORDER BY scope,item_id,locale,block_type"), {"id": order_id}).mappings()]


@pytest.mark.parametrize("second_code,mode", [("SUPPLEMENTARY_PAY", None), ("CONCURRENT_DUTY_START", None), ("CONCURRENT_DUTY_START", "RATE"), ("CONCURRENT_DUTY_START", "PAY")])
def test_combined_preview_apply_regenerate_ru_kk(database, second_code, mode):
    conn, actor, employee, versions = database
    order_id, first_template = create_draft(database)
    before = saved_blocks(conn, order_id)
    second_template = next(row for row in versions if row["item_type_code"] == second_code and row["status"] == "PUBLISHED" and (variant(row) or None) == mode)
    detail = add(database, order_id, second_template)
    assert detail["order"]["order_type_code"] == "COMPOSITE"
    assert [item["employee_id"] for item in detail["items"]] == [employee, employee]
    assert {item["item_type_code"] for item in detail["items"]} == {"TRANSFER", second_code}
    first_id, second_id = [item["item_id"] for item in detail["items"]]
    assert [block for block in saved_blocks(conn, order_id) if block["item_id"] != second_id] == before
    assert additions.get_add_item_context(order_id)["default_employee_id"] == employee

    before_preview = saved_blocks(conn, order_id)
    audit_before = conn.execute(text("SELECT count(*) FROM personnel_order_template_applications WHERE order_id=:id"), {"id": order_id}).scalar_one()
    preview = applications.preview_template_application(order_id)
    assert saved_blocks(conn, order_id) == before_preview
    assert conn.execute(text("SELECT count(*) FROM personnel_order_template_applications WHERE order_id=:id"), {"id": order_id}).scalar_one() == audit_before
    assert not any(entry["blocked"] for entry in preview["items"])
    assert [entry["template"]["template_version_id"] for entry in preview["items"]] == [first_template["template_version_id"], second_template["template_version_id"]]
    for locale in ("ru", "kk"):
        assert preview["order_proposed"][f"title_{locale}"] == first_template[f"title_{locale}"]
        for entry in preview["items"]:
            body = entry["proposed"][f"body_{locale}"]
            assert body and "{{" not in body and "[[" not in body
        assert preview["items"][0]["proposed"][f"body_{locale}"] != preview["items"][1]["proposed"][f"body_{locale}"]

    applications.apply_template_application(order_id, actor, expected_document_revision=preview["order_revision"], confirm_reapply=True)
    for entry in preview["items"]:
        for locale in ("ru", "kk"):
            actual = conn.execute(text("SELECT generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:id AND locale=:locale AND block_type='body'"), {"id": entry["order_item_id"], "locale": locale}).scalar_one()
            assert actual == entry["proposed"][f"body_{locale}"]
    conn.execute(text("UPDATE personnel_order_item_editorial_blocks SET override_text='Ручная правка' WHERE order_item_id=:id AND locale='ru' AND block_type='body'"), {"id": second_id})
    conn.execute(text("UPDATE personnel_order_editorial_blocks SET override_text='Общий заголовок' WHERE order_id=:id AND locale='ru' AND block_type='title'"), {"id": order_id})
    generation.generate_editorial(order_id, user_id=actor, conn=conn)
    after = saved_blocks(conn, order_id)
    assert next(row for row in after if row["item_id"] == second_id and row["locale"] == "ru" and row["block_type"] == "body")["override_text"] == "Ручная правка"
    assert next(row for row in after if row["scope"] == "ORDER" and row["locale"] == "ru" and row["block_type"] == "title")["override_text"] == "Общий заголовок"
    refreshed = applications.preview_template_application(order_id)
    assert [entry["template"] for entry in refreshed["items"]] == [entry["template"] for entry in preview["items"]]
    assert len([row for row in after if row["scope"] == "ORDER" and row["block_type"] == "title"]) == 2
    assert len([row for row in after if row["scope"] == "ORDER" and row["block_type"] == "preamble"]) == 2
    with pytest.raises(applications.TemplateApplicationError, match="overrides"):
        applications.apply_template_application(order_id, actor, expected_document_revision=refreshed["order_revision"], confirm_reapply=True)
    output_dir = os.environ.get("COMPOSITE_PRINT_FIXTURE_DIR")
    if output_dir:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        fixture = {"detail": queries.get_personnel_order(order_id), "editorial": editorial.get_editorial_state(order_id)}
        (target / f"{second_code}-{mode or 'simple'}.json").write_text(json.dumps(fixture, ensure_ascii=False, default=str), encoding="utf-8")


def test_same_type_same_employee_and_exact_version(database):
    conn, actor, _, _ = database
    order_id, template = create_draft(database, "SUPPLEMENTARY_PAY")
    detail = add(database, order_id, template)
    assert detail["order"]["order_type_code"] == "SUPPLEMENTARY_PAY"
    generation.generate_editorial(order_id, user_id=actor, conn=conn)
    preview = applications.preview_template_application(order_id)
    assert len(preview["items"]) == 2
    assert all(entry["template"]["template_version_id"] == template["template_version_id"] for entry in preview["items"])


def test_archived_binding_survives_a_different_current_publication(database):
    conn, actor, _, versions = database
    order_id, published = create_draft(database)
    archived = next(row for row in versions if row["item_type_code"] == "TRANSFER" and row["status"] == "ARCHIVED")
    # Simulate the history of this newly created test draft. Template rows
    # remain unchanged; an already archived catalog version is used verbatim.
    conn.execute(text("UPDATE personnel_orders SET selected_template_version_id=:version WHERE order_id=:id"), {"version": archived["template_version_id"], "id": order_id})
    conn.execute(text("INSERT INTO personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id) SELECT order_id,order_item_id,:version,CAST(:snapshot AS jsonb),rendered_snapshot,previous_editorial_blocks,applied_by_user_id FROM personnel_order_template_applications WHERE order_id=:id ORDER BY template_application_id DESC LIMIT 1"), {"version": archived["template_version_id"], "id": order_id, "snapshot": json.dumps({key: archived[key] for key in applications._FIELDS}, ensure_ascii=False)})
    pay = next(row for row in versions if row["item_type_code"] == "SUPPLEMENTARY_PAY")
    detail = add(database, order_id, pay)
    generation.generate_editorial(order_id, user_id=actor, conn=conn)
    preview = applications.preview_template_application(order_id)
    assert preview["items"][0]["template"]["template_version_id"] == archived["template_version_id"] != published["template_version_id"]
    assert preview["items"][1]["template"]["template_version_id"] == pay["template_version_id"]
    assert not any(entry["blocked"] for entry in preview["items"])
    assert detail["order"]["status"] == "DRAFT"


def test_same_type_different_versions_and_other_employee(database):
    conn, actor, employee, versions = database
    order_id, first = create_draft(database, "CONCURRENT_DUTY_START")
    second = next(row for row in versions if row["item_type_code"] == "CONCURRENT_DUTY_START" and row["status"] == "PUBLISHED" and row["template_version_id"] != first["template_version_id"])
    other = conn.execute(text("SELECT employee_id FROM employees WHERE employee_id<>:id ORDER BY employee_id LIMIT 1"), {"id": employee}).scalar_one()
    commands.create_personnel_order_item(order_id=order_id, item_type_code=second["item_type_code"], template_version_id=second["template_version_id"], employee_id=other, effective_date=date(2026, 10, 21), payload=payload(second["item_type_code"], second), actor_user_id=actor)
    generation.generate_editorial(order_id, user_id=actor, conn=conn)
    preview = applications.preview_template_application(order_id)
    assert [entry["template"]["template_version_id"] for entry in preview["items"]] == [first["template_version_id"], second["template_version_id"]]
    assert not any(entry["blocked"] for entry in preview["items"])


def test_legacy_binding_without_header_pin(database):
    conn, actor, employee, _ = database
    order_id, template = create_draft(database, "SUPPLEMENTARY_PAY")
    conn.execute(text("UPDATE personnel_orders SET selected_template_version_id=NULL WHERE order_id=:id"), {"id": order_id})
    detail = commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employee, effective_date=date(2026, 10, 21), payload=payload("SUPPLEMENTARY_PAY"), actor_user_id=actor)
    generation.generate_editorial(order_id, user_id=actor, conn=conn)
    preview = applications.preview_template_application(order_id)
    assert len(detail["items"]) == 2
    assert all(entry["template"]["template_version_id"] == template["template_version_id"] for entry in preview["items"])


@pytest.mark.parametrize("problem", ["wrong_type", "missing_fields", "wrong_revision", "audit_failure"])
def test_failures_are_atomic(database, monkeypatch, problem):
    conn, actor, employee, versions = database
    order_id, first = create_draft(database)
    second = next(row for row in versions if row["item_type_code"] == "SUPPLEMENTARY_PAY")
    before = saved_blocks(conn, order_id)
    # The service normally owns a transaction; savepoint reproduces its rollback
    # while retaining this fixture's outer transaction.
    with pytest.raises((queries.PersonnelOrderValidationError, applications.TemplateApplicationError, RuntimeError)):
        with conn.begin_nested():
            if problem in ("wrong_type", "missing_fields"):
                commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", template_version_id=first["template_version_id"] if problem == "wrong_type" else second["template_version_id"], employee_id=employee, effective_date=date(2026, 10, 21), payload={})
            else:
                add(database, order_id, second)
                preview = applications.preview_template_application(order_id)
                if problem == "audit_failure":
                    def fail(): raise RuntimeError("audit failpoint")
                    monkeypatch.setattr(applications, "AUDIT_INSERT_HOOK", fail)
                applications.apply_template_application(order_id, actor, expected_document_revision=999 if problem == "wrong_revision" else preview["order_revision"], confirm_reapply=True)
    assert saved_blocks(conn, order_id) == before
    assert conn.execute(text("SELECT count(*) FROM personnel_order_items WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
