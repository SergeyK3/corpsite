"""Proposed genuine stage-3 upgrade of the verified local snapshot.

Does not claim that the canonical ancestors of hrrecall001 were executed.
Must be rehearsed on a restored copy before authorization for working corpsite.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = 'hrlocal301'
down_revision = 'za0b1c2d3e4f'
branch_labels = None
depends_on = None

ROOT = Path(__file__).resolve().parents[3]
PREPARATION = ROOT / 'runtime/personnel-stage3-preparation'
TABLES = ['org_units', 'personnel_section_settings', 'personnel_order_templates',
          'personnel_order_template_versions', 'personnel_orders', 'personnel_order_items']


def fingerprints(conn, names, *, after=False):
    result = {}
    for name in names:
        quoted = conn.dialect.identifier_preparer.quote(name)
        expression = 'to_jsonb(t)'
        if after and name == 'personnel_order_template_versions':
            expression += " - 'template_id'"
        if after and name == 'personnel_orders':
            expression += " - 'selected_template_version_id'"
        digest = hashlib.sha256()
        count = 0
        for row in conn.execute(text(f'SELECT ({expression})::text FROM public.{quoted} t ORDER BY ({expression})::text')):
            digest.update(row[0].encode('utf-8') + b'\n')
            count += 1
        result[name] = {'count': count, 'sha256': digest.hexdigest()}
    return result


def validate_baseline(conn, expected):
    if conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all() != expected['revision']:
        raise RuntimeError('STOP: baseline revision changed')
    queries = {
        'columns': '''SELECT table_name,column_name,data_type,character_maximum_length,is_nullable,column_default
            FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(:tables)
            ORDER BY table_name,ordinal_position''',
        'constraints': '''SELECT conrelid::regclass::text AS table_name,conname,contype,convalidated,
            pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE connamespace='public'::regnamespace
            AND conrelid::regclass::text=ANY(:tables) ORDER BY conrelid::regclass::text,conname''',
        'indexes': '''SELECT tablename,indexname,indexdef FROM pg_indexes
            WHERE schemaname='public' AND tablename=ANY(:tables) ORDER BY tablename,indexname''',
        'triggers': '''SELECT tgrelid::regclass::text AS table_name,tgname,tgenabled,
            pg_get_triggerdef(oid) AS definition FROM pg_trigger WHERE NOT tgisinternal
            AND tgrelid::regclass::text=ANY(:tables) ORDER BY tgrelid::regclass::text,tgname''',
    }
    for key, query in queries.items():
        actual = [dict(r) for r in conn.execute(text(query), {'tables': TABLES}).mappings()]
        def normalized(rows):
            result = [dict(row) for row in rows]
            # pg_dump/restore reparses this one expression: array cast becomes
            # casts on individual elements. Admit only these two exact forms.
            equivalents = {
                "CHECK (((language)::text = ANY ((ARRAY['kk'::character varying, 'ru'::character varying])::text[])))",
                "CHECK (((language)::text = ANY (ARRAY[('kk'::character varying)::text, ('ru'::character varying)::text])))",
            }
            for row in result:
                if (key == 'constraints' and row['table_name'] == 'personnel_section_settings'
                        and row['conname'] == 'personnel_section_settings_language_check'
                        and row['definition'] in equivalents):
                    row['definition'] = 'verified_language_check_ru_kk'
            return result
        if normalized(actual) != normalized(expected[key]):
            raise RuntimeError(f'STOP: {key} differ from the reviewed physical snapshot')
    names = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
    if names != sorted(expected['fingerprints']):
        raise RuntimeError('STOP: public table inventory changed')
    if fingerprints(conn, names) != expected['fingerprints']:
        raise RuntimeError('STOP: data changed; take a fresh backup and review a fresh snapshot')


def upgrade():
    expected = json.loads((PREPARATION / 'preflight.json').read_text(encoding='utf-8'))
    manifest = json.loads((PREPARATION / 'recovery-manifest.json').read_text(encoding='utf-8'))
    backup = PREPARATION / 'corpsite-before-stage3.dump'
    if not backup.is_file() or hashlib.sha256(backup.read_bytes()).hexdigest() != manifest['backup']['sha256']:
        raise RuntimeError('STOP: the reviewed backup is missing or changed')
    for relative, digest in manifest['files'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'STOP: reviewed preparation file changed: {relative}')
    conn = op.get_bind()
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    conn.execute(text("SET LOCAL statement_timeout='120s'"))
    conn.execute(text('LOCK TABLE public.personnel_order_template_versions, public.personnel_orders, public.personnel_order_items IN ACCESS EXCLUSIVE MODE'))
    validate_baseline(conn, expected)
    # orgkk001 and hrlang001 are physically present; the exact snapshot above
    # validates their objects and preserves the current language, including ru.
    for name in ['hrtpl001_independent_personnel_templates.py', 'hrrecall001_annual_leave_recall_drafts.py']:
        source = ROOT / 'alembic/versions' / name
        spec = importlib.util.spec_from_file_location(name[:-3], source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.upgrade()
    if fingerprints(conn, expected['fingerprints'], after=True) != expected['fingerprints']:
        raise RuntimeError('STOP: old data changed; rollback the complete upgrade')
    if conn.execute(text('SELECT count(*) FROM personnel_order_template_versions WHERE template_id IS NULL')).scalar_one():
        raise RuntimeError('STOP: missing template identity')
    if conn.execute(text('''SELECT count(*) FROM personnel_order_template_versions v
        JOIN personnel_order_templates t ON t.template_id=v.template_id
        WHERE v.item_type_code<>t.item_type_code''')).scalar_one():
        raise RuntimeError('STOP: mismatched template type')


def downgrade():
    raise RuntimeError('Recovery downgrade is not automatic; restore the verified pre-upgrade backup')
