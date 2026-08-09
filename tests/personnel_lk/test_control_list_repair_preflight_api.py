"""Narrow API tests for ADR-065 exact-IIN repair preflight."""
from __future__ import annotations

import json
import hashlib
import hmac
import logging
import struct
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import engine
from app.main import app
from app.personnel_lk.application.personnel_order_evidence_fingerprint import (
    EvidenceKeySnapshot,
    configure_evidence_key_provider,
)
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.personnel_lk.conftest import (
    load_org_fixture,
    require_personnel_lk_schema,
    seed_user_id,
    unique_iin,
)
from tests.personnel_applications.conftest import insert_person_with_iin
from tests.ppr.conftest import insert_employee, ppr_db_available

ROUTE = "/directory/personnel/lk/control-list-repair/preflight"
TEST_ORG_SCOPE = "corpsite-test"
TEST_KEY_ID = "test-key-v1"
TEST_COLUMN_KEY = bytes(range(32))
TEST_OUTER_KEY = bytes(range(32, 64))


class _FixtureKeyProvider:
    def __init__(self, state="ACTIVE", returned_key_id=None):
        self.state = state
        self.returned_key_id = returned_key_id

    def resolve_verification_key(self, **kwargs):
        return EvidenceKeySnapshot(
            organization_scope_id=kwargs["organization_scope_id"],
            profile_id=kwargs["profile_id"],
            profile_version=kwargs["profile_version"],
            key_id=self.returned_key_id or kwargs["key_id"],
            state=self.state,
            column_hmac_key=TEST_COLUMN_KEY,
            outer_hmac_key=TEST_OUTER_KEY,
        )


@pytest.fixture
def evidence_key_provider(monkeypatch):
    monkeypatch.setenv("ADR065_ORGANIZATION_SCOPE_ID", TEST_ORG_SCOPE)
    configure_evidence_key_provider(_FixtureKeyProvider())
    try:
        yield
    finally:
        configure_evidence_key_provider(None)


def _fixture_lp(value: bytes) -> bytes:
    return struct.pack(">Q", len(value)) + value


def _fixture_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _fixture_tv(value) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, bool):
        return b"B" + (b"\x01" if value else b"\x00")
    if isinstance(value, int):
        return b"I" + _fixture_lp(str(value).encode("ascii"))
    if isinstance(value, datetime):
        return b"t" + _fixture_lp(_fixture_timestamp(value).encode("ascii"))
    if isinstance(value, date):
        return b"d" + _fixture_lp(value.isoformat().encode("ascii"))
    if isinstance(value, str):
        return b"s" + _fixture_lp(value.encode("utf-8"))
    if isinstance(value, (dict, list)):
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return b"j" + _fixture_lp(encoded)
    raise AssertionError(type(value))


def _fixture_replacement(table: str, pk_name: str, pk: int, column: str, value):
    if value is None:
        return None
    message = (
        b"ADR065-PO-EVIDENCE-COLUMN\x00"
        + _fixture_lp(b"adr065-po-evidence") + _fixture_lp(b"1")
        + _fixture_lp(TEST_ORG_SCOPE.encode()) + _fixture_lp(TEST_KEY_ID.encode())
        + _fixture_lp(table.encode()) + _fixture_lp(pk_name.encode())
        + _fixture_lp(str(pk).encode()) + _fixture_lp(column.encode())
        + _fixture_lp(_fixture_tv(value))
    )
    return {"algorithm": "HMAC-SHA-256", "profile_id": "adr065-po-evidence",
            "profile_version": 1, "key_id": TEST_KEY_ID,
            "fingerprint": hmac.new(TEST_COLUMN_KEY, message, hashlib.sha256).hexdigest()}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture(scope='module')
def repair_schema():
    require_personnel_lk_schema()
    with engine.begin() as conn:
        required = (
            "employee_identities",
            "hr_import_batches",
            "hr_import_rows",
            "hr_import_normalized_records",
            "person_assignments",
        )
        required = required + (
            "person_assignment_activation_watermark",
            "personnel_order_evidence_scopes",
        )
        if any(not table_exists(conn, table) for table in required):
            pytest.skip("ADR-065 preflight dependencies are not migrated")
        watermark = conn.execute(text("SELECT effective_date FROM public.person_assignment_activation_watermark WHERE singleton IS TRUE")).scalar_one_or_none()
        current = conn.execute(text("SELECT ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date")).scalar_one()
        if watermark != current:
            pytest.skip("test DB activation watermark is not current")
    yield


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFC", " ".join(value.split()).casefold())


def _complete_intent(scenario: dict, *, evidence_type: str = "EXTERNAL_REFERENCE") -> dict:
    org = scenario["org"]
    assert org["org_unit_id"] is not None and org["position_id"] is not None
    if evidence_type == "PERSONNEL_ORDER":
        evidence = {
            "evidence_type": "PERSONNEL_ORDER",
            "personnel_order_id": scenario["personnel_order_id"],
            "evidence_record_id": scenario["personnel_order_item_id"],
            "evidence_profile_id": "adr065-po-evidence",
            "evidence_profile_version": 1,
            "evidence_key_id": "test-key-v1",
            "evidence_fingerprint": "b" * 64,
            "admissibility_confirmed": True,
        }
    else:
        evidence = {
            "evidence_type": "EXTERNAL_REFERENCE",
            "evidence_fingerprint": "a" * 64,
            "admissibility_confirmed": True,
        }
    return {
        "org_unit": {
            "org_unit_id": org["org_unit_id"],
            "org_unit_normalized_stable_code": scenario["org_code"],
            "operator_confirmed_normalized_org_name": scenario["org_name"],
        },
        "position": {
            "position_id": org["position_id"],
            "operator_confirmed_normalized_position_name": scenario["position_name"],
        },
        "rate": "1",
        "employment_type": "primary",
        "is_primary": True,
        "start_date": scenario["business_date"].isoformat(),
        "evidence": evidence,
        "reason_code": "EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED",
        "verifier_confirmation": {
            "verifier_user_id": scenario["user_id"],
            "confirmation_at": "2026-08-09T10:00:00Z",
            "confirmation_reference": "ADR065-PREFLIGHT-TEST",
        },
    }


