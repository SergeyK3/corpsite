"""Explicit reviewed server IDs only. Never infer links from job-name similarity."""
import hashlib,json
from pathlib import Path

def read_review(path):
    review=json.loads(Path(path).read_text(encoding='utf8'))
    if review.get('format')!='job-positions-server-link-review-v1':raise ValueError('Unexpected server link review format')
    return review

def plan_server_catalog(rows,review,positions,catalog=(),links=(),*,catalog_planner):
    texts=[{key:row[key] for key in ('job_code','job_nameru','job_namekk','job_namekk_doc')} for row in rows]
    digest=hashlib.sha256(json.dumps(texts,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()
    if len(rows)!=88 or digest!=review['catalog_texts_sha256']:raise ValueError('Approved 88 profession texts differ from reviewed catalog')
    approved={row['position_id']:row for row in review['approved_links']}
    requested={pid:row['job_code'] for row in rows for pid in row['legacy_position_ids']}
    if len(approved)!=len(review['approved_links']) or len(approved)!=review['approved_link_count']:raise ValueError('Duplicate/incorrect reviewed IDs')
    if sum(len(row['legacy_position_ids']) for row in rows)!=len(requested):raise ValueError('Duplicate catalog IDs')
    if requested!={pid:row['job_code'] for pid,row in approved.items()}:raise ValueError('Catalog links differ from explicit reviewed IDs')
    existing={int(row['position_id']):dict(row) for row in positions}
    if len(existing)!=len(positions):raise ValueError('Duplicate factual position IDs')
    name_conflicts=[{'position_id':pid,'expected_name':row['server_name'],'actual_name':existing[pid].get('name'),'job_code':row['job_code']}
                    for pid,row in approved.items() if pid in existing and existing[pid].get('name')!=row['server_name']]
    active=[{**row,'legacy_position_ids':[pid for pid in row['legacy_position_ids'] if pid in existing]} for row in rows]
    plan=catalog_planner(active,positions,catalog,links)
    unreviewed_existing=[dict(link) for link in links if int(link['position_id']) not in approved]
    plan['conflicts'] += [f"Reviewed name changed for ID {row['position_id']}: {row['expected_name']} / {row['actual_name']}" for row in name_conflicts]
    plan['conflicts'] += [f"Existing link ID {row['position_id']} -> {row['job_code']} has no reviewed server mapping (preserved)" for row in unreviewed_existing]
    skipped=[];newly_present=[]
    for row in review['skipped_missing_links']:
        (skipped if row['position_id'] not in existing else newly_present).append(dict(row))
    skipped += [{**row,'reason':'Reviewed ID is now absent; skipped, no historical position created'} for pid,row in approved.items() if pid not in existing]
    plan.update({'original_link_count':review['original_link_count'],'reviewed_link_count':len(approved),'active_link_count':sum(len(row['legacy_position_ids']) for row in active),
                 'skipped_missing_links':sorted(skipped,key=lambda r:r['position_id']),'skipped_missing_ids':sorted(row['position_id'] for row in skipped),
                 'withheld_links':review['withheld_links'],'unreviewed_now_present':newly_present,'name_conflicts':name_conflicts,
                 'unreviewed_existing_links':unreviewed_existing,'server_positions_sha256':review['server_positions_sha256']})
    plan['can_apply']=plan['can_apply'] and not plan['conflicts']
    return plan

def database_plan(conn,rows,review,*,catalog_module):
    positions=conn.execute(catalog_module.text('SELECT position_id,name FROM public.positions ORDER BY position_id')).mappings().all()
    ready=bool(conn.execute(catalog_module.text("SELECT to_regclass('public.job_positions_catalog')")).scalar())
    catalog=conn.execute(catalog_module.text('SELECT * FROM public.job_positions_catalog')).mappings().all() if ready else []
    links=conn.execute(catalog_module.text('SELECT * FROM public.position_job_catalog')).mappings().all() if ready else []
    plan=plan_server_catalog(rows,review,positions,catalog,links,catalog_planner=catalog_module.plan_catalog)
    plan['schema_ready']=ready;plan['can_apply']=plan['can_apply'] and ready
    return plan

def apply_catalog(conn,rows,review,*,catalog_module):
    conn.execute(catalog_module.text('LOCK TABLE public.job_positions_catalog, public.position_job_catalog IN EXCLUSIVE MODE'))
    conn.execute(catalog_module.text('LOCK TABLE public.positions IN SHARE MODE'))
    plan=database_plan(conn,rows,review,catalog_module=catalog_module)
    if not plan['can_apply']:raise ValueError('Server import blocked: inspect reviewed names and existing-link conflicts')
    active=[{key:row[key] for key in catalog_module.FIELDS} for row in plan['mappings']]
    catalog_module.apply_catalog(conn,active)
    return plan
