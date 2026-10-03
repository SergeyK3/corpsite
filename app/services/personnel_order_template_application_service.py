"""Published templates applied atomically to all active item-level blocks."""
from __future__ import annotations
import json, re
from typing import Any, Mapping
from sqlalchemy import text
from app.db.engine import engine
from app.services.personnel_order_template_validation import validate_template_texts
from app.services.personnel_orders_editorial.service import get_editorial_state
from app.services.personnel_orders_editorial.position_dictionary import document_nominative_personnel_order_position, localized_personnel_order_position
from app.services.personnel_order_termination_reason import termination_reason_text
from app.services.personnel_order_unpaid_leave_contract import UnpaidLeaveContractError, format_leave_date, period_clause_kk, period_clause_ru, period_text, unpaid_leave_period

_FIELDS=("title_ru","title_kk","preamble_ru","preamble_kk","body_template_ru","body_template_kk","basis_template_ru","basis_template_kk")
_TOKEN=re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
AUDIT_INSERT_HOOK = None  # Test-only failpoint; production leaves this unset.
class TemplateApplicationError(ValueError):
 def __init__(self,message:str,conflict:bool=False): super().__init__(message); self.conflict=conflict

def _snapshot(payload:Mapping[str,Any],key:str,fallback:str,locale:str="ru")->str:
 value=payload.get(key)
 if isinstance(value,Mapping): return str(value.get(locale) or value.get("name") or "").strip() or fallback
 return str(payload.get(f"{key}_{locale}") or (value if locale=="ru" else "") or "").strip() or fallback
def _name(payload:Mapping[str,Any],employee:Mapping[str,Any]|None)->str:
 raw=payload.get("employee")
 if isinstance(raw,Mapping) and isinstance(raw.get("name"),Mapping):
  value=str(raw["name"].get("canonical") or "").strip()
  if value:return value
 return str(payload.get("source_employee_name") or (employee or {}).get("full_name") or "").strip()
def _mapped_text(value:Any,*keys:str)->str:
 if not isinstance(value,Mapping): return ""
 for key in keys:
  candidate=value.get(key)
  if isinstance(candidate,str) and candidate.strip(): return candidate.strip()
 return ""
def _document_form_kk(payload:Mapping[str,Any],field:str)->str:
 """Read an explicit source/payload document form, never derive grammar."""
 forms=payload.get("document_forms_kk")
 aliases={
  "org_unit.document_genitive_kk":("org_unit_document_genitive_kk","org_unit_genitive","document_genitive_kk"),
  "position.document_possessive_kk":("position_document_possessive_kk","position_possessive","document_possessive_kk"),
  "employee.full_name_dative_kk":("employee_full_name_dative_kk","employee_dative","full_name_dative_kk"),
  "employee.full_name_genitive_kk":("employee_full_name_genitive_kk","employee_genitive","full_name_genitive_kk"),
 }
 direct=_mapped_text(forms,*aliases[field])
 if direct: return direct
 # Historical source snapshots may have kept the form next to the entity.
 if field.startswith("org_unit."):
  return _mapped_text(payload.get("org_unit_name"),"document_genitive_kk","genitive_kk")
 if field.startswith("position."):
  return _mapped_text(payload.get("position_name"),"document_possessive_kk","possessive_kk")
 employee=payload.get("employee")
 name=employee.get("name") if isinstance(employee,Mapping) else None
 return _mapped_text(name,"full_name_dative_kk" if field.endswith("dative_kk") else "full_name_genitive_kk","dative_kk" if field.endswith("dative_kk") else "genitive_kk")
def _document_form_ru(payload:Mapping[str,Any],field:str)->str:
 forms=payload.get("document_forms_ru")
 aliases={"employee.full_name_dative_ru":("employee_full_name_dative_ru","employee_dative","full_name_dative_ru")}
 direct=_mapped_text(forms,*aliases[field])
 if direct:return direct
 employee=payload.get("employee")
 name=employee.get("name") if isinstance(employee,Mapping) else None
 return _mapped_text(name,"full_name_dative_ru","dative_ru")
