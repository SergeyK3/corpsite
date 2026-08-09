"""ADR-065 preflight schema dependencies.

Revision ID: l9m0n1o2p3q4
Revises: j7k8l9m0n1o2
"""

from alembic import op
import sqlalchemy as sa


revision = "l9m0n1o2p3q4"
down_revision = "j7k8l9m0n1o2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personnel_order_evidence_scopes",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("transaction_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("transaction_timestamp()")),
        sa.CheckConstraint("generation > 0", name="chk_poes_generation"),
        sa.ForeignKeyConstraint(["order_id"], ["personnel_orders.order_id"], name="fk_poes_order", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("order_id", name="pk_personnel_order_evidence_scopes"),
        schema="public",
    )
    op.execute(
        """
        INSERT INTO public.personnel_order_evidence_scopes(order_id)
        SELECT order_id FROM public.personnel_orders ORDER BY order_id
        ON CONFLICT (order_id) DO NOTHING
        """
    )
    op.execute(
        """
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
            RAISE EXCEPTION 'ADR065 personnel-order evidence-scope backfill mismatch';
          END IF;
        END $$
        """
    )

    op.create_table(
        "person_assignment_activation_watermark",
        sa.Column("singleton", sa.Boolean(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("singleton IS TRUE", name="chk_paaw_singleton"),
        sa.CheckConstraint("generation > 0", name="chk_paaw_generation"),
        sa.CheckConstraint("processed_at <= updated_at", name="chk_paaw_timestamp_order"),
        sa.PrimaryKeyConstraint("singleton", name="pk_person_assignment_activation_watermark"),
        schema="public",
    )
    op.execute(
        """
        UPDATE public.person_assignments
        SET active_flag = (
          lifecycle_status = 'active'
          AND start_date <= ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date
          AND (end_date IS NULL OR end_date >= ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date)
        )
        WHERE active_flag IS DISTINCT FROM (
          lifecycle_status = 'active'
          AND start_date <= ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date
          AND (end_date IS NULL OR end_date >= ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date)
        )
        """
    )
    op.execute(
        """
        INSERT INTO public.person_assignment_activation_watermark
               (singleton,effective_date,processed_at,generation,updated_at)
        VALUES (TRUE,
                ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date,
                transaction_timestamp(),1,transaction_timestamp())
        ON CONFLICT (singleton) DO NOTHING
        """
    )
    op.execute(
        """
        DO $$
        DECLARE expected_date DATE :=
          ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date;
        BEGIN
          IF (SELECT count(*) FROM public.person_assignment_activation_watermark) <> 1
             OR NOT EXISTS (
               SELECT 1 FROM public.person_assignment_activation_watermark
               WHERE singleton IS TRUE AND effective_date=expected_date AND generation=1
                 AND processed_at <= updated_at
             ) THEN
            RAISE EXCEPTION 'ADR065 activation-watermark initialization mismatch';
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE current_date_d DATE :=
          ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date;
        BEGIN
          IF (SELECT count(*) FROM public.person_assignment_activation_watermark) <> 1
             OR NOT EXISTS (
               SELECT 1 FROM public.person_assignment_activation_watermark
               WHERE singleton IS TRUE AND effective_date=current_date_d AND generation=1
             ) THEN
            RAISE EXCEPTION 'ADR065 downgrade refused: watermark has retained runtime state';
          END IF;
          IF EXISTS (
            SELECT 1 FROM public.personnel_order_evidence_scopes WHERE generation <> 1
          ) THEN
            RAISE EXCEPTION 'ADR065 downgrade refused: evidence scopes have retained runtime state';
          END IF;
        END $$
        """
    )
    op.drop_table("person_assignment_activation_watermark", schema="public")
    op.drop_table("personnel_order_evidence_scopes", schema="public")
