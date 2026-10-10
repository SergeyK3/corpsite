"""Read-only release check: preserve legacy rows, version IDs, history and title sources."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--state',type=Path,required=True)
parser.add_argument('--phase',choices=('before','after'),required=True)
args=parser.parse_args()
root=args.repo.resolve()
sys.path.insert(0,str(root))
from dotenv import load_dotenv
load_dotenv(root/'.env')
from app.db.engine import engine
from sqlalchemy import text

protected_files=[
    'app/services/personnel_order_template_initial_data.py',
    'app/services/personnel_order_template_catalog_data.py',
    'corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts',
]
protected_files += [str(path.relative_to(root)).replace('\\','/') for path in (root/'app/resources/personnel_order_templates').rglob('*') if path.is_file()]
def legacy_content(path: str) -> bytes:
    content=(root/path).read_bytes().replace(b'\r\n',b'\n')
    if path in protected_files[:2]:
        # Only the new recall entry is allowed; all older text remains protected.
        content=content.split(b'\nfrom app.services.personnel_order_recall_contract')[0]
    elif path.endswith('personnelOrderCanonicalTitles.ts'):
        content=b'\n'.join(line for line in content.splitlines() if not line.lstrip().startswith(b'"LEAVE.ANNUAL.RECALL":'))
    return content.rstrip()

files={p:hashlib.sha256(legacy_content(p)).hexdigest() for p in protected_files}
with engine.connect() as conn:
    revisions=conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    tables=conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'personnel_order%' OR tablename='employee_events') AND tablename<>'personnel_order_templates' ORDER BY tablename")).scalars().all()
    fingerprints={}
    for table in tables:
        rows=conn.execute(text(f'''SELECT (to_jsonb(t)-ARRAY['template_id','selected_template_version_id']::text[])::text FROM public."{table}" t ORDER BY 1''')).scalars().all()
        fingerprints[table]={'rows':len(rows),'sha256':hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    if args.phase=='after':
        assert revisions==['hrrecall001'],revisions
        assert conn.execute(text('SELECT count(*) FROM personnel_order_template_versions WHERE template_id IS NULL')).scalar_one()==0
        assert conn.execute(text('''SELECT count(*) FROM personnel_order_template_versions v JOIN personnel_order_templates t ON t.template_id=v.template_id WHERE v.item_type_code<>t.item_type_code''')).scalar_one()==0
state={'files':files,'tables':fingerprints}
if args.phase=='before':
    assert revisions in (['orgkk001'],['hrlang001'],['hrtpl001']),revisions
    assert not args.state.exists(),'Do not overwrite the baseline'
    args.state.parent.mkdir(parents=True,exist_ok=True)
    args.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
else:
    assert state==json.loads(args.state.read_text(encoding='utf-8')),'STOP: legacy rows or protected title files changed'
print('OK:',','.join(revisions),'; preserved version/order/application data and title sources')
