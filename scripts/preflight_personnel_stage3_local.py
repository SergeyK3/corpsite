"""Read-only inventory for the local stage-3 recovery. Never runs migrations."""
import hashlib
import json
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    root = Path(__file__).resolve().parents[1]
    url = make_url(dotenv_values(root / '.env')['DATABASE_URL'])
    if url.host not in {'localhost', '127.0.0.1', '::1'} or url.database != 'corpsite':
        raise SystemExit('STOP: expected loopback corpsite')
    report = {}
    with create_engine(url).connect() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        report['revision'] = conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all()
        tables = ['org_units', 'personnel_section_settings', 'personnel_order_templates',
                  'personnel_order_template_versions', 'personnel_orders', 'personnel_order_items']
        report['columns'] = [dict(r) for r in conn.execute(text('''
            SELECT table_name,column_name,data_type,character_maximum_length,is_nullable,column_default
            FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(:tables)
            ORDER BY table_name,ordinal_position
        '''), {'tables': tables}).mappings()]
        report['constraints'] = [dict(r) for r in conn.execute(text('''
            SELECT conrelid::regclass::text AS table_name,conname,contype,convalidated,
                   pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE connamespace='public'::regnamespace
              AND conrelid::regclass::text=ANY(:tables) ORDER BY conrelid::regclass::text,conname
        '''), {'tables': tables}).mappings()]
        report['indexes'] = [dict(r) for r in conn.execute(text('''
            SELECT tablename,indexname,indexdef FROM pg_indexes
            WHERE schemaname='public' AND tablename=ANY(:tables) ORDER BY tablename,indexname
        '''), {'tables': tables}).mappings()]
        report['triggers'] = [dict(r) for r in conn.execute(text('''
            SELECT tgrelid::regclass::text AS table_name,tgname,tgenabled,
                   pg_get_triggerdef(oid) AS definition
            FROM pg_trigger WHERE NOT tgisinternal AND tgrelid::regclass::text=ANY(:tables)
            ORDER BY tgrelid::regclass::text,tgname
        '''), {'tables': tables}).mappings()]
        report['versions_by_type'] = [dict(r) for r in conn.execute(text('''
            SELECT item_type_code,status,count(*) AS count FROM personnel_order_template_versions
            GROUP BY item_type_code,status ORDER BY item_type_code,status
        ''')).mappings()]
        report['invalid_template_names'] = conn.execute(text('''
            SELECT count(*) FROM personnel_order_template_versions
            WHERE title_ru IS NULL OR btrim(title_ru)='' OR title_kk IS NULL OR btrim(title_kk)=''
        ''')).scalar_one()
        report['duplicate_version_numbers'] = [list(r) for r in conn.execute(text('''
            SELECT item_type_code,version_number,count(*) FROM personnel_order_template_versions
            GROUP BY item_type_code,version_number HAVING count(*)>1
        '''))]
        report['language_rows'] = [dict(r) for r in conn.execute(text('SELECT * FROM personnel_section_settings')).mappings()]
        report['fingerprints'] = {}
        # All old public tables, including users and events, without exporting row contents.
        names = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
        for name in names:
            quoted = conn.dialect.identifier_preparer.quote(name)
            digest = hashlib.sha256()
            count = 0
            for row in conn.execute(text(f'SELECT to_jsonb(t)::text FROM public.{quoted} t ORDER BY to_jsonb(t)::text')):
                digest.update(row[0].encode('utf-8') + b'\n')
                count += 1
            report['fingerprints'][name] = {'count': count, 'sha256': digest.hexdigest()}
    output = root / 'runtime/personnel-stage3-preparation/preflight.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(output), 'revision': report['revision'],
                      'tables': len(report['fingerprints']), 'versions_by_type': report['versions_by_type'],
                      'invalid_template_names': report['invalid_template_names'],
                      'duplicate_version_numbers': report['duplicate_version_numbers'],
                      'language_rows': report['language_rows']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
