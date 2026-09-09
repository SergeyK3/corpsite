"""Stage 1 general-information draft workflow.

Only acceptance writes canonical Person/PPR data.  All other calls write or
refresh private Stage 1 draft records only.
"""
from __future__ import annotations
import hashlib, json, re
from collections import Counter
from datetime import date
from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.services.personnel_record_event_service import emit_personnel_record_event

POLICY_VERSION = 'PPR_STAGE1_GENERAL_V1'
FIELDS = ('full_name','last_name','first_name','middle_name','iin','birth_date')
class Stage1Error(RuntimeError): code='STAGE1_ERROR'
class Stage1NotFoundError(Stage1Error): code='STAGE1_NOT_FOUND'
class Stage1ConflictError(Stage1Error): code='STAGE1_CONFLICT'
class Stage1ValidationError(Stage1Error): code='STAGE1_VALIDATION'

def _hash(v: Any) -> str: return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def _norm(v: Any) -> str: return ' '.join(str(v or '').strip().split())
def _date(v: Any) -> str|None:
    try: return date.fromisoformat(_norm(v)).isoformat() if _norm(v) else None
    except ValueError: return None
def _source(payload: dict[str,Any]) -> dict[str,str|None]:
    name=_norm(payload.get('full_name')); pieces=name.split(' '); iin=re.sub(r'\D','',str(payload.get('iin') or ''))
    out={'full_name':name or None,'last_name':None,'first_name':None,'middle_name':None,'iin':iin if re.fullmatch(r'\d{12}',iin) else None,'birth_date':_date(payload.get('birth_date'))}
    if len(pieces) in (2,3) and all(x and not x.endswith('.') for x in pieces): out.update(last_name=pieces[0],first_name=pieces[1],middle_name=pieces[2] if len(pieces)==3 else None)
    return out

def _derive(conn: Connection, participant: dict[str,Any], lock=False) -> dict[str,Any]:
    suffix=' FOR UPDATE' if lock else ''
    row=conn.execute(text(f'''SELECT p.person_id,p.full_name,p.last_name,p.first_name,p.middle_name,p.iin,p.birth_date,p.updated_at,e.employee_id,e.person_id employee_person_id,e.is_active,e.operational_status,r.row_id,r.normalized_payload
      FROM public.ppr_stage0_cohort_participants s JOIN public.employees e ON e.employee_id=s.employee_id JOIN public.persons p ON p.person_id=s.person_id JOIN public.hr_import_rows r ON r.row_id=s.source_row_id
      WHERE s.stage0_cohort_run_id=:cohort AND s.employee_id=:employee{suffix}'''),{'cohort':participant['stage0_cohort_run_id'],'employee':participant['employee_id']}).mappings().one_or_none()
    if row is None: raise Stage1ConflictError('STAGE1_COHORT_PARTICIPANT_STALE')
    d=dict(row)
    if not d['is_active'] or d['operational_status']!='active' or int(d['employee_person_id'])!=int(d['person_id']): raise Stage1ConflictError('STAGE1_EMPLOYEE_PERSON_LINK_STALE')
    source=_source(dict(d['normalized_payload'] or {})); current={f:(d[f].isoformat() if f=='birth_date' and d[f] else _norm(d[f]) or None) for f in FIELDS}; proposal={}; conflicts=[]
    for f in FIELDS:
        if not source[f]: continue
        if current[f] is None: proposal[f]=str(source[f])
        elif current[f]!=str(source[f]): conflicts.append({'field':f,'code':'STAGE1_CANONICAL_VALUE_CONFLICT'})
    fingerprint=_hash({'employee':d['employee_id'],'person':d['person_id'],'row':d['row_id'],'source':source,'current':current,'proposal':proposal,'conflicts':conflicts,'updated':d['updated_at']})
    return {'source':source,'current':current,'proposal':proposal,'conflicts':conflicts,'fingerprint':fingerprint,'person_updated_at':d['updated_at']}

def get_stage1_run(conn:Connection,*,run_id:int)->dict[str,Any]:
    run=conn.execute(text('SELECT stage1_run_id,stage0_cohort_run_id,status,current_position,created_at,accepted_at FROM public.ppr_stage1_general_runs WHERE stage1_run_id=:id'),{'id':run_id}).mappings().one_or_none()
    if run is None: raise Stage1NotFoundError('STAGE1_RUN_NOT_FOUND')
    rows=[dict(x) for x in conn.execute(text("""SELECT x.position,x.employee_id,x.person_id,x.source_row_id,x.proposed_values,x.conflicts,x.status,x.error_code,x.error_detail,x.completed_at,r.source_row_number,r.normalized_payload->>'full_name' display_name FROM public.ppr_stage1_general_participants x JOIN public.hr_import_rows r ON r.row_id=x.source_row_id WHERE x.stage1_run_id=:id ORDER BY x.position"""),{'id':run_id}).mappings()]
    for x in rows:
        values=dict(x.pop('proposed_values') or {}); x['source']=values.get('source',{}); x['current']=values.get('current',{}); x['proposal']=values.get('proposal',{}); x['conflicts']=list(x['conflicts'] or [])
    return {'run':dict(run),'participants':rows,'counts':dict(Counter(x['status'] for x in rows))}

