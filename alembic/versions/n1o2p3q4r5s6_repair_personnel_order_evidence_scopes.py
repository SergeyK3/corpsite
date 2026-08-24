"""Repair missing ADR-065 personnel-order evidence scopes.

Revision ID: n1o2p3q4r5s6
Revises: m0n1o2p3q4r5
"""
from alembic import op
import sqlalchemy as sa


revision = "n1o2p3q4r5s6"
down_revision = "m0n1o2p3q4r5"
branch_labels = None
depends_on = None


_CREATE_SCOPE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.personnel_order_evidence_scopes (
    order_id BIGINT NOT NULL,
    generation BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT transaction_timestamp(),
    CONSTRAINT chk_poes_generation CHECK (generation > 0),
    CONSTRAINT fk_poes_order FOREIGN KEY (order_id)
        REFERENCES public.personnel_orders(order_id) ON DELETE RESTRICT,
    CONSTRAINT pk_personnel_order_evidence_scopes PRIMARY KEY (order_id)
)
"""

_VALIDATE_SCOPE_TABLE_SQL = """
DO $$
DECLARE
  expected_columns TEXT[] := ARRAY[
    'order_id|bigint|f|',
    'generation|bigint|f|1',
    'created_at|timestamp with time zone|f|transaction_timestamp()',
    'updated_at|timestamp with time zone|f|transaction_timestamp()'
  ];
  actual_columns TEXT[];
BEGIN
  SELECT array_agg(
           a.attname || '|' || pg_catalog.format_type(a.atttypid, a.atttypmod) || '|'
           || CASE WHEN a.attnotnull THEN 'f' ELSE 't' END || '|'
           || COALESCE(pg_get_expr(d.adbin, d.adrelid), '')
           ORDER BY a.attnum
         )
    INTO actual_columns
    FROM pg_attribute a
    LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
   WHERE a.attrelid='public.personnel_order_evidence_scopes'::regclass
     AND a.attnum > 0 AND NOT a.attisdropped;

  IF actual_columns IS DISTINCT FROM expected_columns THEN
    RAISE EXCEPTION 'personnel_order_evidence_scopes column/default mismatch: %', actual_columns;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
     WHERE c.conrelid='public.personnel_order_evidence_scopes'::regclass
       AND c.conname='pk_personnel_order_evidence_scopes'
       AND c.contype='p'
       AND c.conkey=ARRAY[(SELECT attnum FROM pg_attribute
                            WHERE attrelid='public.personnel_order_evidence_scopes'::regclass
                              AND attname='order_id' AND NOT attisdropped)]::smallint[]
  ) THEN
    RAISE EXCEPTION 'personnel_order_evidence_scopes primary-key mismatch';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
     WHERE c.conrelid='public.personnel_order_evidence_scopes'::regclass
       AND c.conname='fk_poes_order'
       AND c.contype='f'
       AND c.confrelid='public.personnel_orders'::regclass
       AND c.confdeltype='r'
       AND c.conkey=ARRAY[(SELECT attnum FROM pg_attribute
                            WHERE attrelid='public.personnel_order_evidence_scopes'::regclass
                              AND attname='order_id' AND NOT attisdropped)]::smallint[]
       AND c.confkey=ARRAY[(SELECT attnum FROM pg_attribute
                             WHERE attrelid='public.personnel_orders'::regclass
                               AND attname='order_id' AND NOT attisdropped)]::smallint[]
  ) THEN
    RAISE EXCEPTION 'personnel_order_evidence_scopes foreign-key mismatch';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
     WHERE c.conrelid='public.personnel_order_evidence_scopes'::regclass
       AND c.conname='chk_poes_generation'
       AND c.contype='c'
       AND pg_get_constraintdef(c.oid)= 'CHECK ((generation > 0))'
  ) THEN
    RAISE EXCEPTION 'personnel_order_evidence_scopes check mismatch';
  END IF;
END $$
"""

_BACKFILL_SQL = """
INSERT INTO public.personnel_order_evidence_scopes(order_id, generation)
SELECT order_id, 1
FROM public.personnel_orders
ON CONFLICT (order_id) DO NOTHING
"""

_VERIFY_CORRESPONDENCE_SQL = """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.personnel_orders po
    LEFT JOIN public.personnel_order_evidence_scopes s ON s.order_id=po.order_id
    WHERE s.order_id IS NULL
  ) OR EXISTS (
    SELECT 1 FROM public.personnel_order_evidence_scopes s
    LEFT JOIN public.personnel_orders po ON po.order_id=s.order_id
    WHERE po.order_id IS NULL
  ) THEN
    RAISE EXCEPTION 'personnel-order evidence-scope correspondence mismatch';
  END IF;
END $$
"""


def repair_personnel_order_evidence_scopes(bind) -> None:
    """Create/verify derived scope state without changing existing scope rows."""
    bind.execute(sa.text(_CREATE_SCOPE_TABLE_SQL))
    bind.execute(sa.text(_VALIDATE_SCOPE_TABLE_SQL))
    bind.execute(sa.text(_BACKFILL_SQL))
    bind.execute(sa.text(_VERIFY_CORRESPONDENCE_SQL))


def upgrade() -> None:
    repair_personnel_order_evidence_scopes(op.get_bind())


def downgrade() -> None:
    # Repair is intentionally non-destructive: the table may predate this revision.
    pass
