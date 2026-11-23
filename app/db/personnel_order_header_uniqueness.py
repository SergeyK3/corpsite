"""Canonical key shared by duplicate previews and the active-order unique index."""
NUMBER_KEY_SQL = "upper(btrim(regexp_replace(translate(order_number,'‐‑‒–—―','-------'),'\\s+',' ','g')))"
ORDER_YEAR_SQL = "EXTRACT(YEAR FROM order_date)"
ACTIVE_HEADER_SQL = "deleted_at IS NULL AND order_date IS NOT NULL AND order_number IS NOT NULL AND btrim(order_number) <> ''"
# Retain this historical index name so the earlier podup001 migration can run
# unchanged before learning007 replaces its date key with a calendar-year key.
INDEX_NAME = 'uq_personnel_orders_active_number_date'
