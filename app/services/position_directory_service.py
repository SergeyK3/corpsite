"""The single read/write contract for exact position variants and their families."""
import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import text

EDITABLE = ('name_kk', 'document_nominative_ru', 'document_possessive_kk',
            'translation_status', 'document_form_status', 'record_kind')


def normalize_alias(value):
    return re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def consumer_position(value):
    result = dict(value or {})
    if result.get('translation_status') == 'needs_review':
        result['name_kk'] = None
        result['job_namekk'] = None
    if result.get('document_form_status') == 'needs_review':
        result['document_possessive_kk'] = None
        result['job_namekk_doc'] = None
    return result


def resolve_existing_name(connection, name, exclude_id=None):
    """Search text is never allowed to silently create a second identity."""
    normalized = normalize_alias(name)
    matches = connection.execute(text('SELECT position_id,name FROM public.positions')).mappings()
    for row in matches:
        if row['position_id'] != exclude_id and normalize_alias(row['name']) == normalized:
            return int(row['position_id'])
    return connection.execute(text('SELECT position_id FROM public.position_aliases '
        'WHERE normalized_alias=:value AND (:id IS NULL OR position_id<>:id)'),
        {'value': normalized, 'id': exclude_id}).scalar()


def get_position(connection, position_id):
    row = connection.execute(text('SELECT * FROM public.position_directory WHERE position_id=:id'),
                             {'id': position_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Position not found.')
    result = dict(row)
    result['aliases'] = list(connection.execute(text('SELECT alias_text FROM public.position_aliases '
        'WHERE position_id=:id ORDER BY alias_id'), {'id': position_id}).scalars())
    return result


def save_details(connection, position_id, payload):
    """Called in the same transaction as the compatible RU/category mutation."""
    row = connection.execute(text('SELECT * FROM public.positions WHERE position_id=:id FOR UPDATE'),
                             {'id': position_id}).mappings().one()
    supplied = payload.model_fields_set
    changes = {key: getattr(payload, key) for key in EDITABLE if key in supplied}
    for key in ('name_kk', 'document_nominative_ru', 'document_possessive_kk'):
        if key in changes:
            changes[key] = (changes[key] or '').strip() or None
    state = {**row, **changes}
    if state['translation_status'] == 'confirmed' and not state['name_kk']:
        raise HTTPException(422, 'Confirmed Kazakh title must not be empty.')
    if state['document_form_status'] == 'confirmed' and not state['document_possessive_kk']:
        raise HTTPException(422, 'Confirmed Kazakh document form must not be empty.')
    if changes:
        connection.execute(text('UPDATE public.positions SET '+', '.join(f'{k}=:{k}' for k in changes)
            +' WHERE position_id=:id'), {'id': position_id, **changes})
    if 'job_code' in supplied:
        code = (payload.job_code or '').strip() or None
        if code and not connection.execute(text('SELECT 1 FROM public.job_positions_catalog WHERE job_code=:code'),
                                          {'code': code}).first():
            raise HTTPException(422, 'Unknown position family.')
        if code:
            connection.execute(text('INSERT INTO public.position_job_catalog(position_id,job_code) '
                'VALUES (:id,:code) ON CONFLICT(position_id) DO UPDATE SET job_code=excluded.job_code'),
                {'id': position_id, 'code': code})
        else:
            connection.execute(text('DELETE FROM public.position_job_catalog WHERE position_id=:id'), {'id': position_id})
    if 'aliases' in supplied:
        aliases = {normalize_alias(v): v.strip() for v in payload.aliases if v.strip()}
        if '' in aliases:
            raise HTTPException(422, 'Empty search synonym.')
        for normalized in aliases:
            if len(aliases[normalized])>500 or resolve_existing_name(connection, aliases[normalized], position_id):
                raise HTTPException(409, 'Search synonym conflicts with another position.')
            other = connection.execute(text('SELECT position_id FROM public.position_aliases '
                'WHERE normalized_alias=:value AND position_id<>:id'), {'value': normalized,'id': position_id}).first()
            if other:
                raise HTTPException(409, 'Search synonym belongs to another position.')
        connection.execute(text('DELETE FROM public.position_aliases WHERE position_id=:id'), {'id': position_id})
        for normalized, label in aliases.items():
            connection.execute(text('INSERT INTO public.position_aliases(position_id,alias_text,normalized_alias) '
                'VALUES (:id,:label,:normalized)'), {'id': position_id, 'label': label, 'normalized': normalized})
    return get_position(connection, position_id)
