"""Print read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel.print import PersonnelPrintAdapter
from app.document_engine.adapters.personnel.views import (
    PersonnelPrintReadView,
    PersonnelPrintRecordReadView,
    PersonnelReadBundle,
)
from app.document_engine.read_models.print import PrintReadModel, PrintRecordReadModel


class PrintReadService:
    """Maps Personnel print adapter output → shared print read model (metadata only)."""

    @staticmethod
    def from_record_view(view: PersonnelPrintRecordReadView) -> PrintRecordReadModel:
        return PrintRecordReadModel(
            print_id=view.print_id,
            order_id=view.order_id,
            locale=view.locale,
            format=view.format,
            file_path=view.file_path,
            file_url=view.file_url,
            is_signed_copy=view.is_signed_copy,
            render_version=view.render_version,
            generated_at=view.generated_at,
        )

    @staticmethod
    def from_adapter_view(view: PersonnelPrintReadView) -> PrintReadModel:
        return PrintReadModel(
            order_id=view.order_id,
            lifecycle_state=view.lifecycle_state,
            archive_state=view.archive_state,
            status_mark=view.status_mark,
            printable=view.printable,
            records=tuple(
                PrintReadService.from_record_view(record) for record in view.records
            ),
        )

    @staticmethod
    def from_header_and_prints(
        header: Mapping[str, Any],
        prints: Iterable[Mapping[str, Any]],
    ) -> PrintReadModel:
        view = PersonnelPrintAdapter.from_header_and_prints(header, prints)
        return PrintReadService.from_adapter_view(view)

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> PrintReadModel | None:
        if bundle.print_view is None:
            return None
        return PrintReadService.from_adapter_view(bundle.print_view)
