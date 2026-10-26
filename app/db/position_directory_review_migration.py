"""Canonical posdir001 policy v2; keep the applied local v1 helper immutable.

Text values still come from the existing directory/catalog. The view comment is
a transactional receipt: repeats must not reset subsequent human confirmations.
Legacy schemas require a separate, explicitly reviewed, drift-checked transition.
"""
from sqlalchemy import text
from app.db.position_directory_migration import upgrade as legacy_upgrade
from app.db.position_directory_migration import downgrade

POLICY = 'posdir001:forms-needs-review:v2'
REVIEW_COLUMNS = {'document_nominative_ru','document_possessive_kk','translation_status',
                  'document_form_status','record_kind','revision'}
ROW_FIELDS = ('position_id','name','category','name_kk','document_nominative_ru',
              'document_possessive_kk','translation_status','document_form_status','record_kind','revision')


def _receipt(connection):
    return connection.execute(text("SELECT obj_description(to_regclass('public.position_directory'),'pg_class')")).scalar()


def _mark(connection):
    connection.execute(text("COMMENT ON VIEW public.position_directory IS 'posdir001:forms-needs-review:v2'"))


def upgrade(connection):
    columns=set(connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='positions'")).scalars())
    if _receipt(connection)==POLICY:
        if not REVIEW_COLUMNS.issubset(columns):
            raise RuntimeError('Position review policy receipt conflicts with the actual schema')
        return  # No refill, no status reset, and no sequence consumption.
    if REVIEW_COLUMNS & columns:
        raise RuntimeError('Existing position-directory schema requires an owner-reviewed status transition; do not stamp or reset confirmed rows')
    # Preserve supplied legacy text byte-for-byte, including surrounding spaces.
    existing={r['position_id']:r['name_kk'] for r in connection.execute(text('SELECT position_id,name_kk FROM public.positions WHERE NULLIF(btrim(name_kk),\'\') IS NOT NULL')).mappings()}
    legacy_upgrade(connection)
    for position_id,value in existing.items():
        connection.execute(text('UPDATE public.positions SET name_kk=:value WHERE position_id=:id'),{'id':position_id,'value':value})
    # Canonical migration has just created these status fields. No prior human
    # confirmation exists in them; catalog presence does not constitute review.
    connection.execute(text("UPDATE public.positions SET translation_status='needs_review',document_form_status='needs_review'"))
    _mark(connection)


def review_existing_directory(connection,manifest):
    """Explicit future local transition, never invoked implicitly by upgrade().

Require a reviewed decision for every legacy row, exact before values and an
explicit justification for every retained confirmed status. Texts/IDs/links are
not editable through this operation. Caller owns the transaction.
"""
    if _receipt(connection)==POLICY:return
    if manifest.get('policy')!=POLICY or manifest.get('owner_approved') is not True:
        raise RuntimeError('An explicitly owner-approved legacy review manifest is required')
    rows=[dict(r) for r in connection.execute(text('SELECT '+','.join(ROW_FIELDS)+' FROM public.positions ORDER BY position_id FOR UPDATE')).mappings()]
    decisions=manifest.get('positions',[])
    ids=[d['before']['position_id'] for d in decisions]
    if len(set(ids))!=len(ids) or set(ids)!={r['position_id'] for r in rows}:
        raise RuntimeError('Legacy transition must cover every position exactly once')
    indexed={d['before']['position_id']:d for d in decisions}
    # Validate the complete set before any write; revision is not used as an
    # unreliable guess whether a legacy confirmed value was manual or generated.
    for row in rows:
        decision=indexed[row['position_id']]
        if decision['before']!=row:raise RuntimeError('Legacy position changed since owner review')
        for status,value_field in (('translation_status','name_kk'),('document_form_status','document_possessive_kk')):
            target=decision.get(status)
            if target not in ('needs_review','confirmed'):raise RuntimeError('Invalid reviewed status')
            if target=='confirmed' and (not str(row[value_field] or '').strip() or not decision.get('confirmation_evidence')):
                raise RuntimeError('Confirmed legacy text requires a nonempty value and explicit review evidence')
    for row in rows:
        decision=indexed[row['position_id']]
        if any(row[k]!=decision[k] for k in ('translation_status','document_form_status')):
            connection.execute(text('UPDATE public.positions SET translation_status=:translation_status,document_form_status=:document_form_status,revision=revision+1 WHERE position_id=:id'),
                {'id':row['position_id'],**{k:decision[k] for k in ('translation_status','document_form_status')}})
    _mark(connection)