def _order(conn:Any,order_id:int):
 from app.services.personnel_orders_command_service import require_active_personnel_order
 require_active_personnel_order(conn,order_id,lock=True)
 order=conn.execute(text("SELECT * FROM public.personnel_orders WHERE order_id=:id FOR UPDATE"),{"id":order_id}).mappings().first()
 if not order or order["archived_at"] is not None or order["status"]!="DRAFT": raise TemplateApplicationError("Template application is available only for a non-archived DRAFT order.")
 items=conn.execute(text("SELECT * FROM public.personnel_order_items WHERE order_id=:id AND item_status='ACTIVE' ORDER BY item_number,item_id"),{"id":order_id}).mappings().all()
 if not items: raise TemplateApplicationError("Template application requires at least one ACTIVE item.")
 if len({str(x["item_type_code"]) for x in items})!=1: raise TemplateApplicationError("Template application requires ACTIVE items of one type.")
 template=conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:t AND status='PUBLISHED'"),{"t":items[0]["item_type_code"]}).mappings().first()
 if not template: raise TemplateApplicationError("No PUBLISHED template exists for this item type.")
 return order,list(items),dict(template)
def _values(conn:Any,item:Mapping[str,Any]):
 employee=conn.execute(text("SELECT e.full_name,p.name position_name,ou.name org_unit_name FROM public.employees e LEFT JOIN public.positions p ON p.position_id=e.position_id LEFT JOIN public.org_units ou ON ou.unit_id=e.org_unit_id WHERE e.employee_id=:id"),{"id":item["employee_id"]}).mappings().first()
 payload=item["payload"] or {}; posru=_snapshot(payload,"position_name",str((employee or {}).get("position_name") or "")); unitru=_snapshot(payload,"org_unit_name",str((employee or {}).get("org_unit_name") or "")); poskk=_snapshot(payload,"position_name","","kk"); unitkk=_snapshot(payload,"org_unit_name","","kk"); warnings=[]; missing=[]
 unpaid=str(item["item_type_code"]) == "LEAVE.UNPAID.GRANT"
 if not unpaid:
  poskk=poskk or localized_personnel_order_position(posru,"kk") or posru; unitkk=unitkk or unitru
 forms={field:_document_form_kk(payload,field) for field in ("org_unit.document_genitive_kk","position.document_possessive_kk","employee.full_name_dative_kk","employee.full_name_genitive_kk")}
 if unpaid:
  for field,value in forms.items():
   if not value:
    warnings.append({"code":"KK_DOCUMENT_FORM_MISSING","message":f"Missing confirmed document form: {field}."}); missing.append(field)
 values={"employee.full_name":_name(payload,employee),"employee.full_name_dative_ru":_document_form_ru(payload,"employee.full_name_dative_ru"),"position.title_ru":posru,"position.document_nominative_ru":document_nominative_personnel_order_position(posru),"position.title_kk":poskk,"org_unit.title_ru":unitru,"org_unit.title_kk":unitkk,**forms,"effective_date":str(item.get("effective_date") or ""),"effective_date_local":str(item.get("effective_date") or ""),"termination.reason.ru":termination_reason_text(payload.get("termination_reason") or payload.get("reason"),"ru"),"termination.reason.kk":termination_reason_text(payload.get("termination_reason") or payload.get("reason"),"kk"),"termination.unused_leave_days":str(payload.get("unused_leave_days") or ""),"basis":str(payload.get("basis") or "")}
 if unpaid:
  try: p=unpaid_leave_period(payload)
  except UnpaidLeaveContractError as exc: raise TemplateApplicationError(str(exc)) from exc
  start=p["start"]; end=p["end"]
  values.update({"leave.start_ru":format_leave_date(start,"ru") if start else "","leave.start_kk":format_leave_date(start,"kk") if start else "","leave.end_ru":format_leave_date(end,"ru") if end else "","leave.end_kk":format_leave_date(end,"kk") if end else "","leave.days":str(p["days"]),"leave.period_text_ru":period_text(p,"ru"),"leave.period_text_kk":period_text(p,"kk"),"leave.period_clause_ru":period_clause_ru(p),"leave.period_clause_kk":period_clause_kk(p)})
  basis=conn.execute(text("SELECT basis_type,document_date,document_number FROM public.personnel_order_item_bases WHERE order_item_id=:id"),{"id":item["item_id"]}).mappings().first()
  if basis and basis["basis_type"]=="PERSONAL_APPLICATION":
   if basis["document_date"]: values.update({"basis.application_date_ru":" от "+format_leave_date(basis["document_date"],"ru"),"basis.application_date_kk":" "+format_leave_date(basis["document_date"],"kk")+" күнгі"})
   if basis["document_number"]:values["basis.application_number_suffix"]=" № "+str(basis["document_number"])
 return values,warnings,missing
