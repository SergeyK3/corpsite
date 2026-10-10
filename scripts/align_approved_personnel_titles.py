"""One-off, title-only data correction. Dry-run by default; no remote calls.

Build a fresh plan on each database; selectors never use IDs from another DB.
See runtime/approved-personnel-titles/REPORT.txt for deployment and rollback.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import text
from app.db.engine import engine

TITLES = {
    'HIRE': 'Жұмысқа қабылдау туралы',
    'TRANSFER': 'Ауыстыру туралы',
    'TERMINATION': 'Еңбек шартын бұзу туралы',
    'CONCURRENT_DUTY_START': 'Қоса атқару туралы',
    'CONCURRENT_DUTY_END': 'Ставканы алып тастау туралы',
    'SUPPLEMENTARY_PAY': 'Қосымша ақы туралы',
    'LEAVE.ANNUAL.GRANT': 'Еңбек демалысы туралы',
    'LEAVE.UNPAID.GRANT': 'Жалақы сақталмайтын демалыс беру туралы',
    'LEAVE.CHILDCARE.GRANT': 'Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы',
    'RETURN_FROM_CHILDCARE_LEAVE': 'Бала күтіміне байланысты демалыстан жұмысқа шығу туралы',
}
ALIASES = {
    'TERMINATION': ['Жұмыстан босату туралы'],
    'CONCURRENT_DUTY_START': ['Қоса атқаруды белгілеу туралы'],
    'CONCURRENT_DUTY_END': ['Қоса атқаруды тоқтату туралы'],
    'SUPPLEMENTARY_PAY': ['Қосымша ақы төлеу туралы'],
    'LEAVE.ANNUAL.GRANT': ['Жыл сайынғы ақылы еңбек демалысын беру туралы'],
    'LEAVE.UNPAID.GRANT': ['Еңбекақысы сақталмайтын демалыс туралы', 'Ақысыз демалыс туралы', 'Еңбекақысы сақталмайтын демалыс'],
    'LEAVE.CHILDCARE.GRANT': ['Бала күтіміне байланысты жалақы сақталмайтын демалыс'],
}
RU_TITLES = {
    'LEAVE.ANNUAL.GRANT': 'О трудовом отпуске',
    'LEAVE.UNPAID.GRANT': 'Об отпуске без содержания',
}
RU_OLD = {
    'LEAVE.ANNUAL.GRANT': 'О предоставлении ежегодного оплачиваемого трудового отпуска',
    'LEAVE.UNPAID.GRANT': 'О предоставлении отпуска без сохранения заработной платы',
}
COMPOSITE = {
    'Ақылы демалыс туралы': 'Ақылы демалыс туралы',
    'Еңбек демалысынан шақырту': 'Еңбек демалысынан шақырту туралы',
    'Еңбек демалысынан шақырту туралы': 'Еңбек демалысынан шақырту туралы',
    'Еңбек демалысын ұзарту туралы': 'Еңбек демалысын ұзарту туралы',
    'Бұйрыққа өзгеріс енгізу туралы': 'Бұйрыққа өзгеріс енгізі туралы',
    'Бұйрыққа өзгеріс енгізі туралы': 'Бұйрыққа өзгеріс енгізі туралы',
}
REPLACEMENTS = {old: TITLES[code] for code in (
    'TERMINATION', 'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', 'LEAVE.ANNUAL.GRANT'
) for old in ALIASES[code]}
FILES = (
    'app/services/personnel_order_template_initial_data.py',
    'app/services/personnel_order_template_catalog_data.py',
    'app/services/personnel_orders_editorial/generators.py',
    'app/api/ppr_self_orders_router.py',
    'corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts',
    'corpsite-ui/app/directory/personnel/_lib/personnelOrderPrintViewModel.ts',
    'corpsite-ui/app/directory/personnel/_components/PersonnelOrderDetailDrawer.tsx',
    'tests/test_personnel_order_template_draft_validation.py',
    'app/services/personnel_order_template_manifest.py',
)
TEST_HASH_REPLACEMENTS = {
    'bc34ed5af9bbc3e3e1fd7dd874aeebecc9b2d2b918692526c59abaabfc2c78a2': '9de2f78c755fe3015150117ced15279c550a77ca767f0937bec3e008cc0d516e',
    '6d3af87099855f0270cc9c015e24fa44dfc98bcd8ea7f7ebccb2848dd77fcdce': '9c677af7e12215a6cad5e6b553c17d6d00e05727c6096e4ef6a4c58554b101d8',
    '6f9dc6cd6a6424d061d1d154142e18a4f02bdaaaa581f2d3fb96370bade07fc0': 'e67abd7c08964bf96f2d77cb166b31dda6b877667a50e7d767ecf4617086f7fa',
    '9ac3b1e220d4f174350626cb65d97949abcdce9ddadb6ba02c4846242e7bb96d': '028db60f236058ff430996abb48010eb2f6491ec98e12a6021c002d2c9f53c0d',
    '028db60f236058ff430996abb48010eb2f6491ec98e12a6021c002d2c9f53c0d': 'cf74a3322817548e5f18b82e98e745137c22291ddb2d8db68cf4590d28e39810',
    'df3b6b2c648e392e99cba29ce45ed9f15272f50e253420d4a37f0b62f13a3eed': '23723590c2419afb132196b65c5d3f2b48cc560c672f66e10f615dd35ea42f71',
}
CARD_OLD = 'const currentTitle = editorial?.order_blocks.find((block) => block.block_type === "title" && block.locale === orderLanguage)?.effective_text?.trim() || "—";'
CARD_NEW = CARD_OLD.replace('|| "—";', '|| order?.source_title?.trim() || "—";')
HISTORICAL_UNPAID = '''    # Frozen v1 predates the approved Russian title correction (2026-10-06).
    ("LEAVE.UNPAID.GRANT", 1, "52bf1df2e2d79cfc900207022525b890a47ab71b426b6fa9b0b2f51f29159cd5"):
        ("94aa0e60cc35f4634067addc48467cdaca669bfbc17d9f194e4d4c8107c03fe4", (
            "employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru",
            "org_unit.title_kk", "leave.start_ru", "leave.start_kk", "leave.end_ru", "leave.end_kk",
            "leave.days", "leave.period_text_ru", "leave.period_text_kk", "leave.period_clause_ru",
            "leave.period_clause_kk", "org_unit.document_genitive_kk", "position.document_possessive_kk",
            "position.document_nominative_ru", "employee.full_name_dative_ru", "employee.full_name_dative_kk",
            "employee.full_name_genitive_kk", "basis.application_date_ru", "basis.application_date_kk",
            "basis.application_number_suffix",
        )),
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())


def snapshot(conn):
    tables = conn.execute(text("""SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND (table_name LIKE 'personnel_order%'
        OR table_name IN ('employee_events','employee_assignments','person_assignments','employees')) ORDER BY 1""")).scalars().all()
    return {t: sorted(conn.execute(text(f'SELECT to_jsonb(t) FROM public.{t} t')).scalars().all(), key=digest) for t in tables}


def order_key(row):
    # Original provenance, or the registered number and date, or draft creation time.
    source = (row.get('storage_json') or {}).get('source_identifier')
    return {'order_type_code': row['order_type_code'], 'order_number': row['order_number'],
            'order_date': row['order_date'], 'source_identifier': source,
            'draft_created_at': row['created_at'] if not source and not row['order_number'] else None}


def target_for(row):
    code, title = row['order_type_code'], row['source_title']
    if code == 'COMPOSITE':
        return COMPOSITE.get(title)
    if code in TITLES and title in [TITLES[code], *ALIASES.get(code, [])]:
        return TITLES[code]
    return None


def make_plan(state):
    edits, skipped, matched = [], [], []
    orders = state['personnel_orders']
    keys = Counter(digest(order_key(r)) for r in orders)

    def add(table, key, row, fields):
        changed = {k: v for k, v in fields.items() if row[k] != v}
        if changed:
            existing = next((e for e in edits if e['table'] == table and e['key'] == key), None)
            if existing:
                existing['after'].update(changed)
                existing['fields'] = sorted(set(existing['fields']) | set(changed))
            else:
                edits.append({'table': table, 'key': key, 'before': row, 'after': {**row, **changed}, 'fields': sorted(changed)})

    for row in orders:
        key = order_key(row)
        target = target_for(row)
        if not row['source_title'] and row['order_type_code'] == 'LEAVE.UNPAID.GRANT':
            items = [i for i in state['personnel_order_items'] if i['order_id'] == row['order_id']]
            if items and all(i['item_type_code'] == 'LEAVE.UNPAID.GRANT' and i['period_start'] and i['period_end'] for i in items):
                target = TITLES['LEAVE.UNPAID.GRANT']
        if not target or keys[digest(key)] != 1:
            skipped.append({'key': key, 'title': row['source_title'], 'reason': 'Нет однозначного соответствия по сохранённым данным' if not target else 'Неуникальный устойчивый ключ'})
            continue
        # Refuse conflicting active title copies. Historical/raw fields are never traversed.
        related = [b for b in state['personnel_order_editorial_blocks'] if b['order_id'] == row['order_id'] and b['locale'] == 'kk' and b['block_type'] == 'title']
        localized = [b for b in state['personnel_order_localized_texts'] if b['order_id'] == row['order_id'] and b['locale'] == 'kk']
        accepted = {target, row['source_title'], *ALIASES.get(row['order_type_code'], [])}
        sj = row['storage_json'] or {}
        values = [sj.get('source_title')]
        values += [b[f] for b in related for f in ('generated_text', 'override_text')]
        values += [b['title'] for b in localized]
        if any(v and v.strip() and v not in accepted for v in values):
            skipped.append({'key': key, 'title': row['source_title'], 'reason': 'Противоречащие отображаемые заголовки', 'titles': values})
            continue
        fields = {'source_title': target}
        if 'source_title' in sj:
            fields['storage_json'] = {**sj, 'source_title': target}
        add('personnel_orders', key, row, fields)
        for b in related:
            add('personnel_order_editorial_blocks', {'order': key, 'locale': 'kk', 'block_type': 'title'}, b,
                {f: target for f in ('generated_text', 'override_text') if b[f] and b[f].strip()})
        for b in localized:
            add('personnel_order_localized_texts', {'order': key, 'locale': 'kk'}, b, {'title': target})
        matched.append({'key': key, 'old': row['source_title'], 'target': target})
    # Exact Russian title fields only; never descend into original source text or history.
    for row in orders:
        code = row['order_type_code']
        key = order_key(row)
        if code not in RU_TITLES or keys[digest(key)] != 1:
            continue
        old, target = RU_OLD[code], RU_TITLES[code]
        fields = {}
        if row['source_title'] == old:
            fields['source_title'] = target
        sj = row['storage_json'] or {}
        if sj.get('source_title') == old:
            fields['storage_json'] = {**sj, 'source_title': target}
        add('personnel_orders', key, row, fields)
        if row['source_title'] in {old, target}:
            skipped[:] = [s for s in skipped if s.get('key') != key]
            matched.append({'key': key, 'old': row['source_title'], 'target': target})
        for b in state['personnel_order_editorial_blocks']:
            if b['order_id'] == row['order_id'] and b['locale'] == 'ru' and b['block_type'] == 'title':
                add('personnel_order_editorial_blocks', {'order': key, 'locale': 'ru', 'block_type': 'title'}, b,
                    {f: target for f in ('generated_text', 'override_text') if b[f] == old})
        for b in state['personnel_order_localized_texts']:
            if b['order_id'] == row['order_id'] and b['locale'] == 'ru' and b['title'] == old:
                add('personnel_order_localized_texts', {'order': key, 'locale': 'ru'}, b, {'title': target})
    for row in state['personnel_order_template_versions']:
        if row['status'] == 'ARCHIVED':
            continue
        code = row['item_type_code']
        if code in RU_TITLES and row['title_ru'] == RU_OLD[code]:
            add('personnel_order_template_versions', {k: row[k] for k in ('item_type_code','version_number','status')}, row, {'title_ru': RU_TITLES[code]})
        if code in TITLES and row['title_kk'] in [TITLES[code], *ALIASES.get(code, [])]:
            add('personnel_order_template_versions', {k: row[k] for k in ('item_type_code','version_number','status')}, row, {'title_kk': TITLES[code]})
        else:
            skipped.append({'template': {k: row[k] for k in ('item_type_code','version_number','status')}, 'title': row['title_kk'], 'reason': 'Неизвестное название; требуется содержательная проверка версии'})
    files = []
    for name in FILES:
        before = (ROOT / name).read_bytes().decode('utf-8')
        after = before
        for old, new in REPLACEMENTS.items():
            after = after.replace(old, new)
        if not name.startswith('tests/'):
            # Quote boundaries prevent replacing the prefix of the childcare title.
            for code, old in RU_OLD.items():
                for quote in ('"', "'"):
                    after = after.replace(quote + old + quote, quote + RU_TITLES[code] + quote)
        if name.startswith('tests/'):
            for old, new in TEST_HASH_REPLACEMENTS.items():
                after = after.replace(old, new)
        if name.endswith('PersonnelOrderDetailDrawer.tsx'):
            if (CARD_OLD in before) == (CARD_NEW in before):
                raise RuntimeError('Unknown card title expression; review server code before applying')
            after = after.replace(CARD_OLD, CARD_NEW)
        if name.endswith('personnel_order_template_manifest.py'):
            newline = '\r\n' if '\r\n' in after else '\n'
            entry = HISTORICAL_UNPAID.replace('\n', newline)
            if entry not in after:
                anchor = '_HISTORICAL_MANIFESTS = {' + newline
                if after.count(anchor) != 1 or '52bf1df2e2d79cfc900207022525b890a47ab71b426b6fa9b0b2f51f29159cd5' in after:
                    raise RuntimeError('Unknown historical manifest registry; review before applying')
                after = after.replace(anchor, anchor + entry)
        if before != after:
            files.append({'path': name, 'before': before, 'after': after})
    return {'package_revision': '20261006-ru-v2', 'edits': edits, 'files': files, 'skipped': skipped, 'matched': matched}


def resolve(state, edit):
    table, key = edit['table'], edit['key']
    if table == 'personnel_order_template_versions':
        rows = [r for r in state[table] if all(r[k] == v for k, v in key.items())]
    else:
        ok = key if table == 'personnel_orders' else key['order']
        orders = [r for r in state['personnel_orders'] if order_key(r) == ok]
        if len(orders) != 1:
            raise RuntimeError('Order stable selector is not unique')
        rows = orders if table == 'personnel_orders' else [r for r in state[table] if r['order_id'] == orders[0]['order_id'] and all(r[k] == v for k, v in key.items() if k != 'order')]
    if len(rows) != 1:
        raise RuntimeError('Stable selector is not unique')
    return rows[0]


def execute(conn, state, plan, rollback=False):
    expected = deepcopy(state)
    template_edits = [e for e in plan['edits'] if e['table'] == 'personnel_order_template_versions']
    trigger = 'trg_guard_published_personnel_order_template'
    if template_edits:
        # A maintenance-only exception for the explicitly authorized title correction.
        # PostgreSQL DDL and the lock are transactional: any failure restores the guard.
        assert all(set(e['fields']) <= {'title_kk', 'title_ru'} for e in template_edits)
        conn.execute(text('LOCK TABLE public.personnel_order_template_versions IN ACCESS EXCLUSIVE MODE'))
        enabled = conn.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='public.personnel_order_template_versions'::regclass AND tgname=:name"), {'name': trigger}).scalar_one()
        if enabled != 'O':
            raise RuntimeError('Unexpected template guard state')
        conn.execute(text(f'ALTER TABLE public.personnel_order_template_versions DISABLE TRIGGER {trigger}'))
    primary = {'personnel_orders': 'order_id', 'personnel_order_template_versions': 'template_version_id',
               'personnel_order_editorial_blocks': 'editorial_block_id', 'personnel_order_localized_texts': 'localized_text_id'}
    for edit in plan['edits']:
        row = resolve(state, edit)
        before, after = (edit['after'], edit['before']) if rollback else (edit['before'], edit['after'])
        if row != before:
            raise RuntimeError('Record changed since plan/backup; refusing write')
        table = edit['table']
        fields = edit['fields']
        assignments = ','.join(f'{f}=CAST(:{f} AS jsonb)' if f == 'storage_json' else f'{f}=:{f}' for f in fields)
        params = {f: json.dumps(after[f], ensure_ascii=False) if f == 'storage_json' else after[f] for f in fields}
        params['pk'] = row[primary[table]]
        assert conn.execute(text(f'UPDATE public.{table} SET {assignments} WHERE {primary[table]}=:pk'), params).rowcount == 1
        index = expected[table].index(row)
        expected[table][index] = deepcopy(after)
    if template_edits:
        conn.execute(text(f'ALTER TABLE public.personnel_order_template_versions ENABLE TRIGGER {trigger}'))
        assert conn.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='public.personnel_order_template_versions'::regclass AND tgname=:name"), {'name': trigger}).scalar_one() == enabled
    # All columns of all order tables, events, assignments and employees must agree.
    actual = snapshot(conn)
    assert {t: sorted(rows, key=digest) for t, rows in expected.items()} == actual, 'Unexpected non-title mutation; transaction rolled back'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', type=Path)
    p.add_argument('--plan', type=Path)
    p.add_argument('--backup', type=Path)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--expected-database', default='corpsite')
    a = p.parse_args()
    if engine.url.host not in {'localhost','127.0.0.1','::1'} or engine.url.database != a.expected_database:
        p.error('Only the explicitly named loopback database is allowed')
    if a.apply and (not a.plan or not a.backup):
        p.error('--apply requires --plan and --backup')
    written = []
    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout='10s'"))
            if a.apply or a.rollback:
                tables = list(snapshot(conn))
                conn.execute(text('LOCK TABLE ' + ','.join('public.'+t for t in tables) + ' IN SHARE ROW EXCLUSIVE MODE'))
            else:
                conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            state = snapshot(conn)
            plan = json.loads(a.rollback.read_text('utf-8')) if a.rollback else make_plan(state)
            if a.apply:
                approved = json.loads(a.plan.read_text('utf-8'))
                if plan != approved:
                    raise RuntimeError('Fresh plan differs from reviewed plan; rerun dry-run')
                if plan['edits'] or plan['files']:
                    save(a.backup, plan, exclusive=True)
            if a.apply or a.rollback:
                for f in plan['files']:
                    old, new = (f['after'], f['before']) if a.rollback else (f['before'], f['after'])
                    path = ROOT / f['path']
                    if path.read_bytes().decode('utf-8') != old:
                        raise RuntimeError('Source file changed; refusing overwrite: ' + f['path'])
                    written.append((path, old))
                    path.write_bytes(new.encode('utf-8'))
                execute(conn, state, plan, rollback=bool(a.rollback))
            if not a.apply and not a.rollback and a.plan:
                save(a.plan, plan)
    except BaseException:
        for path, old in reversed(written):
            path.write_bytes(old.encode('utf-8'))
        raise
    changed_orders = {digest(e['key'] if e['table']=='personnel_orders' else e['key']['order']) for e in plan['edits'] if e['table'] != 'personnel_order_template_versions'}
    report = {'package_revision': plan.get('package_revision', '20261006-v1'),
              'applied': a.apply, 'rollback': bool(a.rollback), 'order_count': len(changed_orders),
              'database_template_count': sum(e['table']=='personnel_order_template_versions' for e in plan['edits']),
              'changed_source_files': [f['path'] for f in plan['files']], 'changed_rows': len(plan['edits']),
              'skipped': plan['skipped'], 'protected_data_verified': True,
              'changes': [{k: v for k,v in e.items() if k not in ('before','after')} | {'values': {f:{'before':e['before'][f],'after':e['after'][f]} for f in e['fields'] if f!='storage_json'}} for e in plan['edits']]}
    save(a.report, report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('changes','skipped')}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