def _fixture_personnel_order_fingerprint(conn, *, order_id: int, item_id: int) -> str:
    specs = (
        ("header", "personnel_orders", "order_id", ("order_id", "order_number", "order_date", "order_type_code", "order_class", "status", "source_mode", "legal_basis_article", "signed_by_employee_id", "signed_by_name", "signed_by_position", "executor_name", "basis_summary", "comment", "void_reason", "voided_at", "voided_by", "void_kind", "archived_at", "archived_by", "archive_reason_code", "archive_reason_text", "created_by", "created_at", "updated_at")),
        ("items", "personnel_order_items", "item_id", ("item_id", "order_id", "item_number", "item_type_code", "employee_id", "effective_date", "period_start", "period_end", "payload", "item_status", "void_reason", "voided_at", "voided_by", "created_at")),
        ("item_bases", "personnel_order_item_bases", "item_basis_id", ("item_basis_id", "order_item_id", "basis_type", "subject_employee_id", "document_date", "document_number", "free_text", "metadata", "created_at", "updated_at")),
        ("attachments", "personnel_order_attachments", "attachment_id", ("attachment_id", "order_id", "attachment_kind", "storage_type", "file_path", "file_url", "file_comment", "locale", "created_by", "created_at")),
    )
    protected = {
        "personnel_orders": {"basis_summary", "comment"},
        "personnel_order_items": {"payload"},
        "personnel_order_item_bases": {"free_text", "metadata"},
        "personnel_order_attachments": {"file_path", "file_url", "file_comment"},
    }
    sql = {
        "header": "SELECT * FROM public.personnel_orders WHERE order_id=:id ORDER BY order_id",
        "items": "SELECT * FROM public.personnel_order_items WHERE order_id=:id ORDER BY item_id",
        "item_bases": "SELECT b.* FROM public.personnel_order_item_bases b JOIN public.personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id ORDER BY b.item_basis_id",
        "attachments": "SELECT * FROM public.personnel_order_attachments WHERE order_id=:id ORDER BY attachment_id",
    }
    collections = {}
    for name, table, pk_name, columns in specs:
        rows = list(conn.execute(text(sql[name]), {"id": order_id}).mappings())
        tuples = []
        for row in rows:
            values = []
            for column in columns:
                value = row[column]
                if column in protected[table]:
                    value = _fixture_replacement(table, pk_name, int(row[pk_name]), column, value)
                elif isinstance(value, datetime):
                    value = _fixture_timestamp(value)
                elif isinstance(value, date):
                    value = value.isoformat()
                elif isinstance(value, int) and not isinstance(value, bool):
                    value = str(value)
                values.append(value)
            tuples.append(values)
        collections[name] = tuples
    generation = conn.execute(text("SELECT generation FROM public.personnel_order_evidence_scopes WHERE order_id=:id"), {"id": order_id}).scalar_one()
    envelope = {"algorithm": "HMAC-SHA-256", "profile_id": "adr065-po-evidence",
                "profile_version": 1, "key_id": TEST_KEY_ID,
                "organization_scope_id": TEST_ORG_SCOPE,
                "personnel_order_id": str(order_id),
                "selected_evidence_item_id": str(item_id),
                "evidence_scope_generation": str(generation), **collections}
    encoded = json.dumps(envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    message = (b"ADR065-PO-EVIDENCE-OUTER\x00" + _fixture_lp(b"adr065-po-evidence")
               + _fixture_lp(b"1") + _fixture_lp(TEST_ORG_SCOPE.encode())
               + _fixture_lp(TEST_KEY_ID.encode()) + _fixture_lp(encoded))
    return hmac.new(TEST_OUTER_KEY, message, hashlib.sha256).hexdigest()


@contextmanager
def _scenario(*, person_status: str | None = None, linked: bool = False):
    token = uuid4().hex[:10]
    iin = unique_iin("7")
    person_ids: list[int] = []
    employee_id: int | None = None
    batch_id: int | None = None
    personnel_order_id: int | None = None
    with engine.begin() as conn:
        user_id = seed_user_id(conn)
        business_date = conn.execute(
            text(
                'SELECT effective_date FROM public.person_assignment_activation_watermark '
                'WHERE singleton IS TRUE'
            )
        ).scalar_one()
        org = load_org_fixture(conn)
        if org["org_unit_id"] is None or org["position_id"] is None:
            pytest.skip("org unit/position fixture unavailable")
        org_row = conn.execute(
            text("SELECT name, code FROM public.org_units WHERE unit_id=:id"),
            {"id": org["org_unit_id"]},
        ).mappings().one()
        position_row = conn.execute(
            text("SELECT name FROM public.positions WHERE position_id=:id"),
            {"id": org["position_id"]},
        ).mappings().one()
        person_id = None
        if person_status is not None:
            person_id = insert_person_with_iin(
                conn, full_name=f"ADR065 Person {token}", iin=iin, prefix="adr065"
            )
            person_ids.append(person_id)
            if person_status != "active":
                conn.execute(
                    text(
                        "UPDATE public.persons SET person_status=:status "
                        "WHERE person_id=:person_id"
                    ),
                    {"status": person_status, "person_id": person_id},
                )
        employee_id = insert_employee(
            conn,
            full_name=f"ADR065 Employee {token}",
            person_id=person_id if linked else None,
        )
        insert_returning_id(
            conn,
            table="employee_identities",
            id_col="identity_id",
            values={
                "employee_id": employee_id,
                "identity_type": "IIN",
                "identity_value": iin,
                "is_primary": True,
                "created_by": user_id,
            },
        )
        batch_id = insert_returning_id(
            conn,
            table="hr_import_batches",
            id_col="batch_id",
            values={
                "source_type": "HR_CONTROL_LIST",
                "file_name": f"adr065-{token}.xlsx",
                "import_code": f"ADR065-{token}",
                "imported_by": user_id,
                "status": "PARSED",
                "total_rows": 1,
                "valid_rows": 1,
                "error_rows": 0,
            },
        )
        row_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.hr_import_rows (
                        batch_id, source_sheet, source_row_number,
                        raw_payload, normalized_payload, match_status, employee_id
                    ) VALUES (
                        :batch_id, 'control', 1,
                        CAST(:payload AS jsonb), CAST(:payload AS jsonb),
                        'AUTO_MATCH', :employee_id
                    ) RETURNING row_id
                    """
                ),
                {
                    "batch_id": batch_id,
                    "payload": json.dumps(
                        {
                            "iin": iin,
                            "full_name": "must-not-drive-lookup",
                            "org_unit": 999999,
                            "position": 999999,
                            "start_date": "1900-01-01",
                        }
                    ),
                    "employee_id": employee_id,
                },
            ).scalar_one()
        )
        normalized_ids: list[int] = []
        for index in (2, 0, 1):
            normalized_ids.append(
                insert_returning_id(
                    conn,
                    table="hr_import_normalized_records",
                    id_col="normalized_record_id",
                    values={
                        "batch_id": batch_id,
                        "row_id": row_id,
                        "employee_id": employee_id,
                        "fragment_index": index,
                        "source_field": "training",
                        "source_text": f"fragment-{index}",
                        "source_record_key": f"adr065:{token}:{index}",
                        "record_kind": "training",
                        "parse_method": "regex_v1",
                        "review_status": "pending",
                    },
                )
            )
        personnel_order_id = insert_returning_id(
            conn,
            table="personnel_orders",
            id_col="order_id",
            values={
                "order_number": f"ADR065-{token}",
                "order_date": date(2026, 7, 10),
                "order_type_code": "HIRE",
                "status": "DRAFT",
                "source_mode": "PAPER",
                "created_by": user_id,
            },
        )
        conn.execute(
            text("INSERT INTO public.personnel_order_evidence_scopes(order_id) VALUES (:id)"),
            {"id": personnel_order_id},
        )
        personnel_order_item_id = insert_returning_id(
            conn,
            table="personnel_order_items",
            id_col="item_id",
            values={
                "order_id": personnel_order_id,
                "item_number": 1,
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "item_status": "ACTIVE",
            },
        )
    try:
        yield {
            "iin": iin,
            "employee_id": employee_id,
            "person_ids": person_ids,
            "batch_id": batch_id,
            "row_id": row_id,
            "normalized_record_ids": normalized_ids,
            "org": org,
            "org_code": str(org_row["code"] or ""),
            "org_name": _normalized(str(org_row["name"] or "")),
            "position_name": _normalized(str(position_row["name"] or "")),
            "user_id": user_id,
            "business_date": business_date,
            "personnel_order_id": personnel_order_id,
            "personnel_order_item_id": personnel_order_item_id,
        }
    finally:
        with engine.begin() as conn:
            if personnel_order_id is not None:
                conn.execute(
                    text("DELETE FROM public.personnel_order_item_bases WHERE order_item_id IN (SELECT item_id FROM public.personnel_order_items WHERE order_id=:id)"),
                    {"id": personnel_order_id},
                )
                conn.execute(
                    text("DELETE FROM public.personnel_order_attachments WHERE order_id=:id"),
                    {"id": personnel_order_id},
                )
                conn.execute(
                    text("DELETE FROM public.personnel_order_items WHERE order_id=:id"),
                    {"id": personnel_order_id},
                )
                conn.execute(
                    text("DELETE FROM public.personnel_order_evidence_scopes WHERE order_id=:id"),
                    {"id": personnel_order_id},
                )
                conn.execute(
                    text("DELETE FROM public.personnel_orders WHERE order_id=:id"),
                    {"id": personnel_order_id},
                )
            if batch_id is not None:
                conn.execute(
                    text("DELETE FROM public.hr_import_batches WHERE batch_id=:id"),
                    {"id": batch_id},
                )
            if employee_id is not None:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id=:id"),
                    {"id": employee_id},
                )
            if person_ids:
                conn.execute(
                    text("DELETE FROM public.person_assignments WHERE person_id=ANY(:ids)"),
                    {"ids": person_ids},
                )
                conn.execute(
                    text("DELETE FROM public.persons WHERE person_id=ANY(:ids)"),
                    {"ids": person_ids},
                )


def _request(scenario: dict, *, intent: dict | None = None) -> dict:
    return {
        "iin": scenario["iin"],
        "import_selection": {
            "batch_id": scenario["batch_id"],
            "row_id": scenario["row_id"],
            "normalized_record_ids": list(reversed(scenario["normalized_record_ids"])),
        },
        "assignment_intent": intent if intent is not None else _complete_intent(scenario),
    }


def _codes(body: dict) -> set[str]:
    return {item["code"] for item in body["blockers"]}


def test_route_registered() -> None:
    methods = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "path")
        for method in getattr(route, "methods", set())
    }
    assert (ROUTE, "POST") in methods


def test_application_engine_hides_sql_parameters() -> None:
    assert engine.hide_parameters is True


def test_real_exact_iin_sql_path_masks_bind_values_in_engine_logs(
    client, repair_schema, privileged_headers, caplog
) -> None:
    with _scenario() as scenario:
        with caplog.at_level(logging.INFO, logger='sqlalchemy.engine'):
            response = client.post(
                ROUTE,
                json=_request(scenario),
                headers=privileged_headers,
            )
        assert response.status_code == 200, response.text
        if scenario['iin'] in caplog.text:
            pytest.fail('full IIN appeared in SQLAlchemy engine logs', pytrace=False)
        assert 'SQL parameters hidden due to hide_parameters=True' in caplog.text


def test_sqlalchemy_exception_after_real_iin_bind_is_safe(
    client, repair_schema, privileged_headers, caplog
) -> None:
    from app.directory import personnel_lk_routes

    with _scenario() as scenario:
        def fail_after_exact_iin_sql(
            conn, cursor, statement, parameters, context, executemany
        ):
            if scenario['iin'] in repr(parameters):
                raise SQLAlchemyError('database failure contained ' + scenario['iin'])

        event.listen(engine, 'after_cursor_execute', fail_after_exact_iin_sql)
        try:
            with caplog.at_level(logging.INFO):
                response = client.post(
                    ROUTE,
                    json=_request(scenario),
                    headers=privileged_headers,
                )
        finally:
            event.remove(engine, 'after_cursor_execute', fail_after_exact_iin_sql)
        assert response.status_code == 500
        assert response.json()['detail'] == {
            'code': 'CONTROL_LIST_REPAIR_PREFLIGHT_INTERNAL_ERROR',
            'message': 'Control-list repair preflight is temporarily unavailable.',
        }
        if scenario['iin'] in response.text or scenario['iin'] in caplog.text:
            pytest.fail('full IIN appeared outside the failed SQL transaction', pytrace=False)
        assert 'SQLAlchemyError' in caplog.get_records('call')[0].message or (
            'SQLAlchemyError' in caplog.text
        )


def test_preflight_requires_personnel_admin(client, repair_schema, seed) -> None:
    iin = "123456789012"
    response = client.post(
        ROUTE,
        json={"iin": iin},
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert response.status_code == 403
    assert iin not in response.text


@pytest.mark.parametrize(
    "iin",
    [
        " 12345678901",
        "12345678901 ",
        "12345678901-",
        "\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19\uff10\uff11\uff12",
        "12345678901",
    ],
)
def test_iin_is_exactly_twelve_ascii_digits(
    client, privileged_headers, caplog, iin
) -> None:
    with caplog.at_level(logging.INFO):
        response = client.post(ROUTE, json={"iin": iin}, headers=privileged_headers)
    assert response.status_code == 422
    assert iin not in response.text
    assert iin not in caplog.text
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "iin"]
    assert set(detail[0]) <= {"type", "loc", "msg"}


@pytest.mark.parametrize(
    ("exception_factory", "expected_type"),
    [
        (lambda iin: SQLAlchemyError(f"statement bind contained {iin}"), "SQLAlchemyError"),
        (lambda iin: RuntimeError(f"internal payload contained {iin}"), "RuntimeError"),
    ],
)
def test_internal_errors_are_stable_and_do_not_expose_iin(
    client,
    repair_schema,
    privileged_headers,
    monkeypatch,
    caplog,
    exception_factory,
    expected_type,
) -> None:
    from app.directory import personnel_lk_routes

    with _scenario() as scenario:
        def fail(*args, **kwargs):
            raise exception_factory(scenario["iin"])

        monkeypatch.setattr(personnel_lk_routes, "control_list_repair_preflight", fail)
        with caplog.at_level(logging.ERROR, logger=personnel_lk_routes.__name__):
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
        assert response.status_code == 500
        assert response.json()["detail"] == {
            "code": "CONTROL_LIST_REPAIR_PREFLIGHT_INTERNAL_ERROR",
            "message": "Control-list repair preflight is temporarily unavailable.",
        }
        assert scenario["iin"] not in response.text
        assert scenario["iin"] not in caplog.text
        assert expected_type in caplog.text


def test_successful_p0_is_server_classified_and_iin_is_redacted(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] == "P0_CREATE"
        assert body["mode"] == "LINK_AND_OPEN_MISSING_ASSIGNMENT"
        assert body["proposed_outcome"] == "EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED"
        assert body["preflight_complete"] is True
        assert body["apply_available"] is False
        assert body["blockers"] == []
        assert scenario["iin"] not in response.text
        assert body["request_iin"] == {"present": True, "last4": scenario["iin"][-4:]}
        assert body["selected_import"]["normalized_record_ids"] == sorted(
            scenario["normalized_record_ids"]
        )


def test_successful_singleton_p1_is_server_classified(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="active") as scenario:
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] == "P1_ADOPT"
        assert [item["person_id"] for item in body["person_candidates"]] == scenario["person_ids"]
        assert body["preflight_complete"] is True
        assert body["apply_available"] is False


def test_omitted_optional_import_selection_returns_discovery_but_not_complete(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        response = client.post(
            ROUTE,
            json={
                "iin": scenario["iin"],
                "assignment_intent": _complete_intent(scenario),
            },
            headers=privileged_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] == "P0_CREATE"
        assert body["selected_import"] is None
        assert len(body["import_records"]) == 1
        assert "IMPORT_SELECTION_REQUIRED" in _codes(body)
        assert body["preflight_complete"] is False
        assert body["apply_available"] is False


def test_exact_import_selection_rejects_missing_normalized_record(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload["import_selection"]["normalized_record_ids"].append(2_147_483_647)
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert {
            "IMPORT_NORMALIZED_RECORD_NOT_FOUND",
            "IMPORT_SELECTION_INCOMPLETE",
        } <= _codes(response.json())
        assert response.json()["preflight_complete"] is False


def test_exact_import_selection_requires_existing_control_batch_row_and_iin(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload["import_selection"]["batch_id"] = 9_223_372_036_854_775_000
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert "IMPORT_BATCH_NOT_FOUND" in _codes(response.json())

        payload = _request(scenario)
        payload["import_selection"]["row_id"] = 9_223_372_036_854_775_000
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert "IMPORT_ROW_NOT_FOUND" in _codes(response.json())

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.hr_import_batches SET source_type='OTHER' "
                    "WHERE batch_id=:batch_id"
                ),
                {"batch_id": scenario["batch_id"]},
            )
        try:
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
            assert "IMPORT_BATCH_SOURCE_MISMATCH" in _codes(response.json())
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_batches "
                        "SET source_type='HR_CONTROL_LIST' WHERE batch_id=:batch_id"
                    ),
                    {"batch_id": scenario["batch_id"]},
                )

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.hr_import_rows "
                    "SET normalized_payload=jsonb_set("
                    "normalized_payload, '{iin}', "
                    "to_jsonb(CAST('000000000000' AS text))"
                    ") WHERE row_id=:row_id"
                ),
                {"row_id": scenario["row_id"]},
            )
        try:
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
            assert "IMPORT_ROW_IIN_MISMATCH" in _codes(response.json())
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_rows "
                        "SET normalized_payload=jsonb_set("
                        "normalized_payload, '{iin}', to_jsonb(CAST(:iin AS text))"
                        ") WHERE row_id=:row_id"
                    ),
                    {"iin": scenario["iin"], "row_id": scenario["row_id"]},
                )


@pytest.mark.parametrize("record_ids", [[], [1, 1]])
def test_exact_import_selection_requires_nonempty_unique_ids(
    client, repair_schema, privileged_headers, record_ids
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload["import_selection"]["normalized_record_ids"] = record_ids
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 422
        assert scenario["iin"] not in response.text


def test_import_row_and_normalized_ownership_must_match_employee(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        other_employee_id: int | None = None
        try:
            with engine.begin() as conn:
                other_employee_id = insert_employee(
                    conn,
                    full_name=f"ADR065 other Employee {uuid4().hex[:8]}",
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_rows SET employee_id=:other "
                        "WHERE row_id=:row_id"
                    ),
                    {"other": other_employee_id, "row_id": scenario["row_id"]},
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records SET employee_id=:other "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {
                        "other": other_employee_id,
                        "record_id": scenario["normalized_record_ids"][0],
                    },
                )
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
            assert response.status_code == 200, response.text
            assert response.json()["classification"] is None
            assert {
                "IMPORT_ROW_OWNERSHIP_CONFLICT",
                "IMPORT_NORMALIZED_RECORD_OWNERSHIP_CONFLICT",
            } <= _codes(response.json())
            assert response.json()["preflight_complete"] is False
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_rows SET employee_id=:employee_id "
                        "WHERE row_id=:row_id"
                    ),
                    {
                        "employee_id": scenario["employee_id"],
                        "row_id": scenario["row_id"],
                    },
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records "
                        "SET employee_id=:employee_id "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {
                        "employee_id": scenario["employee_id"],
                        "record_id": scenario["normalized_record_ids"][0],
                    },
                )
                if other_employee_id is not None:
                    conn.execute(
                        text("DELETE FROM public.employees WHERE employee_id=:id"),
                        {"id": other_employee_id},
                    )


def test_normalized_record_from_another_row_is_rejected(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        other_row_id: int | None = None
        record_id = scenario["normalized_record_ids"][0]
        try:
            with engine.begin() as conn:
                other_row_id = int(
                    conn.execute(
                        text(
                            """
                            INSERT INTO public.hr_import_rows (
                                batch_id, source_sheet, source_row_number,
                                raw_payload, normalized_payload, match_status, employee_id
                            ) VALUES (
                                :batch_id, 'control', 2,
                                CAST(:payload AS jsonb), CAST(:payload AS jsonb),
                                'AUTO_MATCH', :employee_id
                            ) RETURNING row_id
                            """
                        ),
                        {
                            "batch_id": scenario["batch_id"],
                            "payload": json.dumps({"iin": scenario["iin"]}),
                            "employee_id": scenario["employee_id"],
                        },
                    ).scalar_one()
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records SET row_id=:other_row "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {"other_row": other_row_id, "record_id": record_id},
                )
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
            assert response.status_code == 200, response.text
            assert response.json()["classification"] is None
            assert {
                "IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH",
                "IMPORT_SELECTION_INCOMPLETE",
            } <= _codes(response.json())
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records SET row_id=:row_id "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {"row_id": scenario["row_id"], "record_id": record_id},
                )
                if other_row_id is not None:
                    conn.execute(
                        text("DELETE FROM public.hr_import_rows WHERE row_id=:id"),
                        {"id": other_row_id},
                    )


def test_row_or_normalized_record_from_another_batch_is_rejected(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        other_batch_id: int | None = None
        record_id = scenario["normalized_record_ids"][0]
        try:
            with engine.begin() as conn:
                other_batch_id = insert_returning_id(
                    conn,
                    table="hr_import_batches",
                    id_col="batch_id",
                    values={
                        "source_type": "HR_CONTROL_LIST",
                        "file_name": f"adr065-other-{uuid4().hex[:8]}.xlsx",
                        "import_code": f"ADR065-OTHER-{uuid4().hex[:8]}",
                        "imported_by": scenario["user_id"],
                        "status": "PARSED",
                        "total_rows": 0,
                        "valid_rows": 0,
                        "error_rows": 0,
                    },
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records SET batch_id=:batch_id "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {"batch_id": other_batch_id, "record_id": record_id},
                )
            response = client.post(
                ROUTE, json=_request(scenario), headers=privileged_headers
            )
            assert response.status_code == 200, response.text
            assert response.json()["classification"] is None
            assert "IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH" in _codes(response.json())

            payload = _request(scenario)
            payload["import_selection"]["batch_id"] = other_batch_id
            row_response = client.post(
                ROUTE, json=payload, headers=privileged_headers
            )
            assert row_response.status_code == 200, row_response.text
            assert "IMPORT_ROW_BATCH_MISMATCH" in _codes(row_response.json())
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records SET batch_id=:batch_id "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {"batch_id": scenario["batch_id"], "record_id": record_id},
                )
                if other_batch_id is not None:
                    conn.execute(
                        text("DELETE FROM public.hr_import_batches WHERE batch_id=:id"),
                        {"id": other_batch_id},
                    )


@pytest.mark.parametrize('include_cross_batch_sibling', [False, True])
def test_same_row_cross_batch_sibling_is_detected_even_when_omitted(
    client,
    repair_schema,
    privileged_headers,
    include_cross_batch_sibling,
) -> None:
    with _scenario() as scenario:
        other_batch_id: int | None = None
        try:
            with engine.begin() as conn:
                other_batch_id = insert_returning_id(
                    conn,
                    table='hr_import_batches',
                    id_col='batch_id',
                    values={
                        'source_type': 'HR_CONTROL_LIST',
                        'file_name': f'adr065-cross-{uuid4().hex[:8]}.xlsx',
                        'import_code': f'ADR065-CROSS-{uuid4().hex[:8]}',
                        'imported_by': scenario['user_id'],
                        'status': 'PARSED',
                        'total_rows': 0,
                        'valid_rows': 0,
                        'error_rows': 0,
                    },
                )
                sibling_id = insert_returning_id(
                    conn,
                    table='hr_import_normalized_records',
                    id_col='normalized_record_id',
                    values={
                        'batch_id': other_batch_id,
                        'row_id': scenario['row_id'],
                        'employee_id': scenario['employee_id'],
                        'fragment_index': 99,
                        'source_field': 'training',
                        'source_text': 'cross-batch sibling',
                        'source_record_key': f'adr065:cross:{uuid4().hex}',
                        'record_kind': 'training',
                        'parse_method': 'regex_v1',
                        'review_status': 'pending',
                    },
                )
            payload = _request(scenario)
            if include_cross_batch_sibling:
                payload['import_selection']['normalized_record_ids'].append(sibling_id)
            response = client.post(ROUTE, json=payload, headers=privileged_headers)
            assert response.status_code == 200, response.text
            body = response.json()
            assert body['classification'] is None
            assert body['mode'] is None
            assert body['proposed_outcome'] is None
            assert 'IMPORT_NORMALIZED_RECORD_BATCH_MISMATCH' in _codes(body)
            if include_cross_batch_sibling:
                assert 'IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH' in _codes(body)
            else:
                assert 'IMPORT_SELECTION_INCOMPLETE' in _codes(body)
            assert body['preflight_complete'] is False
            assert body['apply_available'] is False
        finally:
            if other_batch_id is not None:
                with engine.begin() as conn:
                    conn.execute(
                        text('DELETE FROM public.hr_import_batches WHERE batch_id=:id'),
                        {'id': other_batch_id},
                    )


def test_multiple_employee_identity_is_fail_closed(
    client, repair_schema, privileged_headers, monkeypatch
) -> None:
    from app.personnel_lk.application import control_list_repair_preflight_service as service

    with _scenario() as scenario:
        original = service._load_employees

        def duplicate(conn, iin):
            rows = original(conn, iin)
            return rows + [{**rows[0], "employee_id": rows[0]["employee_id"] + 1}]

        monkeypatch.setattr(service, "_load_employees", duplicate)
        response = _post_write_free(
            client, privileged_headers, scenario, _request(scenario)
        )
        assert response.status_code == 200
        assert response.json()["classification"] is None
        assert "EMPLOYEE_IIN_CONFLICT" in _codes(response.json())


def test_ambiguous_and_incompatible_person_candidates_are_fail_closed(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="active") as scenario:
        with engine.begin() as conn:
            incompatible_id = insert_returning_id(
                conn,
                table="persons",
                id_col="person_id",
                values={
                    "full_name": f"ADR065 inactive {uuid4().hex[:8]}",
                    "iin": scenario["iin"],
                    "match_key": f"adr065-inactive:{uuid4().hex}",
                    "person_status": "inactive",
                    "source": "manual",
                },
            )
            scenario["person_ids"].append(incompatible_id)
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert "AMBIGUOUS_PERSON" in _codes(response.json())
        assert [item["compatible"] for item in response.json()["person_candidates"]] == [
            True,
            False,
        ]


def test_single_incompatible_person_candidate_is_fail_closed(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="inactive") as scenario:
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert "INCOMPATIBLE_PERSON" in _codes(response.json())
        assert "AMBIGUOUS_PERSON" not in _codes(response.json())


def test_merged_person_candidate_is_fail_closed(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="active") as scenario:
        with engine.begin() as conn:
            survivor_id = insert_person_with_iin(
                conn,
                full_name=f"ADR065 merge survivor {uuid4().hex[:8]}",
                iin=None,
                prefix="adr065-survivor",
            )
            scenario["person_ids"].append(survivor_id)
            conn.execute(
                text(
                    "UPDATE public.persons "
                    "SET person_status='merged', merged_into_person_id=:survivor "
                    "WHERE person_id=:candidate"
                ),
                {
                    "survivor": survivor_id,
                    "candidate": scenario["person_ids"][0],
                },
            )
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert "INCOMPATIBLE_PERSON" in _codes(response.json())
        assert response.json()["person_candidates"][0]["incompatibility_reason"] == (
            "PERSON_MERGED"
        )


def test_ineligible_employee_status_is_fail_closed(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.employees SET operational_status='suspended' "
                    "WHERE employee_id=:employee_id"
                ),
                {"employee_id": scenario["employee_id"]},
            )
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert "EMPLOYEE_STATE_NOT_ELIGIBLE" in _codes(response.json())


def test_existing_link_and_primary_assignment_block_composite(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="active", linked=True) as scenario:
        with engine.begin() as conn:
            assignment_id = insert_returning_id(
                conn,
                table="person_assignments",
                id_col="assignment_id",
                values={
                    "person_id": scenario["person_ids"][0],
                    "org_unit_id": scenario["org"]["org_unit_id"],
                    "position_id": scenario["org"]["position_id"],
                    "employment_type": "primary",
                    "rate": 1,
                    "start_date": date(2026, 7, 2),
                    "active_flag": True,
                    "is_primary": True,
                    "lifecycle_status": "active",
                    "assignment_key": f"adr065:{uuid4().hex}",
                    "source": "manual",
                },
            )
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert {"EMPLOYEE_ALREADY_LINKED", "PRIMARY_ASSIGNMENT_EXISTS"} <= _codes(response.json())
        assert response.json()["primary_assignments"][0]["assignment_id"] == assignment_id


@pytest.mark.parametrize(
    "missing",
    [
        "org_unit",
        "position",
        "rate",
        "employment_type",
        "is_primary",
        "start_date",
        "evidence",
        "reason_code",
        "verifier_confirmation",
    ],
)
def test_each_assignment_decision_is_required(
    client, repair_schema, privileged_headers, missing
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent.pop(missing)
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] is None
        assert body["mode"] is None
        assert body["proposed_outcome"] is None
        assert body["missing_assignment_inputs"] == [missing]
        assert "ASSIGNMENT_INTENT_INCOMPLETE" in _codes(body)
        assert body["preflight_complete"] is False
        assert body["apply_available"] is False


def test_multiple_missing_assignment_inputs_are_sorted_and_stop_classification(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        for field in ('verifier_confirmation', 'org_unit', 'evidence'):
            intent.pop(field)
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['missing_assignment_inputs'] == [
            'evidence',
            'org_unit',
            'verifier_confirmation',
        ]
        assert body['classification'] is None
        assert body['mode'] is None
        assert body['proposed_outcome'] is None


def test_incomplete_intent_and_missing_import_selection_do_not_expose_p0_p1(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload.pop('import_selection')
        payload['assignment_intent'].pop('position')
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['classification'] is None
        assert body['mode'] is None
        assert body['proposed_outcome'] is None
        assert 'ASSIGNMENT_INTENT_INCOMPLETE' in _codes(body)
        assert 'IMPORT_SELECTION_REQUIRED' in _codes(body)
        assert body['preflight_complete'] is False
        assert body['apply_available'] is False


def test_external_reference_evidence_is_accepted(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        response = client.post(
            ROUTE,
            json=_request(
                scenario,
                intent=_complete_intent(scenario, evidence_type="EXTERNAL_REFERENCE"),
            ),
            headers=privileged_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preflight_complete"] is True
        assert response.json()["missing_assignment_inputs"] == []
        assert response.json()["invalid_assignment_inputs"] == []


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [("missing", "ACTIVE_STATE_WATERMARK_INVALID"),
     ("stale", "ACTIVE_STATE_STALE"),
     ("future", "ACTIVE_STATE_FUTURE")],
)
def test_watermark_noncurrent_states_fail_closed(
    client, repair_schema, privileged_headers, state, expected_code
) -> None:
    with _scenario() as scenario:
        with engine.begin() as conn:
            original = dict(conn.execute(text("SELECT * FROM public.person_assignment_activation_watermark WHERE singleton IS TRUE")).mappings().one())
            if state == "missing":
                conn.execute(text("DELETE FROM public.person_assignment_activation_watermark"))
            else:
                delta = -1 if state == "stale" else 1
                conn.execute(text("UPDATE public.person_assignment_activation_watermark SET effective_date=effective_date+:delta"), {"delta": delta})
        try:
            response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["classification"] is None
            assert body["mode"] is None and body["proposed_outcome"] is None
            assert expected_code in _codes(body)
            assert body["preflight_complete"] is False
            assert body["apply_available"] is False
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.person_assignment_activation_watermark"))
                conn.execute(text("INSERT INTO public.person_assignment_activation_watermark(singleton,effective_date,processed_at,generation,updated_at) VALUES (:singleton,:effective_date,:processed_at,:generation,:updated_at)"), original)


def test_missing_watermark_schema_fails_closed_without_500(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE public.person_assignment_activation_watermark RENAME TO person_assignment_activation_watermark_absent_test"))
        try:
            response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
            assert response.status_code == 200, response.text
            body = response.json()
            assert "ACTIVE_STATE_SCHEMA_UNAVAILABLE" in _codes(body)
            assert body["classification"] is None
            assert body["preflight_complete"] is False
            assert body["apply_available"] is False
        finally:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE public.person_assignment_activation_watermark_absent_test RENAME TO person_assignment_activation_watermark"))


def test_personnel_order_evidence_fails_closed_without_normative_hmac_profile(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        response = client.post(
            ROUTE,
            json=_request(
                scenario,
                intent=_complete_intent(scenario, evidence_type="PERSONNEL_ORDER"),
            ),
            headers=privileged_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] is None
        assert body["preflight_complete"] is False
        assert body["apply_available"] is False
        assert body["invalid_assignment_inputs"] == ["evidence"]
        assert "EVIDENCE_FINGERPRINT_UNVERIFIABLE" in _codes(body)


def test_personnel_order_evidence_exact_fingerprint_is_accepted(
    client, repair_schema, privileged_headers, evidence_key_provider
) -> None:
    with _scenario() as scenario:
        with engine.connect() as conn:
            fingerprint = _fixture_personnel_order_fingerprint(
                conn,
                order_id=scenario["personnel_order_id"],
                item_id=scenario["personnel_order_item_id"],
            )
        intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
        intent["evidence"]["evidence_fingerprint"] = fingerprint
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] == "P0_CREATE"
        assert body["preflight_complete"] is True
        assert body["apply_available"] is False


@pytest.mark.parametrize("component", ["header", "items", "item_bases", "attachments", "generation"])
def test_personnel_order_fingerprint_binds_every_collection_and_generation(
    client, repair_schema, privileged_headers, evidence_key_provider, component
) -> None:
    with _scenario() as scenario:
        with engine.begin() as conn:
            fingerprint = _fixture_personnel_order_fingerprint(
                conn, order_id=scenario["personnel_order_id"], item_id=scenario["personnel_order_item_id"]
            )
            if component == "header":
                conn.execute(text("UPDATE public.personnel_orders SET comment='changed' WHERE order_id=:id"), {"id": scenario["personnel_order_id"]})
            elif component == "items":
                conn.execute(
                    text("UPDATE public.personnel_order_items SET payload=CAST(:payload AS jsonb) WHERE item_id=:id"),
                    {"id": scenario["personnel_order_item_id"], "payload": json.dumps({"changed": True})},
                )
            elif component == "item_bases":
                conn.execute(text("INSERT INTO public.personnel_order_item_bases(order_item_id,basis_type,metadata) VALUES (:id,'OTHER','{}'::jsonb)"), {"id": scenario["personnel_order_item_id"]})
            elif component == "attachments":
                conn.execute(text("INSERT INTO public.personnel_order_attachments(order_id,attachment_kind,created_by,file_path,file_comment) VALUES (:id,'BASIS_DOCUMENT',:user_id,'test/changed','changed')"), {"id": scenario["personnel_order_id"], "user_id": scenario["user_id"]})
            else:
                conn.execute(text("UPDATE public.personnel_order_evidence_scopes SET generation=generation+1 WHERE order_id=:id"), {"id": scenario["personnel_order_id"]})
        intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
        intent["evidence"]["evidence_fingerprint"] = fingerprint
        response = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classification"] is None
        assert "EVIDENCE_FINGERPRINT_MISMATCH" in _codes(body)
        assert body["preflight_complete"] is False
        assert body["apply_available"] is False


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [("SCHEDULED", "EVIDENCE_KEY_NOT_YET_VALID"),
     ("REVOKED", "EVIDENCE_KEY_REVOKED"),
     ("DESTROYED", "EVIDENCE_KEY_DESTROYED")],
)
def test_personnel_order_key_states_fail_closed(
    client, repair_schema, privileged_headers, monkeypatch, state, expected_code
) -> None:
    monkeypatch.setenv("ADR065_ORGANIZATION_SCOPE_ID", TEST_ORG_SCOPE)
    configure_evidence_key_provider(_FixtureKeyProvider(state=state))
    try:
        with _scenario() as scenario:
            with engine.connect() as conn:
                fingerprint = _fixture_personnel_order_fingerprint(conn, order_id=scenario["personnel_order_id"], item_id=scenario["personnel_order_item_id"])
            intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
            intent["evidence"]["evidence_fingerprint"] = fingerprint
            body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
            assert expected_code in _codes(body)
            assert body["classification"] is None
            assert body["apply_available"] is False
    finally:
        configure_evidence_key_provider(None)


def test_verification_only_rotated_key_remains_verifiable(
    client, repair_schema, privileged_headers, monkeypatch
) -> None:
    monkeypatch.setenv("ADR065_ORGANIZATION_SCOPE_ID", TEST_ORG_SCOPE)
    configure_evidence_key_provider(_FixtureKeyProvider(state="VERIFICATION_ONLY"))
    try:
        with _scenario() as scenario:
            with engine.connect() as conn:
                fingerprint = _fixture_personnel_order_fingerprint(conn, order_id=scenario["personnel_order_id"], item_id=scenario["personnel_order_item_id"])
            intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
            intent["evidence"]["evidence_fingerprint"] = fingerprint
            body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
            assert body["preflight_complete"] is True
            assert body["classification"] == "P0_CREATE"
    finally:
        configure_evidence_key_provider(None)


def test_unknown_evidence_key_fails_closed(
    client, repair_schema, privileged_headers, monkeypatch
) -> None:
    monkeypatch.setenv("ADR065_ORGANIZATION_SCOPE_ID", TEST_ORG_SCOPE)
    configure_evidence_key_provider(_FixtureKeyProvider(returned_key_id="different-key"))
    try:
        with _scenario() as scenario:
            intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
            body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
            assert "EVIDENCE_KEY_UNKNOWN" in _codes(body)
            assert body["classification"] is None
            assert body["apply_available"] is False
    finally:
        configure_evidence_key_provider(None)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [("evidence_profile_id", "unknown-profile", "EVIDENCE_PROFILE_UNSUPPORTED"),
     ("evidence_profile_version", 2, "EVIDENCE_PROFILE_VERSION_UNSUPPORTED")],
)
def test_unknown_evidence_profile_or_version_fails_closed(
    client, repair_schema, privileged_headers, evidence_key_provider, field, value, expected_code
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
        intent["evidence"][field] = value
        body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
        assert expected_code in _codes(body)
        assert body["classification"] is None
        assert body["apply_available"] is False


def test_fingerprint_from_another_selected_item_does_not_verify(
    client, repair_schema, privileged_headers, evidence_key_provider
) -> None:
    with _scenario() as scenario:
        with engine.begin() as conn:
            second_item = conn.execute(text("INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload,item_status) VALUES (:order_id,2,'HIRE',:employee_id,'{}'::jsonb,'ACTIVE') RETURNING item_id"), {"order_id": scenario["personnel_order_id"], "employee_id": scenario["employee_id"]}).scalar_one()
            fingerprint = _fixture_personnel_order_fingerprint(conn, order_id=scenario["personnel_order_id"], item_id=scenario["personnel_order_item_id"])
        intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
        intent["evidence"]["evidence_record_id"] = int(second_item)
        intent["evidence"]["evidence_fingerprint"] = fingerprint
        body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
        assert "EVIDENCE_FINGERPRINT_MISMATCH" in _codes(body)
        assert body["classification"] is None


def test_fingerprint_from_another_order_does_not_verify(
    client, repair_schema, privileged_headers, evidence_key_provider
) -> None:
    with _scenario() as scenario:
        other_order_id = other_item_id = None
        try:
            with engine.begin() as conn:
                other_order_id = conn.execute(text("INSERT INTO public.personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES (:number,:date,'HIRE','DRAFT','PAPER',:user_id) RETURNING order_id"), {"number": f"ADR065-OTHER-{uuid4().hex[:8]}", "date": date(2026,7,10), "user_id": scenario["user_id"]}).scalar_one()
                conn.execute(text("INSERT INTO public.personnel_order_evidence_scopes(order_id) VALUES (:id)"), {"id": other_order_id})
                other_item_id = conn.execute(text("INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload,item_status) VALUES (:order_id,1,'HIRE',:employee_id,'{}'::jsonb,'ACTIVE') RETURNING item_id"), {"order_id": other_order_id, "employee_id": scenario["employee_id"]}).scalar_one()
                fingerprint = _fixture_personnel_order_fingerprint(conn, order_id=other_order_id, item_id=other_item_id)
            intent = _complete_intent(scenario, evidence_type="PERSONNEL_ORDER")
            intent["evidence"]["evidence_fingerprint"] = fingerprint
            body = client.post(ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers).json()
            assert "EVIDENCE_FINGERPRINT_MISMATCH" in _codes(body)
            assert body["classification"] is None
        finally:
            if other_order_id is not None:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": other_order_id})
                    conn.execute(text("DELETE FROM public.personnel_order_evidence_scopes WHERE order_id=:id"), {"id": other_order_id})
                    conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": other_order_id})


@pytest.mark.parametrize(
    "reason_code",
    [
        "ACTIVE_ENROLLMENT_CONFIRMED",
        "CONSISTENT_STATE_VERIFIED",
        "EXISTING_CARD_PERSON_LINK_GAP_CONFIRMED",
        "EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED",
        "MISSING_PRIMARY_ASSIGNMENT_CONFIRMED",
        "ERRONEOUS_ASSIGNMENT_RECORD_CONFIRMED",
        "REAL_LIFECYCLE_EPISODE_COMPLETION_CONFIRMED",
        "CURRENT_ASSIGNMENT_CHANGE_CONFIRMED",
        "FUTURE_ASSIGNMENT_PRESERVATION_CONFIRMED",
        "FUTURE_ASSIGNMENT_CHANGE_CONFIRMED",
    ],
)
def test_closed_reason_vocabulary_and_composite_compatibility(
    client, repair_schema, privileged_headers, reason_code
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent["reason_code"] = reason_code
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        if reason_code == "EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED":
            assert body["preflight_complete"] is True
        else:
            assert body["classification"] is None
            assert "REASON_MODE_INCOMPATIBLE" in _codes(body)
            assert body["preflight_complete"] is False
        assert body["apply_available"] is False


def test_mode_as_reason_is_rejected(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload["assignment_intent"]["reason_code"] = "LINK_AND_OPEN_MISSING_ASSIGNMENT"
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 422
        assert scenario["iin"] not in response.text


def test_current_reason_placeholder_rejects_free_text_pending_normative_vocabulary(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        response = client.post(ROUTE, json=_request(scenario), headers=privileged_headers)
        assert response.status_code == 200
        assert response.json()["preflight_complete"] is True
        payload = _request(scenario)
        payload["assignment_intent"]["reason_code"] = "FREE_TEXT_REASON"
        rejected = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert rejected.status_code == 422
        assert scenario["iin"] not in rejected.text


@pytest.mark.parametrize('rate', ['0.01', '0.1', '1', '1.01', '1.5'])
def test_canonical_numeric_4_2_rate_is_accepted(
    client, repair_schema, privileged_headers, rate
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['rate'] = rate
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()['preflight_complete'] is True


@pytest.mark.parametrize(
    'rate',
    [1, 1.0, '0', '0.001', '1.00', '1.50', '1e0', '01', '1.51'],
)
def test_noncanonical_or_out_of_range_rate_is_rejected(
    client, repair_schema, privileged_headers, rate
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['rate'] = rate
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422
        if scenario['iin'] in response.text:
            pytest.fail('validation response exposed full IIN', pytrace=False)


@pytest.mark.parametrize(
    'confirmation_at',
    [
        '2026-08-09T10:00:00+00:00',
        '2026-08-09T10:00:00.000000Z',
        '2026-02-30T10:00:00Z',
        '2026-08-09 10:00:00Z',
    ],
)
def test_confirmation_at_requires_exact_valid_utc_seconds(
    client, repair_schema, privileged_headers, confirmation_at
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['verifier_confirmation']['confirmation_at'] = confirmation_at
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    'confirmation_reference',
    [' leading', 'trailing ', 'unicode-ә', '', 'a' * 129],
)
def test_confirmation_reference_uses_exact_ascii_vocabulary(
    client, repair_schema, privileged_headers, confirmation_reference
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['verifier_confirmation']['confirmation_reference'] = confirmation_reference
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422


def test_future_start_date_is_blocked_by_open_start_date(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['start_date'] = (scenario['business_date'] + timedelta(days=1)).isoformat()
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['classification'] is None
        assert body['invalid_assignment_inputs'] == ['start_date']
        assert 'INVALID_ASSIGNMENT_DATES' in _codes(body)
        assert body['preflight_complete'] is False
        assert body['apply_available'] is False


@pytest.mark.parametrize('replacement', [' CODE', 'CODE ', 'CОDE'])
def test_org_stable_code_rejects_whitespace_and_unicode_confusables(
    client, repair_schema, privileged_headers, replacement
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['org_unit']['org_unit_normalized_stable_code'] = replacement
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422


def test_org_stable_code_is_case_sensitive(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        code = scenario['org_code']
        replacement = ''.join(
            char.swapcase() if char.isascii() and char.isalpha() else char
            for char in code
        )
        if replacement == code:
            pytest.skip('selected test org code has no ASCII letters')
        intent = _complete_intent(scenario)
        intent['org_unit']['org_unit_normalized_stable_code'] = replacement
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['classification'] is None
        assert 'ORG_UNIT_CONFIRMATION_MISMATCH' in _codes(body)


def test_position_confirmation_rejects_non_normalized_input(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent['position']['operator_confirmed_normalized_position_name'] += ' X'
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    ("field_path", "replacement", "invalid_name", "blocker"),
    [
        (
            ("org_unit", "operator_confirmed_normalized_org_name"),
            "wrong org",
            "org_unit",
            "ORG_UNIT_CONFIRMATION_MISMATCH",
        ),
        (
            ("org_unit", "org_unit_normalized_stable_code"),
            "wrong-code",
            "org_unit",
            "ORG_UNIT_CONFIRMATION_MISMATCH",
        ),
        (
            ("position", "operator_confirmed_normalized_position_name"),
            "wrong position",
            "position",
            "POSITION_NAME_MISMATCH",
        ),
    ],
)
def test_confirmation_tuples_must_match_selected_ids(
    client,
    repair_schema,
    privileged_headers,
    field_path,
    replacement,
    invalid_name,
    blocker,
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent[field_path[0]][field_path[1]] = replacement
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["classification"] is None
        assert response.json()["invalid_assignment_inputs"] == [invalid_name]
        assert blocker in _codes(response.json())


@pytest.mark.parametrize(
    "field",
    ["evidence_fingerprint", "admissibility_confirmed"],
)
def test_incomplete_evidence_is_reported_as_missing_assignment_input(
    client, repair_schema, privileged_headers, field
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent["evidence"].pop(field)
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["missing_assignment_inputs"] == ["evidence"]
        assert "ASSIGNMENT_INTENT_INCOMPLETE" in _codes(response.json())


@pytest.mark.parametrize(
    "evidence",
    [
        {
            "evidence_type": "UNKNOWN",
            "evidence_fingerprint": "a" * 64,
            "admissibility_confirmed": True,
        },
        {
            "evidence_type": "EXTERNAL_REFERENCE",
            "personnel_order_id": 1,
            "evidence_fingerprint": "a" * 64,
            "admissibility_confirmed": True,
        },
        {
            "evidence_type": "PERSONNEL_ORDER",
            "personnel_order_id": 1,
            "evidence_record_id": 1,
            "evidence_fingerprint": "a" * 64,
            "external_reference": "forbidden",
            "admissibility_confirmed": True,
        },
    ],
)
def test_unsupported_or_mutually_inconsistent_evidence_shapes_are_rejected(
    client, repair_schema, privileged_headers, evidence
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent["evidence"] = evidence
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 422
        assert scenario["iin"] not in response.text


def test_is_primary_must_be_explicitly_true(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        intent = _complete_intent(scenario)
        intent["is_primary"] = False
        response = client.post(
            ROUTE, json=_request(scenario, intent=intent), headers=privileged_headers
        )
        assert response.status_code == 200
        assert response.json()["invalid_assignment_inputs"] == ["is_primary"]
        assert "ASSIGNMENT_INTENT_INCOMPLETE" in _codes(response.json())
        assert response.json()["classification"] is None
        assert response.json()["mode"] is None
        assert response.json()["proposed_outcome"] is None


def test_unknown_request_and_assignment_fields_are_rejected(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload["authoritative_mode"] = "P0_CREATE"
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 422
        payload = _request(scenario)
        payload["assignment_intent"]["comment"] = "not controlled"
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 422


def test_import_and_employee_projection_do_not_infer_assignment_intent(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        payload = _request(scenario)
        payload.pop("assignment_intent")
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["missing_assignment_inputs"] == sorted(
            [
                "org_unit",
                "position",
                "rate",
                "employment_type",
                "is_primary",
                "start_date",
                "evidence",
                "reason_code",
                "verifier_confirmation",
            ]
        )
        assert body["classification"] is None
        assert body["mode"] is None
        assert body["proposed_outcome"] is None
        assert body["preflight_complete"] is False


def test_preflight_does_not_read_hire_events_or_personnel_orders_for_intent(
    client, repair_schema, privileged_headers
) -> None:
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    with _scenario() as scenario:
        payload = _request(scenario)
        payload.pop("assignment_intent")
        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            response = client.post(ROUTE, json=payload, headers=privileged_headers)
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
        assert response.status_code == 200, response.text
        observed_sql = "\n".join(statements)
        assert "employee_events" not in observed_sql
        assert "personnel_orders" not in observed_sql
        assert response.json()["missing_assignment_inputs"] == sorted(
            [
                "org_unit",
                "position",
                "rate",
                "employment_type",
                "is_primary",
                "start_date",
                "evidence",
                "reason_code",
                "verifier_confirmation",
            ]
        )
        assert response.json()["classification"] is None
        assert response.json()["mode"] is None
        assert response.json()["proposed_outcome"] is None


def test_client_cannot_supply_classification_mode_or_outcome(
    client, privileged_headers
) -> None:
    response = client.post(
        ROUTE,
        json={
            "iin": "123456789012",
            "classification": "P0_CREATE",
            "mode": "LINK_AND_OPEN_MISSING_ASSIGNMENT",
            "proposed_outcome": "EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED",
        },
        headers=privileged_headers,
    )
    assert response.status_code == 422


def test_exact_iin_lookup_has_no_name_fallback(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        wrong_iin = scenario["iin"][:-1] + ("0" if scenario["iin"][-1] != "0" else "1")
        response = client.post(
            ROUTE,
            json={"iin": wrong_iin, "assignment_intent": _complete_intent(scenario)},
            headers=privileged_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["import_records"] == []
        assert body["employees"] == []
        assert body["person_candidates"] == []
        assert "EMPLOYEE_NOT_FOUND" in _codes(body)
        assert "CONTROL_LIST_RECORD_NOT_FOUND" in _codes(body)


def _read_snapshot(conn, scenario: dict) -> dict:
    side_effect_tables = (
        "audit_log",
        "employee_events",
        "personnel_record_events",
        "hr_sync_audit_log",
        "personnel_application_lifecycle_audit",
        "personnel_application_resolution_audit",
    )
    return {
        "employee": conn.execute(
            text(
                "SELECT to_jsonb(e) FROM public.employees e "
                "WHERE employee_id=:id"
            ),
            {"id": scenario["employee_id"]},
        ).scalar_one(),
        "identities": conn.execute(
            text(
                "SELECT to_jsonb(ei) FROM public.employee_identities ei "
                "WHERE employee_id=:id ORDER BY identity_id"
            ),
            {"id": scenario["employee_id"]},
        ).scalars().all(),
        "persons": conn.execute(
            text(
                "SELECT to_jsonb(p) FROM public.persons p "
                "WHERE iin=:iin ORDER BY person_id"
            ),
            {"iin": scenario["iin"]},
        ).scalars().all(),
        "assignments": conn.execute(
            text(
                "SELECT to_jsonb(pa) FROM public.person_assignments pa "
                "WHERE person_id=ANY(:ids) ORDER BY assignment_id"
            ),
            {"ids": scenario["person_ids"] or [-1]},
        ).scalars().all(),
        "batch": conn.execute(
            text(
                "SELECT to_jsonb(b) FROM public.hr_import_batches b "
                "WHERE batch_id=:batch"
            ),
            {"batch": scenario["batch_id"]},
        ).scalar_one(),
        "import_rows": conn.execute(
            text(
                "SELECT to_jsonb(r) FROM public.hr_import_rows r "
                "WHERE batch_id=:batch ORDER BY row_id"
            ),
            {"batch": scenario["batch_id"]},
        ).scalars().all(),
        "normalized_records": conn.execute(
            text(
                "SELECT to_jsonb(nr) FROM public.hr_import_normalized_records nr "
                "WHERE row_id=:row_id ORDER BY normalized_record_id"
            ),
            {"row_id": scenario["row_id"]},
        ).scalars().all(),
        "activation_watermark": conn.execute(
            text(
                "SELECT to_jsonb(w) FROM public.person_assignment_activation_watermark w "
                "WHERE singleton IS TRUE"
            )
        ).scalar_one(),
        "personnel_order": conn.execute(
            text("SELECT to_jsonb(po) FROM public.personnel_orders po WHERE order_id=:id"),
            {"id": scenario["personnel_order_id"]},
        ).scalar_one(),
        "personnel_order_items": conn.execute(
            text("SELECT to_jsonb(i) FROM public.personnel_order_items i WHERE order_id=:id ORDER BY item_id"),
            {"id": scenario["personnel_order_id"]},
        ).scalars().all(),
        "personnel_order_evidence_scope": conn.execute(
            text("SELECT to_jsonb(s) FROM public.personnel_order_evidence_scopes s WHERE order_id=:id"),
            {"id": scenario["personnel_order_id"]},
        ).scalar_one(),
        "side_effect_counts": tuple(
            (
                table,
                conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one(),
            )
            for table in side_effect_tables
            if table_exists(conn, table)
        ),
        "sequences": tuple(
            conn.execute(
                text(
                    "SELECT sequencename, last_value FROM pg_sequences "
                    "WHERE schemaname='public' AND ("
                    "sequencename LIKE 'persons%' "
                    "OR sequencename LIKE 'person_assignments%' "
                    "OR sequencename LIKE 'employee_identities%' "
                    "OR sequencename LIKE 'hr_import%' "
                    "OR sequencename LIKE '%audit%' "
                    "OR sequencename LIKE '%event%' "
                    "OR sequencename LIKE '%operation%') ORDER BY sequencename"
                )
            ).all()
        ),
    }


def _post_write_free(
    client,
    privileged_headers,
    scenario: dict,
    payload: dict,
):
    statements: list[str] = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with engine.connect() as conn:
        before = _read_snapshot(conn, scenario)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = client.post(ROUTE, json=payload, headers=privileged_headers)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    with engine.connect() as conn:
        after = _read_snapshot(conn, scenario)
    assert after == before
    forbidden = ("INSERT", "UPDATE", "DELETE", "MERGE", "NEXTVAL", "SETVAL")
    assert not any(
        statement.lstrip().upper().startswith(forbidden)
        or "NEXTVAL(" in statement.upper()
        or "SETVAL(" in statement.upper()
        for statement in statements
    )
    return response


@pytest.mark.parametrize("person_status", [None, "active"])
def test_successful_p0_and_p1_are_write_free(
    client, repair_schema, privileged_headers, person_status
) -> None:
    with _scenario(person_status=person_status) as scenario:
        response = _post_write_free(
            client, privileged_headers, scenario, _request(scenario)
        )
        assert response.status_code == 200, response.text
        assert response.json()["classification"] == (
            "P0_CREATE" if person_status is None else "P1_ADOPT"
        )


def test_incomplete_intent_and_import_selection_exits_are_write_free(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        no_intent = _request(scenario)
        no_intent.pop("assignment_intent")
        response = _post_write_free(
            client, privileged_headers, scenario, no_intent
        )
        assert "ASSIGNMENT_INTENT_INCOMPLETE" in _codes(response.json())

        no_selection = _request(scenario)
        no_selection.pop("import_selection")
        response = _post_write_free(
            client, privileged_headers, scenario, no_selection
        )
        assert "IMPORT_SELECTION_REQUIRED" in _codes(response.json())

        incomplete_selection = _request(scenario)
        incomplete_selection["import_selection"]["normalized_record_ids"].pop()
        response = _post_write_free(
            client, privileged_headers, scenario, incomplete_selection
        )
        assert "IMPORT_SELECTION_INCOMPLETE" in _codes(response.json())


@pytest.mark.parametrize("person_status", ["inactive", "active"])
def test_person_resolution_blocked_exits_are_write_free(
    client, repair_schema, privileged_headers, person_status
) -> None:
    with _scenario(person_status=person_status) as scenario:
        if person_status == "active":
            with engine.begin() as conn:
                incompatible_id = insert_returning_id(
                    conn,
                    table="persons",
                    id_col="person_id",
                    values={
                        "full_name": f"ADR065 inactive {uuid4().hex[:8]}",
                        "iin": scenario["iin"],
                        "match_key": f"adr065-inactive:{uuid4().hex}",
                        "person_status": "inactive",
                        "source": "manual",
                    },
                )
                scenario["person_ids"].append(incompatible_id)
        response = _post_write_free(
            client, privileged_headers, scenario, _request(scenario)
        )
        assert response.status_code == 200
        assert response.json()["classification"] is None
        expected = "INCOMPATIBLE_PERSON" if person_status == "inactive" else "AMBIGUOUS_PERSON"
        assert expected in _codes(response.json())


def test_structural_and_import_ownership_blocked_exits_are_write_free(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario(person_status="active", linked=True) as scenario:
        response = _post_write_free(
            client, privileged_headers, scenario, _request(scenario)
        )
        assert "EMPLOYEE_ALREADY_LINKED" in _codes(response.json())

    with _scenario() as scenario:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.hr_import_rows SET employee_id=NULL WHERE row_id=:row_id"
                ),
                {"row_id": scenario["row_id"]},
            )
            conn.execute(
                text(
                    "UPDATE public.hr_import_normalized_records SET employee_id=NULL "
                    "WHERE normalized_record_id=:record_id"
                ),
                {"record_id": scenario["normalized_record_ids"][0]},
            )
        try:
            response = _post_write_free(
                client, privileged_headers, scenario, _request(scenario)
            )
            assert "IMPORT_ROW_OWNERSHIP_CONFLICT" in _codes(response.json())
            assert "IMPORT_NORMALIZED_RECORD_OWNERSHIP_CONFLICT" in _codes(
                response.json()
            )
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE public.hr_import_rows SET employee_id=:employee_id "
                        "WHERE row_id=:row_id"
                    ),
                    {
                        "employee_id": scenario["employee_id"],
                        "row_id": scenario["row_id"],
                    },
                )
                conn.execute(
                    text(
                        "UPDATE public.hr_import_normalized_records "
                        "SET employee_id=:employee_id "
                        "WHERE normalized_record_id=:record_id"
                    ),
                    {
                        "employee_id": scenario["employee_id"],
                        "record_id": scenario["normalized_record_ids"][0],
                    },
                )


def test_cross_batch_provenance_blocker_is_write_free(
    client, repair_schema, privileged_headers
) -> None:
    with _scenario() as scenario:
        other_batch_id: int | None = None
        try:
            with engine.begin() as conn:
                other_batch_id = insert_returning_id(
                    conn,
                    table='hr_import_batches',
                    id_col='batch_id',
                    values={
                        'source_type': 'HR_CONTROL_LIST',
                        'file_name': f'adr065-write-free-{uuid4().hex[:8]}.xlsx',
                        'import_code': f'ADR065-WF-{uuid4().hex[:8]}',
                        'imported_by': scenario['user_id'],
                        'status': 'PARSED',
                        'total_rows': 0,
                        'valid_rows': 0,
                        'error_rows': 0,
                    },
                )
                insert_returning_id(
                    conn,
                    table='hr_import_normalized_records',
                    id_col='normalized_record_id',
                    values={
                        'batch_id': other_batch_id,
                        'row_id': scenario['row_id'],
                        'employee_id': scenario['employee_id'],
                        'fragment_index': 100,
                        'source_field': 'training',
                        'source_text': 'cross-batch write-free sibling',
                        'source_record_key': f'adr065:wf:{uuid4().hex}',
                        'record_kind': 'training',
                        'parse_method': 'regex_v1',
                        'review_status': 'pending',
                    },
                )
            response = _post_write_free(
                client, privileged_headers, scenario, _request(scenario)
            )
            assert response.status_code == 200, response.text
            assert 'IMPORT_NORMALIZED_RECORD_BATCH_MISMATCH' in _codes(response.json())
        finally:
            if other_batch_id is not None:
                with engine.begin() as conn:
                    conn.execute(
                        text('DELETE FROM public.hr_import_batches WHERE batch_id=:id'),
                        {'id': other_batch_id},
                    )


@pytest.mark.parametrize(
    "exception_factory",
    [
        lambda iin: SQLAlchemyError(f"statement bind contained {iin}"),
        lambda iin: RuntimeError(f"internal payload contained {iin}"),
    ],
)
def test_error_exits_are_write_free(
    client,
    repair_schema,
    privileged_headers,
    monkeypatch,
    exception_factory,
) -> None:
    from app.personnel_lk.application import control_list_repair_preflight_service

    with _scenario() as scenario:
        original = control_list_repair_preflight_service._load_employees

        def fail_after_business_select(conn, iin):
            rows = original(conn, iin)
            assert rows
            raise exception_factory(scenario["iin"])

        monkeypatch.setattr(
            control_list_repair_preflight_service,
            "_load_employees",
            fail_after_business_select,
        )
        response = _post_write_free(
            client, privileged_headers, scenario, _request(scenario)
        )
        assert response.status_code == 500


def test_route_starts_repeatable_read_read_only_transaction(
    client, repair_schema, privileged_headers, monkeypatch
) -> None:
    from app.directory import personnel_lk_routes

    original = personnel_lk_routes.control_list_repair_preflight

    def inspect_transaction(conn, **kwargs):
        assert conn.execute(text("SHOW transaction_isolation")).scalar_one() == (
            "repeatable read"
        )
        assert conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        return original(conn, **kwargs)

    monkeypatch.setattr(
        personnel_lk_routes,
        "control_list_repair_preflight",
        inspect_transaction,
    )
    with _scenario() as scenario:
        response = client.post(
            ROUTE, json=_request(scenario), headers=privileged_headers
        )
        assert response.status_code == 200, response.text
