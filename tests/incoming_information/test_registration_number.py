# tests/incoming_information/test_registration_number.py
from __future__ import annotations

import threading
from datetime import UTC, date, datetime

import pytest

from app.db.engine import engine
from app.incoming_information.application.registration_service import register_incoming_document
from app.incoming_information.domain.status import ACCESS_LEVEL_RESTRICTED
from tests.incoming_information.conftest import (
    utc_today,
    cleanup_incoming_documents,
    grant_user_permission,
    lookup_dictionary_id,
    revoke_user_access_grants,
    revoke_user_permission,
)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_number_is_year_scoped_and_unique(seed):
    user_id = int(seed["executor_user_id"])
    unit_id = int(seed["unit_id"])
    document_ids: list[int] = []
    with engine.begin() as conn:
        grant_user_permission(conn, user_id, "INCOMING_INFO_REGISTER")
    with engine.begin() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="LETTER")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PHONE")
        user = {"user_id": user_id}
        first = register_incoming_document(
            conn,
            user=user,
            received_at=utc_today(),
            document_type_id=doc_type_id,
            receipt_channel_id=channel_id,
            summary="Устное обращение по телефону",
            access_level=ACCESS_LEVEL_RESTRICTED,
            sender_kind="EXTERNAL_TEXT",
            sender_text="Гражданин Иванов",
            addressee_kind="ORG_UNIT",
            addressee_org_unit_id=unit_id,
            registration_org_unit_id=unit_id,
        )
        second = register_incoming_document(
            conn,
            user=user,
            received_at=utc_today(),
            document_type_id=doc_type_id,
            receipt_channel_id=channel_id,
            summary="Второе обращение",
            sender_kind="EXTERNAL_TEXT",
            sender_text="Гражданин Петров",
            addressee_kind="ORG_UNIT",
            addressee_org_unit_id=unit_id,
            registration_org_unit_id=unit_id,
        )
        document_ids.extend([first.incoming_document_id, second.incoming_document_id])
        assert first.registration_number.startswith(f"ВХ-{datetime.now(UTC).year}-")
        assert second.registration_number.startswith(f"ВХ-{datetime.now(UTC).year}-")
        assert first.registration_number != second.registration_number
        assert second.registration_seq == first.registration_seq + 1

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, document_ids)
        revoke_user_permission(conn, user_id, "INCOMING_INFO_REGISTER")
        revoke_user_access_grants(conn, user_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_number_concurrent_allocation(seed):
    user_id = int(seed["executor_user_id"])
    unit_id = int(seed["unit_id"])
    numbers: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()
    document_ids: list[int] = []

    with engine.begin() as conn:
        grant_user_permission(conn, user_id, "INCOMING_INFO_REGISTER")

    def worker() -> None:
        try:
            with engine.begin() as conn:
                doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="COMPLAINT")
                channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PAPER")
                created = register_incoming_document(
                    conn,
                    user={"user_id": user_id},
                    received_at=utc_today(),
                    document_type_id=doc_type_id,
                    receipt_channel_id=channel_id,
                    summary="Жалоба",
                    sender_kind="EXTERNAL_TEXT",
                    sender_text="Заявитель",
                    addressee_kind="ORG_UNIT",
                    addressee_org_unit_id=unit_id,
                    registration_org_unit_id=unit_id,
                )
                with lock:
                    numbers.append(created.registration_number)
                    document_ids.append(created.incoming_document_id)
        except Exception as exc:
            with lock:
                errors.append(exc)

    with engine.begin() as conn:
        grant_user_permission(conn, user_id, "INCOMING_INFO_REGISTER")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(numbers) == 4
    assert len(set(numbers)) == 4

    with engine.begin() as conn:
        revoke_user_permission(conn, user_id, "INCOMING_INFO_REGISTER")
        revoke_user_access_grants(conn, user_id)
        cleanup_incoming_documents(conn, document_ids)
