"""Keep electronic hire identity in the application until HR verification.

Revision ID: eha004
Revises: ehpub20261123
"""
from alembic import op

revision = "eha004"
down_revision = "ehpub20261123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.personnel_applications ALTER COLUMN person_id DROP NOT NULL;
        ALTER TABLE public.personnel_applications
            ADD CONSTRAINT chk_electronic_hire_unlinked_person
            CHECK (person_id IS NOT NULL OR application_source = 'electronic');
        ALTER TABLE public.electronic_hire_applications
            ADD COLUMN preliminary_full_name TEXT,
            ADD COLUMN preliminary_iin TEXT,
            ADD COLUMN preliminary_birth_date DATE;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM public.personnel_applications WHERE person_id IS NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade: unverified electronic hire drafts exist';
            END IF;
        END $$;
        ALTER TABLE public.electronic_hire_applications
            DROP COLUMN preliminary_birth_date,
            DROP COLUMN preliminary_iin,
            DROP COLUMN preliminary_full_name;
        ALTER TABLE public.personnel_applications DROP CONSTRAINT chk_electronic_hire_unlinked_person;
        ALTER TABLE public.personnel_applications ALTER COLUMN person_id SET NOT NULL;
    """)
