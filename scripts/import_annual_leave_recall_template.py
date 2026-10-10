"""Import the reviewed recall texts through the installed draft service only."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import sys

SOURCE_SHA256 = 'a4b26bdea3b7cf275ce4fb3a0d5571f0c1dd9cc9c233cb426ad0f84efbc44796'
CODE = 'LEAVE.ANNUAL.RECALL'
FIELDS = ('title_ru', 'title_kk', 'preamble_ru', 'preamble_kk',
          'body_template_ru', 'body_template_kk', 'basis_template_ru', 'basis_template_kk')


def require(condition, message):
    if not condition:
        raise RuntimeError('STOP: ' + message)


def read_source(path):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, 'reviewed JSON SHA256 differs')
    data = json.loads(raw)
    require(data['format'] == 'personnel-template-texts-v1' and data['item_type_code'] == CODE,
            'unexpected source format/type')
    require(set(data['texts']) == set(FIELDS) and all(isinstance(data['texts'][f], str) for f in FIELDS),
            'exactly eight text fields required')
    require(data['import_policy'] == {'create_independent_draft': True, 'publish': False},
            'unexpected import policy')
    return data


class TransactionEngine:
    """Keep the service's begin/connect calls in one caller-owned transaction."""
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        return nullcontext(self.conn)

    def connect(self):
        return nullcontext(self.conn)


