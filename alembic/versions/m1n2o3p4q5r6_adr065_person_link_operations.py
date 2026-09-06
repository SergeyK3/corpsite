"""ADR-065 first slice: immutable Person link operation journal."""
from alembic import op

revision = "m1n2o3p4q5r6"
down_revision = "td006afnd601"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.personnel_identity_link_operations (
      operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      request_id TEXT NOT NULL UNIQUE,
      request_fingerprint TEXT NOT NULL,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id),
      employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id),
      person_id BIGINT NOT NULL REFERENCES public.persons(person_id),
      decision TEXT NOT NULL CHECK (decision IN ('CREATE','ADOPT')),
      old_full_name TEXT NOT NULL,
      new_full_name TEXT NOT NULL,
      normalized_record_ids JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("REVOKE UPDATE, DELETE ON public.personnel_identity_link_operations FROM PUBLIC")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.prevent_personnel_identity_link_operation_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'personnel identity link operations are immutable'; END;
    $$;
    CREATE TRIGGER trg_personnel_identity_link_operations_immutable
      BEFORE UPDATE OR DELETE ON public.personnel_identity_link_operations
      FOR EACH ROW EXECUTE FUNCTION public.prevent_personnel_identity_link_operation_mutation();
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_personnel_identity_link_operations_immutable ON public.personnel_identity_link_operations")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_personnel_identity_link_operation_mutation()")
    op.execute("DROP TABLE IF EXISTS public.personnel_identity_link_operations")
