"""Create one typed MANUAL personnel-order draft without HR consequences."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.personnel_order_header_uniqueness import INDEX_NAME

from app.db.engine import engine
from app.db.models.personnel_orders import PERSONNEL_ORDER_ITEM_TYPE_CODES, SOURCE_MODE_MANUAL
from app.services.personnel_order_document_header_service import duplicate_preview, PersonnelOrderDuplicateError
from app.services.personnel_orders_command_service import PersonnelOrderConflictError
from app.services.personnel_orders_query_service import PersonnelOrderValidationError
from app.services.personnel_order_evidence_scope_service import create_personnel_order_evidence_scope_tx
from app.services.personnel_orders_editorial.generation_service import generate_editorial
from app.services.personnel_order_catalog_context import employee_catalog_context, snapshot_catalog_forms
from app.services.personnel_order_creation_schema import creation_capabilities


def _unresolved_subject_payload(subject: Mapping[str, Any]) -> dict[str, Any]:
    values = {
        key: str(subject.get(key) or "").strip()
        for key in ("full_name", "org_unit_name", "position_name", "specialty")
    }
    if not all(values.values()):
        raise PersonnelOrderValidationError("UNRESOLVED_SUBJECT_FIELDS_REQUIRED")
    return {
        "source_employee_name": values["full_name"],
        "source_org_unit_name": values["org_unit_name"],
        "source_position_name": values["position_name"],
        "unresolved_subject": {**values, "needs_employee_link": True},
    }


def _employee_document_context(conn: Any, *, employee_id: int, effective_date: date, use_catalog: bool = True) -> dict[str, str]:
    row = employee_catalog_context(conn, employee_id, effective_date) if use_catalog else _legacy_employee_context(conn,employee_id,effective_date)
    if row is None:
        raise PersonnelOrderValidationError("EMPLOYEE_NOT_FOUND")
    return row


def _selected_employee_payload(conn: Any, *, employee_id: int, effective_date: date, context: Optional[Mapping[str, Any]], use_catalog: bool = True) -> dict[str, Any]:
    resolved = _employee_document_context(conn, employee_id=employee_id, effective_date=effective_date,use_catalog=use_catalog)
    overrides = dict(context or {})
    position = str(overrides.get("position_name") or resolved["position_name"] or "").strip()
    org_unit = str(overrides.get("org_unit_name") or resolved["org_unit_name"] or "").strip()
    specialty = str(overrides.get("specialty") or "").strip()
    return snapshot_catalog_forms({
        "source_employee_name": resolved["full_name"],
        "source_org_unit_name": org_unit,
        "source_position_name": position,
        "document_specialty": specialty or None,
    }, resolved)


def prepare_manual_item_payload(conn: Any, *, item_type_code: str, employee_id: Optional[int], effective_date: date, period_start: Optional[date] = None, period_end: Optional[date] = None, item_payload: Optional[Mapping[str, Any]] = None, unresolved_subject: Optional[Mapping[str, Any]] = None, document_subject_context: Optional[Mapping[str, Any]] = None, template_version_id: int | None = None, capabilities: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """Use the same typed contract for the first and subsequent employees."""
    capabilities = capabilities or creation_capabilities(conn, item_type_code)
    if item_type_code == 'LEAVE.ANNUAL.RECALL':
        # Recall uses explicit bilingual document placement, not the
        # possessive forms required by the leave-grant constructors.
        resolved = _employee_document_context(conn, employee_id=employee_id, effective_date=effective_date,
            use_catalog=capabilities['job_catalog_supported'])
        base_payload = snapshot_catalog_forms({
            'source_employee_name': resolved['full_name'],
            'source_position_name': (document_subject_context or {}).get('position_name') or resolved.get('position_title_ru') or resolved.get('position_name'),
            'source_org_unit_name': (document_subject_context or {}).get('org_unit_name') or resolved.get('org_unit_name'),
            'recall_position_kk': resolved.get('position_title_kk') or '',
            'recall_org_unit_kk': resolved.get('org_unit_title_kk') or '',
        }, resolved)
    else:
        base_payload = (
        _unresolved_subject_payload(unresolved_subject)
        if unresolved_subject is not None
        else _selected_employee_payload(
            conn,
            employee_id=int(employee_id),
            effective_date=effective_date,
            context=document_subject_context,
            use_catalog=capabilities['job_catalog_supported'],
        )
        )
    for key in ("document_forms_ru", "document_forms_kk"):
        if key in (item_payload or {}):
            base_payload[key] = {**base_payload.get(key, {}), **dict(item_payload[key])}
    if item_type_code == "LEAVE.UNPAID.GRANT":
        from app.services.personnel_order_unpaid_leave_contract import unpaid_leave_period

        supplied = dict(item_payload or {})
        supplied_leave = supplied.get("leave") if isinstance(supplied.get("leave"), Mapping) else {}
        period = unpaid_leave_period({"leave": supplied_leave})
        if period_start != period["start"] or period_end != period["end"] or effective_date != period_start:
            raise PersonnelOrderValidationError("UNPAID_LEAVE_PERIOD_MISMATCH")
        base_payload.update(supplied)
    if item_type_code in {"LEAVE.CHILDCARE.GRANT", "LEAVE.ANNUAL.RECALL"}:
        from app.services.personnel_orders_command_service import _validate_leave_draft_item
        base_payload.update(dict(item_payload or {}))
        _validate_leave_draft_item(item_type_code=item_type_code, employee_id=employee_id, effective_date=effective_date, period_start=period_start, period_end=period_end, payload=base_payload)
    if item_type_code == "TRANSFER" and (template_version_id is not None or "transfer" in (item_payload or {})):
        from app.services.personnel_order_transfer_contract import transfer_values
        supplied = (item_payload or {}).get("transfer", {})
        try:
            transfer_values(supplied)
        except ValueError as exc:
            raise PersonnelOrderValidationError(str(exc)) from exc
        base_payload["transfer"] = dict(supplied)
        base_payload["to_rate"] = supplied["rate"]
    if item_type_code == "SUPPLEMENTARY_PAY":
        selected_texts = conn.execute(text("SELECT body_template_ru,body_template_kk FROM personnel_order_template_versions WHERE template_version_id=:id AND item_type_code=:type AND status IN ('PUBLISHED','ARCHIVED')"), {'id':template_version_id,'type':item_type_code}).mappings().first() if template_version_id else None
        if 'allowance' in (item_payload or {}) or any('allowance.' in value for value in (selected_texts or {}).values()):
            from app.services.personnel_order_supplementary_pay_contract import values as supplementary_values, BASE_TYPE
            from app.services.personnel_order_service_area_contract import normalize_recipient
            allowance = dict((item_payload or {}).get('allowance') or {})
            recipient = normalize_recipient((item_payload or {}).get('allowance_recipient'))
            try:
                assignments=conn.execute(text("SELECT pa.assignment_id FROM person_assignments pa JOIN employees e ON e.person_id=pa.person_id WHERE e.employee_id=:employee AND pa.active_flag IS TRUE AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)"),{'employee':employee_id}).scalars().all()
                if recipient.get('assignment_id') is not None and recipient['assignment_id'] not in assignments: raise ValueError('Выбранное назначение не принадлежит получателю доплаты.')
                if len(assignments)>1 and recipient.get('assignment_id') is None: raise ValueError('Выберите назначение получателя доплаты.')
                validated = supplementary_values(allowance,recipient,effective_date)
            except ValueError as exc:
                raise PersonnelOrderValidationError(str(exc)) from exc
            base_payload['allowance'] = {key:allowance[key] for key in ('employee_dative_ru','employee_dative_kk','basis_ru','basis_kk')}
            base_payload['allowance'].update(percent=int(validated['allowance.percent']),basis_type=BASE_TYPE)
            from app.services.personnel_order_russian_reference_forms import russian_reference_case
            recipient['org_unit_genitive_ru'] = recipient.get('org_unit_genitive_ru') or russian_reference_case(recipient.get('org_unit_ru'),'genitive')
            base_payload['allowance_recipient'] = recipient
    if item_type_code == "CONCURRENT_DUTY_START" and (template_version_id is not None or "concurrent" in (item_payload or {})):
        from app.services.personnel_order_concurrent_contract import concurrent_values
        supplied = (item_payload or {}).get("concurrent", {})
        from app.services.personnel_order_replacement_contract import variant, replacement_values, optional_placement
        selected_texts = conn.execute(text("SELECT body_template_ru,body_template_kk FROM personnel_order_template_versions WHERE template_version_id=:id AND item_type_code=:type AND status IN ('PUBLISHED','ARCHIVED')"), {"id":template_version_id,"type":item_type_code}).mappings().first() if template_version_id else None
        mode = variant(selected_texts or {})
        from app.services.personnel_order_service_area_contract import enabled as area_enabled,values as area_values,BASE_TYPE,normalize_recipient
        service_area = area_enabled(selected_texts or {})
        try:
            if mode:
                replacement = dict((item_payload or {}).get("replacement") or {})
                if service_area:
                    recipient=normalize_recipient((item_payload or {}).get('allowance_recipient'))
                    assignments=conn.execute(text("SELECT pa.assignment_id FROM person_assignments pa JOIN employees e ON e.person_id=pa.person_id WHERE e.employee_id=:employee AND pa.active_flag IS TRUE AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)"),{'employee':employee_id}).scalars().all()
                    if recipient.get('assignment_id') is not None and recipient['assignment_id'] not in assignments:raise ValueError('Выбранное назначение не принадлежит получателю доплаты.')
                    if len(assignments)>1 and recipient.get('assignment_id') is None:raise ValueError('Выберите назначение получателя доплаты.')
                    validated=area_values(supplied,replacement,effective_date,recipient)
                    base_payload['allowance_recipient']=recipient
                    replacement['allowance_basis_type']=BASE_TYPE
                    for key in ('allowance_basis_ru','allowance_basis_kk','rate','total_rate'):replacement.pop(key,None)
                    if replacement.get('term_type')!='DATE':replacement.pop('end_date',None)
                else:
                    validated = replacement_values(supplied, replacement, effective_date, mode, optional_placement=optional_placement(selected_texts or {}))
                replacement["mode"] = mode
                if optional_placement(selected_texts or {}): replacement["allowance_percent"] = int(validated["allowance.percent"])
                base_payload["replacement"] = replacement
            else:
                concurrent_values(supplied, effective_date)
        except ValueError as exc:
            raise PersonnelOrderValidationError(str(exc)) from exc
        base_payload["concurrent"] = dict(supplied)
        if mode != "PAY":
            base_payload["concurrent_rate"] = supplied["rate"]
            base_payload["total_rate"] = supplied["total_rate"]
        else:
            for key in ("rate", "total_rate"): base_payload["concurrent"].pop(key,None)
    if item_type_code == "CONCURRENT_DUTY_END" and (template_version_id is not None or "concurrent" in (item_payload or {})):
        from app.services.personnel_order_concurrent_end_contract import cessation_values
        supplied = (item_payload or {}).get("concurrent", {})
        try:
            cessation_values(supplied, effective_date)
        except ValueError as exc:
            raise PersonnelOrderValidationError(str(exc)) from exc
        base_payload["concurrent"] = dict(supplied)
        base_payload["concurrent_rate"] = supplied["rate"]
        base_payload["remaining_rate"] = supplied["remaining_rate"]
    return base_payload


def create_manual_draft(*, created_by: int, template_version_id: int | None = None, order_number: str, order_date: date, source_title: str, source_title_locale: str, item_type_code: str, employee_id: Optional[int], effective_date: date, period_start: Optional[date] = None, period_end: Optional[date] = None, item_payload: Optional[Mapping[str, Any]] = None, unresolved_subject: Optional[Mapping[str, Any]] = None, document_subject_context: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    number = str(order_number or "").strip()
    title = str(source_title or "").strip()
    if not number or not title:
        raise PersonnelOrderValidationError("Manual order number and source title are required.")
    if item_type_code not in PERSONNEL_ORDER_ITEM_TYPE_CODES:
        raise PersonnelOrderValidationError("Unsupported item type.")
    if (employee_id is None) == (unresolved_subject is None):
        raise PersonnelOrderValidationError("SUBJECT_SELECTION_REQUIRED")
    duplicate = duplicate_preview(order_number=number, order_date=order_date)
    if duplicate["blocking"]:
        raise PersonnelOrderDuplicateError(duplicate)
    with engine.begin() as conn:
        capabilities=creation_capabilities(conn,item_type_code)
        if not capabilities['creation_supported']:
            raise PersonnelOrderValidationError(capabilities['creation_reason'])
        if template_version_id is not None and not capabilities['independent_supported']:
            raise PersonnelOrderValidationError("Независимые варианты шаблонов недоступны в текущей схеме БД. Выберите основной вид приказа; требуется миграция hrtpl001.")
        base_payload = prepare_manual_item_payload(conn, item_type_code=item_type_code, employee_id=employee_id, effective_date=effective_date, period_start=period_start, period_end=period_end, item_payload=item_payload, unresolved_subject=unresolved_subject, document_subject_context=document_subject_context, template_version_id=template_version_id, capabilities=capabilities)
        # Recheck inside the write transaction; browser preview is never authoritative.
        duplicate = duplicate_preview(order_number=number, order_date=order_date,conn=conn)
        if duplicate["blocking"]:
            raise PersonnelOrderDuplicateError(duplicate)
        if template_version_id is not None:
            selected = conn.execute(text("SELECT template_version_id FROM public.personnel_order_template_versions WHERE template_version_id=:id AND item_type_code=:type AND status='PUBLISHED' FOR SHARE"), {"id": template_version_id, "type": item_type_code}).first()
            if selected is None:
                raise PersonnelOrderValidationError("Selected published template does not belong to this order type or is no longer published.")
        order_id = _insert_manual_order(conn,{"number":number,"order_date":order_date,"item_type":item_type_code,"source_mode":SOURCE_MODE_MANUAL,"title":title,"locale":source_title_locale,"created_by":created_by,"template_version":template_version_id},supports_selection=capabilities['independent_supported'])
        conn.execute(text("""
            INSERT INTO personnel_order_items(order_id,item_number,item_type_code,item_status,employee_id,effective_date,period_start,period_end,payload)
            VALUES(:order_id,1,:item_type,'ACTIVE',:employee_id,:effective_date,:period_start,:period_end,CAST(:payload AS jsonb))
        """), {"order_id": order_id, "item_type": item_type_code, "employee_id": employee_id, "effective_date": effective_date, "period_start": period_start, "period_end": period_end, "payload": json.dumps(base_payload, ensure_ascii=False)})
        create_personnel_order_evidence_scope_tx(conn, order_id=order_id)
        generate_editorial(order_id, user_id=created_by, conn=conn)
        if template_version_id is not None:
            from app.services.personnel_order_template_application_service import apply_template_application_tx, TemplateApplicationError
            try:
                apply_template_application_tx(conn, order_id, created_by, expected_document_revision=1)
            except TemplateApplicationError as exc:
                raise PersonnelOrderValidationError(str(exc)) from exc
    return {"order_id": order_id, "order_number": number, "order_type_code": item_type_code, "status": "DRAFT", "source_mode": SOURCE_MODE_MANUAL, "document_revision": 1, "document_review_state": "NEEDS_REVIEW"}


def _insert_manual_order(conn, values, *, supports_selection):
    # The pre-stage-3 path has no version-link column and keeps the old generator.
    extra_column=",selected_template_version_id" if supports_selection else ""
    extra_value=",:template_version" if supports_selection else ""
    try:
        return int(conn.execute(text(f"""
        INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,source_title,source_title_locale,storage_json,created_by{extra_column})
        VALUES(:number,:order_date,:item_type,'DRAFT',:source_mode,:title,:locale,'{{}}'::jsonb,:created_by{extra_value})
        RETURNING order_id
        """),values).scalar_one())
    except IntegrityError as exc:
        if getattr(getattr(exc.orig,'diag',None),'constraint_name',None)==INDEX_NAME:
            duplicate=duplicate_preview(order_number=values['number'],order_date=values['order_date'])
            if duplicate['blocking']:raise PersonnelOrderDuplicateError(duplicate) from exc
        raise


def _legacy_employee_context(conn: Any, employee_id: int, effective_date: date) -> dict[str, str]:
    """Read the primary assignment effective on the document date; never change it."""
    row = conn.execute(text("""
        SELECT
            COALESCE(NULLIF(BTRIM(e.full_name), ''), NULLIF(BTRIM(p.full_name), '')) AS full_name,
            COALESCE(pa_pos.name, e_pos.name) AS position_name,
            COALESCE(pa_ou.name, e_ou.name) AS org_unit_name
        FROM employees e
        LEFT JOIN persons p ON p.person_id = e.person_id
        LEFT JOIN LATERAL (
            SELECT pa.position_id, pa.org_unit_id
            FROM person_assignments pa
            WHERE pa.person_id = e.person_id
              AND pa.active_flag IS TRUE
              AND pa.is_primary IS TRUE
              AND pa.lifecycle_status = 'active'
              AND pa.start_date <= :effective_date
              AND (pa.end_date IS NULL OR pa.end_date >= :effective_date)
            ORDER BY pa.start_date DESC, pa.assignment_id DESC
            LIMIT 1
        ) primary_assignment ON TRUE
        LEFT JOIN positions pa_pos ON pa_pos.position_id = primary_assignment.position_id
        LEFT JOIN org_units pa_ou ON pa_ou.unit_id = primary_assignment.org_unit_id
        LEFT JOIN positions e_pos ON e_pos.position_id = e.position_id
        LEFT JOIN org_units e_ou ON e_ou.unit_id = e.org_unit_id
        WHERE e.employee_id = :employee_id
    """), {"employee_id": employee_id, "effective_date": effective_date}).mappings().one_or_none()
    if row is None:
        raise PersonnelOrderValidationError("EMPLOYEE_NOT_FOUND")
    return {key: str(row.get(key) or "").strip() for key in ("full_name", "position_name", "org_unit_name")}
