"""Server-specific reviewed import; missing IDs skipped, no historical rows created."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from app.services import job_catalog_service as catalog
from app.services import job_catalog_server_policy as policy
from scripts.import_job_catalog import migration_preflight

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='reference-data/job-positions/server-catalog-v1.json')
    p.add_argument('--review',default='reference-data/job-positions/server-link-review-v1.json')
    p.add_argument('--report',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];rows=catalog.read_catalog(args.source);review=policy.read_review(args.review)
    url=make_url(dotenv_values(root/'.env')['DATABASE_URL'])
    if url.host not in {'localhost','127.0.0.1','::1'} or url.database!='corpsite':raise SystemExit('STOP: expected loopback corpsite from server .env')
    applied=False
    with create_engine(url,hide_parameters=True).connect() as conn:
        with conn.begin():
            if not args.apply:conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            migration=migration_preflight(conn)
            plan=policy.database_plan(conn,rows,review,catalog_module=catalog)
            plan['migration']=migration;plan['can_apply']=plan['can_apply'] and not migration['blockers']
            if args.apply and plan['can_apply']:
                plan=policy.apply_catalog(conn,rows,review,catalog_module=catalog);plan['migration']=migration;applied=True
    plan['applied']=applied;plan['source_sha256']=catalog.source_sha256(args.source)
    path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({key:plan[key] for key in ('rows','reviewed_link_count','active_link_count','skipped_missing_ids','conflicts','can_apply','planned_changes','applied')},ensure_ascii=True,indent=2))
    print('Full report: '+str(path))
    if not plan['can_apply']:raise SystemExit('STOP: inspect the server import report; nothing applied')

if __name__=='__main__':main()
