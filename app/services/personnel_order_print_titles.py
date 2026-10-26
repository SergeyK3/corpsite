"""Official headings are explicit version data, independent of internal names."""
PRINT_TITLE_FIELDS = ('print_title_ru', 'print_title_kk')

# Explicit document headings for new built-in drafts, never a transformation
# of an internal name. Existing versions and order snapshots are not backfilled.
INITIAL_PRINT_TITLES_RU = {
    'HIRE': 'О приёме на работу',
    'TRANSFER': 'О переводе',
    'TERMINATION': 'Об увольнении',
    'CONCURRENT_DUTY_START': 'О совмещении',
    'CONCURRENT_DUTY_END': 'О прекращении совмещения',
    'LEAVE.ANNUAL.GRANT': 'О трудовом отпуске',
    'LEAVE.UNPAID.GRANT': 'Об отпуске без содержания',
    'LEAVE.CHILDCARE.GRANT': 'О неоплачиваемом отпуске по уходу за ребенком',
    'LEAVE.ANNUAL.RECALL': 'Об отзыве из отпуска',
    'SUPPLEMENTARY_PAY': 'О дополнительной оплате',
    'RETURN_FROM_CHILDCARE_LEAVE': 'О выходе на работу из отпуска по уходу за ребёнком',
}
VARIANT_PRINT_TITLES_RU = {
    ('CONCURRENT_DUTY_START', 'О совмещении (О замещении на время отпуска как доп ставка)'): 'О замещении',
}
APPROVED_VARIANT_PRINT_TITLES = {
    ('CONCURRENT_DUTY_START', 'О совмещении (простой, как по доп ставке)'):
        {'print_title_ru':'О совмещении','print_title_kk':'Қоса атқару туралы'},
}


def initial_print_titles(item_type_code, internal_name_ru=None):
    approved = APPROVED_VARIANT_PRINT_TITLES.get((item_type_code, internal_name_ru))
    if approved is not None:
        return dict(approved)
    return {'print_title_ru': VARIANT_PRINT_TITLES_RU.get((item_type_code, internal_name_ru), INITIAL_PRINT_TITLES_RU.get(item_type_code)),
            'print_title_kk': None}  # A new variant needs an explicitly approved KK heading.


def approved_variant_print_titles(item_type_code, internal_name_ru):
    return dict(APPROVED_VARIANT_PRINT_TITLES.get((item_type_code, internal_name_ru), {}))


def version_print_titles(version):
    """Apply an explicit approved pair to a known immutable published version.

    This read projection never rewrites a version or an existing order snapshot.
    Other templates/locales still require their own approved values.
    """
    result=dict(version)
    if str(version.get('status') or '').upper() in {'PUBLISHED','ARCHIVED'}:
        for field,value in approved_variant_print_titles(version.get('item_type_code'),version.get('title_ru')).items():
            if not str(result.get(field) or '').strip():
                result[field]=value
    return result


def print_title_errors(template):
    return [f'Печатный заголовок {locale.upper()}: требуется согласование.'
            for locale in ('ru', 'kk')
            if not str(template.get(f'print_title_{locale}') or '').strip()]


def printable_template(template, *, preview=False):
    result = dict(template)
    # Old in-memory/archival snapshots have only the historical paper headings.
    # Live version rows are normalized with explicit print-title keys by resolver.
    if not any(key in template for key in PRINT_TITLE_FIELDS):
        return result
    errors = print_title_errors(template)
    if errors and not preview:
        raise ValueError(' '.join(errors))
    for locale in ('ru', 'kk'):
        result[f'title_{locale}'] = str(template.get(f'print_title_{locale}') or '').strip() or f'[Печатный заголовок {locale.upper()}: требуется согласование]'
    return result


def template_text_snapshot(template, text_fields):
    snapshot = {key: template[key] for key in text_fields}
    if template.get('_print_title_source') != 'LEGACY':
        snapshot.update({key: template.get(key) for key in PRINT_TITLE_FIELDS})
    return snapshot


def rendered_order_snapshot(proposed, template):
    """Keep the actual paper headings in the order-level immutable snapshot."""
    result = dict(proposed)
    if template.get('_print_title_source') != 'LEGACY':
        result.update({f'print_title_{locale}': proposed.get(f'title_{locale}') for locale in ('ru', 'kk')})
    return result


def order_print_title_snapshot(application, *, composite=False):
    """Read frozen fields only; never consult today's mutable template name."""
    snapshot = application.get('template_snapshot') or {}
    rendered = (application.get('rendered_snapshot') or {}).get('order') or {}
    source = rendered if any(key in rendered for key in PRINT_TITLE_FIELDS) else ({} if composite else snapshot)
    legacy = not any(key in source for key in PRINT_TITLE_FIELDS)
    titles = {key: source.get(key) if not legacy else None for key in PRINT_TITLE_FIELDS}
    missing = [locale for locale in ('ru', 'kk') if not str(titles[f'print_title_{locale}'] or '').strip()]
    return {'template_version_id': application['template_version_id'], **titles,
            'template_title_ru': snapshot.get('title_ru'), 'template_title_kk': snapshot.get('title_kk'),
            'legacy': legacy, 'requires_update': bool(missing), 'missing_locales': missing}


def load_order_print_title_snapshot(conn, order_id, items, *, composite=False):
    from sqlalchemy import text
    active = [item for item in items if str(item.get('item_status') or '').upper() == 'ACTIVE']
    if not active or not conn.execute(text("SELECT to_regclass('public.personnel_order_template_applications')")).scalar_one():
        return None
    first = min(active, key=lambda item: (item['item_number'], item['item_id']))
    applications = conn.execute(text('''SELECT template_version_id,order_item_id,template_snapshot,rendered_snapshot
        FROM public.personnel_order_template_applications WHERE order_id=:id
        ORDER BY applied_at DESC,template_application_id DESC'''), {'id':order_id}).mappings().all()
    for application in applications:
        covered = {application['order_item_id']}
        covered.update(item.get('order_item_id') for item in (application.get('rendered_snapshot') or {}).get('items', []) if isinstance(item,dict))
        if first['item_id'] in covered:
            return order_print_title_snapshot(application,composite=composite)
    return None


def pin_print_titles(template, snapshot=None, rendered=None):
    """Use the order's own snapshot even if the directory/version is changed."""
    result = dict(template)
    result['_print_title_source'] = 'SNAPSHOT' if snapshot is not None else 'VERSION'
    if snapshot is not None and not any(key in snapshot or key in (rendered or {}) for key in PRINT_TITLE_FIELDS):
        result['_print_title_source'] = 'LEGACY'
    for locale in ('ru', 'kk'):
        key = f'print_title_{locale}'
        if snapshot is not None:
            result[key] = ((rendered or {})[key] if key in (rendered or {}) else
                           snapshot[key] if key in snapshot else
                           (rendered or {}).get(f'title_{locale}', snapshot.get(f'title_{locale}')))
        else:
            result.setdefault(key, None)
    return result
