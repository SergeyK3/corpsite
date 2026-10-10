"""Canonical key shared by duplicate previews and the active-order unique index."""
NUMBER_KEY_SQL = "upper(btrim(regexp_replace(translate(order_number,'‐‑‒–—―','-------'),'\\s+',' ','g')))"
ACTIVE_HEADER_SQL = "deleted_at IS NULL AND order_date IS NOT NULL AND order_number IS NOT NULL AND btrim(order_number) <> ''"
INDEX_NAME = 'uq_personnel_orders_active_number_date'