def _render(template:Mapping[str,Any],values:Mapping[str,str]):
 texts={k:template[k] for k in _FIELDS}; validate_template_texts(str(template["item_type_code"]),texts); missing=set()
 def each(key,value):
  def repl(match):
   token=match.group(1); value=values.get(f"{token}.{'kk' if key.endswith('_kk') else 'ru'}",values.get(token,"")); missing.add(token) if not value.strip() and not token.startswith("basis.application_") else None; return value
  return _TOKEN.sub(repl,value)
 result={key:each(key,value) for key,value in texts.items()}
 if missing:raise TemplateApplicationError("Required template data is missing: "+", ".join(sorted(missing)))
 return result
def _blocks(conn,order_id,item_ids):
 return conn.execute(text("SELECT editorial_block_id block_id,'ORDER' scope,NULL::bigint order_item_id,locale,block_type,generated_text,override_text,revision FROM public.personnel_order_editorial_blocks WHERE order_id=:id UNION ALL SELECT item_editorial_block_id,'ITEM',order_item_id,locale,block_type,generated_text,override_text,revision FROM public.personnel_order_item_editorial_blocks WHERE order_item_id=ANY(:items)"),{"id":order_id,"items":item_ids}).mappings().all()
def _preview(conn,order_id):
 order,items,template=_order(conn,order_id); item_ids=[int(x["item_id"]) for x in items]; entries=[]
 for item in items:
  values,warnings,missing_data=_values(conn,item)
  try: rendered=_render(template,values)
  except TemplateApplicationError as exc:
   missing_data.append(str(exc)); rendered={"body_template_ru":"","body_template_kk":"","basis_template_ru":"","basis_template_kk":""}
  entries.append({"order_item_id":int(item["item_id"]),"item_number":int(item["item_number"]),"current":{},"proposed":{"body_ru":rendered["body_template_ru"],"body_kk":rendered["body_template_kk"],"basis_ru":rendered["basis_template_ru"],"basis_kk":rendered["basis_template_kk"]},"warnings":warnings,"missing_data":missing_data,"blocked":bool(missing_data)})
 blocks=_blocks(conn,order_id,item_ids)
 for entry in entries:entry["current"]={f"{x['locale']}:{x['block_type']}":dict(x) for x in blocks if x["order_item_id"]==entry["order_item_id"]}
 overrides=[{"block_id":x["block_id"],"scope":x["scope"],"block_type":str(x["block_type"]).upper(),"language":str(x["locale"]).upper(),"order_item_id":x["order_item_id"]} for x in blocks if (x["override_text"] or "").strip()]
 prior=conn.execute(text("SELECT a.template_application_id application_id,a.template_version_id,t.version_number template_version_number,a.applied_at,a.applied_by_user_id FROM public.personnel_order_template_applications a JOIN public.personnel_order_template_versions t ON t.template_version_id=a.template_version_id WHERE a.order_id=:id ORDER BY a.applied_at DESC,a.template_application_id DESC LIMIT 1"),{"id":order_id}).mappings().first()
 result={"available":True,"template":{"template_version_id":template["template_version_id"],"version_number":template["version_number"],"item_type_code":template["item_type_code"]},"has_overrides":bool(overrides),"override_blocks":overrides,"has_prior_application":bool(prior),"last_application":dict(prior) if prior else None,"order_current":{f"{x['locale']}:{x['block_type']}":dict(x) for x in blocks if x["scope"]=="ORDER"},"order_proposed":{k:template[k] for k in ("title_ru","title_kk","preamble_ru","preamble_kk")},"items":entries,"order_revision":order["document_revision"]}
 if len(entries)==1: result["current"]={**result["order_current"],**entries[0]["current"]}; result["proposed"]={**result["order_proposed"],**{f"{k}_template_{lang}":entries[0]["proposed"][f"{k}_{lang}"] for k in ("body","basis") for lang in ("ru","kk")}}
 return result
