"""Source-only childcare title correction. No database writes or publications."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TYPE = 'LEAVE.CHILDCARE.GRANT'
FORMAT = 'childcare-builtin-titles-20261006-v3'
TITLES = {'title_ru': 'О неоплачиваемом отпуске по уходу за ребенком',
          'title_kk': 'Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы'}
PY_FILES = {
    'app/services/personnel_order_childcare_contract.py': ('TEXTS', False),
    'app/services/personnel_order_template_initial_data.py': ('INITIAL_TEXTS_BY_TYPE', True),
    'app/services/personnel_order_template_catalog_data.py': ('CATALOG_PROJECTIONS', True),
    'app/services/personnel_orders_editorial/generators.py': ('DOCUMENT_TITLES', True),
}
UI_FILE = 'corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts'
ALLOWED = {*PY_FILES, UI_FILE}


def require(ok, message):
    if not ok: raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def dict_value(node, key):
    require(isinstance(node, ast.Dict), f'Expected dictionary for {key}')
    values = [v for k,v in zip(node.keys, node.values)
              if (isinstance(k, ast.Constant) and k.value == key)
              or (key == TYPE and isinstance(k, ast.Name) and k.id == 'ORDER_TYPE_LEAVE_CHILDCARE_GRANT')]
    require(len(values) == 1, f'Expected one {key} entry in source')
    return values[0]


def python_edits(raw, variable, nested):
    source = raw.decode('utf-8-sig')
    tree = ast.parse(source)
    nodes = []
    for stmt in tree.body:
        names = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
        if any(isinstance(n, ast.Name) and n.id == variable for n in names): nodes.append(stmt.value)
    require(len(nodes) == 1, f'Expected one {variable} assignment')
    node = dict_value(nodes[0], TYPE) if nested else nodes[0]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == 'CHILDCARE_TEXTS' and not node.keywords:
        return []
    lines = source.encode('utf-8').splitlines(keepends=True)
    bom = 3 if raw.startswith(b'\xef\xbb\xbf') else 0
    edits = []
    for field, target in TITLES.items():
        value = dict_value(node, field.removeprefix('title_') if variable == 'DOCUMENT_TITLES' else field)
        if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name) and value.value.id == 'CHILDCARE_TEXTS' and isinstance(value.slice, ast.Constant) and value.slice.value == field:
            continue
        require(isinstance(value, ast.Constant) and isinstance(value.value, str), f'Unsupported title expression for {field}')
        if value.value == target: continue
        start = bom + sum(map(len, lines[:value.lineno-1])) + value.col_offset
        end = bom + sum(map(len, lines[:value.end_lineno-1])) + value.end_col_offset
        edits.append({'field':field, 'line':value.lineno, 'start':start, 'end':end,
                      'before':value.value, 'after':target,
                      'old_literal':raw[start:end].decode('utf-8'),
                      'new_literal':json.dumps(target, ensure_ascii=False)})
    return edits


def ui_titles_and_edits(raw):
    source = raw.decode('utf-8-sig')
    require('export const PERSONNEL_ORDER_CANONICAL_TITLES' in source, 'Unknown frontend title table')
    entries = list(re.finditer(r'''["']LEAVE\.CHILDCARE\.GRANT["']\s*:\s*\{([^{}]*)\}''', source))
    require(len(entries) == 1, 'Expected one childcare entry in frontend title table')
    entry = entries[0]
    titles, edits = {}, []
    bom = 3 if raw.startswith(b'\xef\xbb\xbf') else 0
    for locale in ('ru','kk'):
        matches = list(re.finditer(r'''\b''' + locale + r'''\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')''', entry.group(1)))
        require(len(matches) == 1, f'Expected one frontend {locale} title')
        match = matches[0]
        old = ast.literal_eval(match.group(1))
        field = 'title_'+locale
        titles[field] = old
        if old == TITLES[field]: continue
        a, b = entry.start(1) + match.start(1), entry.start(1) + match.end(1)
        edits.append({'field':field, 'line':source.count('\n', 0, a)+1,
                      'start':bom+len(source[:a].encode('utf-8')), 'end':bom+len(source[:b].encode('utf-8')),
                      'before':old, 'after':TITLES[field], 'old_literal':match.group(1),
                      'new_literal':json.dumps(TITLES[field], ensure_ascii=False)})
    return titles, edits


def patched(raw, edits):
    for edit in sorted(edits, key=lambda e:e['start'], reverse=True):
        require(raw[edit['start']:edit['end']].decode('utf-8') == edit['old_literal'], 'Source span mismatch')
        raw = raw[:edit['start']] + edit['new_literal'].encode('utf-8') + raw[edit['end']:]
    return raw


def build_plan(root=ROOT):
    files = []
    for name in sorted(ALLOWED):
        path = root/name
        if name.endswith('personnel_order_childcare_contract.py') and not path.exists(): continue
        require(path.is_file() and not path.is_symlink(), f'Expected existing regular file: {name}')
        raw = path.read_bytes()
        edits = ui_titles_and_edits(raw)[1] if name == UI_FILE else python_edits(raw, *PY_FILES[name])
        after = patched(raw, edits)
        if name.endswith('.py'): ast.parse(after.decode('utf-8-sig'))
        files.append({'path':name, 'before_sha256':sha(raw), 'after_sha256':sha(after),
                      'original_b64':base64.b64encode(raw).decode('ascii'), 'edits':edits})
    return {'format':FORMAT, 'type':TYPE, 'files':files}


def report(plan, mode):
    changed = [f for f in plan['files'] if f['edits']]
    return {'format':FORMAT, 'mode':mode,
            'changed_files':[f['path'] for f in changed],
            'backend_restart_required':any(f['path'].endswith('.py') for f in changed),
            'frontend_build_required':any(f['path'].startswith('corpsite-ui/') for f in changed),
            'changes':[{'path':f['path'], 'edits':f['edits']} for f in changed],
            'database_writes':0, 'new_versions':0}


def restore_or_apply(plan, root=ROOT, rollback=False):
    require(plan.get('format') == FORMAT and plan.get('type') == TYPE, 'Wrong source plan revision')
    prepared = []
    require(len({f['path'] for f in plan['files']}) == len(plan['files']), 'Duplicate file')
    for f in plan['files']:
        name = f['path']
        require(name in ALLOWED, 'File outside approved title sources')
        path = root/name
        require(path.is_file() and not path.is_symlink(), 'Missing or symlinked source')
        raw = base64.b64decode(f['original_b64'], validate=True)
        edits = ui_titles_and_edits(raw)[1] if name == UI_FILE else python_edits(raw, *PY_FILES[name])
        require(edits == f['edits'] and sha(raw) == f['before_sha256'], 'Backup contains non-title changes')
        after = patched(raw, edits)
        require(sha(after) == f['after_sha256'], 'Incorrect result hash')
        expected, output = (after, raw) if rollback else (raw, after)
        require(path.read_bytes() == expected, f'Source changed after planning: {name}')
        if expected != output: prepared.append((path, expected, output))
    written = []
    try:
        for path, before, after in prepared:
            written.append((path, before))
            with path.open('wb') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            require(path.read_bytes() == after, 'Written source mismatch')
    except BaseException:
        for path, before in reversed(written): path.write_bytes(before)
        raise


def probe():
    """Read actual editor base in a read-only transaction; never persist a draft."""
    from contextlib import nullcontext
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import text
    from app.db.engine import engine
    from app.services import personnel_order_template_draft_service as service
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    from app.services.personnel_orders_editorial.generators import generate_order_block
    require(engine.url.host in ('localhost','127.0.0.1','::1') and engine.url.database == 'corpsite', 'Expected local corpsite database')
    with engine.connect() as conn, conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        class BoundEngine:
            def connect(self): return nullcontext(conn)
        original = service.engine
        service.engine = BoundEngine()
        try:
            rows = conn.execute(text('SELECT to_jsonb(t) FROM personnel_order_template_versions t WHERE item_type_code=:type ORDER BY version_number'), {'type':TYPE}).scalars().all()
            base = service.get_editor_base(TYPE)
            published = service.get_published(TYPE)
        finally: service.engine = original
    spec = get_personnel_order_template_spec(TYPE)
    texts = dict(spec.initial_texts)
    frontend, _ = ui_titles_and_edits((ROOT/UI_FILE).read_bytes())
    title_fields = lambda value: {f:value[f] for f in TITLES}
    return {'editor_base_source':base['source'], 'editor_base_titles':title_fields(base),
            'initial_titles':title_fields(texts), 'catalog_titles':title_fields(spec.catalog_projection),
            'frontend_fallback_titles':frontend,
            'creation_title_source':'PUBLISHED' if published else 'FRONTEND_FALLBACK',
            'creation_titles':title_fields(published) if published else frontend,
            'generator_titles':{'title_'+lang:generate_order_block('title', lang, {'order_type_code':TYPE})['generated_text'] for lang in ('ru','kk')},
            'non_title_initial_sha256':sha(json.dumps({k:v for k,v in texts.items() if k not in TITLES}, sort_keys=True, ensure_ascii=False).encode()),
            'stored_versions_count':len(rows),
            'stored_versions_sha256':sha(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode())}


def fresh_probe():
    # Read edited source afresh, independent of loaded modules and stale pyc files.
    # -B prevents creation of this unique cache path; no cleanup is necessary.
    cache = str(ROOT/'runtime'/('.childcare-no-pyc-'+uuid4().hex))
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-X', 'pycache_prefix='+cache,
                             str(Path(__file__).resolve()), '--probe'], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    require(result.returncode == 0, 'Read-only verification failed: '+result.stderr)
    return json.loads(result.stdout)


def check_probe(value):
    for field in ('editor_base_titles','initial_titles','catalog_titles','frontend_fallback_titles','creation_titles','generator_titles'):
        require(value[field] == TITLES, f'Titles still differ in {field}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--rollback', type=Path)
    group.add_argument('--verify', action='store_true')
    group.add_argument('--probe', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--require-initial', action='store_true')
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe(), ensure_ascii=False)); return
    require(args.report is not None, '--report required')
    if args.verify:
        value = fresh_probe()
        check_probe(value)
        if args.require_initial: require(value['editor_base_source'] == 'INITIAL', 'Editor no longer uses INITIAL')
        result = {'format':FORMAT, 'mode':'verify', 'verified':True, **value}
    elif args.rollback:
        plan = json.loads(args.rollback.read_text('utf-8'))
        restore_or_apply(plan, rollback=True)
        result = report(plan, 'rollback')
    else:
        require(args.plan is not None, '--plan required')
        plan = build_plan()
        before = fresh_probe()
        if args.require_initial: require(before['editor_base_source'] == 'INITIAL', 'Editor no longer uses INITIAL')
        if args.apply:
            require(args.backup is not None, '--backup required')
            require(plan == json.loads(args.plan.read_text('utf-8')), 'Source plan is stale; rebuild it')
            if any(f['edits'] for f in plan['files']): save(args.backup, plan, exclusive=True)
            restore_or_apply(plan)
            try:
                after = fresh_probe()
                check_probe(after)
                for field in ('non_title_initial_sha256','stored_versions_sha256','stored_versions_count','editor_base_source'):
                    require(before[field] == after[field], f'Unexpected change: {field}')
            except BaseException:
                restore_or_apply(plan, rollback=True)
                raise
            result = {**report(plan, 'apply'), 'verified':True, 'before_probe':before, 'after_probe':after}
        else:
            save(args.plan, plan)
            result = {**report(plan, 'preview'), 'before_probe':before}
    save(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
