"""WP-PPR-MIG-005G-A full ten-section persisted projection catalog.

The upgrade adds only safe status rows for existing active-universe projection
members.  It neither reads source payloads nor copies personnel values.
"""
from alembic import op
from sqlalchemy import text

revision = "ppr005gfull01"
down_revision = "ppr005fevent01"
branch_labels = None
depends_on = None

_LEGACY_SECTIONS = "'general','education','training'"
_FULL_SECTIONS = "'general','education','training','relatives','military','employment_biography','employment_history','foreign_languages','awards','academic_degrees_titles'"
_NEW_SECTIONS = "'relatives','military','employment_biography','employment_history','foreign_languages','awards','academic_degrees_titles'"


def upgrade() -> None:
    op.execute(f"""
    ALTER TABLE public.ppr_migration_section_status_projection
      DROP CONSTRAINT IF EXISTS ppr_migration_section_status_projection_section_code_check;
    ALTER TABLE public.ppr_migration_section_status_projection
      ADD CONSTRAINT ck_ppr_migration_status_projection_section_code
      CHECK (section_code IN ({_FULL_SECTIONS}));
    """)
    backfill_missing_section_rows(op.get_bind())


def backfill_missing_section_rows(connection) -> None:
    """Add only absent catalog rows from safe legacy projection context.

    Kept separately so the PostgreSQL contract can exercise the exact upgrade
    statement against a synthetic legacy three-row snapshot.
    """
    new_values = ",".join(f"({value})" for value in _NEW_SECTIONS.split(","))
    # Existing three cells are authoritative for membership and safe technical
    # context.  The migration adds exactly the missing catalog rows, without
    # generating stage/PMF evidence or copying any PII/raw personnel data.
    connection.execute(text(f"""
    INSERT INTO public.ppr_migration_section_status_projection(
      universe_id,person_id,employee_context_id,org_unit_id,section_code,
      status_code,reason_code,source_cohort_run_id,source_row_id,
      stage_run_id,stage1_run_id,stage_participant_id,stage1_participant_id,
      pmf_run_id,evidence_kind,policy_version,parser_version,
      source_fingerprint,target_fingerprint,binding_fingerprint,calculated_at,row_version
    )
    SELECT base.universe_id,base.person_id,base.employee_context_id,base.org_unit_id,
           catalog.section_code,
           'NOT_STARTED','SECTION_PROCESSING_NOT_CONNECTED',
           base.source_cohort_run_id,base.source_row_id,
           NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
           base.source_fingerprint,base.target_fingerprint,base.binding_fingerprint,
           now(),1
    FROM (
      SELECT DISTINCT ON (universe_id,person_id)
             universe_id,person_id,employee_context_id,org_unit_id,
             source_cohort_run_id,source_row_id,
             source_fingerprint,target_fingerprint,binding_fingerprint
      FROM public.ppr_migration_section_status_projection
      WHERE section_code IN ({_LEGACY_SECTIONS})
      ORDER BY universe_id,person_id,section_code
    ) AS base
    CROSS JOIN (VALUES {new_values}) AS catalog(section_code)
    ON CONFLICT (universe_id,person_id,section_code) DO NOTHING;
    """))


def downgrade() -> None:
    # Do not silently delete the seven newly persisted section rows.
    op.execute(f"""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM public.ppr_migration_section_status_projection
        WHERE section_code IN ({_NEW_SECTIONS})
      ) THEN
        RAISE EXCEPTION 'Cannot downgrade ppr005gfull01: full-section projection data exists';
      END IF;
    END
    $$;
    """)
    op.execute(f"""
    ALTER TABLE public.ppr_migration_section_status_projection
      DROP CONSTRAINT IF EXISTS ck_ppr_migration_status_projection_section_code;
    ALTER TABLE public.ppr_migration_section_status_projection
      ADD CONSTRAINT ppr_migration_section_status_projection_section_code_check
      CHECK (section_code IN ({_LEGACY_SECTIONS}));
    """)
