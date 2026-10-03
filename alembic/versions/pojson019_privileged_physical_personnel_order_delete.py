"""Permit a transaction-local, privileged physical personnel-order cleanup."""
from alembic import op

revision = "pojson019"
down_revision = "pojson018"
branch_labels = None
depends_on = None

def upgrade() -> None:
    for function_name, message in (
        ("guard_personnel_order_template_application_append_only", "personnel_order_template_applications is append-only"),
        ("guard_personnel_order_draft_deletion_audit", "personnel_order_draft_deletion_audit is append-only"),
        ("guard_technical_personnel_order_deletion_audit", "technical_personnel_order_deletion_audit is append-only"),
        ("guard_technical_personnel_order_provenance_audit", "technical_personnel_order_provenance_audit is append-only"),
    ):
        op.execute(f"""
        CREATE OR REPLACE FUNCTION public.{function_name}() RETURNS trigger AS $$
        BEGIN
          IF current_setting('corpsite.allow_personnel_order_physical_delete', true) = 'on' THEN RETURN OLD; END IF;
          RAISE EXCEPTION '{message}';
        END $$ LANGUAGE plpgsql;
        """)


def downgrade() -> None:
    op.execute("""CREATE OR REPLACE FUNCTION public.guard_personnel_order_draft_deletion_audit() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'personnel_order_draft_deletion_audit is append-only'; END $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE OR REPLACE FUNCTION public.guard_personnel_order_template_application_append_only() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'personnel_order_template_applications is append-only'; END $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE OR REPLACE FUNCTION public.guard_technical_personnel_order_deletion_audit() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'technical_personnel_order_deletion_audit is append-only'; END $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE OR REPLACE FUNCTION public.guard_technical_personnel_order_provenance_audit() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'technical_personnel_order_provenance_audit is append-only'; END $$ LANGUAGE plpgsql;""")
