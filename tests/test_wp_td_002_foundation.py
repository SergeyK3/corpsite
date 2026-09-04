from __future__ import annotations

import hashlib
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Event

import pytest
from pydantic import ValidationError
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app import auth
from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.security.admin_permissions import (
    TEST_PERSONNEL_DELETION_APPROVE,
    TEST_PERSONNEL_DELETION_AUDIT_READ,
    TEST_PERSONNEL_DELETION_EXECUTE,
    TEST_PERSONNEL_DELETION_REQUEST,
    has_admin_permission,
    get_test_personnel_deletion_capabilities,
)
from app.security import admin_permissions
from app.services import test_personnel_deletion_service as service
from app.directory import test_personnel_deletion_routes as td_routes
from app.directory.test_personnel_deletion_schemas import (
    TestPersonnelDraftCreateIn as PersonnelDraftCreateIn,
)


@pytest.fixture
def td_actors():
    created: list[int] = []
    with engine.begin() as conn:
        for code in ("HR_HEAD",):
            present = conn.execute(text("""SELECT 1 FROM users u JOIN roles r USING(role_id)
                WHERE r.code=:code AND u.is_active=TRUE LIMIT 1"""), {"code": code}).first()
            if not present:
                role_id = conn.execute(text("SELECT role_id FROM roles WHERE code=:code"), {"code": code}).scalar_one()
                user_id = conn.execute(text("""INSERT INTO users(user_id,full_name,role_id,is_active,login)
                    VALUES((SELECT COALESCE(MAX(user_id),0)+1 FROM users),:name,:role,TRUE,:login) RETURNING user_id"""),
                    {"name": f"WP TD {code}", "role": role_id, "login": f"wp-td-{code.lower()}-{uuid.uuid4().hex[:8]}"}).scalar_one()
                created.append(int(user_id))
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ON (r.code) u.user_id, u.role_id, r.code
                FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
                WHERE r.code IN ('ADMIN','HR_HEAD') AND u.is_active=TRUE
                ORDER BY r.code, u.user_id
                """
            )
        ).mappings().all()
    actors = {str(row["code"]): dict(row) for row in rows}
    assert set(actors) == {"ADMIN", "HR_HEAD"}
    yield actors
    if created:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE user_id=ANY(:ids)"), {"ids": created})


@pytest.fixture
def td_candidates(td_actors):
    suffix = uuid.uuid4().hex[:12]
    actor = int(td_actors["ADMIN"]["user_id"])
    created: list[tuple[int, int]] = []
    with engine.begin() as conn:
        for label, status in (("pending", "intake_pending"), ("submitted", "intake_submitted"), ("drift", "intake_pending")):
            person_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.persons (full_name, match_key, source)
                        VALUES (:name, :match_key, 'manual') RETURNING person_id
                        """
                    ),
                    {"name": f"WP TD {label} 100%_\\ {suffix}", "match_key": f"wp-td-{label}-{suffix}"},
                ).scalar_one()
            )
            application_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.personnel_applications (
                            person_id, status, application_received_at, registered_by_user_id, idempotency_key
                        ) VALUES (:person_id, :status, :received, :actor, :key)
                        RETURNING application_id
                        """
                    ),
                    {"person_id": person_id, "status": status, "received": date.today(),
                     "actor": actor, "key": f"wp-td-{label}-{suffix}"},
                ).scalar_one()
            )
            created.append((person_id, application_id))
    yield {"pending": created[0], "submitted": created[1], "drift": created[2], "suffix": suffix}
    with engine.begin() as conn:
        person_ids = [row[0] for row in created]
        application_ids = [row[1] for row in created]
        conn.execute(text("DELETE FROM public.contacts WHERE person_id=ANY(:ids)"), {"ids": person_ids})
        conn.execute(text("DELETE FROM public.personnel_applications WHERE application_id=ANY(:ids)"), {"ids": application_ids})
        conn.execute(text("DELETE FROM public.persons WHERE person_id=ANY(:ids)"), {"ids": person_ids})


def _as(client, actor):
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": int(actor["user_id"]), "role_id": int(actor["role_id"]), "role_code": actor["code"]
    }
    return client


def _draft_payload(target, *, suffix, status="pending"):
    person_id, application_id = target
    return {
        "basis": "LEGACY_MANIFEST",
        "reason_code": "LEGACY_SYNTHETIC_TEST_DATA",
        "search_field": "full_name",
        "original_mask": f"WP TD {status}*{suffix}",
        "targets": [{"person_id": person_id, "application_id": application_id}],
        "idempotency_key": f"create-{status}-{suffix}-{uuid.uuid4().hex[:6]}",
    }


def test_permission_matrix_is_exact(td_actors):
    admin = int(td_actors["ADMIN"]["user_id"])
    hr = int(td_actors["HR_HEAD"]["user_id"])
    assert has_admin_permission(admin, TEST_PERSONNEL_DELETION_REQUEST)
    assert has_admin_permission(admin, TEST_PERSONNEL_DELETION_EXECUTE)
    assert has_admin_permission(admin, TEST_PERSONNEL_DELETION_AUDIT_READ)
    assert not has_admin_permission(admin, TEST_PERSONNEL_DELETION_APPROVE)
    assert has_admin_permission(hr, TEST_PERSONNEL_DELETION_APPROVE)
    assert has_admin_permission(hr, TEST_PERSONNEL_DELETION_AUDIT_READ)
    assert not has_admin_permission(hr, TEST_PERSONNEL_DELETION_REQUEST)
    assert not has_admin_permission(hr, TEST_PERSONNEL_DELETION_EXECUTE)


def test_auth_me_projects_exact_test_personnel_capabilities(client, td_actors):
    admin = auth._enrich_user_context(dict(td_actors["ADMIN"]))
    hr = auth._enrich_user_context(dict(td_actors["HR_HEAD"]))
    assert admin["can_request_test_personnel_deletion"] is True
    assert admin["can_approve_test_personnel_deletion"] is False
    assert admin["can_read_test_personnel_deletion_audit"] is True
    assert hr["can_request_test_personnel_deletion"] is False
    assert hr["can_approve_test_personnel_deletion"] is True
    assert hr["can_read_test_personnel_deletion_audit"] is True
    assert "can_execute_test_personnel_deletion" not in admin
    assert "can_execute_test_personnel_deletion" not in hr
    previous_override = app.dependency_overrides.get(get_current_user)
    try:
        app.dependency_overrides[get_current_user] = lambda: admin
        admin_me = client.get("/auth/me")
        assert admin_me.status_code == 200
        assert admin_me.json()["can_request_test_personnel_deletion"] is True
        assert "can_execute_test_personnel_deletion" not in admin_me.json()
        app.dependency_overrides[get_current_user] = lambda: hr
        hr_me = client.get("/auth/me")
        assert hr_me.status_code == 200
        assert hr_me.json()["can_approve_test_personnel_deletion"] is True
        assert "can_execute_test_personnel_deletion" not in hr_me.json()
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_override


def test_admissible_primary_role_without_permission_has_no_capability(monkeypatch, td_actors):
    monkeypatch.setattr(admin_permissions, "has_admin_permission", lambda _user_id, _code: False)
    capabilities = admin_permissions.get_test_personnel_deletion_capabilities(
        td_actors["ADMIN"]["user_id"]
    )
    assert capabilities == {
        "can_request_test_personnel_deletion": False,
        "can_approve_test_personnel_deletion": False,
        "can_read_test_personnel_deletion_audit": False,
    }


def test_create_schema_still_rejects_unknown_comment(td_candidates):
    with pytest.raises(ValidationError):
        PersonnelDraftCreateIn.model_validate({
            **_draft_payload(td_candidates["pending"], suffix="schema-comment"),
            "comment": "Свободный комментарий создания запрещён",
        })


def test_mask_contract_and_preview_are_read_only(td_candidates):
    person_id, application_id = td_candidates["pending"]
    before = engine.connect().execute(text("SELECT COUNT(*) FROM public.test_personnel_deletion_requests")).scalar_one()
    wildcard = service.preview_candidates(
        mask=f"WP TD pend?ng*{td_candidates['suffix']}", field="full_name", person_ids=[], application_ids=[]
    )
    literal = service.preview_candidates(
        mask=f"WP TD pending 100%_\\ {td_candidates['suffix']}", field="full_name", person_ids=[], application_ids=[]
    )
    after = engine.connect().execute(text("SELECT COUNT(*) FROM public.test_personnel_deletion_requests")).scalar_one()
    assert [(row["person_id"], row["application_id"]) for row in wildcard["items"]] == [(person_id, application_id)]
    assert literal["count"] == 1
    assert before == after
    assert service.glob_to_ilike(r"ABC%_\\*") == "ABC\\%\\_\\\\\\\\%"
    with pytest.raises(service.TestPersonnelDeletionError, match="Mask"):
        service.normalize_mask("**")


def test_create_freezes_exact_manifest_and_is_idempotent(client, td_actors, td_candidates):
    admin_client = _as(client, td_actors["ADMIN"])
    payload = _draft_payload(td_candidates["pending"], suffix=td_candidates["suffix"])
    first = admin_client.post("/directory/test-personnel-deletion/requests", json=payload)
    second = admin_client.post("/directory/test-personnel-deletion/requests", json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["request_id"] == second.json()["request_id"]
    assert len(first.json()["targets"]) == 1
    # Another matching row already exists; the request remains the exact submitted manifest.
    detail = admin_client.get(f"/directory/test-personnel-deletion/requests/{first.json()['request_id']}")
    assert len(detail.json()["targets"]) == 1


def test_submit_approve_reject_cancel_and_submitted_attestation(client, td_actors, td_candidates):
    admin_client = _as(client, td_actors["ADMIN"])
    payload = _draft_payload(td_candidates["pending"], suffix=td_candidates["suffix"])
    draft = admin_client.post("/directory/test-personnel-deletion/requests", json=payload).json()
    submitted = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": draft["version"], "idempotency_key": f"submit-{td_candidates['suffix']}"},
    )
    assert submitted.status_code == 200, submitted.text
    pending = submitted.json()
    assert pending["status"] == "PENDING_HR_APPROVAL"
    repeated = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": draft["version"], "idempotency_key": f"submit-{td_candidates['suffix']}"},
    )
    assert repeated.status_code == 200 and repeated.json()["version"] == pending["version"]

    with pytest.raises(service.TestPersonnelDeletionError) as separation:
        service.decide_request(
            request_id=uuid.UUID(draft["request_id"]), actor_user_id=int(td_actors["ADMIN"]["user_id"]),
            expected_version=pending["version"], decision="APPROVE",
            idempotency_key=f"sod-{td_candidates['suffix']}", comment=None,
            submitted_synthetic_confirmed=False,
        )
    assert separation.value.code == "TD_SEPARATION_OF_DUTIES"

    hr_client = _as(client, td_actors["HR_HEAD"])
    approved = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{draft['request_id']}/approve",
        json={"expected_version": pending["version"], "idempotency_key": f"approve-{td_candidates['suffix']}",
              "comment": "Synthetic fixture confirmed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["approval_expires_at"] is not None
    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE test_personnel_deletion_decisions SET comment='changed' WHERE request_id=:id"), {"id": draft["request_id"]})

    admin_client = _as(client, td_actors["ADMIN"])
    cancelled = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/cancel",
        json={"expected_version": approved.json()["version"], "idempotency_key": f"cancel-{td_candidates['suffix']}"},
    )
    assert cancelled.json()["status"] == "CANCELLED"

    submitted_payload = _draft_payload(td_candidates["submitted"], suffix=td_candidates["suffix"], status="submitted")
    submitted_draft = admin_client.post("/directory/test-personnel-deletion/requests", json=submitted_payload).json()
    queued = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{submitted_draft['request_id']}/submit",
        json={"expected_version": 1, "idempotency_key": f"submit-submitted-{td_candidates['suffix']}"},
    ).json()
    hr_client = _as(client, td_actors["HR_HEAD"])
    denied = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{submitted_draft['request_id']}/approve",
        json={"expected_version": queued["version"], "idempotency_key": f"approve-no-attest-{td_candidates['suffix']}"},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "TD_SUBMITTED_ATTESTATION_REQUIRED"
    accepted = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{submitted_draft['request_id']}/approve",
        json={"expected_version": queued["version"], "idempotency_key": f"approve-attest-{td_candidates['suffix']}",
              "submitted_synthetic_confirmed": True},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["decisions"][-1]["submitted_synthetic_confirmed"] is True

    admin_client = _as(client, td_actors["ADMIN"])
    reject_payload = _draft_payload(td_candidates["pending"], suffix=td_candidates["suffix"], status="reject")
    reject_draft = admin_client.post("/directory/test-personnel-deletion/requests", json=reject_payload).json()
    reject_pending = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{reject_draft['request_id']}/submit",
        json={"expected_version": 1, "idempotency_key": f"submit-reject-{td_candidates['suffix']}"},
    ).json()
    hr_client = _as(client, td_actors["HR_HEAD"])
    rejected = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{reject_draft['request_id']}/reject",
        json={"expected_version": reject_pending["version"], "idempotency_key": f"reject-{td_candidates['suffix']}"},
    )
    assert rejected.json()["status"] == "REJECTED"


def test_optimistic_lock_fingerprint_change_and_expiry(client, td_actors, td_candidates, monkeypatch):
    admin_client = _as(client, td_actors["ADMIN"])
    payload = _draft_payload(td_candidates["drift"], suffix=td_candidates["suffix"], status="drift")
    draft = admin_client.post("/directory/test-personnel-deletion/requests", json=payload).json()
    stale = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": 99, "idempotency_key": f"stale-{td_candidates['suffix']}"},
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "TD_VERSION_CONFLICT"
    queued = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": 1, "idempotency_key": f"submit-drift-{td_candidates['suffix']}"},
    ).json()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO public.contacts (person_id, full_name) VALUES (:id, 'Synthetic Contact')"),
                     {"id": td_candidates["drift"][0]})
    hr_client = _as(client, td_actors["HR_HEAD"])
    drift = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{draft['request_id']}/approve",
        json={"expected_version": queued["version"], "idempotency_key": f"approve-drift-{td_candidates['suffix']}"},
    )
    assert drift.status_code == 409
    assert drift.json()["detail"]["request"]["status"] == "REAPPROVAL_REQUIRED"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.contacts WHERE person_id=:id"), {"id": td_candidates["drift"][0]})
    admin_client = _as(client, td_actors["ADMIN"])
    resubmitted = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": drift.json()["detail"]["request"]["version"],
              "idempotency_key": f"resubmit-drift-{td_candidates['suffix']}"},
    )
    assert resubmitted.status_code == 200 and resubmitted.json()["status"] == "PENDING_HR_APPROVAL"

    # A separate pending request transitions to EXPIRED when HR attempts a late decision.
    payload2 = _draft_payload(td_candidates["pending"], suffix=td_candidates["suffix"], status="expire")
    admin_client = _as(client, td_actors["ADMIN"])
    draft2 = admin_client.post("/directory/test-personnel-deletion/requests", json=payload2).json()
    queued2 = admin_client.post(
        f"/directory/test-personnel-deletion/requests/{draft2['request_id']}/submit",
        json={"expected_version": 1, "idempotency_key": f"submit-expire-{td_candidates['suffix']}"},
    ).json()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE public.test_personnel_deletion_requests SET expires_at=created_at+interval '1 microsecond' WHERE request_id=:id"),
            {"id": draft2["request_id"]},
        )
    hr_client = _as(client, td_actors["HR_HEAD"])
    expired = hr_client.post(
        f"/directory/test-personnel-deletion/approvals/{draft2['request_id']}/approve",
        json={"expected_version": queued2["version"], "idempotency_key": f"approve-expire-{td_candidates['suffix']}"},
    )
    assert expired.status_code == 409
    assert expired.json()["detail"]["request"]["status"] == "EXPIRED"


def test_existing_test_records_have_expected_hardened_classification(client, td_actors):
    suffix = uuid.uuid4().hex[:10]
    actor = int(td_actors["ADMIN"]["user_id"])
    created: list[tuple[int, int]] = []
    with engine.begin() as conn:
        for index in range(11):
            prefix = "Demo Intake Applicant" if index < 8 else "Debug Applicant"
            status = "intake_submitted" if index < 6 else "intake_pending"
            person_id = int(conn.execute(text("""INSERT INTO persons(full_name,match_key,source)
                VALUES(:name,:key,'manual') RETURNING person_id"""), {
                "name": f"{prefix} {index} {suffix}", "key": f"td002b-eleven-{index}-{suffix}",
            }).scalar_one())
            application_id = int(conn.execute(text("""INSERT INTO personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key)
                VALUES(:person_id,:status,current_date,:actor,:key) RETURNING application_id"""), {
                "person_id": person_id, "status": status, "actor": actor,
                "key": f"td002b-eleven-app-{index}-{suffix}",
            }).scalar_one())
            conn.execute(text("""INSERT INTO personnel_record_events(
                person_id,record_table_name,record_id,event_type,event_payload)
                VALUES(:person_id,'personnel_applications',:application_id,'CREATED','{}'::jsonb)"""), {
                "person_id": person_id, "application_id": application_id,
            })
            conn.execute(text("""INSERT INTO ppr_command_executions(
                command_id,command_type,person_id,request_fingerprint,status,result_payload)
                VALUES(:command_id,'REGISTER',:person_id,:fingerprint,'completed','{}'::jsonb)"""), {
                "command_id": f"td002b-eleven-command-{index}-{suffix}",
                "person_id": person_id, "fingerprint": hashlib.sha256(
                    f"{person_id}:{application_id}:{suffix}".encode()
                ).hexdigest(),
            })
            created.append((person_id, application_id))
        blocked_person_id = created[-1][0]
        conn.execute(text("INSERT INTO personnel(person_id,date_from) VALUES(:id,current_date)"), {"id": blocked_person_id})
        conn.execute(text("INSERT INTO contacts(person_id,full_name) VALUES(:id,'Synthetic legacy contact')"), {"id": blocked_person_id})

    try:
        debug = service.preview_candidates(mask=f"Debug Applicant*{suffix}", field="full_name", person_ids=[], application_ids=[])
        demo = service.preview_candidates(mask=f"Demo Intake Applicant*{suffix}", field="full_name", person_ids=[], application_ids=[])
        assert debug["count"] == 3 and demo["count"] == 8
        assert all({"PPR_EVENT_TOMBSTONE_REQUIRED", "PPR_COMMAND_TOMBSTONE_REQUIRED"}.issubset(row["tombstone_required_codes"]) for row in debug["items"] + demo["items"])
        assert all(not {"PPR_EVENT_TOMBSTONE_REQUIRED", "PPR_COMMAND_TOMBSTONE_REQUIRED"}.intersection(row["blocking_codes"]) for row in debug["items"] + demo["items"])
        all_rows = debug["items"] + demo["items"]
        allowed = [row for row in all_rows if not row["blocking_codes"]]
        blocked = [row for row in all_rows if row["blocking_codes"]]
        submitted = [row for row in all_rows if row["application_status"] == "intake_submitted"]
        assert len(allowed) == 10
        assert len(blocked) == 1
        assert len(submitted) == 6
        assert all("SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED" in row["hr_attestation_codes"] for row in submitted)
        assert {"LEGACY_PERSONNEL_PRESENT", "CONTACT_PRESENT"}.issubset(blocked[0]["blocking_codes"])

        admin_client = _as(client, td_actors["ADMIN"])
        draft = admin_client.post("/directory/test-personnel-deletion/requests", json={
            "basis": "LEGACY_MANIFEST", "reason_code": "LEGACY_SYNTHETIC_TEST_DATA",
            "original_mask": f"*Applicant*{suffix}",
            "targets": [{"person_id": row["person_id"], "application_id": row["application_id"]} for row in allowed],
            "idempotency_key": f"existing-ten-{uuid.uuid4().hex}",
        })
        assert draft.status_code == 201, draft.text
        pending = admin_client.post(
            f"/directory/test-personnel-deletion/requests/{draft.json()['request_id']}/submit",
            json={"expected_version": 1, "idempotency_key": f"existing-ten-submit-{uuid.uuid4().hex}"},
        )
        assert pending.status_code == 200, pending.text
        hr_client = _as(client, td_actors["HR_HEAD"])
        approved = hr_client.post(
            f"/directory/test-personnel-deletion/approvals/{draft.json()['request_id']}/approve",
            json={"expected_version": 2, "idempotency_key": f"existing-ten-approve-{uuid.uuid4().hex}", "submitted_synthetic_confirmed": True},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        employee_person_id = allowed[0]["person_id"]
        with engine.begin() as conn:
            employee_id = conn.execute(text("""INSERT INTO employees(employee_id,full_name,person_id)
                VALUES((SELECT COALESCE(MAX(employee_id),0)+1 FROM employees),'WP TD synthetic employee',:person_id)
                RETURNING employee_id"""), {"person_id": employee_person_id}).scalar_one()
        employee = service.preview_candidates(mask=None, field="full_name", person_ids=[employee_person_id], application_ids=[])
        assert any("EMPLOYEE_PRESENT" in row["blocking_codes"] for row in employee["items"])
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM employees WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})
            conn.execute(text("DELETE FROM contacts WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})
            conn.execute(text("DELETE FROM personnel WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})
            conn.execute(text("DELETE FROM ppr_command_executions WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})
            conn.execute(text("DELETE FROM personnel_record_events WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})
            conn.execute(text("DELETE FROM personnel_applications WHERE application_id=ANY(:ids)"), {"ids": [a for _, a in created]})
            conn.execute(text("DELETE FROM persons WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in created]})


def test_history_minimizes_pii_and_append_only(td_actors, td_candidates):
    request = service.create_draft(
        actor_user_id=int(td_actors["ADMIN"]["user_id"]), basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA", preview_criteria={"field": "full_name"}, original_mask="WP TD pending*",
        targets=[{"person_id": td_candidates["pending"][0], "application_id": td_candidates["pending"][1]}],
        idempotency_key=f"audit-{td_candidates['suffix']}",
    )
    serialized = str(request["history"] + request["targets"]).lower()
    assert f"wp td pending 100%_\\ {td_candidates['suffix']}".lower() not in serialized
    assert "123456789012" not in serialized and "person@example.org" not in serialized
    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.test_personnel_deletion_history SET result_code='CHANGED' WHERE request_id=:id"), {"id": request["request_id"]})


def test_legacy_hard_delete_is_closed_and_execution_endpoint_absent(client, td_actors, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    admin_client = _as(client, td_actors["ADMIN"])
    suffix = uuid.uuid4().hex[:10]
    with engine.begin() as conn:
        person_id = int(conn.execute(text("""INSERT INTO persons(full_name,match_key,source)
            VALUES('WP TD delete sentinel',:key,'manual') RETURNING person_id"""), {"key": f"delete-sentinel-{suffix}"}).scalar_one())
        employee_id = int(conn.execute(text("""INSERT INTO employees(employee_id,full_name,person_id)
            VALUES((SELECT COALESCE(MAX(employee_id),0)+1 FROM employees),'WP TD delete sentinel',:person_id)
            RETURNING employee_id"""), {"person_id": person_id}).scalar_one())
    try:
        response = admin_client.delete(f"/directory/employees/{employee_id}")
        assert response.status_code == 410
        assert response.json()["detail"]["code"] == "TD_LEGACY_HARD_DELETE_DISABLED"
        bulk = admin_client.post("/directory/employees/bulk-delete", json={"employee_ids": [employee_id]})
        assert bulk.status_code == 410
        with engine.connect() as conn:
            assert conn.execute(text("SELECT EXISTS(SELECT 1 FROM public.employees WHERE employee_id=:id)"), {"id": employee_id}).scalar_one()
        execute = admin_client.post(f"/directory/test-personnel-deletion/requests/{uuid.uuid4()}/execute", json={})
        assert execute.status_code in {404, 405}
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM employees WHERE employee_id=:id"), {"id": employee_id})
            conn.execute(text("DELETE FROM persons WHERE person_id=:id"), {"id": person_id})


def test_provenance_is_not_inferred_and_is_append_only(td_candidates, td_actors):
    person_id, application_id = td_candidates["pending"]
    preview = service.preview_candidates(mask=None, field="full_name", person_ids=[person_id], application_ids=[])
    assert preview["items"][0]["has_test_provenance"] is False
    with engine.begin() as conn:
        provenance_id = conn.execute(
            text(
                """
                INSERT INTO public.test_personnel_provenance (
                    target_type,target_id,environment,test_run_id,creation_source,purpose,
                    created_by_user_id,source_artifact_hash
                ) VALUES ('APPLICATION',:target,:env,:run,'pytest','synthetic fixture',:actor,:hash)
                RETURNING provenance_id
                """
                ), {"target": application_id, "env": (__import__("os").getenv("APP_ENV") or "dev").strip().lower(), "run": f"run-{td_candidates['suffix']}",
                    "actor": int(td_actors["ADMIN"]["user_id"]), "hash": "a"*64},
            ).scalar_one()
    assert service.preview_candidates(mask=None, field="full_name", person_ids=[person_id], application_ids=[])["items"][0]["has_test_provenance"] is True
    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.test_personnel_provenance WHERE provenance_id=:id"), {"id": provenance_id})
    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.test_personnel_provenance SET purpose='changed' WHERE provenance_id=:id"), {"id": provenance_id})


def test_relationship_matrix_contains_required_hardening_links():
    matrix = {row["code"]: row for row in service.relationship_matrix_contract()}
    expected = {
        "PPR_METADATA_PRESENT", "MERGED_PERSON_REFERENCE_PRESENT", "ALL_APPLICATIONS_PRESENT",
        "ENROLLMENT_QUEUE_PRESENT", "INTAKE_RECONCILIATION_PRESENT", "INTAKE_LINK_PRESENT",
        "INTAKE_DRAFT_PRESENT", "ENROLLMENT_HISTORY_RETAINED", "SECURITY_AUDIT_RETAINED",
        "HR_IMPORT_ROW_RETAINED", "HR_IMPORT_NORMALIZED_RETAINED",
        "EMPLOYEE_ASSIGNMENT_LINK_PRESENT", "EMPLOYEE_EVENT_PRESENT", "EMPLOYEE_IDENTITY_PRESENT",
        "TERMINATION_RECORD_PRESENT", "ONBOARDING_ATTACHMENT_PRESENT", "PERSONNEL_ORDER_ITEM_PRESENT",
        "PERSONNEL_ORDER_AUDIT_RETAINED", "OPERATIONAL_ORDER_SIGNING_PRESENT",
        "ACCESS_GRANT_RETAINED", "PERSONNEL_VISIBILITY_RETAINED", "LEGACY_IMPORT_STAGE_RETAINED",
        "PERSONNEL_MIGRATION_RUN_PRESENT", "HR_BASELINE_ENTRY_RETAINED",
        "HR_CHANGE_EVENT_RETAINED", "HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED",
        "HR_MONTHLY_REFERENCE_ENTRY_RETAINED", "INCOMING_DOCUMENT_PARTICIPATION_PRESENT",
        "INCOMING_DOCUMENT_ASSIGNMENT_PRESENT", "INCOMING_DOCUMENT_ATTACHMENT_PRESENT",
        "INCOMING_DOCUMENT_AUDIT_RETAINED", "INCOMING_DOCUMENT_DEADLINE_CHANGE_PRESENT",
        "INCOMING_DOCUMENT_OPERATIONAL_ORDER_LINK_PRESENT",
        "INCOMING_DOCUMENT_PERSONNEL_ORDER_LINK_PRESENT", "INCOMING_DOCUMENT_TRANSFER_PRESENT",
        "PERSONNEL_ORDER_ATTACHMENT_PRESENT", "PERSONNEL_ORDER_EDITORIAL_BLOCK_PRESENT",
        "PERSONNEL_ORDER_EVIDENCE_SCOPE_PRESENT", "PERSONNEL_ORDER_ITEM_BASIS_PRESENT",
        "PERSONNEL_ORDER_LOCALIZED_TEXT_PRESENT", "PERSONNEL_ORDER_PRINT_PRESENT",
        "CONTACT_ACCESS_PRESENT", "KEY_CONTACT_PRESENT", "ORG_UNIT_KEY_STAFF_PRESENT",
        "ONBOARDING_NOTIFICATION_PRESENT",
        "ONBOARDING_TASK_AUDIT_PRESENT", "USER_LINKAGE_EXECUTE_ITEM_PRESENT",
        "USER_LINKAGE_REVIEW_DECISION_PRESENT", "PROVENANCE_STATE_RETAINED",
        "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED", "APPLICATION_STATUS_NOT_ELIGIBLE",
    }
    assert expected <= set(matrix)
    assert matrix["PPR_EVENT_TOMBSTONE_REQUIRED"]["category"] == "TOMBSTONE_REQUIRED"
    assert matrix["PPR_EVENT_TOMBSTONE_REQUIRED"]["submit_allowed"] is True
    assert matrix["PPR_COMMAND_TOMBSTONE_REQUIRED"]["approval_allowed"] is True
    assert matrix["LEGACY_PERSONNEL_PRESENT"]["category"] == "BLOCK"
    submitted = matrix["SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED"]
    assert submitted["category"] == "HR_ATTESTATION_REQUIRED"
    assert submitted["required_hr_decision"] == "submitted_synthetic_confirmed=true"


@pytest.mark.parametrize("rule", service.RELATIONSHIP_MATRIX, ids=lambda rule: rule.code)
def test_each_relationship_rule_has_nonempty_contract_and_valid_postgresql(rule):
    assert all(isinstance(value, str) and value.strip() for value in (
        rule.code, rule.table, rule.category, rule.lookup, rule.state_digest, rule.sql,
    ))
    assert rule.keys and all(isinstance(key, str) and key.strip() for key in rule.keys)
    assert all(isinstance(value, bool) for value in (
        rule.create_allowed, rule.submit_allowed, rule.approval_allowed,
        rule.future_execution_allowed,
    ))
    params = {
        "person_id": -1, "application_id": -1, "application_ids": [-1],
        "early_actions": list(service.EARLY_LIFECYCLE_ACTIONS), "environment": "pytest",
    }
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass(:name)"), {
            "name": f"public.{rule.table}",
        }).scalar_one() is not None
        conn.execute(text(rule.sql), params).mappings().all()


def test_canonical_state_digest_is_row_order_independent_and_update_sensitive():
    states = [{"id": 2, "status": "open"}, {"id": 1, "status": "closed"}]
    assert service._canonical_state_digest(states) == service._canonical_state_digest(list(reversed(states)))
    changed = [{"id": 2, "status": "updated"}, {"id": 1, "status": "closed"}]
    assert service._canonical_state_digest(states) != service._canonical_state_digest(changed)


@pytest.mark.parametrize("comment", [
    "ИИН 123456789012",
    "write to person@example.org",
    "call +7 (777) 123-45-67",
])
def test_comment_rejects_obvious_pii(comment):
    with pytest.raises(service.TestPersonnelDeletionError) as error:
        service.validate_comment(comment)
    assert error.value.code == "TD_COMMENT_PII_FORBIDDEN"


def test_same_count_update_changes_fingerprint(client, td_actors, td_candidates):
    person_id, application_id = td_candidates["pending"]
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO personnel_record_metadata
            (person_id,ppr_lifecycle_state,hr_relationship_context,version)
            VALUES(:id,'CREATED','CANDIDATE',1)"""), {"id": person_id})
    try:
        admin = _as(client, td_actors["ADMIN"])
        draft = admin.post("/directory/test-personnel-deletion/requests", json=_draft_payload(
            (person_id, application_id), suffix=f"same-count-{uuid.uuid4().hex[:8]}"
        )).json()
        with engine.begin() as conn:
            conn.execute(text("UPDATE personnel_record_metadata SET version=2 WHERE person_id=:id"), {"id": person_id})
        response = admin.post(
            f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
            json={"expected_version": 1, "idempotency_key": f"same-count-submit-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "TD_FINGERPRINT_CHANGED"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_record_metadata WHERE person_id=:id"), {"id": person_id})