def preview_template_application(order_id:int)->dict[str,Any]:
 with engine.connect() as conn:return _preview(conn,order_id)
def apply_template_application(order_id:int,actor_user_id:int,*,expected_document_revision:int,confirm_replace_overrides:bool=False,confirm_reapply:bool=False)->dict[str,Any]:
    with engine.begin() as conn:
        preview = _preview(conn, order_id)
        order, items, template = _order(conn, order_id)
        blocked = [str(entry["item_number"]) for entry in preview["items"] if entry.get("blocked")]
        if blocked:
            raise TemplateApplicationError("Template application is blocked for item(s): " + ", ".join(blocked))
        if int(order["document_revision"]) != expected_document_revision:
            raise TemplateApplicationError("Order revision conflict.", True)
        if preview["has_overrides"] and not confirm_replace_overrides:
            raise TemplateApplicationError("Manual overrides require explicit replacement confirmation.", True)
        if preview["has_prior_application"] and not confirm_reapply:
            raise TemplateApplicationError("Template was already applied; explicit reapply confirmation is required.", True)
        before = _blocks(conn, order_id, [int(x["item_id"]) for x in items])
        for lang in ("ru", "kk"):
            for block in ("title", "preamble"):
                conn.execute(text("UPDATE public.personnel_order_editorial_blocks SET generated_text=:v,override_text=NULL,revision=revision+1,updated_at=now() WHERE order_id=:id AND locale=:l AND block_type=:b"), {"v": preview["order_proposed"][f"{block}_{lang}"], "id": order_id, "l": lang, "b": block})
        for entry in preview["items"]:
            for lang in ("ru", "kk"):
                for block in ("body", "basis"):
                    conn.execute(text("UPDATE public.personnel_order_item_editorial_blocks SET generated_text=:v,override_text=NULL,revision=revision+1,updated_at=now() WHERE order_item_id=:id AND locale=:l AND block_type=:b"), {"v": entry["proposed"][f"{block}_{lang}"], "id": entry["order_item_id"], "l": lang, "b": block})
        if AUDIT_INSERT_HOOK:
            AUDIT_INSERT_HOOK()
        conn.execute(text("INSERT INTO public.personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id) VALUES(:o,:i,:t,CAST(:s AS jsonb),CAST(:r AS jsonb),CAST(:p AS jsonb),:a)"), {"o": order_id, "i": items[0]["item_id"], "t": template["template_version_id"], "s": json.dumps({k: template[k] for k in _FIELDS}, ensure_ascii=False), "r": json.dumps({"order": preview["order_proposed"], "items": preview["items"]}, ensure_ascii=False, default=str), "p": json.dumps([dict(x) for x in before], default=str), "a": actor_user_id})
    return get_editorial_state(order_id)
