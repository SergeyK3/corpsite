"""Read-only schema/data/owner/ACL snapshots for public and staging."""
import hashlib
from sqlalchemy import text

SUPPORTED_SCHEMAS={'public','staging'}
STAGING_TABLES={'org_sync_code_map','stg_employees_local','stg_org_units_local'}

def schema_state(conn,schema,*,include_rows=True):
    if schema not in SUPPORTED_SCHEMAS:raise ValueError('Unsupported schema')
    params={'schema':schema}
    namespace=conn.execute(text("SELECT nspname,pg_get_userbyid(nspowner) AS owner,obj_description(oid,'pg_namespace') AS comment FROM pg_namespace WHERE nspname=:schema"),params).mappings().first()
    if namespace is None:return None
    queries={
      'columns':"SELECT table_name,column_name,ordinal_position,column_default,is_nullable,data_type,udt_schema,udt_name,character_maximum_length,numeric_precision,numeric_scale,datetime_precision,collation_schema,collation_name,is_identity,identity_generation,identity_start,identity_increment,identity_minimum,identity_maximum,identity_cycle,is_generated,generation_expression FROM information_schema.columns WHERE table_schema=:schema ORDER BY table_name,ordinal_position",
      'relations':"SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity,c.relforcerowsecurity,obj_description(c.oid,'pg_class') AS comment,CASE WHEN c.relkind IN ('v','m') THEN pg_get_viewdef(c.oid,true) END AS view_definition FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relkind IN ('r','p','v','m','S','f') ORDER BY c.relname",
      'constraints':"SELECT c.relname,co.conname,co.contype,co.convalidated,pg_get_constraintdef(co.oid) AS definition FROM pg_constraint co JOIN pg_class c ON c.oid=co.conrelid JOIN pg_namespace n ON n.oid=co.connamespace WHERE n.nspname=:schema ORDER BY c.relname,co.conname",
      'indexes':"SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=:schema ORDER BY tablename,indexname",
      'triggers':"SELECT c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
      'policies':"SELECT tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=:schema ORDER BY tablename,policyname",
      'functions':"SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_userbyid(p.proowner) AS owner,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=:schema AND p.prokind IN ('f','p') ORDER BY p.proname,arguments",
      'types':"SELECT t.typname,t.typtype,pg_get_userbyid(t.typowner) AS owner,t.typnotnull,t.typdefault,ARRAY(SELECT e.enumlabel FROM pg_enum e WHERE e.enumtypid=t.oid ORDER BY e.enumsortorder) AS enum_labels,ARRAY(SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c WHERE c.contypid=t.oid ORDER BY c.conname) AS domain_constraints FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname=:schema ORDER BY t.typname",
      'type_attributes':"SELECT t.typname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace JOIN pg_class c ON c.oid=t.typrelid JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname=:schema AND c.relkind='c' AND a.attnum>0 AND NOT a.attisdropped ORDER BY t.typname,a.attnum",
      'column_comments':"SELECT c.relname,a.attname,col_description(c.oid,a.attnum) AS comment FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname=:schema AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
      'sequences':"SELECT sequencename,sequenceowner,data_type,start_value,min_value,max_value,increment_by,cycle,cache_size FROM pg_sequences WHERE schemaname=:schema ORDER BY sequencename",
      'namespace_acl':"SELECT pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_namespace n CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname=:schema ORDER BY grantor,grantee,a.privilege_type,a.is_grantable",
      'relation_acl':"SELECT c.relname,pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 's'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) a WHERE n.nspname=:schema AND c.relkind IN ('r','p','v','m','S','f') ORDER BY c.relname,grantor,grantee,a.privilege_type,a.is_grantable",
      'column_acl':"SELECT c.relname,at.attname,pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute at ON at.attrelid=c.oid CROSS JOIN LATERAL aclexplode(at.attacl) a WHERE n.nspname=:schema AND at.attnum>0 AND NOT at.attisdropped ORDER BY c.relname,at.attname,grantor,grantee,a.privilege_type,a.is_grantable",
      'function_acl':"SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE n.nspname=:schema ORDER BY p.proname,arguments,grantor,grantee,a.privilege_type,a.is_grantable",
      'type_acl':"SELECT t.typname,pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace CROSS JOIN LATERAL aclexplode(COALESCE(t.typacl,acldefault('T',t.typowner))) a WHERE n.nspname=:schema ORDER BY t.typname,grantor,grantee,a.privilege_type,a.is_grantable",
      'default_acl':"SELECT pg_get_userbyid(d.defaclrole) AS owner,COALESCE(n.nspname,'<global>') AS schema,d.defaclobjtype,pg_get_userbyid(a.grantor) AS grantor,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE n.nspname=:schema OR d.defaclnamespace=0 ORDER BY owner,schema,d.defaclobjtype,grantor,grantee,a.privilege_type,a.is_grantable",
    }
    result={'namespace':dict(namespace),'layout':{key:[dict(row) for row in conn.execute(text(query),params).mappings()] for key,query in queries.items()}}
    if include_rows:
        quote=conn.dialect.identifier_preparer.quote
        tables={}
        for relation in result['layout']['relations']:
            if relation['relkind'] not in {'r','p','m'}:continue
            name=relation['relname'];hasher=hashlib.sha256();count=0
            for row in conn.execute(text(f'SELECT to_jsonb(t)::text FROM {quote(schema)}.{quote(name)} t ORDER BY 1')):
                hasher.update(row[0].encode('utf8')+b'\n');count+=1
            tables[name]={'rows':count,'sha256':hasher.hexdigest()}
        result['tables']=tables
        result['sequence_values']={}
        for sequence in result['layout']['sequences']:
            name=sequence['sequencename'];value=conn.execute(text(f'SELECT last_value,is_called FROM {quote(schema)}.{quote(name)}')).mappings().one()
            result['sequence_values'][name]=dict(value)
    return result

def require_staging(state):
    if state is None or not STAGING_TABLES.issubset(state['tables']):raise RuntimeError('STOP: required staging schema/tables absent')

def verify_staging(conn,expected):
    if schema_state(conn,'staging')!=expected:raise RuntimeError('STOP: staging structure/data/owners/ACL/sequences differ from baseline')
