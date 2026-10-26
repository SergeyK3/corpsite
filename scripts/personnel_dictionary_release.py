"""Addressed dictionary release: snapshot/plan, dry-run by default, explicit apply.

Only six allowlisted dictionaries can be written. Production backup stays on VPS.
No employee/order/template contents are exported; protected rows are hashed in SQL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import create_engine,text
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.plan_personnel_dictionary_transfer import make_plan,position_key,fingerprint

TABLES=('job_positions_catalog','medical_specialty_groups','positions','medical_specialties','position_job_catalog','position_aliases')
IDS={'positions':'position_id','medical_specialties':'medical_specialty_id','medical_specialty_groups':'group_id','position_aliases':'alias_id'}
POLICY='posdir001:forms-needs-review:v2'


def read_state(conn):
    conn.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
    state={'format':'personnel-dictionary-target-v2','time_utc':datetime.now(timezone.utc).isoformat(),
           'database_name':conn.exec_driver_sql('SELECT current_database()').scalar(),
           'database_revision':list(conn.execute(text('SELECT version_num FROM public.alembic_version ORDER BY version_num')).scalars()),
           'policy_receipt':conn.execute(text("SELECT obj_description(to_regclass('public.position_directory'),'pg_class')")).scalar(),
           'dictionary_columns':[dict(r) for r in conn.execute(text("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")).mappings()],
           'dictionaries':{}}
    for table in TABLES:
        rows=list(conn.exec_driver_sql(f'SELECT to_jsonb(t) FROM public.{table} t ORDER BY to_jsonb(t)::text').scalars())
        state['dictionaries'][table]={'rows':rows,'count':len(rows)}
    return state


def prepare_plan(inventory,state,approvals):
    result=make_plan(inventory,state,state,approvals)
    result['target_data_fingerprint']=fingerprint(state['dictionaries'])
    result['approval_fingerprint']=fingerprint(approvals)
    result['target_database']=state['database_name']
    if state.get('policy_receipt')!=POLICY:result['global_blockers'].append('Position review policy v2 is not installed')
    return result


def protected_hashes(conn):
    tables=list(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars())
    result={}
    for table in tables:
        if table in TABLES:continue
        if not re.fullmatch(r'[a-z_][a-z0-9_]*',table):raise RuntimeError('Unexpected protected table identifier')
        # Only counts/digests leave the DB; never fetch personnel JSON into Python.
        row=conn.exec_driver_sql(f"SELECT count(*) AS count,md5(COALESCE(string_agg(h,'|' ORDER BY h),'')) AS digest FROM (SELECT md5(to_jsonb(t)::text) h FROM public.{table} t) rows").mappings().one()
        result[table]=dict(row)
    return result


def resolve(conn,table,key):
    if table not in TABLES:raise RuntimeError('Non-dictionary write refused')
    rows=list(conn.exec_driver_sql(f'SELECT to_jsonb(t) FROM public.{table} t').scalars())
    if table=='positions':matched=[r for r in rows if position_key(r)==key]
    elif table=='medical_specialties':
        groups={r['group_id']:r['code'] for r in conn.exec_driver_sql('SELECT to_jsonb(t) FROM public.medical_specialty_groups t').scalars()}
        matched=[r for r in rows if r['code']==key['code'] and groups[r['group_id']]==key['group_code']]
    elif table=='position_job_catalog':
        position=resolve(conn,'positions',key['position']);matched=[r for r in rows if position and r['position_id']==position['position_id']]
    elif table=='position_aliases':matched=[r for r in rows if r['normalized_alias']==key['normalized_alias']]
    else:matched=[r for r in rows if all(r.get(k)==v for k,v in key.items())]
    if len(matched)>1:raise RuntimeError('Semantic target key is ambiguous')
    return matched[0] if matched else None


def apply_approved(conn,plan,inventory,approvals,*,execute=False,after_write=None):
    state=read_state(conn)
    if state['database_revision']!=['poprint001'] or state['policy_receipt']!=POLICY:
        raise RuntimeError('Canonical head/policy mismatch; no stamp or implicit migration')
    if plan.get('review_policy')!='auto_needs_review' or plan.get('format')!='personnel-dictionary-proposal-v2':
        raise RuntimeError('Historical/pre-review-policy plans cannot be applied')
    if plan.get('target_database')!=state['database_name']:
        raise RuntimeError('Plan belongs to another database; test plans cannot be applied to production')
    if plan['source_inventory_fingerprint']!=fingerprint(inventory) or plan['approval_fingerprint']!=fingerprint(approvals):
        raise RuntimeError('Inventory or owner approvals changed')
    if execute:
        conn.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        for name in ('position_directory_write','medical_specialties_write'):
            conn.execute(text('SELECT pg_advisory_xact_lock(hashtext(:name))'),{'name':name})
        conn.exec_driver_sql('LOCK TABLE '+','.join('public.'+t for t in TABLES)+' IN SHARE ROW EXCLUSIVE MODE')
        state=read_state(conn)
    current=prepare_plan(inventory,state,approvals)
    if current['global_blockers']:raise RuntimeError('Unresolved plan blockers: '+str(current['global_blockers']))
    # Repeating the same approved package after success is a read-only no-op.
    if all(r['operation']=='SKIP' for r in current['records']):
        return {'applied':False,'already_applied':True,'operations':{'SKIP':len(current['records'])}}
    if fingerprint(state['dictionaries'])!=plan['target_data_fingerprint'] or current['records']!=plan['records']:
        raise RuntimeError('Target drift since plan review; recalculate and approve a new plan')
    if not execute:return {'applied':False,'already_applied':False,'operations':current['expected_operations']}
    before=protected_hashes(conn);journal=[]
    for table in TABLES:
        for record in plan['records']:
            if record['table']!=table or record['operation']=='SKIP':continue
            if record['operation'] not in ('INSERT','UPDATE'):raise RuntimeError('Unapproved operation')
            lookup=record.get('match_key',record['key'])
            previous=resolve(conn,table,lookup)
            if record.get('target_identity_guard') and (previous is None or previous['position_id']!=record['target_identity_guard']['expected_target_position_id']):
                raise RuntimeError('Approved target ID does not match semantic lookup')
            wanted=dict(record['desired'])
            if table=='medical_specialties':
                group=resolve(conn,'medical_specialty_groups',{'code':record['key']['group_code']})
                if group is None:raise RuntimeError('Specialty group not found')
                wanted['group_id']=group['group_id']
            elif table in ('position_job_catalog','position_aliases'):
                pkey=record['key']['position'] if table=='position_job_catalog' else wanted.pop('position')
                position=resolve(conn,'positions',pkey)
                if position is None:raise RuntimeError('Position dependency not found')
                wanted['position_id']=position['position_id']
                if table=='position_aliases':wanted['normalized_alias']=record['key']['normalized_alias']
            if table=='positions' and any(k in wanted for k in ('position_id','revision')):raise RuntimeError('Source IDs/revisions refused')
            if any(not re.fullmatch(r'[a-z_]+',k) for k in wanted):raise RuntimeError('Unexpected column name')
            if record['operation']=='INSERT':
                if previous is not None:raise RuntimeError('INSERT target already exists')
                keys=list(wanted)
                statement=f'INSERT INTO public.{table} ('+','.join(keys)+') VALUES ('+','.join(':'+k for k in keys)+') RETURNING *'
                changed=dict(conn.execute(text(statement),wanted).mappings().one())
            else:
                if previous is None:raise RuntimeError('UPDATE target is missing')
                identity=IDS.get(table)
                if identity is None:raise RuntimeError('Unsupported UPDATE identity')
                assignments=','.join(k+'=:'+k for k in wanted)
                if table=='positions':assignments+=',revision=revision+1'
                changed=dict(conn.execute(text(f'UPDATE public.{table} SET {assignments} WHERE {identity}=:_target RETURNING *'),{**wanted,'_target':previous[identity]}).mappings().one())
            journal.append({'table':table,'key':record['key'],'operation':record['operation'],'before':previous,'after':changed})
            if after_write:after_write(len(journal))
    verified=prepare_plan(inventory,read_state(conn),approvals)
    if any(r['operation']!='SKIP' for r in verified['records']):raise RuntimeError('Post-transfer reconciliation failed')
    after=protected_hashes(conn)
    if before!=after:raise RuntimeError('Protected employee/order/template data changed; rollback required')
    return {'applied':True,'already_applied':False,'operations':plan['expected_operations'],'journal':journal,
            'protected_tables_verified':len(before),'protected_before':before,'protected_after':after}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('snapshot','plan','apply'))
    parser.add_argument('--inventory',type=Path);parser.add_argument('--approvals',type=Path)
    parser.add_argument('--snapshot',type=Path);parser.add_argument('--plan',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--approve-plan-sha256')
    args=parser.parse_args();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    os.umask(0o077)
    if args.action=='plan':result=prepare_plan(read(args.inventory),read(args.snapshot),read(args.approvals))
    else:
        from dotenv import dotenv_values
        root=Path(__file__).resolve().parents[1]
        url=os.environ.get('DATABASE_URL') or dotenv_values(root/'.env').get('DATABASE_URL')
        if not url:parser.error('DATABASE_URL unavailable')
        if args.apply:
            if args.action!='apply' or args.approve_plan_sha256!=hashlib.sha256(args.plan.read_bytes()).hexdigest():
                parser.error('--apply requires the SHA256 of the explicitly approved plan')
            if args.output.exists():parser.error('Journal already exists; use a new path and retain the original before images')
        options='' if args.apply else '-c default_transaction_read_only=on'
        db=create_engine(url,hide_parameters=True,connect_args={'options':options})
        try:
            with db.begin() as conn:
                conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'+('' if args.apply else ', READ ONLY'))
                result=read_state(conn) if args.action=='snapshot' else apply_approved(conn,read(args.plan),read(args.inventory),read(args.approvals),execute=args.apply)
                if args.apply:
                    # Persist rollback evidence before COMMIT; a failed write
                    # must roll back the DB transaction, not lose the before images.
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    pending={**result,'transaction_status':'pending_commit'}
                    with args.output.open('x',encoding='utf-8') as stream:
                        json.dump(pending,stream,ensure_ascii=False,indent=2,default=str)
                        stream.flush();os.fsync(stream.fileno())
            if args.apply:result['transaction_status']='committed'
        finally:db.dispose()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_name(args.output.name+'.tmp.'+uuid4().hex)
    with temporary.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,default=str)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,args.output)
    print(json.dumps({k:v for k,v in result.items() if k in ('applied','already_applied','operations','protected_tables_verified','expected_operations','global_blockers')}))


if __name__=='__main__':main()
