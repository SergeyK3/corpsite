"""Personnel print read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel._mapping import (
    optional_str,
    parse_archive_state,
    parse_lifecycle_state,
    parse_locale_code,
)
from app.document_engine.adapters.personnel.views import (
    PersonnelPrintReadView,
    PersonnelPrintRecordReadView,
)


class PersonnelPrintAdapter:
    """Maps PO print metadata → shared print read view.

    Does not generate PDF/HTML — records only.
    """

    @staticmethod
    def status_mark_for_lifecycle(status: str) -> str:
        normalized = str(status or "").strip().upper()
        if normalized == "DRAFT":
            return "draft"
        if normalized == "READY_FOR_SIGNATURE":
            return "unsigned"
        if normalized == "VOIDED":
            return "cancelled"
        return "none"

    @staticmethod
    def from_print_record(row: Mapping[str, Any]) -> PersonnelPrintRecordReadView:
        return PersonnelPrintRecordReadView(
            print_id=int(row["print_id"]),
            order_id=int(row["order_id"]),
            locale=parse_locale_code(row.get("locale")),
            format=str(row.get("format") or ""),
            file_path=optional_str(row.get("file_path")),
            file_url=optional_str(row.get("file_url")),
            is_signed_copy=bool(row.get("is_signed_copy")),
            render_version=int(row.get("render_version") or 1),
            generated_at=optional_str(row.get("generated_at")),
        )

    @staticmethod
    def from_header_and_prints(
        header: Mapping[str, Any],
        prints: Iterable[Mapping[str, Any]],
    ) -> PersonnelPrintReadView:
        lifecycle = parse_lifecycle_state(header.get("status"))
        archive = parse_archive_state(is_archived=bool(header.get("is_archived")))
        status_mark = PersonnelPrintAdapter.status_mark_for_lifecycle(str(header.get("status") or ""))
        records = tuple(PersonnelPrintAdapter.from_print_record(row) for row in prints)
        return PersonnelPrintReadView(
            order_id=int(header["order_id"]),
            lifecycle_state=lifecycle,
            archive_state=archive,
            status_mark=status_mark,
            printable=True,
            records=records,
        )
