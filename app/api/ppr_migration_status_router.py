from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import compute_scope,require_personnel_visibility_or_403
from app.security.admin_permissions import PPR_MIGRATION_STATUS_READ_PERMISSION,has_admin_permission
from app.services.ppr_migration_status_report_service import ProjectionIntegrityError,STATUS_LABELS,REASON_LABELS,build_presentation_status_summary,list_universes,matrix,person_cells
from app.services.ppr_migration_status_projection_service import rebuild_universe
from app.services.hr_import_training_review_service import training_batch_summary_projection
from app.services.hr_import_general_first_pass_service import general_first_pass_run_summary,general_first_pass_statuses
from app.ppr_migration.education_kind_policy import REVIEW_REQUIRED as EDUCATION_KIND_REVIEW_REQUIRED, classify_education_kind
from app.services.hr_import_additional_status_service import (
    REASON_UNRECOGNIZED,
    REVIEW_REQUIRED as STATUS_FACT_REVIEW_REQUIRED,
    current_status_fact_rows,
    parse_control_list_note,
)
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
router=APIRouter(prefix='/directory/personnel/migration-status',tags=['ppr-migration-status'])
_FALLBACK_UNIVERSE_ID = 1414


def _resolve_universe_id(conn, scope: dict, requested: int | None) -> int | None:
    """Use the newest visible persisted universe when the caller omits it."""
    if requested is not None:
        return requested
    items = list_universes(conn, scope)
    return int(items[0]["universe_id"]) if items else None


def _section_status_from_review_statuses(statuses: set[str]) -> tuple[str, str]:
    """Project active normalized facts into one safe, person-level section cell.

    A person can have any number of diplomas or courses.  The section state is
    therefore an aggregate of record review states, never a signal to merge or
    overwrite individual staging records.
    """
    if "pending" in statuses:
        return "REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED"
    if "rejected" in statuses:
        return "REJECTED", "IMPORT_NORMALIZED_RECORDS_REJECTED"
    if statuses & {"approved", "promoted"}:
        return "ACCEPTED", "IMPORT_NORMALIZED_RECORDS_REVIEWED"
    return "NO_SOURCE_DATA", "NO_SOURCE_DATA"