def preview_stage1(conn:Connection,*,stage0_cohort_run_id:int,actor_user_id:int)->dict[str,Any]:
    participants=[dict(x) for x in conn.execute(text('SELECT stage0_cohort_run_id,position,employee_id,person_id,source_row_id FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id ORDER BY position'),{'id':stage0_cohort_run_id}).mappings()]
    if not participants: raise Stage1ValidationError('STAGE1_COHORT_EMPTY_OR_NOT_FOUND')
    items=[{**p,**_derive(conn,p),'status':'PENDING'} for p in participants]
    fingerprint=_hash({'policy':POLICY_VERSION,'cohort':stage0_cohort_run_id,'items':[{'employee':x['employee_id'],'fingerprint':x['fingerprint']} for x in items]})
    existing=conn.execute(text('SELECT stage1_run_id FROM public.ppr_stage1_general_runs WHERE preview_fingerprint=:f'),{'f':fingerprint}).scalar_one_or_none()
    if existing: return get_stage1_run(conn,run_id=int(existing))
    run=conn.execute(text("INSERT INTO public.ppr_stage1_general_runs(stage0_cohort_run_id,status,preview_fingerprint,policy_version,created_by_user_id) VALUES(:cohort,'DRY_RUN_COMPLETED',:f,:policy,:actor) RETURNING stage1_run_id"),{'cohort':stage0_cohort_run_id,'f':fingerprint,'policy':POLICY_VERSION,'actor':actor_user_id}).scalar_one()
    for x in items: conn.execute(text("""INSERT INTO public.ppr_stage1_general_participants(stage1_run_id,position,employee_id,person_id,source_row_id,source_fingerprint,person_updated_at,proposed_values,conflicts,status) VALUES(:run,:position,:employee,:person,:row,:fingerprint,:updated,CAST(:values AS jsonb),CAST(:conflicts AS jsonb),'PENDING')"""),{'run':run,'position':x['position'],'employee':x['employee_id'],'person':x['person_id'],'row':x['source_row_id'],'fingerprint':x['fingerprint'],'updated':x['person_updated_at'],'values':json.dumps({'source':x['source'],'current':x['current'],'proposal':x['proposal']},ensure_ascii=False),'conflicts':json.dumps(x['conflicts'])})
    return get_stage1_run(conn,run_id=int(run))

def approve_stage1(conn:Connection,*,run_id:int)->dict[str,Any]:
    status=conn.execute(text('SELECT status FROM public.ppr_stage1_general_runs WHERE stage1_run_id=:id FOR UPDATE'),{'id':run_id}).scalar_one_or_none()
    if status is None: raise Stage1NotFoundError('STAGE1_RUN_NOT_FOUND')
    if status not in {'DRY_RUN_COMPLETED','APPROVED'}: raise Stage1ConflictError('STAGE1_RUN_NOT_APPROVABLE')
    if conn.execute(text('SELECT count(*) FROM public.ppr_stage1_general_participants WHERE stage1_run_id=:id AND jsonb_array_length(conflicts)>0'),{'id':run_id}).scalar_one(): raise Stage1ValidationError('STAGE1_BLOCKING_CONFLICTS_REMAIN')
    conn.execute(text("UPDATE public.ppr_stage1_general_runs SET status='APPROVED' WHERE stage1_run_id=:id"),{'id':run_id}); return get_stage1_run(conn,run_id=run_id)

