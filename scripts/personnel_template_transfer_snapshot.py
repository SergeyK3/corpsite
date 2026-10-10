"""Read-only template inventory; safe to execute via SSH stdin on older code."""
from __future__ import annotations
import json
import subprocess
from sqlalchemy import text

TABLES = ('personnel_order_templates', 'personnel_order_template_versions')

def snapshot(conn):
    tables = {r[0] for r in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))}
    database=dict(conn.execute(text("SELECT current_database() AS name,current_user AS role,(SELECT oid FROM pg_database WHERE datname=current_database()) AS oid,inet_server_addr()::text AS address,inet_server_port() AS port")).mappings().one())
    result = {'format':'personnel-template-target-v1', 'database':database,'templates':[], 'versions':[], 'references':{},
              'schema':{'alembic':list(conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars()),
                        'columns':{}, 'indexes':[], 'constraints':[]}}
    for table, key in zip(TABLES, ('templates','versions')):
        if table not in tables:continue
        result['schema']['columns'][table] = list(conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t ORDER BY ordinal_position"),{'t':table}).scalars())
        result[key] = [dict(r) for r in conn.execute(text('SELECT * FROM public.'+table+' ORDER BY 1')).mappings()]
    order_cols = set(conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='personnel_orders'")).scalars())
    if 'selected_template_version_id' in order_cols:
        for vid, count in conn.execute(text('SELECT selected_template_version_id,count(*) FROM public.personnel_orders WHERE selected_template_version_id IS NOT NULL GROUP BY 1')):
            result['references'].setdefault(str(vid),{})['orders'] = count
    if 'personnel_order_template_applications' in tables:
        for vid, count in conn.execute(text('SELECT template_version_id,count(*) FROM public.personnel_order_template_applications GROUP BY 1')):
            result['references'].setdefault(str(vid),{})['applications'] = count
    result['schema']['indexes'] = [dict(r) for r in conn.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='personnel_orders' ORDER BY indexname")).mappings()]
    result['schema']['constraints'] = [dict(r) for r in conn.execute(text("SELECT conname,pg_get_constraintdef(oid) definition FROM pg_constraint WHERE conrelid='public.personnel_orders'::regclass ORDER BY conname")).mappings()]
    if {'order_date','order_number','deleted_at'} <= order_cols:
        result['schema']['active_header_duplicate_groups'] = conn.execute(text(r"""SELECT count(*) FROM (
          SELECT upper(btrim(regexp_replace(translate(order_number,'‐‑‒–—―','-------'),'\s+',' ','g'))),order_date
          FROM public.personnel_orders WHERE deleted_at IS NULL AND order_date IS NOT NULL AND order_number IS NOT NULL AND btrim(order_number)<>''
          GROUP BY 1,2 HAVING count(*)>1) d""")).scalar_one()
    return json.loads(json.dumps(result,default=str,ensure_ascii=False))

def main():
    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    import os
    load_dotenv('.env')
    engine = create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        data = snapshot(conn)
    data['code'] = {'head':subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD'],text=True).strip(),
                    'tracked_changes':subprocess.check_output(['git','--no-optional-locks','status','--short','--untracked-files=no'],text=True).splitlines()}
    print(json.dumps(data,ensure_ascii=False,sort_keys=True))

if __name__ == '__main__':main()
