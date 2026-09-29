"""Published template preview/application using the existing editorial-block storage."""
from __future__ import annotations
import re
from typing import Any, Mapping
from sqlalchemy import text
from app.db.engine import engine
from app.services.personnel_order_template_validation import validate_template_texts
from app.services.personnel_orders_editorial.service import get_editorial_state
from app.services.personnel_order_termination_reason import termination_reason_text
from app.services.personnel_orders_editorial.generators import format_personnel_order_date_numeric
from app.services.personnel_orders_editorial.position_dictionary import localized_personnel_order_position

_FIELDS = ("title_ru","title_kk","preamble_ru","preamble_kk","body_template_ru","body_template_kk","basis_template_ru","basis_template_kk")
_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
class TemplateApplicationError(ValueError):
    def __init__(self, message: str, conflict: bool=False): super().__init__(message); self.conflict=conflict


def _employee_full_name_for_preview(
    payload: Mapping[str, Any], employee: Mapping[str, Any] | None,
) -> str:
    """Return the historical item's canonical name, never a search/display label.

    Reconstruction stores the name that identified the employee in the item's
    payload.  It must win over ``employees.full_name``: the latter is allowed
    to be a compact directory display name and may also have changed since the
    order was created.
    """
    payload_employee = payload.get("employee")
    if isinstance(payload_employee, Mapping):
        payload_name = payload_employee.get("name")
        if isinstance(payload_name, Mapping):
            canonical = str(payload_name.get("canonical") or "").strip()
            if canonical:
                return canonical

    source_name = str(payload.get("source_employee_name") or "").strip()
    if source_name:
        return source_name

    return str((employee or {}).get("full_name") or "").strip()


def _context(conn: Any, order_id: int) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str,str]]:
    order=conn.execute(text("SELECT * FROM public.personnel_orders WHERE order_id=:id FOR UPDATE"),{"id":order_id}).mappings().first()
    if not order or order["archived_at"] is not None or order["status"]!='DRAFT': raise TemplateApplicationError("Template application is available only for a non-archived DRAFT order.")
    items=conn.execute(text("SELECT * FROM public.personnel_order_items WHERE order_id=:id AND item_status='ACTIVE'"),{"id":order_id}).mappings().all()
    if len(items)!=1: raise TemplateApplicationError("Template application requires exactly one ACTIVE item.")
    item=items[0]
    template=conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='PUBLISHED'"),{"type":item["item_type_code"]}).mappings().first()
    if not template: raise TemplateApplicationError("No PUBLISHED template exists for this item type.")
    employee=conn.execute(text("SELECT e.full_name, p.name position_name, ou.name org_unit_name FROM public.employees e LEFT JOIN public.positions p ON p.position_id=e.position_id LEFT JOIN public.org_units ou ON ou.unit_id=e.org_unit_id WHERE e.employee_id=:id"),{"id":item["employee_id"]}).mappings().first()
    payload=item["payload"] or {}; reason=payload.get("termination_reason") or payload.get("reason")
    effective_date = str(item["effective_date"] or "")
    canonical_name = _employee_full_name_for_preview(payload, employee)
    values={"employee.full_name":canonical_name,"position.title_ru":str(employee["position_name"] or ""),"position.title_kk":localized_personnel_order_position(employee["position_name"],"kk"),"org_unit.title_ru":str(employee["org_unit_name"] or ""),"org_unit.title_kk":str(employee["org_unit_name"] or ""),"effective_date":effective_date,"effective_date_local":format_personnel_order_date_numeric(effective_date),"termination.reason.ru":termination_reason_text(reason,"ru"),"termination.reason.kk":termination_reason_text(reason,"kk"),"termination.unused_leave_days":str(payload.get("unused_leave_days") or ""),"basis":str(payload.get("basis") or order["basis_summary"] or "")}
    return order,item,dict(template),values