def execute_next_stage1(conn:Connection,*,run_id:int)->dict[str,Any]:
    run=conn.execute(text('SELECT stage0_cohort_run_id,status,current_position FROM public.ppr_stage1_general_runs WHERE stage1_run_id=:id FOR UPDATE'),{'id':run_id}).mappings().one_or_none()
    if run is None: raise Stage1NotFoundError('STAGE1_RUN_NOT_FOUND')
    if run['status'] not in {'APPROVED','RUNNING','PAUSED_ON_ERROR'}: raise Stage1ConflictError('STAGE1_RUN_NOT_EXECUTABLE')
    p=conn.execute(text("SELECT stage1_participant_id,position,employee_id,person_id,source_row_id FROM public.ppr_stage1_general_participants WHERE stage1_run_id=:id AND position>=:pos AND status IN ('PENDING','ERROR') ORDER BY position LIMIT 1 FOR UPDATE"),{'id':run_id,'pos':run['current_position']}).mappings().one_or_none()
    if p is None: conn.execute(text("UPDATE public.ppr_stage1_general_runs SET status='COMPLETED_PENDING_REVIEW' WHERE stage1_run_id=:id"),{'id':run_id}); return get_stage1_run(conn,run_id=run_id)
    try:
        d=_derive(conn,{**dict(p),'stage0_cohort_run_id':run['stage0_cohort_run_id']},lock=True)
        if d['conflicts']: raise Stage1ConflictError('STAGE1_CANONICAL_VALUE_CONFLICT')
        conn.execute(text("UPDATE public.ppr_stage1_general_participants SET source_fingerprint=:f,person_updated_at=:u,proposed_values=CAST(:v AS jsonb),conflicts='[]'::jsonb,status='COMPLETED',error_code=NULL,error_detail=NULL,completed_at=now() WHERE stage1_participant_id=:id"),{'id':p['stage1_participant_id'],'f':d['fingerprint'],'u':d['person_updated_at'],'v':json.dumps({'source':d['source'],'current':d['current'],'proposal':d['proposal']},ensure_ascii=False)})
        conn.execute(text("UPDATE public.ppr_stage1_general_runs SET status='RUNNING',current_position=:pos WHERE stage1_run_id=:id"),{'id':run_id,'pos':int(p['position'])+1})
    except Stage1Error as e:
        conn.execute(text("UPDATE public.ppr_stage1_general_participants SET status='ERROR',error_code=:code,error_detail=:detail WHERE stage1_participant_id=:id"),{'id':p['stage1_participant_id'],'code':e.code,'detail':str(e)})
        conn.execute(text("UPDATE public.ppr_stage1_general_runs SET status='PAUSED_ON_ERROR',current_position=:pos WHERE stage1_run_id=:id"),{'id':run_id,'pos':p['position']})
    return get_stage1_run(conn,run_id=run_id)

def accept_stage1_run(conn:Connection,*,run_id:int,actor_user_id:int)->dict[str,Any]:
    run=conn.execute(text('SELECT * FROM public.ppr_stage1_general_runs WHERE stage1_run_id=:id FOR UPDATE'),{'id':run_id}).mappings().one_or_none()
    if run is None: raise Stage1NotFoundError('STAGE1_RUN_NOT_FOUND')
    if run['status']!='COMPLETED_PENDING_REVIEW': raise Stage1ConflictError('STAGE1_RUN_NOT_READY_FOR_ACCEPTANCE')
    participants=[dict(x) for x in conn.execute(text('SELECT * FROM public.ppr_stage1_general_participants WHERE stage1_run_id=:id ORDER BY position FOR UPDATE'),{'id':run_id}).mappings()]
    if any(x['status']!='COMPLETED' for x in participants): raise Stage1ValidationError('STAGE1_PARTICIPANTS_NOT_COMPLETED')
    checked=[]
    for x in participants:
        d=_derive(conn,{**x,'stage0_cohort_run_id':run['stage0_cohort_run_id']},lock=True); stored=dict(x['proposed_values'] or {}).get('proposal',{})
        if d['conflicts'] or d['proposal']!=stored: raise Stage1ConflictError('STAGE1_ACCEPTANCE_STALE_OR_CONFLICT')
        checked.append((x,d))
    for x,d in checked:
        if d['proposal']:
            assigns=', '.join(f'{k}=:{k}' for k in d['proposal']); conn.execute(text(f'UPDATE public.persons SET {assigns},updated_at=now() WHERE person_id=:person'),{**d['proposal'],'person':x['person_id']})
        conn.execute(text("INSERT INTO public.personnel_record_metadata(person_id,ppr_lifecycle_state,hr_relationship_context,version) VALUES(:person,'COLLECTING','UNKNOWN',2) ON CONFLICT(person_id) DO NOTHING"),{'person':x['person_id']})
        emit_personnel_record_event(conn,person_id=int(x['person_id']),employee_context_id=int(x['employee_id']),domain_code='general_information',record_table_name='persons',record_id=int(x['person_id']),event_type='PPR_STAGE1_GENERAL_ACCEPTED',actor_id=str(actor_user_id),event_payload={'stage1_run_id':run_id,'source_row_id':int(x['source_row_id']),'fields':sorted(d['proposal'])})
    conn.execute(text("UPDATE public.ppr_stage1_general_runs SET status='ACCEPTED',accepted_by_user_id=:actor,accepted_at=now() WHERE stage1_run_id=:id"),{'id':run_id,'actor':actor_user_id})
    return get_stage1_run(conn,run_id=run_id)
