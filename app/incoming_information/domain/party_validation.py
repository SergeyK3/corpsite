"""Mutual-exclusivity validation for sender/addressee and transfer recipient fields."""
from __future__ import annotations

from typing import Any

from app.incoming_information.domain.errors import IncomingDocumentValidationError
from app.incoming_information.domain.status import (
    ADDRESSEE_KIND_EMPLOYEE,
    ADDRESSEE_KIND_ORG_UNIT,
    ADDRESSEE_KIND_POSITION,
    ADDRESSEE_KIND_TEXT,
    ADDRESSEE_KIND_USER,
    RECIPIENT_KIND_ORG_UNIT,
    RECIPIENT_KIND_TEXT,
    RECIPIENT_KIND_USER,
    SENDER_KIND_EMPLOYEE,
    SENDER_KIND_EXTERNAL_TEXT,
    SENDER_KIND_ORG_UNIT,
    SENDER_KIND_PERSON,
)


def _forbidden_non_null(fields: dict[str, Any], names: tuple[str, ...], *, label: str) -> None:
    for name in names:
        if fields.get(name) is not None:
            raise IncomingDocumentValidationError(f"{name} must not be set for {label}.")


def validate_sender_fields_exclusive(
    sender_kind: str,
    *,
    sender_person_id: int | None,
    sender_employee_id: int | None,
    sender_org_unit_id: int | None,
    sender_text: str | None,
) -> None:
    if sender_kind == SENDER_KIND_EXTERNAL_TEXT:
        _forbidden_non_null(
            {
                "sender_person_id": sender_person_id,
                "sender_employee_id": sender_employee_id,
                "sender_org_unit_id": sender_org_unit_id,
            },
            ("sender_person_id", "sender_employee_id", "sender_org_unit_id"),
            label="EXTERNAL_TEXT sender",
        )
        return
    if sender_kind == SENDER_KIND_PERSON:
        _forbidden_non_null(
            {
                "sender_employee_id": sender_employee_id,
                "sender_org_unit_id": sender_org_unit_id,
                "sender_text": sender_text,
            },
            ("sender_employee_id", "sender_org_unit_id", "sender_text"),
            label="PERSON sender",
        )
        return
    if sender_kind == SENDER_KIND_EMPLOYEE:
        _forbidden_non_null(
            {
                "sender_person_id": sender_person_id,
                "sender_org_unit_id": sender_org_unit_id,
                "sender_text": sender_text,
            },
            ("sender_person_id", "sender_org_unit_id", "sender_text"),
            label="EMPLOYEE sender",
        )
        return
    if sender_kind == SENDER_KIND_ORG_UNIT:
        _forbidden_non_null(
            {
                "sender_person_id": sender_person_id,
                "sender_employee_id": sender_employee_id,
                "sender_text": sender_text,
            },
            ("sender_person_id", "sender_employee_id", "sender_text"),
            label="ORG_UNIT sender",
        )


def validate_addressee_fields_exclusive(
    addressee_kind: str,
    *,
    addressee_user_id: int | None,
    addressee_employee_id: int | None,
    addressee_org_unit_id: int | None,
    addressee_position_id: int | None,
    addressee_text: str | None,
) -> None:
    if addressee_kind == ADDRESSEE_KIND_TEXT:
        _forbidden_non_null(
            {
                "addressee_user_id": addressee_user_id,
                "addressee_employee_id": addressee_employee_id,
                "addressee_org_unit_id": addressee_org_unit_id,
                "addressee_position_id": addressee_position_id,
            },
            ("addressee_user_id", "addressee_employee_id", "addressee_org_unit_id", "addressee_position_id"),
            label="TEXT addressee",
        )
        return
    if addressee_kind == ADDRESSEE_KIND_USER:
        _forbidden_non_null(
            {
                "addressee_employee_id": addressee_employee_id,
                "addressee_org_unit_id": addressee_org_unit_id,
                "addressee_position_id": addressee_position_id,
                "addressee_text": addressee_text,
            },
            ("addressee_employee_id", "addressee_org_unit_id", "addressee_position_id", "addressee_text"),
            label="USER addressee",
        )
        return
    if addressee_kind == ADDRESSEE_KIND_EMPLOYEE:
        _forbidden_non_null(
            {
                "addressee_user_id": addressee_user_id,
                "addressee_org_unit_id": addressee_org_unit_id,
                "addressee_position_id": addressee_position_id,
                "addressee_text": addressee_text,
            },
            ("addressee_user_id", "addressee_org_unit_id", "addressee_position_id", "addressee_text"),
            label="EMPLOYEE addressee",
        )
        return
    if addressee_kind == ADDRESSEE_KIND_ORG_UNIT:
        _forbidden_non_null(
            {
                "addressee_user_id": addressee_user_id,
                "addressee_employee_id": addressee_employee_id,
                "addressee_position_id": addressee_position_id,
                "addressee_text": addressee_text,
            },
            ("addressee_user_id", "addressee_employee_id", "addressee_position_id", "addressee_text"),
            label="ORG_UNIT addressee",
        )
        return
    if addressee_kind == ADDRESSEE_KIND_POSITION:
        _forbidden_non_null(
            {
                "addressee_user_id": addressee_user_id,
                "addressee_employee_id": addressee_employee_id,
                "addressee_org_unit_id": addressee_org_unit_id,
                "addressee_text": addressee_text,
            },
            ("addressee_user_id", "addressee_employee_id", "addressee_org_unit_id", "addressee_text"),
            label="POSITION addressee",
        )


def validate_external_transfer_recipient_exclusive(
    recipient_kind: str,
    *,
    recipient_user_id: int | None,
    recipient_org_unit_id: int | None,
    recipient_text: str | None,
) -> None:
    if recipient_kind == RECIPIENT_KIND_USER:
        _forbidden_non_null(
            {
                "recipient_org_unit_id": recipient_org_unit_id,
                "recipient_text": recipient_text,
            },
            ("recipient_org_unit_id", "recipient_text"),
            label="USER external recipient",
        )
        return
    if recipient_kind == RECIPIENT_KIND_ORG_UNIT:
        _forbidden_non_null(
            {
                "recipient_user_id": recipient_user_id,
                "recipient_text": recipient_text,
            },
            ("recipient_user_id", "recipient_text"),
            label="ORG_UNIT external recipient",
        )
        return
    if recipient_kind == RECIPIENT_KIND_TEXT:
        _forbidden_non_null(
            {
                "recipient_user_id": recipient_user_id,
                "recipient_org_unit_id": recipient_org_unit_id,
            },
            ("recipient_user_id", "recipient_org_unit_id"),
            label="TEXT external recipient",
        )
