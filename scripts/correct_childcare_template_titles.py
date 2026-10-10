"""Standalone correction of existing childcare template title fields only.

No general title package imports, no new template, no order regeneration.
Preview first with --plan/--report; apply requires that fresh plan and a backup.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
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

TYPE = 'LEAVE.CHILDCARE.GRANT'
TITLES = {
    'title_ru': 'О неоплачиваемом отпуске по уходу за ребенком',
    'title_kk': 'Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы',
}
FORMAT = 'childcare-template-titles-20261006-v2'
TABLE = 'personnel_order_template_versions'
TRIGGER = 'trg_guard_published_personnel_order_template'
KEY_FIELDS = ('item_type_code', 'version_number', 'status')
CURRENT_FIELDS = ('is_current', 'is_active', 'active_flag')
HISTORY_STATUSES = {'ARCHIVED', 'DELETED', 'SUPERSEDED', 'RETIRED', 'INACTIVE'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def table_names(conn):
    return conn.execute(text("""SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE' AND (table_name LIKE 'personnel_order%'
          OR table_name IN ('employee_events','person_assignments','employee_assignments','employees'))
        ORDER BY table_name""")).scalars().all()


def snapshot(conn):
    return {t: sorted(conn.execute(text(f'SELECT to_jsonb(t) FROM public.{t} t')).scalars().all(), key=digest)
            for t in table_names(conn)}


def key(row):
    return {field: row[field] for field in (*KEY_FIELDS, *CURRENT_FIELDS) if field in row}


def reader_usage(conn):
    """Use the installed server readers, on the same transaction snapshot.

    The template page reads draft/published/editor-base; the creation-title
    endpoint uses get_published. Never invoke a writer or publish a version.
    """
    try:
        from app.services import personnel_order_template_draft_service as service
    except Exception as exc:
        return {'service_import': {'error': type(exc).__name__}}

    class BoundEngine:
        def connect(self): return nullcontext(conn)

    original = service.engine
    usage = {}
    service.engine = BoundEngine()
    try:
        for name in ('get_draft', 'get_published', 'get_editor_base'):
            try:
                # A failed read must not poison the outer transaction.
                with conn.begin_nested():
                    row = getattr(service, name)(TYPE)
                usage[name] = None if row is None else {
                    f: row.get(f) for f in ('template_version_id', 'version_number', 'status', 'source', *TITLES)
                }
            except Exception as exc:
                usage[name] = {'error': type(exc).__name__}
    finally:
        service.engine = original
    return usage


def selection(row, usage):
    status = str(row.get('status', '')).upper()
    if status in HISTORY_STATUSES or row.get('archived_at') or row.get('deleted_at'):
        return False, 'historical_or_deleted'
    flags = {f: row[f] for f in CURRENT_FIELDS if f in row}
    if any(v is not None and not isinstance(v, bool) for v in flags.values()):
        return False, 'unsupported_current_flag_value'
    # The installed draft reader can legitimately expose a draft whose
    # is_current=False denotes that it is not yet the current publication.
    draft = usage.get('get_draft') or {}
    if status == 'DRAFT' and row.get('template_version_id') is not None and row['template_version_id'] == draft.get('template_version_id'):
        return True, 'draft_used_by_template_page'
    if flags:
        # is_current is the precise version marker; active flags are fallback.
        field = next(f for f in CURRENT_FIELDS if f in flags)
        if flags[field] is not True:
            return False, f'{field}_not_true'
        return True, f'{field}_true'
    if status in ('DRAFT', 'PUBLISHED'):
        return True, 'live_status_without_current_column'
    return False, 'unknown_status_without_current_marker'


def build_plan(state, usage=None, schema=None):
    usage = usage or {}
    rows = sorted([r for r in state[TABLE] if r['item_type_code'] == TYPE],
                  key=lambda r: (r['version_number'], str(r['status']), r.get('template_version_id', 0)))
    targets = []
    inventory = []
    warnings = []
    for row in rows:
        selected, reason = selection(row, usage)
        if not all(isinstance(row.get(f), str) for f in TITLES):
            selected, reason = False, 'unexpected_title_schema'
        inventory.append({
            'template_version_id': row.get('template_version_id'), **key(row),
            **{f: row.get(f) for f in TITLES}, 'selected': selected, 'reason': reason,
        })
        if selected:
            targets.append({'selector': key(row), 'before': row, 'after': {**row, **TITLES}})
    errors = []
    for name, observed in usage.items():
        if observed and observed.get('error'):
            errors.append(f'{name}: {observed["error"]}')
        elif observed and observed.get('template_version_id') is not None:
            if not any(e['before'].get('template_version_id') == observed['template_version_id'] for e in targets):
                errors.append(f'{name} selects a historical/unsupported version; inspect inventory before writing')
    if not rows:
        warnings.append('No stored childcare versions; built-in templates are not database versions and will not be created')
    if not any(str(r['status']).upper() == 'PUBLISHED' for r in rows):
        warnings.append('No PUBLISHED version. No publication will be performed; creation may use its built-in fallback')
    return {'format': FORMAT, 'item_type_code': TYPE, 'reader_usage': usage,
            'schema': schema or [],
            'current_columns': [f for f in CURRENT_FIELDS if any(f in r for r in rows) or any(c['column_name'] == f for c in (schema or []))],
            'versions': inventory, 'warnings': warnings, 'blocking_errors': errors, 'targets': targets}


def validate_plan(plan):
    require(plan.get('format') == FORMAT and plan.get('item_type_code') == TYPE, 'Wrong correction plan')
    require(isinstance(plan.get('targets'), list), 'Invalid targets')
    require(not plan.get('blocking_errors'), 'Installed readers disagree with safe selection; inspect preview')
    selectors = []
    for entry in plan['targets']:
        selector = entry['selector']
        require(selector['item_type_code'] == TYPE and selection(entry['before'], plan.get('reader_usage', {}))[0], 'Target out of scope')
        require(selector == key(entry['before']) == key(entry['after']), 'Selector changed')
        require(entry['after'] == {**entry['before'], **TITLES}, 'Plan contains changes outside approved titles')
        selectors.append(digest(selector))
    require(len(set(selectors)) == len(selectors), 'Duplicate plan selectors')


def write_plan(conn, state, plan, rollback=False):
    validate_plan(plan)
    expected = deepcopy(state)
    changed = []
    for entry in plan['targets']:
        rows = [r for r in state[TABLE] if key(r) == entry['selector']]
        require(len(rows) == 1, 'Stable selector is missing or not unique')
        before, after = (entry['after'], entry['before']) if rollback else (entry['before'], entry['after'])
        require(rows[0] == before, 'Template changed after planning/backup; refusing overwrite')
        if before != after:
            changed.append((entry['selector'], before, after))
    if changed:
        conn.execute(text(f'LOCK TABLE public.{TABLE} IN ACCESS EXCLUSIVE MODE'))
        guard_before = conn.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='public.personnel_order_template_versions'::regclass AND tgname=:name"), {'name': TRIGGER}).scalar_one_or_none()
        require(guard_before in (None, 'O'), 'Unexpected published-template guard state')
        # One maintenance transaction; any exception rolls the DDL back as well.
        if guard_before is not None:
            conn.execute(text(f'ALTER TABLE public.{TABLE} DISABLE TRIGGER {TRIGGER}'))
        for selector, before, after in changed:
            where = ' AND '.join(f'{field} IS NOT DISTINCT FROM :{field}' for field in selector)
            result = conn.execute(text(f"""UPDATE public.{TABLE}
                SET title_ru=:title_ru, title_kk=:title_kk
                WHERE {where}"""),
                {**selector, **{f: after[f] for f in TITLES}})
            require(result.rowcount == 1, 'Unexpected update count')
            expected[TABLE][expected[TABLE].index(before)] = after
        if guard_before is not None:
            conn.execute(text(f'ALTER TABLE public.{TABLE} ENABLE TRIGGER {TRIGGER}'))
        guard_after = conn.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='public.personnel_order_template_versions'::regclass AND tgname=:name"), {'name': TRIGGER}).scalar_one_or_none()
        require(guard_after == guard_before, 'Template guard was not restored')
    expected = {t: sorted(rows, key=digest) for t, rows in expected.items()}
    require(snapshot(conn) == expected, 'Unexpected change outside the two title fields; rolling back')
    return len(changed)


def make_report(plan, *, mode, updated=0):
    return {'format': FORMAT, 'mode': mode, 'updated_templates': updated,
        'planned_templates': sum(e['before'] != e['after'] for e in plan['targets']),
        **{f: plan[f] for f in ('schema', 'current_columns', 'versions', 'reader_usage', 'warnings', 'blocking_errors')},
        'targets': [{
            'template_version_id': e['before'].get('template_version_id'),
            'selector': e['selector'],
            'before': {f: e['after' if mode == 'rollback' else 'before'][f] for f in TITLES},
            'after': {f: e['before' if mode == 'rollback' else 'after'][f] for f in TITLES},
            'previous_package': {
                'russian_childcare_replacement_was_missing': True,
                'kazakh_title_would_have_been_skipped': e['before']['title_kk'] not in {
                    TITLES['title_kk'], 'Бала күтіміне байланысты жалақы сақталмайтын демалыс'},
            },
            'other_fields_sha256': digest({k:v for k,v in e['before'].items() if k not in TITLES}),
        } for e in plan['targets']],
        'existing_orders_modified': 0,
        'new_templates_created': 0,
        'only_title_fields_allowed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--rollback', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--expected-database', default='corpsite')
    args = parser.parse_args()
    require(engine.url.host in ('localhost','127.0.0.1','::1') and engine.url.database == args.expected_database,
            'Use the explicitly named database on its loopback host')
    if args.apply and (not args.plan or not args.backup):
        parser.error('--apply requires --plan and --backup')
    if not args.apply and not args.rollback and not args.plan:
        parser.error('Preview requires --plan')
    count = 0
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout='10s'"))
        if args.apply or args.rollback:
            conn.execute(text('LOCK TABLE '+','.join('public.'+t for t in table_names(conn))+' IN SHARE ROW EXCLUSIVE MODE'))
        else:
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        state = snapshot(conn)
        if args.rollback:
            plan = json.loads(args.rollback.read_text('utf-8'))
            count = write_plan(conn, state, plan, rollback=True)
        else:
            schema = [dict(r) for r in conn.execute(text("SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name=:table ORDER BY ordinal_position"), {'table': TABLE}).mappings()]
            plan = build_plan(state, reader_usage(conn), schema)
            if args.apply:
                validate_plan(plan)
                require(plan == json.loads(args.plan.read_text('utf-8')), 'Plan is stale; rebuild and review it')
                if any(e['before'] != e['after'] for e in plan['targets']):
                    save(args.backup, plan, exclusive=True)
                count = write_plan(conn, state, plan)
            else:
                save(args.plan, plan)
    mode = 'rollback' if args.rollback else 'apply' if args.apply else 'preview'
    report = make_report(plan, mode=mode, updated=count)
    report['all_other_data_verified_unchanged'] = bool(args.apply or args.rollback)
    save(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