def _render(template: Mapping[str,Any], values: Mapping[str,str]) -> dict[str,str]:
    texts={k:template[k] for k in _FIELDS}; validate_template_texts(str(template["item_type_code"]),texts)
    missing=set()
    def render_text(key: str, template_text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            token=match.group(1)
            value=values.get(f"{token}.{'kk' if key.endswith('_kk') else 'ru'}", values.get(token,""))
            if not value.strip(): missing.add(token)
            return value
        return _TOKEN.sub(replace, template_text)
    result={key:render_text(key,value) for key,value in texts.items()}
    if missing: raise TemplateApplicationError("Required template data is missing: "+", ".join(sorted(missing)))
    return result

def preview_template_application(order_id:int)->dict[str,Any]:
    with engine.connect() as conn:
        order,item,template,values=_context(conn,order_id); rendered=_render(template,values)
        blocks=conn.execute(text("SELECT editorial_block_id block_id,'ORDER' scope,NULL::bigint order_item_id,locale,block_type,generated_text,override_text,revision FROM public.personnel_order_editorial_blocks WHERE order_id=:id UNION ALL SELECT item_editorial_block_id,'ITEM',order_item_id,locale,block_type,generated_text,override_text,revision FROM public.personnel_order_item_editorial_blocks WHERE order_item_id=:item"),{"id":order_id,"item":item["item_id"]}).mappings().all()
        prior=conn.execute(text("SELECT a.template_application_id application_id,a.template_version_id,t.version_number template_version_number,a.applied_at,a.applied_by_user_id FROM public.personnel_order_template_applications a JOIN public.personnel_order_template_versions t ON t.template_version_id=a.template_version_id WHERE a.order_id=:id AND a.order_item_id=:item ORDER BY a.applied_at DESC,a.template_application_id DESC LIMIT 1"),{"id":order_id,"item":item["item_id"]}).mappings().first()
    current={f"{r['locale']}:{r['block_type']}":dict(r) for r in blocks}; override_blocks=[{"block_id":r["block_id"],"scope":r["scope"],"block_type":str(r["block_type"]).upper(),"language":str(r["locale"]).upper(),"order_item_id":r["order_item_id"]} for r in blocks if (r["override_text"] or "").strip()]
    return {"available":True,"template":{"template_version_id":template["template_version_id"],"version_number":template["version_number"],"item_type_code":template["item_type_code"]},"has_overrides":bool(override_blocks),"override_blocks":override_blocks,"has_prior_application":bool(prior),"last_application":dict(prior) if prior else None,"current":current,"proposed":rendered,"order_revision":order["document_revision"]}

def apply_template_application(order_id:int, actor_user_id:int, *, expected_document_revision:int, confirm_replace_overrides:bool=False, confirm_reapply:bool=False)->dict[str,Any]:
    with engine.begin() as conn:
        order,item,template,values=_context(conn,order_id)
        if int(order["document_revision"])!=expected_document_revision: raise TemplateApplicationError("Order revision conflict.",True)
        rendered=_render(template,values)
        existing=conn.execute(text("SELECT locale,block_type,generated_text,override_text,revision FROM public.personnel_order_editorial_blocks WHERE order_id=:id UNION ALL SELECT locale,block_type,generated_text,override_text,revision FROM public.personnel_order_item_editorial_blocks WHERE order_item_id=:item"),{"id":order_id,"item":item["item_id"]}).mappings().all()
        if any((r["override_text"] or "").strip() for r in existing) and not confirm_replace_overrides: raise TemplateApplicationError("Manual overrides require explicit replacement confirmation.",True)
        prior=conn.execute(text("SELECT 1 FROM public.personnel_order_template_applications WHERE order_id=:id AND order_item_id=:item LIMIT 1"),{"id":order_id,"item":item["item_id"]}).first()
        if prior and not confirm_reapply: raise TemplateApplicationError("Template was already applied; explicit reapply confirmation is required.",True)
        for locale,suffix in (("ru","ru"),("kk","kk")):
            for block,key in (("title",f"title_{suffix}"),("preamble",f"preamble_{suffix}")):
                conn.execute(text("UPDATE public.personnel_order_editorial_blocks SET generated_text=:v,override_text=NULL,revision=revision+1,updated_at=now() WHERE order_id=:id AND locale=:l AND block_type=:b"),{"v":rendered[key],"id":order_id,"l":locale,"b":block})
            for block,key in (("body",f"body_template_{suffix}"),("basis",f"basis_template_{suffix}")):
                conn.execute(text("UPDATE public.personnel_order_item_editorial_blocks SET generated_text=:v,override_text=NULL,revision=revision+1,updated_at=now() WHERE order_item_id=:item AND locale=:l AND block_type=:b"),{"v":rendered[key],"item":item["item_id"],"l":locale,"b":block})
        conn.execute(text("INSERT INTO public.personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id) VALUES(:order,:item,:template,CAST(:snapshot AS jsonb),CAST(:rendered AS jsonb),CAST(:previous AS jsonb),:actor)"),{"order":order_id,"item":item["item_id"],"template":template["template_version_id"],"snapshot":__import__('json').dumps({k:template[k] for k in _FIELDS},ensure_ascii=False),"rendered":__import__('json').dumps(rendered,ensure_ascii=False),"previous":__import__('json').dumps([dict(x) for x in existing],default=str),"actor":actor_user_id})
    return get_editorial_state(order_id)