def test_idempotency_key_rejects_different_payload(client, td_actors, td_candidates):
    admin = _as(client, td_actors["ADMIN"])
    payload = _draft_payload(td_candidates["pending"], suffix=f"idem-{uuid.uuid4().hex[:8]}")
    first = admin.post("/directory/test-personnel-deletion/requests", json=payload)
    assert first.status_code == 201
    changed = {**payload, "reason_code": "OTHER_APPROVED_TEST_DATA"}
    second = admin.post("/directory/test-personnel-deletion/requests", json=changed)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "TD_IDEMPOTENCY_PAYLOAD_CONFLICT"

    other_payload = _draft_payload(td_candidates["drift"], suffix=f"idem-other-{uuid.uuid4().hex[:8]}")
    other = admin.post("/directory/test-personnel-deletion/requests", json=other_payload).json()
    shared = f"same-command-key-{uuid.uuid4().hex}"
    assert admin.post(f"/directory/test-personnel-deletion/requests/{first.json()['request_id']}/submit", json={
        "expected_version": 1, "idempotency_key": shared,
    }).status_code == 200
    conflict = admin.post(f"/directory/test-personnel-deletion/requests/{other['request_id']}/submit", json={
        "expected_version": 1, "idempotency_key": shared,
    })
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "TD_IDEMPOTENCY_PAYLOAD_CONFLICT"


