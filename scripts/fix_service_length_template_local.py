"""Repair only local unused DRAFT 43/58; never publish or create orders."""
from argparse import Namespace
import hashlib
import json
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db.engine import engine
from app.services.personnel_order_service_length_contract import TYPE, bind_editor_texts
from app.services.personnel_order_template_validation import TEXT_FIELDS, validate_template_texts


def protected(conn):
    filters = {'personnel_order_template_versions': 'WHERE template_version_id<>58',
               'personnel_order_templates': 'WHERE template_id<>43'}
    return {table: hashlib.sha256('\n'.join(conn.execute(text(
        f'SELECT to_jsonb(t)::text FROM {table} t {filters.get(table, "")} ORDER BY to_jsonb(t)::text'
    )).scalars()).encode()).hexdigest() for table in (
        'personnel_order_template_versions', 'personnel_order_templates', 'personnel_orders',
        'personnel_order_items', 'personnel_order_template_applications',
        'employees', 'persons', 'person_assignments', 'employee_events')}


def main():
    assert engine.url.host in {'localhost', '127.0.0.1', '::1'} and engine.url.database == 'corpsite'
    folder = ROOT / 'runtime/service-length-review'
    folder.mkdir(exist_ok=True)
    with engine.connect() as conn:
        before = protected(conn)
        source = dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_id=43 AND template_version_id=58')).mappings().one())
        identity = dict(conn.execute(text('SELECT * FROM personnel_order_templates WHERE template_id=43')).mappings().one())
        assert source['status'] == 'DRAFT' and source['published_at'] is None
        assert source['title_ru'] == 'Об изменении стажа'
        assert source['item_type_code'] in {'QUALIFICATION_CATEGORY', TYPE}
        assert not identity['is_default']
        assert conn.execute(text('SELECT count(*) FROM personnel_order_template_versions WHERE template_id=43')).scalar_one() == 1
        assert not conn.execute(text('SELECT EXISTS(SELECT 1 FROM personnel_orders WHERE selected_template_version_id=58) OR EXISTS(SELECT 1 FROM personnel_order_template_applications WHERE template_version_id=58)')).scalar_one()
    values = bind_editor_texts(source)
    for locale in ('ru', 'kk'):
        key = 'basis_template_' + locale
        inherited = {'ru': 'Основание: Сертификат № KZ0000000000000 от ', 'kk': 'Негіз:  № KZ0000000000000 сертификат.'}[locale]
        if values[key] == inherited:
            values[key] = ('Основание: ' if locale == 'ru' else 'Негіз: ') + '{{basis.' + locale + '}}.'
        # Reuse the entered subject of this exact draft, without inventing a translation.
        values['print_title_' + locale] = source['title_' + locale]
    validate_template_texts(TYPE, {key: values[key] for key in TEXT_FIELDS})
    changed = {key: {'before': source.get(key), 'after': values.get(key)} for key in (*TEXT_FIELDS, 'print_title_ru', 'print_title_kk') if values.get(key) != source.get(key)}
    if '--apply' not in sys.argv:
        print(json.dumps(dict(template_id=43, template_version_id=58, target_type=TYPE, changed_fields=list(changed), action='CHECK_ONLY'), ensure_ascii=True))
        return
    if source['item_type_code'] == TYPE and not changed:
        print('Already repaired; no changes')
        return
    (folder / 'local-draft-before.json').write_text(json.dumps(source, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
    (folder / 'local-identity-before.json').write_text(json.dumps(identity, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'scripts/personnel_stage3_local_recovery'))
    config.cmd_opts = Namespace(x=['approved_local_recovery=1'])
    command.upgrade(config, 'hrlocal306')
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout='5s'"))
        current = dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=58 FOR UPDATE')).mappings().one())
        assert current == source, 'Draft changed during verification; preserve the newer edits'
        assert protected(conn) == before, 'Protected rows changed concurrently; retry after review'
        conn.execute(text('SET CONSTRAINTS fk_personnel_template_version_template DEFERRED'))
        conn.execute(text('UPDATE personnel_order_templates SET item_type_code=:code WHERE template_id=43'), {'code': TYPE})
        keys = (*TEXT_FIELDS, 'print_title_ru', 'print_title_kk')
        conn.execute(text('UPDATE personnel_order_template_versions SET item_type_code=:code,' + ','.join(key + '=:' + key for key in keys) + ',revision=revision+1,updated_at=now() WHERE template_version_id=58 AND template_id=43 AND status=\'DRAFT\''), {**{key: values[key] for key in keys}, 'code': TYPE})
        conn.execute(text('SET CONSTRAINTS fk_personnel_template_version_template IMMEDIATE'))
        assert protected(conn) == before
        after = dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=58')).mappings().one())
    report = dict(template_id=43, template_version_id=58, status=after['status'], item_type_code=TYPE,
        revision=after['revision'], changed_fields=changed, protected_hashes=before, protected_unchanged=True,
        published=False, real_order_created=False, schema_revision='hrlocal306')
    (folder / 'local-draft-after.json').write_text(json.dumps(after, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
    (folder / 'local-repair-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(template_id=43, template_version_id=58, status=after['status'], type=TYPE, revision=after['revision'], protected_unchanged=True)))


if __name__ == '__main__':
    main()
