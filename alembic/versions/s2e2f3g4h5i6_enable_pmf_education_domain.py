"""Enable the existing PMF education domain for approved Stage 2.

The migration is deliberately an activation only: it neither creates PMF
objects nor writes canonical education data.
"""
from alembic import op

revision = "s2e2f3g4h5i6"
down_revision = "s2e1d2u3c4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE r public.personnel_migration_domains%ROWTYPE; n integer;
    BEGIN
      SELECT count(*) INTO n FROM public.personnel_migration_domains WHERE domain_code='education';
      IF n <> 1 THEN RAISE EXCEPTION 'Stage 2 PMF activation requires exactly one education domain, found %', n; END IF;
      SELECT * INTO r FROM public.personnel_migration_domains WHERE domain_code='education' FOR UPDATE;
      IF r.is_enabled IS DISTINCT FROM false THEN RAISE EXCEPTION 'Stage 2 PMF activation expected education.is_enabled=false'; END IF;
      IF r.target_table_names <> '["person_education", "person_training"]'::jsonb
         OR r.control_list_columns <> '["H", "I", "K", "M"]'::jsonb THEN
        RAISE EXCEPTION 'Stage 2 PMF activation rejected incompatible education plugin configuration';
      END IF;
      UPDATE public.personnel_migration_domains SET is_enabled=true, updated_at=now()
       WHERE domain_code='education';
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DO $$
    DECLARE n integer;
    BEGIN
      SELECT count(*) INTO n FROM public.personnel_migration_domains WHERE domain_code='education';
      IF n <> 1 THEN RAISE EXCEPTION 'Stage 2 PMF deactivation requires exactly one education domain, found %', n; END IF;
      PERFORM 1 FROM public.personnel_migration_domains WHERE domain_code='education' FOR UPDATE;
      IF EXISTS (SELECT 1 FROM public.ppr_stage_runs WHERE stage_code='education')
         OR EXISTS (SELECT 1 FROM public.personnel_migration_runs WHERE metadata ? 'stage2')
         OR EXISTS (SELECT 1 FROM public.personnel_migration_items WHERE source_kind='stage2_control_list_fragment')
         OR EXISTS (SELECT 1 FROM public.person_education WHERE metadata ? 'stage2') THEN
        RAISE EXCEPTION 'Stage 2 PMF deactivation blocked: Stage 2 data exists';
      END IF;
      UPDATE public.personnel_migration_domains SET is_enabled=false, updated_at=now()
       WHERE domain_code='education';
    END $$;
    """)
