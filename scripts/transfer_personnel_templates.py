"""Addressed, transactional template transfer. Export/plan never write the DB."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
try:
    from scripts.personnel_template_transfer_snapshot import snapshot
except ModuleNotFoundError:
    from personnel_template_transfer_snapshot import snapshot

COMMIT = '181e750ec9b9f945db4ad28323302edc25045892'
SELECTION = {4:(6,1,'PUBLISHED'),9:(33,2,'PUBLISHED'),10:(16,2,'PUBLISHED'),
             23:(38,3,'PUBLISHED'),24:(36,1,'DRAFT'),28:(44,4,'PUBLISHED')}
FIELDS = ('title_ru','title_kk','preamble_ru','preamble_kk','body_template_ru','body_template_kk','basis_template_ru','basis_template_kk')
TOKEN = re.compile(r'\{\{\s*([\w.]+)\s*\}\}')

class TransferError(ValueError):pass

def require(condition,message):
    if not condition:raise TransferError(message)

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode('utf8')).hexdigest()

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    temporary.replace(path)

def contract(code,values):
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    from app.services.personnel_order_template_validation import validate_template_texts
    from app.services.personnel_order_replacement_contract import variant,optional_placement
    from app.services.personnel_order_service_area_contract import enabled
    validate_template_texts(code,values)
    spec=get_personnel_order_template_spec(code)
    bindings={field:TOKEN.findall(values[field]) for field in FIELDS}
    require({token for tokens in bindings.values() for token in tokens}<=set(spec.allowed_variables),'Unsupported variable binding')
    return {'allowed_variables':list(spec.allowed_variables),
            'required_variables':{field:list(tokens) for field,tokens in spec.required_variables.items()},
            'field_bindings':bindings,
            'capabilities':{'replacement_mode':variant(values) if code=='CONCURRENT_DUTY_START' else None,
                            'replacement_optional_placement':optional_placement(values) if code=='CONCURRENT_DUTY_START' else False,
                            'service_area_allowance':enabled(values) if code=='CONCURRENT_DUTY_START' else False,
                            'simple_allowance':code=='SUPPLEMENTARY_PAY'}}

def export_bundle(state):
    identities={t['template_id']:t for t in state['templates']}
    entries=[]
    for tid,(vid,number,status) in SELECTION.items():
        t=identities.get(tid);require(t is not None,f'Local template {tid} not found')
        versions=[v for v in state['versions'] if v['template_id']==tid]
        selected=next((v for v in versions if v['template_version_id']==vid),None)
        require(selected is not None,f'Local version {vid} missing from template {tid}')
        require((selected['version_number'],selected['status'])==(number,status),f'Local template {tid}: current version/status differs; review inventory')
        require(len([v for v in versions if v['status']==status])==1,f'Multiple active local versions for {tid}')
        require(selected['item_type_code']==t['item_type_code'],'Local type mismatch')
        values={field:selected[field] for field in FIELDS}
        identity={key:t[key] for key in ('item_type_code','name_ru','name_kk','is_default')}
        entry={'key':str(tid),'source':{'template_id':tid,'template_version_id':vid,'version_number':number},
               'identity':identity,'version':{'status':status,'based_on_built_in':selected['based_on_built_in'],'texts':values},
               'contract':contract(t['item_type_code'],values)}
        entry['sha256']=digest(entry)
        entries.append(entry)
    data={'format':'personnel-template-transfer-v1','implementation_commit':COMMIT,'entries':entries}
    data['sha256']=digest(data)
    return data

def validate_bundle(bundle):
    require(set(bundle)=={'format','implementation_commit','entries','sha256'},'Unexpected bundle fields (only templates may be transferred)')
    require(bundle.get('format')=='personnel-template-transfer-v1','Unsupported bundle format')
    require(bundle.get('implementation_commit')==COMMIT,'Wrong implementation commit')
    require(bundle.get('sha256')==digest({k:v for k,v in bundle.items() if k!='sha256'}),'Bundle checksum mismatch')
    keys=[]
    for e in bundle['entries']:
        require(set(e)=={'key','source','identity','version','contract','sha256'},'Unexpected entry fields')
        require(e['sha256']==digest({k:v for k,v in e.items() if k!='sha256'}),'Entry checksum mismatch')
        require(set(e['identity'])=={'item_type_code','name_ru','name_kk','is_default'},'Unexpected identity fields')
        require(set(e['version'])=={'status','based_on_built_in','texts'},'Unexpected version fields')
        require(set(e['source'])=={'template_id','template_version_id','version_number'},'Unexpected source fields')
        require(e['key']==str(e['source']['template_id']) and e['source']['template_id'] in SELECTION,'Wrong source identity')
        require((e['source']['template_version_id'],e['source']['version_number'],e['version']['status'])==SELECTION[e['source']['template_id']],'Source selection/status differs from the reviewed six versions')
        require(e['version']['status'] in ('DRAFT','PUBLISHED'),'Unsupported status')
        require(set(e['version']['texts'])==set(FIELDS),'Exactly eight template text fields required')
        require(all(isinstance(e['identity'][key],str) and e['identity'][key].strip() for key in ('item_type_code','name_ru','name_kk')),'Blank template name/code')
        require(isinstance(e['identity']['is_default'],bool) and isinstance(e['version']['based_on_built_in'],bool),'Invalid settings')
        require(e['contract']==contract(e['identity']['item_type_code'],e['version']['texts']),'Installed code has a different variable contract; update/reconcile code first')
        keys.append(e['key'])
    require(len(keys)==6 and set(keys)==set(map(str,SELECTION)),'Expected exactly the six addressed templates')

def version_equal(v,e):
    return v['based_on_built_in']==e['version']['based_on_built_in'] and all(v[field]==e['version']['texts'][field] for field in FIELDS)

def candidate(t,versions):
    return {'template_id':t['template_id'],'code':t['item_type_code'],'name_ru':t['name_ru'],'name_kk':t['name_kk'],
            'is_default':t['is_default'],'versions':[{'id':v['template_version_id'],'number':v['version_number'],'status':v['status'],'revision':v['revision'],'based_on_built_in':v['based_on_built_in'],
              'content_sha256':digest({field:v[field] for field in FIELDS})} for v in versions if v['template_id']==t['template_id']]}

def prepare_plan(bundle,state,mapping=None):
    validate_bundle(bundle)
    require('template_id' in state['schema']['columns'].get('personnel_order_template_versions',[]),'Independent template schema is missing')
    mapping=mapping or {};require(set(mapping)<=set(e['key'] for e in bundle['entries']),'Unknown mapping key')
    rows=[];errors=[];claimed=set()
    for e in bundle['entries']:
        ident=e['identity'];same=[t for t in state['templates'] if t['item_type_code']==ident['item_type_code']]
        exact=[t for t in same if all(t[k]==ident[k] for k in ('name_ru','name_kk','is_default'))]
        content=[t for t in same if t['is_default']==ident['is_default'] and any(v['template_id']==t['template_id'] and version_equal(v,e) for v in state['versions'])]
        near=[t for t in same if t['name_ru']==ident['name_ru'] or t['name_kk']==ident['name_kk'] or (ident['is_default'] and t['is_default'])]
        # Shared KK captions do not merge identities whose full bilingual names
        # already match another distinct source entry in this same reviewed bundle.
        other_identities=[other['identity'] for other in bundle['entries'] if other['key']!=e['key']]
        near=[t for t in near if not any(all(t[k]==other[k] for k in ('item_type_code','name_ru','name_kk','is_default')) for other in other_identities)]
        selected=None;method=None
        if e['key'] in mapping:
            explicit=mapping[e['key']]
            matches=[t for t in same if t['template_id']==explicit['server_template_id']]
            require(len(matches)==1,'Explicit mapping has a wrong server type/id')
            selected=matches[0]
            require(explicit['candidate_sha256']==digest(candidate(selected,state['versions'])),'Explicit mapping evidence is stale')
            method='explicit-reviewed-code-names-content'
        elif len(exact)==1:
            selected=exact[0];method='exact-code-bilingual-names-settings'
        elif not exact and len(content)==1 and not near:
            # Content alone can suggest a rename, but must never select it silently.
            errors.append({'key':e['key'],'reason':'Names differ; explicit reviewed mapping required','candidates':[candidate(content[0],state['versions'])]})
            continue
        elif exact or near or content:
            involved={t['template_id']:t for t in exact+near+content}
            errors.append({'key':e['key'],'reason':'Ambiguous or partial match; explicit reviewed mapping required',
                           'candidates':[candidate(t,state['versions']) for t in involved.values()]})
            continue
        if selected:
            require(selected['is_default']==ident['is_default'],'Default setting differs; resolve it before transfer')
            require(selected['template_id'] not in claimed,'Two independent local templates would be merged')
            claimed.add(selected['template_id'])
        vs=[v for v in state['versions'] if selected and v['template_id']==selected['template_id']]
        status=e['version']['status'];active=[v for v in vs if v['status']==status]
        require(len(active)<=1,'Target has multiple active versions')
        equal=bool(active and version_equal(active[0],e))
        rename=bool(selected and any(selected[k]!=ident[k] for k in ('name_ru','name_kk')))
        action='CREATE' if selected is None else 'NO_CHANGE' if equal and not rename else 'UPDATE'
        rows.append({'key':e['key'],'local':e['source'],'code':ident['item_type_code'],'name_ru':ident['name_ru'],'name_kk':ident['name_kk'],
                     'server_template_id':selected['template_id'] if selected else None,
                     'server_current_versions':[{'id':v['template_version_id'],'number':v['version_number'],'status':v['status'],
                                                 'references':state['references'].get(str(v['template_version_id']),{})} for v in vs if v['status'] in ('DRAFT','PUBLISHED')],
                     'action':action,'status':status,'match_method':method or 'no-code-name-content-match',
                     'create_version':not equal,'new_version_number':max((v['version_number'] for v in vs),default=0)+1 if not equal else active[0]['version_number'],
                     'archive_version_ids':[v['template_version_id'] for v in active] if not equal else [],
                     'retained_other_active_versions':[v['template_version_id'] for v in vs if v['status'] in ('DRAFT','PUBLISHED') and v['status']!=status]})
    payload={'format':'personnel-template-plan-v1','bundle_sha256':bundle['sha256'],
             'target_sha256':digest({k:v for k,v in state.items() if k!='code'}),'rows':rows,'ambiguities':errors,'mapping':mapping,'ready':not errors}
    payload['sha256']=digest(payload)
    return payload

def apply_plan(conn,bundle,reviewed,actor_login,backup_path,receipt_path):
    require(reviewed.get('sha256')==digest({k:v for k,v in reviewed.items() if k!='sha256'}),'Plan checksum mismatch')
    require(reviewed.get('ready'),'Plan has unresolved ambiguities')
    conn.execute(text("SET LOCAL lock_timeout='10s'"))
    conn.execute(text('LOCK TABLE public.personnel_order_templates, public.personnel_order_template_versions IN SHARE ROW EXCLUSIVE MODE'))
    before=snapshot(conn)
    current=prepare_plan(bundle,before,reviewed.get('mapping'))
    require(current['sha256']==reviewed['sha256'],'Server state changed since preview; regenerate/review the plan')
    actor=conn.execute(text('SELECT user_id FROM public.users WHERE login=:login AND is_active IS TRUE'),{'login':actor_login}).scalar_one_or_none()
    require(actor is not None,'Active server actor login not found')
    affected={r['server_template_id'] for r in reviewed['rows'] if r['server_template_id'] is not None and r['action']!='NO_CHANGE'}
    backup={'format':'personnel-template-backup-v1','bundle_sha256':bundle['sha256'],'plan_sha256':reviewed['sha256'],
            'templates':[t for t in before['templates'] if t['template_id'] in affected],
            'versions':[v for v in before['versions'] if v['template_id'] in affected]}
    backup['sha256']=digest(backup)
    require(not Path(backup_path).exists() and not Path(receipt_path).exists(),'Backup/receipt path already exists; use fresh files')
    write_json(backup_path,backup)  # Fail before writes if backup cannot be saved.
    entries={e['key']:e for e in bundle['entries']};created_templates=[];created_versions=[];changes=[]
    for row in reviewed['rows']:
        e=entries[row['key']];ident=e['identity'];tid=row['server_template_id'];vid=None
        if row['action']=='CREATE':
            tid=conn.execute(text('''INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,is_default,created_by_user_id)
              VALUES(:item_type_code,:name_ru,:name_kk,:is_default,:actor) RETURNING template_id'''),{**ident,'actor':actor}).scalar_one()
            created_templates.append(tid)
        elif row['action']=='UPDATE':
            conn.execute(text('UPDATE public.personnel_order_templates SET name_ru=:ru,name_kk=:kk WHERE template_id=:id'),{'id':tid,'ru':ident['name_ru'],'kk':ident['name_kk']})
        if row['create_version']:
            for old in row['archive_version_ids']:
                conn.execute(text("UPDATE public.personnel_order_template_versions SET status='ARCHIVED',updated_at=now() WHERE template_version_id=:id"),{'id':old})
            published=e['version']['status']=='PUBLISHED'
            vid=conn.execute(text('''INSERT INTO public.personnel_order_template_versions(template_id,item_type_code,version_number,status,
              title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk,
              based_on_built_in,created_by_user_id,updated_by_user_id,published_at,published_by_user_id)
              VALUES(:template,:code,:number,:status,:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,
              :basis_template_ru,:basis_template_kk,:built_in,:actor,:actor,CASE WHEN :published THEN now() ELSE NULL END,
              CASE WHEN :published THEN :actor ELSE NULL END) RETURNING template_version_id'''),
              {**e['version']['texts'],'template':tid,'code':ident['item_type_code'],'number':row['new_version_number'],
               'status':e['version']['status'],'built_in':e['version']['based_on_built_in'],'actor':actor,'published':published}).scalar_one()
            created_versions.append(vid)
        else:
            vid=conn.execute(text('SELECT template_version_id FROM public.personnel_order_template_versions WHERE template_id=:id AND status=:s'),{'id':tid,'s':row['status']}).scalar_one()
        changes.append({'key':row['key'],'action':row['action'],'server_template_id':tid,'server_version_id':vid,'status':row['status']})
    after=snapshot(conn)
    for old in before['versions']:
        new=next(v for v in after['versions'] if v['template_version_id']==old['template_version_id'])
        require(all(new[k]==old[k] for k in old if k not in ('status','updated_at')),'Historical version contents changed')
    require(after['references']==before['references'],'Order/template application references changed')
    repeat_mapping={key:{'server_template_id':reviewed['mapping'][key]['server_template_id'],
                         'candidate_sha256':digest(candidate(next(t for t in after['templates'] if t['template_id']==reviewed['mapping'][key]['server_template_id']),after['versions']))}
                    for key in reviewed.get('mapping',{})}
    repeated=prepare_plan(bundle,after,repeat_mapping)
    require(repeated['ready'] and all(r['action']=='NO_CHANGE' for r in repeated['rows']),'Import is not idempotent')
    receipt={'format':'personnel-template-receipt-v1','backup_sha256':backup['sha256'],'bundle_sha256':bundle['sha256'],
             'created_templates':created_templates,'created_versions':created_versions,'changes':changes,'repeat_mapping':repeat_mapping,
             'post_templates':[t for t in after['templates'] if t['template_id'] in affected|set(created_templates)],
             'post_versions':[v for v in after['versions'] if v['template_id'] in affected|set(created_templates)]}
    receipt['sha256']=digest(receipt)
    write_json(receipt_path,receipt)  # File failure still rolls back the transaction.
    return receipt

def rollback(conn,backup,receipt,apply=False):
    require(backup['sha256']==digest({k:v for k,v in backup.items() if k!='sha256'}),'Backup checksum mismatch')
    require(receipt['sha256']==digest({k:v for k,v in receipt.items() if k!='sha256'}),'Receipt checksum mismatch')
    require(backup['sha256']==receipt['backup_sha256'],'Wrong backup/receipt pair')
    if apply:conn.execute(text('LOCK TABLE public.personnel_order_templates, public.personnel_order_template_versions IN SHARE ROW EXCLUSIVE MODE'))
    state=snapshot(conn);ids={t['template_id'] for t in receipt['post_templates']}
    require([t for t in state['templates'] if t['template_id'] in ids]==receipt['post_templates'],'Affected identities changed after import; refuse rollback')
    require([v for v in state['versions'] if v['template_id'] in ids]==receipt['post_versions'],'Affected versions changed after import; refuse rollback')
    for vid in receipt['created_versions']:
        require(not any(state['references'].get(str(vid),{}).values()),f'Imported version {vid} is already used by an order; refuse destructive rollback')
        require(not conn.execute(text('SELECT 1 FROM public.personnel_order_templates WHERE copied_from_template_version_id=:id'),{'id':vid}).first(),'Imported version is used as copy provenance')
    if apply:
        for vid in receipt['created_versions']:conn.execute(text('DELETE FROM public.personnel_order_template_versions WHERE template_version_id=:id'),{'id':vid})
        for v in backup['versions']:
            now=next(row for row in state['versions'] if row['template_version_id']==v['template_version_id'])
            if now['status']!=v['status'] or now['updated_at']!=v['updated_at']:
                conn.execute(text('UPDATE public.personnel_order_template_versions SET status=:s,updated_at=CAST(:updated AS timestamptz) WHERE template_version_id=:id'),{'s':v['status'],'updated':v['updated_at'],'id':v['template_version_id']})
        for t in backup['templates']:
            conn.execute(text('UPDATE public.personnel_order_templates SET name_ru=:ru,name_kk=:kk WHERE template_id=:id'),{'ru':t['name_ru'],'kk':t['name_kk'],'id':t['template_id']})
        for tid in receipt['created_templates']:conn.execute(text('DELETE FROM public.personnel_order_templates WHERE template_id=:id'),{'id':tid})
    return {'restore_ready':True,'applied':apply,'templates':len(ids),'versions_to_remove':len(receipt['created_versions'])}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    ex=sub.add_parser('export');ex.add_argument('--output',type=Path,required=True)
    pl=sub.add_parser('plan');pl.add_argument('--bundle',type=Path,required=True);pl.add_argument('--snapshot',type=Path);pl.add_argument('--mapping',type=Path);pl.add_argument('--output',type=Path,required=True)
    ap=sub.add_parser('apply');ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--actor-login',required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True)
    rb=sub.add_parser('restore');rb.add_argument('--backup',type=Path,required=True);rb.add_argument('--receipt',type=Path,required=True);rb.add_argument('--apply',action='store_true')
    args=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding='utf8'))
    if args.command=='plan' and args.snapshot:
        result=prepare_plan(read(args.bundle),read(args.snapshot),read(args.mapping) if args.mapping else None)
        write_json(args.output,result);print(json.dumps({'ready':result['ready'],'rows':result['rows'],'ambiguities':result['ambiguities']},ensure_ascii=True));return
    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    import os
    load_dotenv('.env');url=make_url(os.environ['DATABASE_URL'])
    require(url.host in ('localhost','127.0.0.1','::1'),'Only loopback DB connections are accepted; use SSH for remote inventory')
    if args.command=='export':require(url.database=='corpsite','Export must read local corpsite')
    if args.command=='apply':
        require(subprocess.run(['git','merge-base','--is-ancestor',COMMIT,'HEAD'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0,'Code update to 181e750e is required before import')
    engine=create_engine(url,hide_parameters=True)
    with engine.begin() as conn:
        if args.command in ('export','plan') or (args.command=='restore' and not args.apply):conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if args.command=='export':
            result=export_bundle(snapshot(conn));require(not args.output.exists(),'Export path already exists');write_json(args.output,result)
        elif args.command=='plan':
            result=prepare_plan(read(args.bundle),snapshot(conn),read(args.mapping) if args.mapping else None);write_json(args.output,result)
        elif args.command=='apply':result=apply_plan(conn,read(args.bundle),read(args.plan),args.actor_login,args.backup,args.receipt)
        else:result=rollback(conn,read(args.backup),read(args.receipt),apply=args.apply)
    print(json.dumps({'command':args.command,'sha256':result.get('sha256'),'ready':result.get('ready'),'changes':result.get('changes'),'restore':result if args.command=='restore' else None},ensure_ascii=True))

if __name__=='__main__':
    try:main()
    except TransferError as exc:raise SystemExit('STOP: '+str(exc))
    except Exception as exc:raise SystemExit('STOP: '+type(exc).__name__+'; transaction aborted (inspect locally, no credentials printed)')