def test_disappeared_target_becomes_reapproval(client, td_actors, td_candidates):
    person_id, application_id = td_candidates["drift"]
    admin = _as(client, td_actors["ADMIN"])
    draft = admin.post("/directory/test-personnel-deletion/requests", json=_draft_payload(
        (person_id, application_id), suffix=f"missing-{uuid.uuid4().hex[:8]}"
    )).json()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM personnel_applications WHERE application_id=:id"), {"id": application_id})
        conn.execute(text("DELETE FROM persons WHERE person_id=:id"), {"id": person_id})
    response = admin.post(
        f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit",
        json={"expected_version": 1, "idempotency_key": f"missing-submit-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TD_TARGET_STATE_MISSING"
    assert response.json()["detail"]["request"]["status"] == "REAPPROVAL_REQUIRED"


def test_manifest_and_all_append_only_tables_are_db_protected(td_actors, td_candidates):
    request = service.create_draft(
        actor_user_id=int(td_actors["ADMIN"]["user_id"]), basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA", preview_criteria={"selection": "EXACT_MANIFEST"},
        original_mask=None, targets=[{"person_id": td_candidates["pending"][0], "application_id": td_candidates["pending"][1]}],
        idempotency_key=f"guards-{uuid.uuid4().hex}",
    )
    with pytest.raises(Exception, match="WP_TD_002_REQUEST_MANIFEST_IMMUTABLE"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE test_personnel_deletion_requests SET target_set_hash=:h WHERE request_id=:id"), {"h": "f"*64, "id": request["request_id"]})
    with pytest.raises(Exception, match="WP_TD_002_TARGET_MANIFEST_IMMUTABLE"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE test_personnel_deletion_targets SET person_id=person_id+1 WHERE request_id=:id"), {"id": request["request_id"]})


def test_cross_role_personal_grants_do_not_cross_duties(client, td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    grant_ids = []
    with engine.begin() as conn:
        for user_id, code in ((admin_id, TEST_PERSONNEL_DELETION_APPROVE), (hr_id, TEST_PERSONNEL_DELETION_REQUEST)):
            grant_ids.append(int(conn.execute(text("""INSERT INTO access_grants
                (access_role_id,target_type,target_id,granted_by_user_id,reason)
                SELECT access_role_id,'USER',:target,:grantor,:reason FROM access_roles WHERE code=:code
                RETURNING grant_id"""), {"target": user_id, "grantor": admin_id, "reason": f"wp-td-cross-{uuid.uuid4().hex}", "code": code}).scalar_one()))
    try:
        admin_capabilities = get_test_personnel_deletion_capabilities(admin_id)
        hr_capabilities = get_test_personnel_deletion_capabilities(hr_id)
        assert admin_capabilities["can_approve_test_personnel_deletion"] is False
        assert hr_capabilities["can_request_test_personnel_deletion"] is False
        admin = _as(client, td_actors["ADMIN"])
        denied_approve = admin.post(f"/directory/test-personnel-deletion/approvals/{uuid.uuid4()}/approve", json={
            "expected_version": 1, "idempotency_key": uuid.uuid4().hex,
        })
        assert denied_approve.status_code == 403
        hr = _as(client, td_actors["HR_HEAD"])
        denied_preview = hr.post("/directory/test-personnel-deletion/preview", json={
            "person_ids": [td_candidates["pending"][0]],
        })
        assert denied_preview.status_code == 403
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM access_grants WHERE grant_id=ANY(:ids)"), {"ids": grant_ids})


def test_hr_detail_and_queue_apply_person_scope(client, td_actors, td_candidates, monkeypatch):
    admin = _as(client, td_actors["ADMIN"])
    draft = admin.post("/directory/test-personnel-deletion/requests", json=_draft_payload(
        td_candidates["pending"], suffix=f"scope-{uuid.uuid4().hex[:8]}"
    )).json()
    pending = admin.post(f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit", json={
        "expected_version": 1, "idempotency_key": f"scope-submit-{uuid.uuid4().hex}",
    })
    assert pending.status_code == 200

    def deny_scope(*_args, **_kwargs):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person not found.")

    monkeypatch.setattr(td_routes, "assert_ppr_read_allowed_for_person", deny_scope)
    hr = _as(client, td_actors["HR_HEAD"])
    assert hr.get(f"/directory/test-personnel-deletion/approvals/{draft['request_id']}").status_code == 404
    queue = hr.get("/directory/test-personnel-deletion/approvals")
    assert queue.status_code == 200
    assert all(item["request_id"] != draft["request_id"] for item in queue.json()["items"])


def test_unicode_nfc_and_database_case_contract(td_actors):
    actor = int(td_actors["ADMIN"]["user_id"])
    suffix = uuid.uuid4().hex[:8]
    names = [f"Caf\u00e9 ТЕСТ {suffix}", f"Cafe\u0301 тест {suffix}"]
    created = []
    with engine.begin() as conn:
        for index, name in enumerate(names):
            person_id = conn.execute(text("""INSERT INTO persons(full_name,match_key,source)
                VALUES(:name,:key,'manual') RETURNING person_id"""),
                {"name": name, "key": f"unicode-{suffix}-{index}"}).scalar_one()
            application_id = conn.execute(text("""INSERT INTO personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key)
                VALUES(:person_id,'intake_pending',current_date,:actor,:key) RETURNING application_id"""),
                {"person_id": person_id, "actor": actor, "key": f"unicode-{suffix}-{index}"}).scalar_one()
            created.append((person_id, application_id))
    try:
        result = service.preview_candidates(mask=f"CAF\u00c9 тест *{suffix}", field="full_name", person_ids=[], application_ids=[])
        assert {(row["person_id"], row["application_id"]) for row in result["items"]} == set(created)
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_applications WHERE application_id=ANY(:ids)"), {"ids": [r[1] for r in created]})
            conn.execute(text("DELETE FROM persons WHERE person_id=ANY(:ids)"), {"ids": [r[0] for r in created]})


def test_concurrent_idempotent_submit_and_terminal_transitions(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    draft = service.create_draft(
        actor_user_id=admin_id, basis="LEGACY_MANIFEST", reason_code="LEGACY_SYNTHETIC_TEST_DATA",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": td_candidates["pending"][0], "application_id": td_candidates["pending"][1]}],
        idempotency_key=f"concurrent-create-{uuid.uuid4().hex}",
    )
    submit_key = f"concurrent-submit-{uuid.uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.submit_request, request_id=draft["request_id"], actor_user_id=admin_id,
            expected_version=1, idempotency_key=submit_key) for _ in range(2)]
        results = [future.result() for future in futures]
    assert {(item[0]["status"], item[0]["version"]) for item in results} == {("PENDING_HR_APPROVAL", 2)}

    def decide(decision):
        try:
            value, _ = service.decide_request(
                request_id=draft["request_id"], actor_user_id=hr_id, expected_version=2,
                decision=decision, idempotency_key=f"race-{decision}-{uuid.uuid4().hex}", comment=None,
                submitted_synthetic_confirmed=False,
            )
            return value["status"]
        except service.TestPersonnelDeletionError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = {future.result() for future in (pool.submit(decide, "APPROVE"), pool.submit(decide, "REJECT"))}
    assert len(outcomes & {"APPROVED", "REJECTED"}) == 1
    assert "TD_STATUS_CONFLICT" in outcomes

    person_id, application_id = td_candidates["drift"]
    other = service.create_draft(
        actor_user_id=admin_id, basis="LEGACY_MANIFEST", reason_code="LEGACY_SYNTHETIC_TEST_DATA",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"cancel-race-create-{uuid.uuid4().hex}",
    )
    queued, _ = service.submit_request(request_id=other["request_id"], actor_user_id=admin_id,
        expected_version=1, idempotency_key=f"cancel-race-submit-{uuid.uuid4().hex}")

    def cancel_or_approve(action):
        try:
            if action == "CANCEL":
                return service.cancel_request(request_id=other["request_id"], actor_user_id=admin_id,
                    expected_version=queued["version"], idempotency_key=f"cancel-race-{uuid.uuid4().hex}",
                    comment=None)["status"]
            return service.decide_request(request_id=other["request_id"], actor_user_id=hr_id,
                expected_version=queued["version"], decision="APPROVE",
                idempotency_key=f"approve-race-{uuid.uuid4().hex}", comment=None,
                submitted_synthetic_confirmed=False)[0]["status"]
        except service.TestPersonnelDeletionError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = {future.result() for future in (pool.submit(cancel_or_approve, "CANCEL"), pool.submit(cancel_or_approve, "APPROVE"))}
    assert len(outcomes & {"CANCELLED", "APPROVED"}) == 1
    assert outcomes & {"TD_STATUS_CONFLICT", "TD_VERSION_CONFLICT"}


@pytest.mark.parametrize("relationship_class", ["BLOCK", "TOMBSTONE_REQUIRED", "INFORMATIONAL", "HR_ATTESTATION_REQUIRED"])
def test_concurrent_relationship_drift_during_approval_is_observed(relationship_class, td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    person_id, application_id = td_candidates["pending"]
    draft = service.create_draft(
        actor_user_id=admin_id, basis="LEGACY_MANIFEST", reason_code="LEGACY_SYNTHETIC_TEST_DATA",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"blocking-race-create-{uuid.uuid4().hex}",
    )
    pending, _ = service.submit_request(request_id=draft["request_id"], actor_user_id=admin_id,
        expected_version=1, idempotency_key=f"blocking-race-submit-{uuid.uuid4().hex}")

    conn = engine.connect()
    transaction = conn.begin()
    cleanup_sql: tuple[str, dict]
    if relationship_class == "BLOCK":
        contact_id = conn.execute(text("""INSERT INTO contacts(person_id,full_name,phone)
            VALUES(:person_id,'WP TD synthetic contact','000') RETURNING contact_id"""), {"person_id": person_id}).scalar_one()
        cleanup_sql = ("DELETE FROM contacts WHERE contact_id=:id", {"id": contact_id})
    elif relationship_class == "TOMBSTONE_REQUIRED":
        command_id = f"td002b-race-{uuid.uuid4().hex}"
        conn.execute(text("""INSERT INTO ppr_command_executions(
            command_id,command_type,person_id,request_fingerprint,status,result_payload)
            VALUES(:command_id,'REGISTER',:person_id,:fingerprint,'completed','{}'::jsonb)"""), {
            "command_id": command_id, "person_id": person_id, "fingerprint": "a" * 64,
        })
        cleanup_sql = ("DELETE FROM ppr_command_executions WHERE command_id=:id", {"id": command_id})
    elif relationship_class == "INFORMATIONAL":
        conn.execute(text("""INSERT INTO personnel_record_metadata(
            person_id,ppr_lifecycle_state,hr_relationship_context,version)
            VALUES(:person_id,'CREATED','CANDIDATE',1)"""), {"person_id": person_id})
        cleanup_sql = ("DELETE FROM personnel_record_metadata WHERE person_id=:id", {"id": person_id})
    else:
        conn.execute(text("UPDATE personnel_applications SET status='intake_submitted' WHERE application_id=:id"), {"id": application_id})
        cleanup_sql = ("UPDATE personnel_applications SET status='intake_pending' WHERE application_id=:id", {"id": application_id})
    try:
        evaluation_started = Event()
        mutation_committed = Event()
        def pause_before_batch(_conn, _cursor, statement, _parameters, _context, _executemany):
            # Pause before the approval transaction takes its first MVCC
            # snapshot.  Once the concurrent mutation commits, every
            # request/manifest/matrix read must observe that same state.
            if "pg_advisory_xact_lock" in statement:
                evaluation_started.set()
                assert mutation_committed.wait(timeout=10)
        event.listen(engine, "before_cursor_execute", pause_before_batch)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(service.decide_request, request_id=draft["request_id"], actor_user_id=hr_id,
                expected_version=pending["version"], decision="APPROVE",
                idempotency_key=f"blocking-race-approve-{uuid.uuid4().hex}", comment=None,
                submitted_synthetic_confirmed=False)
            assert evaluation_started.wait(timeout=10)
            transaction.commit()
            mutation_committed.set()
            result, code = future.result(timeout=10)
        assert code == "TD_FINGERPRINT_CHANGED"
        assert result["status"] == "REAPPROVAL_REQUIRED"
    finally:
        event.remove(engine, "before_cursor_execute", pause_before_batch)
        mutation_committed.set()
        if transaction.is_active:
            transaction.rollback()
        conn.close()
        with engine.begin() as cleanup:
            cleanup.execute(text(cleanup_sql[0]), cleanup_sql[1])


def _insert_short_lived_provenance(person_id, actor_user_id):
    with engine.begin() as conn:
        return int(conn.execute(text("""INSERT INTO test_personnel_provenance(
            target_type,target_id,environment,test_run_id,creation_source,purpose,
            created_by_user_id,source_artifact_hash,expires_at,provenance_version)
            VALUES('PERSON',:person_id,:environment,:run,'pytest','synthetic fixture',
                   :actor,:artifact,statement_timestamp()+interval '250 milliseconds',1)
            RETURNING provenance_id"""), {
                "person_id": person_id, "environment": (service.os.getenv("APP_ENV") or "dev").strip().lower(),
                "run": f"wp-td-002b-{uuid.uuid4().hex}", "actor": actor_user_id,
                "artifact": uuid.uuid4().hex + uuid.uuid4().hex,
            }).scalar_one())


def _expire_test_provenance(provenance_id):
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_sleep(0.35)"))
        assert conn.execute(text("""SELECT clock_timestamp() > expires_at
            FROM test_personnel_provenance WHERE provenance_id=:id"""), {
            "id": provenance_id,
        }).scalar_one()


def test_provenance_expiry_between_create_and_submit_causes_reapproval(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    person_id, application_id = td_candidates["pending"]
    provenance_id = _insert_short_lived_provenance(person_id, admin_id)
    draft = service.create_draft(
        actor_user_id=admin_id, basis="PROVENANCE", reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"provenance-create-{uuid.uuid4().hex}",
    )
    _expire_test_provenance(provenance_id)
    result, code = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=f"provenance-submit-{uuid.uuid4().hex}",
    )
    assert code == "TD_FINGERPRINT_CHANGED"
    assert result["status"] == "REAPPROVAL_REQUIRED"


def test_provenance_expiry_between_submit_and_approve_causes_reapproval(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    person_id, application_id = td_candidates["drift"]
    provenance_id = _insert_short_lived_provenance(person_id, admin_id)
    draft = service.create_draft(
        actor_user_id=admin_id, basis="PROVENANCE", reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"provenance-create-{uuid.uuid4().hex}",
    )
    pending, _ = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=f"provenance-submit-{uuid.uuid4().hex}",
    )
    _expire_test_provenance(provenance_id)
    result, code = service.decide_request(
        request_id=draft["request_id"], actor_user_id=hr_id, expected_version=pending["version"],
        decision="APPROVE", idempotency_key=f"provenance-approve-{uuid.uuid4().hex}",
        comment=None, submitted_synthetic_confirmed=False,
    )
    assert code == "TD_FINGERPRINT_CHANGED"
    assert result["status"] == "REAPPROVAL_REQUIRED"


def _physically_remove_test_provenance(provenance_id):
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE test_personnel_provenance DISABLE TRIGGER trg_test_personnel_provenance_append_only"))
        try:
            conn.execute(text("DELETE FROM test_personnel_provenance WHERE provenance_id=:id"), {"id": provenance_id})
        finally:
            conn.execute(text("ALTER TABLE test_personnel_provenance ENABLE TRIGGER trg_test_personnel_provenance_append_only"))


def _assert_safe_drift_history(request_id):
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT result_code,result_projection
            FROM test_personnel_deletion_history WHERE request_id=:id
            ORDER BY history_id DESC LIMIT 1"""), {"id": request_id}).mappings().one()
    assert row["result_code"] == "TD_FINGERPRINT_CHANGED"
    serialized = str(row["result_projection"]).lower()
    assert all(key not in serialized for key in ("iin", "phone", "email", "full_name", "display_name", "comment"))


def test_provenance_disappearance_between_create_and_submit_causes_reapproval(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    person_id, application_id = td_candidates["pending"]
    provenance_id = _insert_short_lived_provenance(person_id, admin_id)
    draft = service.create_draft(
        actor_user_id=admin_id, basis="PROVENANCE", reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"provenance-disappear-create-{uuid.uuid4().hex}",
    )
    _physically_remove_test_provenance(provenance_id)
    result, code = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=f"provenance-disappear-submit-{uuid.uuid4().hex}",
    )
    assert code == "TD_FINGERPRINT_CHANGED"
    assert result["status"] == "REAPPROVAL_REQUIRED"
    _assert_safe_drift_history(draft["request_id"])


def test_provenance_disappearance_between_submit_and_approve_causes_reapproval(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    person_id, application_id = td_candidates["drift"]
    provenance_id = _insert_short_lived_provenance(person_id, admin_id)
    draft = service.create_draft(
        actor_user_id=admin_id, basis="PROVENANCE", reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"provenance-disappear-create-{uuid.uuid4().hex}",
    )
    pending, _ = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=f"provenance-disappear-submit-{uuid.uuid4().hex}",
    )
    _physically_remove_test_provenance(provenance_id)
    result, code = service.decide_request(
        request_id=draft["request_id"], actor_user_id=hr_id, expected_version=pending["version"],
        decision="APPROVE", idempotency_key=f"provenance-disappear-approve-{uuid.uuid4().hex}",
        comment=None, submitted_synthetic_confirmed=False,
    )
    assert code == "TD_FINGERPRINT_CHANGED"
    assert result["status"] == "REAPPROVAL_REQUIRED"
    _assert_safe_drift_history(draft["request_id"])


def test_submit_replay_returns_original_projection_after_approval(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    person_id, application_id = td_candidates["pending"]
    draft = service.create_draft(
        actor_user_id=admin_id, basis="LEGACY_MANIFEST", reason_code="LEGACY_SYNTHETIC_TEST_DATA",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"replay-create-{uuid.uuid4().hex}",
    )
    submit_key = f"replay-submit-{uuid.uuid4().hex}"
    original, _ = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=submit_key,
    )
    approved, _ = service.decide_request(
        request_id=draft["request_id"], actor_user_id=hr_id, expected_version=2,
        decision="APPROVE", idempotency_key=f"replay-approve-{uuid.uuid4().hex}",
        comment=None, submitted_synthetic_confirmed=False,
    )
    replay, _ = service.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id, expected_version=1,
        idempotency_key=submit_key,
    )
    assert approved["status"] == "APPROVED"
    assert replay == original
    assert replay["status"] == "PENDING_HR_APPROVAL"
    assert replay["result_code"] == "TD_SUBMITTED"


def test_result_projection_is_append_only_and_contains_no_identity_data(td_actors, td_candidates):
    request = service.create_draft(
        actor_user_id=int(td_actors["ADMIN"]["user_id"]), basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA", preview_criteria={"selection": "EXACT_MANIFEST"},
        original_mask=None,
        targets=[{"person_id": td_candidates["pending"][0], "application_id": td_candidates["pending"][1]}],
        idempotency_key=f"projection-{uuid.uuid4().hex}",
    )
    with engine.connect() as conn:
        projection = conn.execute(text("SELECT result_projection FROM test_personnel_deletion_history WHERE request_id=:id"), {"id": request["request_id"]}).scalar_one()
    serialized = str(projection).lower()
    assert all(key not in serialized for key in ("iin", "phone", "email", "full_name", "display_name", "comment"))
    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE test_personnel_deletion_history SET result_projection='{}'::jsonb WHERE request_id=:id"), {"id": request["request_id"]})


def test_hr_wide_scope_still_receives_only_masked_iin(client, td_actors, td_candidates, monkeypatch):
    admin = _as(client, td_actors["ADMIN"])
    person_id, _ = td_candidates["pending"]
    synthetic_iin = "990101123456"
    with engine.begin() as conn:
        conn.execute(text("UPDATE persons SET iin=:iin WHERE person_id=:id"), {"iin": synthetic_iin, "id": person_id})
    preview = admin.post("/directory/test-personnel-deletion/preview", json={"person_ids": [person_id]})
    assert preview.status_code == 200
    preview_target = preview.json()["items"][0]
    assert "display_name" not in preview_target
    assert preview_target["subject"]
    assert preview_target["masked_iin"] == "********3456"
    assert synthetic_iin not in preview.text
    draft = admin.post("/directory/test-personnel-deletion/requests", json=_draft_payload(
        td_candidates["pending"], suffix=f"iin-{uuid.uuid4().hex[:8]}"
    )).json()
    admin.post(f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit", json={
        "expected_version": 1, "idempotency_key": f"iin-submit-{uuid.uuid4().hex}",
    })
    admin_detail = admin.get(f"/directory/test-personnel-deletion/requests/{draft['request_id']}")
    assert admin_detail.status_code == 200
    assert synthetic_iin not in admin_detail.text
    assert admin_detail.json()["targets"][0]["subject"]
    assert admin_detail.json()["targets"][0]["masked_iin"] == "********3456"
    monkeypatch.setattr(td_routes, "assert_ppr_read_allowed_for_person", lambda *_args, **_kwargs: None)
    hr = _as(client, td_actors["HR_HEAD"])
    detail = hr.get(f"/directory/test-personnel-deletion/approvals/{draft['request_id']}")
    assert detail.status_code == 200
    assert synthetic_iin not in detail.text
    assert detail.json()["targets"][0]["subject"]
    assert detail.json()["targets"][0]["masked_iin"] == "********3456"


def test_safe_identity_has_no_full_iin_escape_hatch(td_candidates):
    person_id, _ = td_candidates["pending"]
    synthetic_iin = "990101123456"
    with engine.begin() as conn:
        conn.execute(text("UPDATE persons SET iin=:iin WHERE person_id=:id"), {"iin": synthetic_iin, "id": person_id})
    identity = service.safe_identity(person_id)
    assert identity["masked_iin"] == "********3456"
    assert identity["subject"]
    assert synthetic_iin not in str(identity)
    with pytest.raises(TypeError):
        service.safe_identity(person_id, include_full_iin=True)


def test_request_read_projection_returns_participant_display_names(
    client, td_actors, td_candidates, monkeypatch,
):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    hr_id = int(td_actors["HR_HEAD"]["user_id"])
    with engine.connect() as conn:
        names = dict(conn.execute(text("SELECT user_id,full_name FROM users WHERE user_id=ANY(:ids)"), {
            "ids": [admin_id, hr_id],
        }).all())
    admin = _as(client, td_actors["ADMIN"])
    draft = admin.post("/directory/test-personnel-deletion/requests", json=_draft_payload(
        td_candidates["drift"], suffix=f"display-{uuid.uuid4().hex[:8]}"
    )).json()
    pending = admin.post(f"/directory/test-personnel-deletion/requests/{draft['request_id']}/submit", json={
        "expected_version": 1, "idempotency_key": f"display-submit-{uuid.uuid4().hex}",
    })
    assert pending.status_code == 200
    monkeypatch.setattr(td_routes, "assert_ppr_read_allowed_for_person", lambda *_a, **_k: None)
    hr = _as(client, td_actors["HR_HEAD"])
    approved = hr.post(f"/directory/test-personnel-deletion/approvals/{draft['request_id']}/approve", json={
        "expected_version": 2, "idempotency_key": f"display-approve-{uuid.uuid4().hex}",
        "comment": "Синтетическая запись подтверждена",
    })
    assert approved.status_code == 200
    admin = _as(client, td_actors["ADMIN"])
    detail = admin.get(f"/directory/test-personnel-deletion/requests/{draft['request_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["initiated_by_user_id"] == admin_id
    assert payload["initiated_by_display_name"] == names[admin_id]
    assert payload["decisions"][-1]["actor_user_id"] == hr_id
    assert payload["decisions"][-1]["actor_display_name"] == names[hr_id]
    serialized_history = str(payload["history"])
    assert names[admin_id] not in serialized_history
    assert names[hr_id] not in serialized_history


def test_identity_and_display_name_projection_is_batched(td_actors, td_candidates):
    admin_id = int(td_actors["ADMIN"]["user_id"])
    targets = [
        {"person_id": person_id, "application_id": application_id}
        for person_id, application_id in (
            td_candidates["pending"], td_candidates["submitted"], td_candidates["drift"]
        )
    ]
    draft = service.create_draft(
        actor_user_id=admin_id, basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA", preview_criteria={"selection": "EXACT_MANIFEST"},
        original_mask=None, targets=targets, idempotency_key=f"projection-batch-{uuid.uuid4().hex}",
    )
    statements = []
    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        detail = service.get_request(draft["request_id"])
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert len(detail["targets"]) == 3
    assert all("subject" in target and "masked_iin" in target for target in detail["targets"])
    assert sum("SELECT person_id,full_name,iin FROM public.persons" in sql for sql in statements) == 1
    assert sum("SELECT user_id,full_name FROM public.users" in sql for sql in statements) == 1


def test_read_projection_uses_safe_missing_identity_and_user_fallbacks():
    missing_person_id = 9_223_372_036_854_000_001
    missing_user_id = 9_223_372_036_854_000_002
    with engine.connect() as conn:
        identity = service._identity_projections(conn, [missing_person_id])[missing_person_id]
        display_name = service._user_display_names(conn, [missing_user_id])[missing_user_id]
    assert identity == {
        "subject": f"Запись #{missing_person_id} недоступна",
        "masked_iin": None,
    }
    assert display_name == f"Пользователь #{missing_user_id}"


def test_legacy_endpoints_never_call_delete_service(client, td_actors, monkeypatch):
    from app.services import employee_hard_delete_service

    called = {"single": 0, "bulk": 0}
    monkeypatch.setattr(employee_hard_delete_service, "hard_delete_employee", lambda *_a, **_k: called.__setitem__("single", called["single"] + 1))
    monkeypatch.setattr(employee_hard_delete_service, "bulk_hard_delete_employees", lambda *_a, **_k: called.__setitem__("bulk", called["bulk"] + 1))
    admin = _as(client, td_actors["ADMIN"])
    assert admin.delete("/directory/employees/1").status_code == 410
    assert admin.post("/directory/employees/bulk-delete", json={"employee_ids": [1]}).status_code == 410
    assert called == {"single": 0, "bulk": 0}


def test_legacy_endpoint_boundary_has_no_database_or_service_access(client, td_actors, monkeypatch):
    from app.directory import employees_routes

    class FailOnDatabaseAccess:
        def __getattr__(self, name):
            raise AssertionError(f"legacy endpoint accessed database through {name}")

    def fail_service(*_args, **_kwargs):
        raise AssertionError("legacy endpoint called a service")

    monkeypatch.setattr(employees_routes, "engine", FailOnDatabaseAccess())
    monkeypatch.setattr(employees_routes, "call_service", fail_service)
    statements = []
    def observe_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe_sql)
    try:
        admin = _as(client, td_actors["ADMIN"])
        single = admin.delete("/directory/employees/999999999")
        bulk = admin.post("/directory/employees/bulk-delete", json={"employee_ids": [999999999]})
    finally:
        event.remove(engine, "before_cursor_execute", observe_sql)
    assert single.status_code == bulk.status_code == 410
    assert single.json()["detail"]["code"] == "TD_LEGACY_HARD_DELETE_DISABLED"
    assert bulk.json()["detail"]["code"] == "TD_LEGACY_HARD_DELETE_DISABLED"
    assert statements == []


@pytest.mark.parametrize("target_count", [1, 11, 200])
def test_relationship_evaluation_query_budget_is_constant(target_count, td_actors):
    suffix = uuid.uuid4().hex[:10]
    actor = int(td_actors["ADMIN"]["user_id"])
    pairs = []
    with engine.begin() as conn:
        for index in range(target_count):
            person_id = conn.execute(text("""INSERT INTO persons(full_name,match_key,source)
                VALUES(:name,:key,'manual') RETURNING person_id"""), {
                "name": f"WP TD budget {index} {suffix}", "key": f"wp-td-budget-{suffix}-{index}",
            }).scalar_one()
            application_id = conn.execute(text("""INSERT INTO personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key)
                VALUES(:person_id,'intake_pending',current_date,:actor,:key) RETURNING application_id"""), {
                "person_id": person_id, "actor": actor, "key": f"wp-td-budget-app-{suffix}-{index}",
            }).scalar_one()
            pairs.append((int(person_id), int(application_id)))
    try:
        measurements = []
        for phase in ("cold", "warm"):
            statements = []
            def count_statements(_conn, _cursor, statement, _parameters, _context, _executemany):
                statements.append(statement)
            event.listen(engine, "before_cursor_execute", count_statements)
            started = time.perf_counter()
            try:
                with engine.connect() as conn:
                    candidates = service._evaluate_candidates(conn, pairs)
            finally:
                elapsed = time.perf_counter() - started
                event.remove(engine, "before_cursor_execute", count_statements)
            assert len(candidates) == target_count
            assert len(statements) == 3
            assert sum("UNION ALL" in statement for statement in statements) == 1
            measurements.append((phase, elapsed))
        cold = measurements[0][1]
        warm = measurements[1][1]
        print(f"WP-TD-002D targets={target_count} cold={cold:.3f}s warm={warm:.3f}s round_trips=3")
        # Local target is <2 s; 25% headroom avoids timing-only CI failures.
        assert warm < 2.5
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_applications WHERE application_id=ANY(:ids)"), {"ids": [a for _, a in pairs]})
            conn.execute(text("DELETE FROM persons WHERE person_id=ANY(:ids)"), {"ids": [p for p, _ in pairs]})


def test_relationship_batch_keeps_two_targets_isolated_and_order_independent(td_actors):
    actor = int(td_actors["ADMIN"]["user_id"])
    suffix = uuid.uuid4().hex
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            pairs = []
            for index in range(2):
                person_id = int(conn.execute(text("""INSERT INTO persons(full_name,match_key,source)
                    VALUES(:name,:key,'manual') RETURNING person_id"""), {
                    "name": f"WP TD isolated {index}", "key": f"wp-td-isolated-{suffix}-{index}",
                }).scalar_one())
                application_id = int(conn.execute(text("""INSERT INTO personnel_applications(
                    person_id,status,application_received_at,registered_by_user_id,idempotency_key)
                    VALUES(:person_id,'intake_pending',current_date,:actor,:key) RETURNING application_id"""), {
                    "person_id": person_id, "actor": actor, "key": f"wp-td-isolated-app-{suffix}-{index}",
                }).scalar_one())
                pairs.append((person_id, application_id))
            conn.execute(text("INSERT INTO contacts(person_id,full_name) VALUES(:id,'WP TD isolated contact')"), {"id": pairs[0][0]})
            forward = service._evaluate_candidates(conn, pairs)
            reverse = service._evaluate_candidates(conn, list(reversed(pairs)))
            by_pair = {(row["person_id"], row["application_id"]): row for row in forward}
            reverse_by_pair = {(row["person_id"], row["application_id"]): row for row in reverse}
            assert "CONTACT_PRESENT" in by_pair[pairs[0]]["blocking_codes"]
            assert "CONTACT_PRESENT" not in by_pair[pairs[1]]["blocking_codes"]
            assert {pair: row["relationship_fingerprint"] for pair, row in by_pair.items()} == {
                pair: row["relationship_fingerprint"] for pair, row in reverse_by_pair.items()
            }
            assert by_pair[pairs[0]]["relationship_fingerprint"] != by_pair[pairs[1]]["relationship_fingerprint"]
        finally:
            transaction.rollback()


class _SerializationFault(Exception):
    pgcode = "40001"
    sqlstate = "40001"


def _raise_serialization_failure():
    raise DBAPIError("WP-TD-002D injected serialization failure", {}, _SerializationFault(), False)


def _retry_probe_request(td_actors, td_candidates):
    return service.create_draft(
        actor_user_id=int(td_actors["ADMIN"]["user_id"]), basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA", preview_criteria={"selection": "EXACT_MANIFEST"},
        original_mask=None,
        targets=[{"person_id": td_candidates["pending"][0], "application_id": td_candidates["pending"][1]}],
        idempotency_key=f"retry-probe-{uuid.uuid4().hex}",
    )


def _write_failed_attempt_state(conn, draft, actor, attempt):
    request_id = draft["request_id"]
    baseline = conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_history WHERE request_id=:id"), {"id": request_id}).scalar_one()
    assert conn.execute(text("SELECT status FROM test_personnel_deletion_requests WHERE request_id=:id"), {"id": request_id}).scalar_one() == "DRAFT"
    assert baseline == 1
    conn.execute(text("UPDATE test_personnel_deletion_requests SET status='REJECTED' WHERE request_id=:id"), {"id": request_id})
    conn.execute(text("""INSERT INTO test_personnel_deletion_decisions(
        request_id,decision,actor_user_id,actor_role_code,permission_code,request_version,target_set_hash)
        VALUES(:id,'REJECT',:actor,'HR_HEAD','TEST_PERSONNEL_DELETION_APPROVE',2,:hash)"""), {
        "id": request_id, "actor": actor, "hash": draft["target_set_hash"],
    })
    conn.execute(text("""INSERT INTO test_personnel_deletion_history(
        request_id,actor_user_id,actor_role_code,permission_code,action,old_status,new_status,
        old_version,new_version,target_set_hash,idempotency_key,command_payload_hash,result_code,result_projection)
        VALUES(:id,:actor,'HR_HEAD','TEST_PERSONNEL_DELETION_APPROVE','REJECT','DRAFT','REJECTED',
        1,2,:hash,:key,:hash,'TD_REJECTED',CAST(:projection AS jsonb))"""), {
        "id": request_id, "actor": actor, "hash": draft["target_set_hash"],
        "key": f"retry-attempt-{attempt}-{uuid.uuid4().hex}",
        "projection": '{"request_id":"retry-probe","status":"REJECTED"}',
    })


def test_serializable_retries_once_with_clean_new_transaction(td_actors, td_candidates):
    draft = _retry_probe_request(td_actors, td_candidates)
    actor = int(td_actors["HR_HEAD"]["user_id"])
    attempts = []
    transactions = []
    def work(conn):
        attempts.append(len(attempts) + 1)
        transactions.append(conn.get_transaction())
        decision_count = conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_decisions WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one()
        assert decision_count == 0
        if len(attempts) == 1:
            _write_failed_attempt_state(conn, draft, actor, attempts[-1])
            _raise_serialization_failure()
        return conn.execute(text("SELECT status FROM test_personnel_deletion_requests WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one()
    assert service._serializable(work) == "DRAFT"
    assert attempts == [1, 2]
    assert transactions[0] is not transactions[1]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM test_personnel_deletion_requests WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == "DRAFT"
        assert conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_decisions WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_history WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == 1


def test_serializable_stops_after_three_cleanly_rolled_back_attempts(td_actors, td_candidates):
    draft = _retry_probe_request(td_actors, td_candidates)
    actor = int(td_actors["HR_HEAD"]["user_id"])
    attempts = []
    transactions = []
    def work(conn):
        attempts.append(len(attempts) + 1)
        transactions.append(conn.get_transaction())
        assert conn.execute(text("SELECT status FROM test_personnel_deletion_requests WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == "DRAFT"
        assert conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_decisions WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == 0
        _write_failed_attempt_state(conn, draft, actor, attempts[-1])
        _raise_serialization_failure()
    with pytest.raises(service.TestPersonnelDeletionError) as error:
        service._serializable(work)
    assert error.value.code == "TD_SERIALIZATION_RETRY_EXHAUSTED"
    assert attempts == [1, 2, 3]
    assert len({id(transaction) for transaction in transactions}) == 3
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM test_personnel_deletion_requests WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == "DRAFT"
        assert conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_decisions WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM test_personnel_deletion_history WHERE request_id=:id"), {"id": draft["request_id"]}).scalar_one() == 1
