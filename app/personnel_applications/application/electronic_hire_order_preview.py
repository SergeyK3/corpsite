"""Read-only HIRE order preview for saved electronic applications."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.application.electronic_hire_service import (
    ElectronicHireError,
    load_electronic_hire,
)
from app.services.personnel_order_item_templates import version_print_titles
from app.services.personnel_order_hire_wording import hire_position_accusative_ru
from app.services.personnel_order_template_application_service import (
    _values,
    render_item_template,
)


def preview_electronic_hire_order(conn: Connection, application_id: int) -> dict[str, Any]:
    application = load_electronic_hire(conn, application_id)
    if application["application_source"] != "electronic":
        raise ElectronicHireError("Предпросмотр доступен для электронного заявления.",
                                  "ORDER_PREVIEW_UNAVAILABLE")
    name = (application["full_name"] if application["candidate_checked_at"] is not None
            else application["preliminary_name"] or application["full_name"])
    if not name or not application["planned_start_date"] or not application["org_unit_ru"] or not application["position_ru"]:
        raise ElectronicHireError("Заполните ФИО и условия приёма для предпросмотра приказа.",
                                  "ORDER_PREVIEW_INCOMPLETE")

    template_row = conn.execute(text("""
        SELECT version.*, template.name_ru, template.name_kk, template.is_default
        FROM public.personnel_order_template_versions version
        JOIN public.personnel_order_templates template USING (template_id)
        WHERE version.item_type_code='HIRE' AND version.status='PUBLISHED'
          AND template.is_default=TRUE
    """)).mappings().one_or_none()
    if template_row is None:
        raise ElectronicHireError("Опубликованный шаблон приказа о приёме не найден.",
                                  "HIRE_TEMPLATE_UNAVAILABLE")
    template = version_print_titles(template_row)
    application_date = application["application_received_at"].strftime("%d.%m.%Y")
    # Only the preview uses the preliminary name as the RU case form. A real
    # order still needs verified identity and the usual document-form checks.
    payload = {
        "source_employee_name": name,
        "employee_full_name_accusative_ru": name,
        "source_org_unit_name": application["org_unit_ru"],
        "org_unit_title_kk": application["org_unit_kk"] or application["org_unit_ru"],
        "source_position_name": application["position_ru"],
        "position_title_kk": application["position_kk"] or application["position_ru"],
        "document_forms_ru": {"position_document_nominative_ru": application["position_document_ru"]},
        "document_forms_kk": {"position_document_possessive_kk": application["position_document_kk"]},
        "employment_rate": float(application["intended_employment_rate"]),
        "hire_basis": {
            "ru": f"черновик электронного заявления №{application_id} от {application_date}",
            "kk": f"{application_date} күнгі №{application_id} электрондық өтініш жобасы",
        },
    }
    item = {
        "item_type_code": "HIRE",
        "item_id": None,
        "order_id": None,
        "employee_id": None,
        "effective_date": application["planned_start_date"],
        "payload": payload,
    }
    values, warnings, missing = _values(conn, item, template)
    if warnings or missing:
        raise ElectronicHireError("Недостаточно данных для предпросмотра приказа.",
                                  "HIRE_PREVIEW_INCOMPLETE")
    if "на должность" in template["body_template_ru"].lower():
        document_ru = application["position_document_ru"] or ""
        values["position.title_ru"] = hire_position_accusative_ru(
            application["position_ru"],
            document_ru if document_ru.strip().casefold() != application["position_ru"].strip().casefold() else "",
        )
    rendered = render_item_template(conn, item, template, values)
    return {
        "application_id": application_id,
        "saved": False,
        "template_version_id": template["template_version_id"],
        "ru": {"title": rendered["title_ru"], "preamble": rendered["preamble_ru"],
               "body": rendered["body_template_ru"], "basis": rendered["basis_template_ru"]},
        "kk": {"title": rendered["title_kk"], "preamble": rendered["preamble_kk"],
               "body": rendered["body_template_kk"], "basis": rendered["basis_template_kk"]},
    }