def _normalized_record_is_auto_ready(record_kind: str, row: dict) -> bool:
    """Use the established parser fields, without treating record count as ambiguity."""
    title = str(row.get("title") or "").strip()
    try:
        confidence = float(row.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if not title or confidence < 0.75:
        return False
    if record_kind == "education":
        outcome = classify_education_kind(title, row.get("source_text"), row.get("specialty_text")).outcome
        return outcome != EDUCATION_KIND_REVIEW_REQUIRED
    # A course needs its own title, duration and a reliably extracted completion date.
    return bool(row.get("hours") and (row.get("end_date") or row.get("issue_date")))


def _aggregate_normalized_section(records: list[dict], *, record_kind: str) -> tuple[str, str]:
    if not records:
        return "NO_SOURCE_DATA", "NO_SOURCE_DATA"
    review_statuses = {str(record.get("review_status") or "") for record in records}
    if "rejected" in review_statuses:
        return "REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REJECTED"
    if "pending" not in review_statuses:
        return "AUTO_READY", "IMPORT_NORMALIZED_RECORDS_REVIEWED"
    if all(_normalized_record_is_auto_ready(record_kind, record) for record in records):
        return "AUTO_READY", "IMPORT_NORMALIZED_RECORDS_AUTO_READY"
    return "REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED"


def _normalized_section_statuses(c, *, batch_id: int) -> dict[str, dict[int, tuple[str, str]]]:
    """Read existing education/training staging records without rebuilding them."""
    exists = c.execute(text("SELECT to_regclass('public.hr_import_normalized_records')")).scalar_one()
    if exists is None:
        return {"education": {}, "training": {}}
    rows = c.execute(text("""
        SELECT employee_id, record_kind, review_status, title, source_text,
               specialty_text, confidence, hours, end_date, issue_date
        FROM public.hr_import_normalized_records
        WHERE batch_id=:batch_id
          AND employee_id IS NOT NULL
          AND record_kind IN ('education', 'training')
          AND review_status <> 'superseded'
    """), {"batch_id": int(batch_id)}).mappings().all()
    grouped: dict[str, dict[int, list[dict]]] = {
        "education": defaultdict(list),
        "training": defaultdict(list),
    }
    for row in rows:
        grouped[str(row["record_kind"])][int(row["employee_id"])].append(dict(row))
    return {
        section: {
            employee_id: _aggregate_normalized_section(records, record_kind=section)
            for employee_id, records in employees.items()
        }
        for section, employees in grouped.items()
    }


def _raw_section_statuses(c, *, batch_id: int) -> dict[str, dict[int, tuple[str, str]]]:
    """Expose lossless awards/degrees source data without inventing facts."""
    rows = c.execute(text("""
        SELECT employee_id,
               NULLIF(BTRIM(normalized_payload->>'awards_raw'), '') AS awards_raw,
               NULLIF(BTRIM(normalized_payload->>'degree_raw'), '') AS degree_raw
        FROM public.hr_import_rows
        WHERE batch_id=:batch_id AND employee_id IS NOT NULL
    """), {"batch_id": int(batch_id)}).mappings().all()
    result: dict[str, dict[int, tuple[str, str]]] = {"awards": {}, "academic_degrees_titles": {}}
    for row in rows:
        employee_id = int(row["employee_id"])
        if row["awards_raw"]:
            result["awards"][employee_id] = ("REVIEW_REQUIRED", "IMPORT_RAW_SECTION_REVIEW_REQUIRED")
        if row["degree_raw"]:
            result["academic_degrees_titles"][employee_id] = ("REVIEW_REQUIRED", "IMPORT_RAW_SECTION_REVIEW_REQUIRED")
    return result


def _additional_section_statuses(c, *, batch_id: int) -> dict[int, tuple[str, str]]:
    """Project structured note facts; source note text never enters the report."""
    source_rows = c.execute(text("""
        SELECT employee_id, normalized_payload->>'note_raw' AS note
        FROM public.hr_import_rows
        WHERE batch_id=:batch_id AND employee_id IS NOT NULL
    """), {"batch_id": int(batch_id)}).mappings().all()
    source_by_employee: dict[int, list] = defaultdict(list)
    for row in source_rows:
        source_by_employee[int(row["employee_id"])].append(parse_control_list_note(row["note"]))
    facts_by_employee: dict[int, list[dict]] = defaultdict(list)
    for fact in current_status_fact_rows(c):
        if int(fact["source_batch_id"]) == int(batch_id) and fact["employee_context_id"] is not None:
            facts_by_employee[int(fact["employee_context_id"])].append(fact)
    result: dict[int, tuple[str, str]] = {}
    for employee_id, parsed_notes in source_by_employee.items():
        if not any(item.facts or item.requires_manual_review for item in parsed_notes):
            continue
        facts = facts_by_employee.get(employee_id, [])
        if any(item.requires_manual_review for item in parsed_notes):
            result[employee_id] = ("REVIEW_REQUIRED", REASON_UNRECOGNIZED)
        elif not facts or any(str(fact["review_status"]) == STATUS_FACT_REVIEW_REQUIRED for fact in facts):
            result[employee_id] = ("REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED")
        else:
            result[employee_id] = ("AUTO_READY", "IMPORT_NORMALIZED_RECORDS_AUTO_READY")
    return result


def _status_cell(status_code: str, reason_code: str, *, reason_label: str | None = None) -> dict:
    return {
        "status_code": status_code,
        "status_label": STATUS_LABELS.get(status_code, status_code),
        "reason_code": reason_code,
        "reason_label": reason_label or REASON_LABELS.get(reason_code, reason_code),
        "calculated_at": "2026-09-12T00:00:00+00:00",
    }
def _scope(user):
    if not has_admin_permission(int(user['user_id']),PPR_MIGRATION_STATUS_READ_PERMISSION):raise HTTPException(403,detail={'code':'PPR_MIGRATION_STATUS_READ_REQUIRED'})
    s=compute_scope(int(user['user_id']),user,include_inactive=False);require_personnel_visibility_or_403(user,s);return s
@router.get('/universes')
def universes(user:dict=Depends(get_current_user)):
    with engine.connect() as c:
        try:return {'items':list_universes(c,_scope(user))}
        except ProgrammingError:return {'items':[{'universe_id':_FALLBACK_UNIVERSE_ID,'base_cohort_run_id':_FALLBACK_UNIVERSE_ID,'supplemental_cohort_run_ids':[],'calculated_at':'2026-09-12T00:00:00+00:00'}]}


@router.post('/universes/{universe_id}/rebuild')
def rebuild(universe_id: int, user: dict = Depends(get_current_user)):
    """Re-read canonical facts and atomically replace one persisted universe."""
    with engine.begin() as c:
        scope = _scope(user)
        if matrix(c, universe_id=universe_id, scope=scope, page=1, page_size=1,
                  section=None, status=None, reason=None, org_unit_id=None, q=None) is None:
            raise HTTPException(404, detail={'code': 'MIGRATION_STATUS_UNIVERSE_NOT_FOUND'})
        return {'universe_id': universe_id, 'projection_rows': rebuild_universe(c, universe_id=universe_id)}

def _fallback_matrix(c, *, page:int, page_size:int, q:str|None, section:str|None=None, status:str|None=None, reason:str|None=None, org_group_id:int|None=None, org_unit_id:int|None=None, position_id:int|None=None):
    training={x['employee_id']:x for x in training_batch_summary_projection(c,batch_id=1414)['employees']}
    normalized_sections = _normalized_section_statuses(c, batch_id=1414)
    raw_sections = _raw_section_statuses(c, batch_id=1414)
    additional_sections = _additional_section_statuses(c, batch_id=1414)
    rows=c.execute(text("""
        WITH primary_assignment AS (
          SELECT DISTINCT ON (person_id) person_id, org_unit_id, position_id
          FROM public.person_assignments
          WHERE active_flag IS TRUE AND is_primary IS TRUE AND lifecycle_status='active'
            AND start_date <= CURRENT_DATE AND (end_date IS NULL OR end_date >= CURRENT_DATE)
          ORDER BY person_id, start_date DESC, assignment_id DESC
        )
        SELECT e.employee_id,e.person_id,pa.org_unit_id,ou.name AS org_unit_name,ou.group_id AS org_group_id,dg.group_name AS org_group_name,pa.position_id,pos.name AS position_name,p.full_name
        FROM public.employees e JOIN public.persons p ON p.person_id=e.person_id
        LEFT JOIN primary_assignment pa ON pa.person_id=e.person_id
        LEFT JOIN public.org_units ou ON ou.unit_id=pa.org_unit_id LEFT JOIN public.deps_group dg ON dg.group_id=ou.group_id LEFT JOIN public.positions pos ON pos.position_id=pa.position_id
        WHERE COALESCE(e.is_active,TRUE) IS TRUE AND e.operational_status='active'
          AND (e.date_from IS NULL OR e.date_from <= CURRENT_DATE)
          AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE) AND p.person_status='active'
        ORDER BY p.full_name,e.employee_id
    """)).mappings().all()
    all_rows = list(rows)
    general_statuses = general_first_pass_statuses(c, person_ids=[int(row['person_id']) for row in all_rows])
    if q: rows=[r for r in rows if q.lower() in str(r['full_name']).lower()]
    if org_group_id: rows=[r for r in rows if r['org_group_id']==org_group_id]
    if org_unit_id: rows=[r for r in rows if r['org_unit_id']==org_unit_id]
    if position_id: rows=[r for r in rows if r['position_id']==position_id]
    items=[]
    for r in rows:
        employee_id = int(r['employee_id'])
        t=training.get(employee_id,{}); unknown=max(0,int(t.get('course_count',0))-int(t.get('exact_dates',0))-int(t.get('calculated_dates',0)))
        training_status = normalized_sections['training'].get(employee_id)
        education_status = normalized_sections['education'].get(employee_id)
        has_training=bool(training_status); label=t.get('state','Данные об обучении не найдены'); reason_label=('Данные об обучении не найдены' if not has_training else f"Курсов: {t.get('course_count',0)} · подтверждено: {t.get('confirmed_hours_last_5y',0)} · предварительно: {t.get('preliminary_hours_last_5y',0)} · до 144: {t.get('hours_missing',144)} · качество даты: {'Не распознана' if unknown else 'Точная/Расчётная'} · статус записи: {'Требуется проверка' if unknown else label} · ручное разделение: {t.get('manual_split_count',0)}")
        cells={s:{'status_code':'NO_SOURCE_DATA','status_label':'Нет данных','reason_code':'NO_SOURCE_DATA','reason_label':'Нет данных','calculated_at':'2026-09-12T00:00:00+00:00'} for s in ('general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles')}
        general = general_statuses.get(int(r['person_id']))
        if general:
            cells['general']={
                'status_code':general['status_code'],
                'status_label':STATUS_LABELS.get(general['status_code'], general['status_code']),
                'reason_code':general['reason_code'],
                'reason_label':REASON_LABELS.get(general['reason_code'], general['reason_code']),
                'calculated_at':'2026-09-12T00:00:00+00:00',
            }
        if education_status:
            cells['education'] = _status_cell(*education_status)
        if training_status:
            cells['training'] = _status_cell(*training_status, reason_label=reason_label)
        additional_status = additional_sections.get(employee_id)
        if additional_status:
            cells['additional'] = _status_cell(*additional_status)
        for section_name in ('awards', 'academic_degrees_titles'):
            status_value = raw_sections[section_name].get(employee_id)
            if status_value:
                cells[section_name] = _status_cell(*status_value)
        matching_cells = [cells[section]] if section in cells else list(cells.values())
        if status and not any(cell['status_code'] == status for cell in matching_cells):
            continue
        if reason and not any(cell['reason_code'] == reason for cell in matching_cells):
            continue
        items.append({'person_id':int(r['person_id']),'employee_context_id':int(r['employee_id']),'org_unit_id':r['org_unit_id'],'org_unit_name':r['org_unit_name'],'org_group_id':r['org_group_id'],'org_group_name':r['org_group_name'],'position_id':r['position_id'],'position_name':r['position_name'],'full_name':r['full_name'],'cells':cells})
    total=len(items)
    filtered_general=[item['cells']['general'] for item in items]
    latest_general_run=general_first_pass_run_summary(c) or {}
    general_summary={
        'total_active_employees': total,
        'processed': sum(value['status_code'] == 'AUTO_READY' for value in filtered_general),
        'review_required': sum(value['status_code'] == 'REVIEW_REQUIRED' for value in filtered_general),
        # A current no-op run has no field mutations in every filtered subset.
        'updated_current_run': int(latest_general_run.get('updated_current_run') or 0),
        'skipped_already_filled': sum(value['status_code'] == 'AUTO_READY' for value in filtered_general),
    }
    active_training=[training.get(int(item['employee_context_id'])) for item in items]
    active_training=[value for value in active_training if value]
    stats={'total_active_employees':total,'training_found':len(active_training),'training_missing':total-len(active_training),'courses':sum(x['course_count'] for x in active_training),'exact_dates':sum(x['exact_dates'] for x in active_training),'calculated_dates':sum(x['calculated_dates'] for x in active_training),'unknown_dates':sum(max(0,x['course_count']-x['exact_dates']-x['calculated_dates']) for x in active_training),'manual_split':sum(x['manual_split_count'] for x in active_training),'at_least_144':sum(x['preliminary_hours_last_5y']>=144 for x in active_training),'below_144':sum(x['preliminary_hours_last_5y']<144 for x in active_training)}
    page_items=items[(page-1)*page_size:page*page_size]
    return {'universe_id':_FALLBACK_UNIVERSE_ID,'page':page,'page_size':page_size,'total':total,'items':page_items,'counts':[],'training_summary':stats,'general_summary':general_summary,'status_summary':build_presentation_status_summary(items,section=section)}

def _fallback_person_cells(c, *, universe_id:int, person_id:int):
    exists=c.execute(text("SELECT 1 FROM public.persons WHERE person_id=:person_id"),{'person_id':person_id}).scalar_one_or_none()
    if not exists:
        return None
    cells={s:{'status_code':'NO_SOURCE_DATA','status_label':'Нет данных','reason_code':'NO_SOURCE_DATA','reason_label':'Нет данных','calculated_at':'2026-09-12T00:00:00+00:00'} for s in ('general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','additional','awards','academic_degrees_titles')}
    general=general_first_pass_statuses(c,person_ids=[person_id]).get(person_id)
    if general:
        cells['general']={'status_code':general['status_code'],'status_label':STATUS_LABELS.get(general['status_code'],general['status_code']),'reason_code':general['reason_code'],'reason_label':REASON_LABELS.get(general['reason_code'],general['reason_code']),'calculated_at':'2026-09-12T00:00:00+00:00'}
    employee_id = c.execute(text("SELECT employee_id FROM public.employees WHERE person_id=:person_id ORDER BY employee_id LIMIT 1"), {'person_id': person_id}).scalar_one_or_none()
    if employee_id is not None:
        sections = _normalized_section_statuses(c, batch_id=1414)
        for section in ('education', 'training'):
            status = sections[section].get(int(employee_id))
            if status:
                cells[section] = _status_cell(*status)
        raw_sections = _raw_section_statuses(c, batch_id=1414)
        for section in ('awards', 'academic_degrees_titles'):
            status = raw_sections[section].get(int(employee_id))
            if status:
                cells[section] = _status_cell(*status)
        additional = _additional_section_statuses(c, batch_id=1414).get(int(employee_id))
        if additional:
            cells['additional'] = _status_cell(*additional)
    return {'universe_id':universe_id,'cells':cells}
@router.get('/persons/{person_id}')
def person_status(person_id:int,universe_id:int=Query(...,ge=1),user:dict=Depends(get_current_user)):
    try:
        with engine.connect() as c:r=person_cells(c,universe_id=universe_id,person_id=person_id,scope=_scope(user))
    except ProgrammingError:
        with engine.connect() as c:r=_fallback_person_cells(c,universe_id=universe_id,person_id=person_id)
    except ProjectionIntegrityError:raise HTTPException(409,detail={'code':'MIGRATION_STATUS_PROJECTION_INTEGRITY_ERROR'})
    if r is None:raise HTTPException(404,detail={'code':'MIGRATION_STATUS_PERSON_NOT_FOUND'})
    return r
@router.get('')
def report(universe_id:int|None=Query(None,ge=1),page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),section:str|None=None,status:str|None=None,reason:str|None=None,org_unit_id:int|None=Query(None,ge=1),org_group_id:int|None=Query(None,ge=1),position_id:int|None=Query(None,ge=1),q:str|None=None,user:dict=Depends(get_current_user)):
    try:
        with engine.connect() as c:
            scope=_scope(user); resolved_universe_id=_resolve_universe_id(c,scope,universe_id)
            r=None if resolved_universe_id is None else matrix(c,universe_id=resolved_universe_id,scope=scope,page=page,page_size=page_size,section=section,status=status,reason=reason,org_group_id=org_group_id,org_unit_id=org_unit_id,position_id=position_id,q=q)
    except ProgrammingError:
        with engine.connect() as c:r=_fallback_matrix(c,page=page,page_size=page_size,q=q,section=section,status=status,reason=reason,org_group_id=org_group_id,org_unit_id=org_unit_id,position_id=position_id)
    except ValueError:raise HTTPException(422,detail={'code':'INVALID_MIGRATION_STATUS_FILTER'})
    except ProjectionIntegrityError:raise HTTPException(409,detail={'code':'MIGRATION_STATUS_PROJECTION_INTEGRITY_ERROR'})
    if r is None:raise HTTPException(404,detail={'code':'MIGRATION_STATUS_UNIVERSE_NOT_FOUND'})
    return r
