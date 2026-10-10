"""Read-only capabilities of the current order schema, without migration or stamp."""
from sqlalchemy import text


def creation_capabilities(conn, item_type_code):
    metadata=conn.execute(text("""
        SELECT to_regclass('public.personnel_order_templates') IS NOT NULL AS identities,
          EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='personnel_orders' AND column_name='selected_template_version_id') AS selected_version,
          to_regclass('public.job_positions_catalog') IS NOT NULL AND to_regclass('public.position_job_catalog') IS NOT NULL AS job_catalog,
          (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_personnel_orders_order_type_code' AND conrelid='public.personnel_orders'::regclass) AS order_codes,
          (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_personnel_order_items_item_type_code' AND conrelid='public.personnel_order_items'::regclass) AS item_codes
    """)).mappings().one()
    token="'"+str(item_type_code)+"'"
    supported=all(token in (metadata[key] or '') for key in ('order_codes','item_codes'))
    independent=bool(metadata['identities'] and metadata['selected_version'])
    return {
        'independent_supported':independent,
        'creation_supported':supported,
        'creation_reason':None if supported else f"Текущая схема БД не разрешает вид {item_type_code} в приказах и пунктах. Для отзыва требуется согласованная миграция hrrecall001; БД автоматически не изменяется.",
        'schema_mode':'INDEPENDENT' if independent else 'LEGACY',
        'job_catalog_supported':bool(metadata['job_catalog']),
    }
