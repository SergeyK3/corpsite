"""Check the proposed recovery graph and the exact baseline, with READ ONLY SQL."""
import copy
import hashlib
import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
folder = root / 'runtime/personnel-stage3-preparation'
manifest = json.loads((folder / 'recovery-manifest.json').read_text(encoding='utf-8'))
for relative, expected in manifest['files'].items():
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
dump = folder / 'corpsite-before-stage3.dump'
assert hashlib.sha256(dump.read_bytes()).hexdigest() == manifest['backup']['sha256']
graph = ScriptDirectory.from_config(Config(str(root / 'scripts/personnel_stage3_local_recovery/alembic.ini')))
assert graph.get_heads() == ['hrlocal302']
assert graph.get_revision('hrlocal302').down_revision == 'hrlocal301'
assert [m.revision for m in graph.iterate_revisions('hrlocal301', 'za0b1c2d3e4f')] == ['hrlocal301']
baseline = graph.get_revision('za0b1c2d3e4f').module
for forbidden in [baseline.upgrade, baseline.downgrade]:
    try:
        forbidden()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Snapshot must never create or remove a database')
migration = graph.get_revision('hrlocal301').module
expected = json.loads((folder / 'preflight.json').read_text(encoding='utf-8'))
url = make_url(dotenv_values(root / '.env')['DATABASE_URL'])
assert url.host in {'localhost', '127.0.0.1', '::1'} and url.database == 'corpsite'
with create_engine(url).connect() as conn:
    conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
    migration.validate_baseline(conn, expected)
    altered = copy.deepcopy(expected)
    altered['constraints'] = []
    try:
        migration.validate_baseline(conn, altered)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Schema drift must reject recovery')
    assert migration.fingerprints(conn, expected['fingerprints']) == expected['fingerprints']
report = {'graph_head': 'hrlocal301', 'baseline': 'za0b1c2d3e4f',
          'source_and_backup_hashes_verified': True, 'baseline_guard_passed': True,
          'schema_drift_rejected': True, 'baseline_creation_rejected': True,
          'all_old_table_fingerprints_unchanged': len(expected['fingerprints']),
          'database_transaction_read_only': True, 'working_database_migration_executed': False,
          'restored_copy_rehearsal_report_available': (folder / 'rehearsal-result.json').exists()}
(folder / 'checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