def run_import(conn, service, data, *, apply=False, verify_only=False, actor_login=None, receipt=None):
    from sqlalchemy import text
    require(conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all()
            == ['hrjobmerge001'], 'expected installed hrjobmerge001; no migrations performed')
    if apply:
        # All template writers are excluded until read-back and preservation checks finish.
        conn.execute(text('LOCK TABLE public.personnel_order_templates, '
                          'public.personnel_order_template_versions IN SHARE ROW EXCLUSIVE MODE'))
    templates = [dict(r) for r in conn.execute(text(
        'SELECT * FROM public.personnel_order_templates ORDER BY template_id')).mappings()]
    versions = [dict(r) for r in conn.execute(text(
        'SELECT * FROM public.personnel_order_template_versions ORDER BY template_version_id')).mappings()]
    candidates = [t for t in templates if t['item_type_code'] == CODE and not t['is_default']
                  and (t['name_ru'] == data['name_ru'] or t['name_kk'] == data['name_kk'])]
    if receipt and receipt.get('template_id') is not None:
        require(receipt.get('source_sha256') == SOURCE_SHA256, 'receipt belongs to another source')
        matches = [t for t in templates if t['template_id'] == receipt['template_id']]
        require(len(matches) == 1, 'previously imported template missing; refusing to recreate')
        require(matches[0] in candidates, 'previously imported template names/type changed')
    require(len(candidates) <= 1, 'ambiguous independent templates with the reviewed names')
    # Preview validation is performed before any write, using the installed service.
    expected_previews = service.preview_draft(CODE, data['texts'])
    require(set(expected_previews) == {'ru', 'kk'}, 'both previews required')
    for locale, preview in expected_previews.items():
        require(all(preview.get(k) for k in ('title', 'preamble', 'body', 'basis')),
                locale + ' preview incomplete')
        require(not any('{{' in str(v) or '}}' in str(v) for v in preview.values()),
                locale + ' preview has unresolved variables')
    old_engine = service.engine
    service.engine = TransactionEngine(conn)
    try:
        action = 'EXISTS' if candidates else 'WOULD_CREATE'
        if not candidates and verify_only:
            raise RuntimeError('STOP: imported independent template not found')
        if not candidates and apply:
            actor = conn.execute(text('SELECT user_id FROM public.users '
                'WHERE login=:login AND is_active=TRUE'), {'login': actor_login}).scalar_one_or_none()
            require(actor is not None, 'active actor login not found')
            # INITIAL copying can create a default identity. Select an existing
            # supported default instead, so this import adds exactly one identity.
            from app.services.personnel_order_template_specs import get_personnel_order_template_spec
            bases = []
            for t in templates:
                if t['is_default']:
                    try:
                        get_personnel_order_template_spec(t['item_type_code'])
                    except ValueError:
                        continue
                    bases.append(t)
            require(bases, 'no existing editable default base; refusing to create extra templates')
            base = next((t for t in bases if t['item_type_code'] == CODE), bases[0])
            created = service.copy_template(CODE, None, data['name_ru'], data['name_kk'],
                actor, None, base_source='INITIAL', source_type_code=base['item_type_code'])
            service.save_draft(CODE, created['revision'], data['texts'], actor,
                created['template_id'], expected_template_version_id=created['template_version_id'])
            candidates = [dict(conn.execute(text('SELECT * FROM public.personnel_order_templates '
                'WHERE template_id=:id'), {'id': created['template_id']}).mappings().one())]
            action = 'CREATED'
        result = {'action': action, 'source_sha256': SOURCE_SHA256, 'item_type_code': CODE,
                  'template_id': None, 'template_version_id': None, 'published': False,
                  'previews': expected_previews, 'all_eight_fields_verified': False}
        if candidates:
            t = candidates[0]
            require(t['name_ru'] == data['name_ru'] and t['name_kk'] == data['name_kk']
                    and not t['is_default'] and t['item_type_code'] == CODE, 'identity changed')
            saved_versions = service.list_versions(CODE, t['template_id'])
            require(len(saved_versions) == 1, 'expected exactly one version; existing template untouched')
            v = saved_versions[0]
            require(v['version_number'] == 1 and v['status'] == 'DRAFT'
                    and v['published_at'] is None and v['published_by_user_id'] is None,
                    'expected unpublished draft v1; existing template untouched')
            require(all(v[f] == data['texts'][f] for f in FIELDS),
                    'saved texts differ; existing template untouched')
            if receipt and receipt.get('template_version_id') is not None:
                require(v['template_version_id'] == receipt['template_version_id'], 'version identity changed')
            actual_previews = service.preview_draft(CODE, {f: v[f] for f in FIELDS})
            require(actual_previews == expected_previews, 'saved previews differ')
            result.update(template_id=t['template_id'], template_version_id=v['template_version_id'],
                          version_number=1, status='DRAFT', revision=v['revision'],
                          all_eight_fields_verified=True, saved_fields={f: v[f] for f in FIELDS},
                          previews=actual_previews)
        after_t = [dict(r) for r in conn.execute(text(
            'SELECT * FROM public.personnel_order_templates ORDER BY template_id')).mappings()]
        after_v = [dict(r) for r in conn.execute(text(
            'SELECT * FROM public.personnel_order_template_versions ORDER BY template_version_id')).mappings()]
        if action == 'CREATED':
            require(len(after_t) == len(templates) + 1 and len(after_v) == len(versions) + 1,
                    'unexpected extra templates/versions')
            after_t = [t for t in after_t if t['template_id'] != result['template_id']]
            after_v = [v for v in after_v if v['template_version_id'] != result['template_version_id']]
        require(after_t == templates and after_v == versions, 'existing templates/versions changed')
        result['existing_templates_unchanged'] = True
        return result
    finally:
        service.engine = old_engine


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--source', type=Path, default=Path(__file__).with_name('annual-leave-recall.json'))
    p.add_argument('--report', type=Path)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--verify-only', action='store_true')
    modes.add_argument('--list-actors', action='store_true')
    p.add_argument('--actor-login')
    args = p.parse_args()
    require(args.repo.is_dir() and (args.repo / 'app').is_dir(), 'installed repository required')
    require(args.list_actors or args.report is not None, '--report required')
    require(not args.apply or bool(args.actor_login), '--actor-login required for apply')
    data = read_source(args.source)
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url
    config = dotenv_values(args.repo / '.env')
    require(bool(config.get('DATABASE_URL')), 'DATABASE_URL missing from repository .env')
    url = make_url(config['DATABASE_URL'])
    require(url.get_backend_name() == 'postgresql' and url.host in {'localhost', '127.0.0.1', '::1'}
            and url.database == 'corpsite', 'expected loopback PostgreSQL corpsite from repository .env')
    os.environ['DATABASE_URL'] = config['DATABASE_URL']
    os.environ['CORPSITE_SKIP_DOTENV'] = '1'
    sys.path.insert(0, str(args.repo.resolve()))
    from app.services import personnel_order_template_draft_service as service
    from sqlalchemy import text
    receipt = None
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        if args.report.exists():
            receipt = json.loads(args.report.read_text(encoding='utf8'))
        # Fail on an unwritable report directory before starting the import.
        from tempfile import TemporaryFile
        with TemporaryFile(dir=args.report.parent):
            pass
    with service.engine.begin() as conn:
        if not args.apply:
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        conn.execute(text("SET LOCAL lock_timeout='10s'"))
        conn.execute(text('SET LOCAL row_security=off'))
        if args.list_actors:
            rows = conn.execute(text('SELECT u.user_id,u.login,u.full_name,r.name AS role_name '
                'FROM public.users u LEFT JOIN public.roles r ON r.role_id=u.role_id '
                'WHERE u.is_active=TRUE ORDER BY u.login')).mappings()
            print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
            return
        result = run_import(conn, service, data, apply=args.apply, verify_only=args.verify_only,
                            actor_login=args.actor_login, receipt=receipt)
    result['committed'] = args.apply and result['action'] == 'CREATED'
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w', encoding='utf8', newline='\n',
                            dir=args.report.parent, delete=False) as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        temp = Path(handle.name)
    temp.replace(args.report)
    print(json.dumps({k: result[k] for k in ('action', 'template_id', 'template_version_id',
        'published', 'all_eight_fields_verified', 'existing_templates_unchanged', 'committed')},
        ensure_ascii=False, indent=2))
    print('Full RU/KZ previews and receipt: ' + str(args.report))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # SQLAlchemy exceptions may include SQL/parameters; do not print credentials.
        if isinstance(exc, (RuntimeError, ValueError)):
            print(str(exc), file=sys.stderr)
        else:
            print('STOP: ' + type(exc).__name__ + '; database transaction failed or report could not be saved', file=sys.stderr)
        sys.exit(1)
