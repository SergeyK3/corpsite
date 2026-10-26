"""Offline, read-only reconciliation. Emits a proposal; contains no DB/write executor.

Input files contain only dictionary values and migration metadata. Local IDs are
used to decode relationships, never as target identifiers or INSERT values.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path

FIELDS={
    'positions':('name','category','name_kk','document_nominative_ru','document_possessive_kk','translation_status','document_form_status','record_kind'),
    'job_positions_catalog':('job_code','job_nameru','job_namekk','job_namekk_doc'),
    'medical_specialty_groups':('code','name','is_active'),
    'medical_specialties':('code','name','name_kk','is_active'),
}
SCHEMA_FIELDS={'positions':set(FIELDS['positions'])-{'name','category','name_kk'},'medical_specialties':{'name_kk'}}
def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().split())
def normalized_alias(value):
    return re.sub(r'[\W_]+',' ',unicodedata.normalize('NFKC',str(value or '')).casefold()).strip()
def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def position_key(row):return {'name':normalized(row['name']),'category':normalized(row['category'])}
def make_plan(inventory,production,schema,approvals=None):
    source={k:v['rows'] for k,v in inventory['dictionaries'].items()}
    target={k:v['rows'] for k,v in production['dictionaries'].items()}
    columns=defaultdict(set)
    for col in schema['dictionary_columns']:columns[col['table_name']].add(col['column_name'])
    records=[];extras=[]
    source_positions={r['position_id']:r for r in source['positions']}
    target_positions={r['position_id']:r for r in target['positions']}
    source_groups={r['group_id']:r['code'] for r in source['medical_specialty_groups']}
    target_groups={r['group_id']:r['code'] for r in target['medical_specialty_groups']}
    decisions=(approvals or {}).get('position_category_decisions',[])
    decision_keys=[json.dumps(position_key(d['source_key']),sort_keys=True) for d in decisions]
    if len(set(decision_keys))!=len(decision_keys):raise ValueError('Duplicate category approvals')
    def decision_for(row):
        return next((d for d in decisions if position_key(d['source_key'])==position_key(row)),None)
    def effective_position(row):
        decision=decision_for(row)
        return {**row,'category':decision['target_category']} if decision else row
    def matching_positions(row):
        decision=decision_for(row)
        keys=[position_key(effective_position(row))]
        if decision and decision.get('existing_key'):keys.append(position_key(decision['existing_key']))
        # Accept the approved before or after key, but never merge two identities.
        return [r for r in target['positions'] if position_key(r) in keys]
    def existing_position_key(row):
        matches=matching_positions(row)
        if len(matches)==1:return position_key(matches[0])
        decision=decision_for(row)
        return position_key(decision['existing_key']) if decision and decision.get('existing_key') else position_key(effective_position(row))
    def record(table,key,wanted,matches,depends=None):
        entry={'table':table,'key':key,'desired':wanted,'dependencies':depends or [],'status':'MATCH','operation':'SKIP','blockers':[]}
        records.append(entry)
        if len(matches)>1:
            entry.update(status='MANUAL',operation='NONE',reason='Ambiguous semantic key; target rows must be resolved manually')
            return entry
        missing=sorted(set(wanted)-columns[table])
        if missing:entry['blockers'].append({'schema_columns_missing':missing})
        if not matches:
            entry.update(status='ADD',operation='INSERT',before=None)
            return entry
        old={k:matches[0].get(k) for k in wanted if k in columns[table]}
        entry['before']=old;entry['before_fingerprint']=fingerprint(old)
        changes={k:{'before':old.get(k),'after':v,'column_present':k in columns[table]} for k,v in wanted.items() if k not in columns[table] or old.get(k)!=v}
        entry['changes']=changes
        if changes:
            entry.update(status='UPDATE',operation='UPDATE')
            conflicts=[]
            for k,change in changes.items():
                if k in ('name_kk','document_possessive_kk','document_nominative_ru','job_nameru','job_namekk','job_namekk_doc','name') and change['before'] and change['before']!=change['after']:
                    conflicts.append(k)
                if k in ('translation_status','document_form_status') and change['before']=='confirmed' and change['after']!='confirmed':conflicts.append(k)
            if conflicts:entry.update(status='CONFLICT',operation='NONE',reason='Existing nonempty value/confirmed state differs',conflicting_fields=conflicts)
        return entry
    for table,key_fields in [('job_positions_catalog',('job_code',)),('medical_specialty_groups',('code',))]:
        for row in source[table]:
            key={k:row[k] for k in key_fields}
            record(table,key,{k:row.get(k) for k in FIELDS[table]},[r for r in target[table] if all(r.get(k)==v for k,v in key.items())])
    position_entries={}
    for row in source['positions']:
        decision=decision_for(row)
        effective=effective_position(row)
        key=position_key(effective)
        matches=matching_positions(row)
        entry=record('positions',key,{k:effective.get(k) for k in FIELDS['positions']},matches)
        if decision:
            entry.update(approval_id=decision['approval_id'],source_key=position_key(row),preserve_existing_target_identity=True)
            if len(matches)!=1:entry.update(status='MANUAL',operation='NONE',reason='Approved existing identity must resolve to exactly one target; INSERT forbidden')
            if decision.get('existing_key'):
                entry['match_key']=existing_position_key(row)
                entry['post_update_key']=key
                entry['target_identity_guard']={'expected_target_position_id':decision['expected_target_position_id'],'purpose':'Verify the semantically matched target; never assign or copy this ID'}
                if len(matches)==1 and matches[0]['position_id']!=decision['expected_target_position_id']:
                    entry.update(status='CONFLICT',operation='NONE',reason='Semantically matched target differs from owner-approved target ID')
        if sum(position_key(effective_position(s))==key for s in source['positions'])>1:
            entry.update(status='MANUAL',operation='NONE',reason='Ambiguous source position key; do not merge identities')
        same_name=[r for r in target['positions'] if normalized(r['name'])==key['name']]
        if not matches and same_name:entry.update(status='MANUAL',operation='NONE',reason='Same title exists in another category; do not add or recategorize implicitly')
        position_entries[row['position_id']]=entry
    for row in source['medical_specialties']:
        group=source_groups[row['group_id']];key={'group_code':group,'code':row['code']}
        matches=[r for r in target['medical_specialties'] if target_groups[r['group_id']]==group and r['code']==row['code']]
        entry=record('medical_specialties',key,{k:row.get(k) for k in FIELDS['medical_specialties']},matches,[{'table':'medical_specialty_groups','key':{'code':group}}])
        if not matches:
            named=[r for r in target['medical_specialties'] if normalized(r['name'])==normalized(row['name']) or row.get('name_kk') and normalized(r.get('name_kk'))==normalized(row['name_kk'])]
            if named:entry.update(status='MANUAL',operation='NONE',reason='Same bilingual name exists under another stable code; identity review required')
    for row in source['position_job_catalog']:
        pos=source_positions[row['position_id']];pkey=position_key(effective_position(pos))
        matched_ids={r['position_id'] for r in matching_positions(pos)}
        links=[r for r in target['position_job_catalog'] if r['position_id'] in matched_ids]
        # Semantic join is represented explicitly. No source ID is written.
        e={'table':'position_job_catalog','key':{'position':pkey},'desired':{'job_code':row['job_code']},'dependencies':[{'table':'positions','key':pkey},{'table':'job_positions_catalog','key':{'job_code':row['job_code']}}], 'before':{'job_code':links[0]['job_code']} if len(links)==1 else None,'blockers':[]}
        if len(matched_ids)>1 or len(links)>1:e.update(status='MANUAL',operation='NONE',reason='Ambiguous position identity/link')
        elif not links:e.update(status='ADD',operation='INSERT')
        elif links[0]['job_code']==row['job_code']:e.update(status='MATCH',operation='SKIP')
        else:e.update(status='CONFLICT',operation='NONE',reason='Existing position family differs; do not rebind automatically')
        decision=decision_for(pos)
        if decision:
            e['approval_id']=decision['approval_id']
            if row['job_code']!=decision['required_job_code']:e.update(status='CONFLICT',operation='NONE',reason='Source family differs from the approved family')
        records.append(e)
    for row in source['position_aliases']:
        pkey=position_key(effective_position(source_positions[row['position_id']]))
        matches=[r for r in target['position_aliases'] if r['normalized_alias']==row['normalized_alias']]
        e={'table':'position_aliases','key':{'normalized_alias':row['normalized_alias']},'desired':{'alias_text':row['alias_text'],'position':pkey},'dependencies':[{'table':'positions','key':pkey}],'blockers':[]}
        if len(matches)>1:e.update(status='MANUAL',operation='NONE',reason='Ambiguous normalized alias')
        elif not matches:
            # A synonym must not hijack another exact position's title.
            same_title=[r for r in target['positions'] if normalized_alias(r['name'])==row['normalized_alias'] and position_key(r)!=pkey]
            if same_title:e.update(status='CONFLICT',operation='NONE',reason='Alias is another position title')
            else:e.update(status='ADD',operation='INSERT')
        elif matches[0]['position_id'] not in {r['position_id'] for r in matching_positions(source_positions[row['position_id']])}:e.update(status='CONFLICT',operation='NONE',reason='Alias belongs to another position')
        elif matches[0]['alias_text']!=row['alias_text']:e.update(status='UPDATE',operation='UPDATE',before={'alias_text':matches[0]['alias_text'],'position':pkey})
        else:e.update(status='MATCH',operation='SKIP')
        records.append(e)
    # Missing dependencies and existing conflicts are never converted into writes.
    indexed={(e['table'],json.dumps(e['key'],sort_keys=True)):e for e in records}
    for e in records:
        for dependency in e['dependencies']:
            dep=indexed.get((dependency['table'],json.dumps(dependency['key'],sort_keys=True)))
            if dep and dep['status'] in ('CONFLICT','MANUAL'):
                e['blockers'].append({'unresolved_dependency':dependency})
                if e['status'] not in ('CONFLICT','MANUAL'):e.update(status='MANUAL',operation='NONE',reason='Dependency requires manual resolution')
    for table in source:
        for row in target[table]:
            if table=='positions':key=position_key(row);exists=any(existing_position_key(s)==key or position_key(effective_position(s))==key for s in source[table])
            elif table=='job_positions_catalog':key={'job_code':row['job_code']};exists=any(s['job_code']==row['job_code'] for s in source[table])
            elif table=='medical_specialty_groups':key={'code':row['code']};exists=any(s['code']==row['code'] for s in source[table])
            elif table=='medical_specialties':key={'group_code':target_groups[row['group_id']],'code':row['code']};exists=any(source_groups[s['group_id']]==key['group_code'] and s['code']==key['code'] for s in source[table])
            elif table=='position_job_catalog':key={'position':position_key(target_positions[row['position_id']]),'job_code':row['job_code']};exists=any(existing_position_key(source_positions[s['position_id']])==key['position'] and s['job_code']==key['job_code'] for s in source[table])
            else:key={'normalized_alias':row['normalized_alias']};exists=any(s['normalized_alias']==key['normalized_alias'] for s in source[table])
            if not exists:extras.append({'table':table,'key':key,'operation':'KEEP_UNCHANGED'})
    counts={table:dict(Counter(e['status'] for e in records if e['table']==table)) for table in source}
    blockers=[]
    if production['database_revision']!=['poprint001']:blockers.append('Schema is not poprint001; separately approve schema update and re-audit; no stamp')
    if any(e['status'] in ('CONFLICT','MANUAL') for e in records):blockers.append('Resolve every CONFLICT/MANUAL before an addressed apply')
    return {'format':'personnel-dictionary-proposal-v1','executable':False,'source_commit':'60997f57e686a233dcd1f1b4dfb566b3e17dfc9e',
        'source_inventory_fingerprint':fingerprint(inventory),'production_snapshot_fingerprint':fingerprint(production),
        'production_schema_revision':production['database_revision'],'required_schema_revision':'poprint001',
        'global_blockers':blockers,
        'owner_approvals':deepcopy(decisions),
        'summary':counts,'records':records,'production_only_keep':extras,
        'expected_operations':dict(Counter(e['operation'] for e in records)),
        'execution_contract':{'stable_keys_only':True,'generated_ids':'target database only; never source IDs',
            'before_updates':'re-select exactly one row by semantic key; compare all before values and schema revision; reject drift',
            'repeat':'desired row already present => SKIP; do not increment revision on no-op',
            'atomicity':'one transaction after explicit review; dependency order groups/families, positions/specialties, aliases/links',
            'protected':'no writes to employees, assignments, orders, snapshots, templates; retain target-only dictionary rows',
            'rollback':'capture per-row before/after in external release artifact; rollback before commit on any mismatch; after commit restore only if current matches recorded after; delete a newly inserted dictionary row only after checking all inbound references, otherwise manual decision'}}

def update_approved_positions(existing,inventory,production,schema,approvals):
    """Reconcile only approved positions and their links; retain all other audit results."""
    if existing['source_inventory_fingerprint']!=fingerprint(inventory):raise ValueError('Source inventory changed')
    if existing['production_snapshot_fingerprint']!=fingerprint(production):raise ValueError('Production snapshot changed; use a separately approved fresh audit')
    decisions=approvals['position_category_decisions']
    keys=[position_key(d['source_key']) for d in decisions]
    rows=inventory['dictionaries']['positions']['rows']
    chosen=[r for r in rows if position_key(r) in keys]
    if len(chosen)!=len(decisions):raise ValueError('Each approval must identify exactly one source position')
    ids={r['position_id'] for r in chosen}
    focused=deepcopy(inventory)
    for name,table in focused['dictionaries'].items():
        table['rows']=[r for r in table['rows'] if r.get('position_id') in ids] if name in ('positions','position_aliases','position_job_catalog') else []
    codes={r['job_code'] for r in focused['dictionaries']['position_job_catalog']['rows']}
    focused['dictionaries']['job_positions_catalog']['rows']=[r for r in inventory['dictionaries']['job_positions_catalog']['rows'] if r['job_code'] in codes]
    delta=make_plan(focused,production,schema,approvals)
    result=deepcopy(existing)
    approved_names={position_key(r)['name'] for r in chosen}
    def affected(entry):
        return entry['table']=='positions' and entry['key']['name'] in approved_names or entry['table']=='position_job_catalog' and entry['key']['position']['name'] in approved_names or entry['table']=='position_aliases' and entry['desired']['position']['name'] in approved_names
    replacements=[r for r in delta['records'] if affected(r)]
    old=[r for r in result['records'] if affected(r)]
    if len(old)!=len(replacements):raise ValueError('Unexpected affected record count')
    # Match replacements by original semantic key, including the approved category change.
    def replacement_for(entry):
        return next(r for r in replacements if r['table']==entry['table'] and (
            r['table']=='positions' and r['source_key']==entry.get('source_key',entry['key']) or
            r['table']=='position_job_catalog' and r['key']['position']['name']==entry['key']['position']['name'] or
            r['table']=='position_aliases' and r['key']==entry['key']))
    result['records']=[replacement_for(r) if affected(r) else deepcopy(r) for r in existing['records']]
    resolved_positions=[r for r in replacements if r['table']=='positions' and r['status'] not in ('MANUAL','CONFLICT')]
    resolved_keys=[r.get('match_key',r['key']) for r in resolved_positions]
    preserved_links=[{'position':pos.get('match_key',pos['key']),'job_code':link['desired']['job_code']}
        for pos in resolved_positions for link in replacements if link['table']=='position_job_catalog' and link['key']['position']==pos['key'] and link['status']=='MATCH']
    result['production_only_keep']=[r for r in result['production_only_keep'] if not (
        r['table']=='positions' and r['key'] in resolved_keys or r['table']=='position_job_catalog' and r['key'] in preserved_links)]
    result['summary']={table:dict(Counter(r['status'] for r in result['records'] if r['table']==table)) for table in existing['summary']}
    result['expected_operations']=dict(Counter(r['operation'] for r in result['records']))
    result['owner_approvals']=deepcopy(decisions)
    if not any(r['status'] in ('CONFLICT','MANUAL') for r in result['records']):
        result['global_blockers']=[b for b in result['global_blockers'] if b!='Resolve every CONFLICT/MANUAL before an addressed apply']
    result['planning_update']={'mode':'addressed_owner_decision','source_positions_rechecked':len(chosen),'source_records_rechecked':len(replacements),'other_records_retained':len(result['records'])-len(replacements),'production_requeried':False}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--production',type=Path,required=True);p.add_argument('--schema',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--approvals',type=Path);p.add_argument('--existing-plan',type=Path)
    args=p.parse_args();read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    approval=read(args.approvals) if args.approvals else None
    if args.existing_plan:
        if approval is None:p.error('--existing-plan requires --approvals')
        result=update_approved_positions(read(args.existing_plan),read(args.inventory),read(args.production),read(args.schema),approval)
    else:result=make_plan(read(args.inventory),read(args.production),read(args.schema),approval)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':result['summary'],'operations':result['expected_operations'],'target_only_keep':len(result['production_only_keep'])},ensure_ascii=True))
if __name__=='__main__':main()
