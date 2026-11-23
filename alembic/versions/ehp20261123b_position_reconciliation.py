"""Queue unmatched HIRE position titles without rewriting historical records.

Revision ID: ehp20261123b
Revises: ehp20261123a
"""
from alembic import op

revision = "ehp20261123b"
down_revision = "ehp20261123a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.electronic_hire_position_requests (
            request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES public.electronic_hire_applications(application_id) ON DELETE RESTRICT,
            source_fingerprint TEXT NOT NULL,
            source_title TEXT NOT NULL,
            org_unit_id BIGINT NOT NULL REFERENCES public.org_units(unit_id) ON DELETE RESTRICT,
            explanation TEXT NOT NULL,
            requested_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
            decision_mode TEXT CHECK (decision_mode IN ('existing','link','new')),
            resolved_position_id BIGINT REFERENCES public.positions(position_id) ON DELETE RESTRICT,
            decision_note TEXT,
            decided_by_user_id BIGINT REFERENCES public.users(user_id) ON DELETE RESTRICT,
            decided_at TIMESTAMPTZ,
            UNIQUE (application_id, source_fingerprint)
        );
        CREATE INDEX ix_eha_position_requests_open
            ON public.electronic_hire_position_requests(requested_at, request_id)
            WHERE status='open';
        CREATE TABLE public.electronic_hire_position_request_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id BIGINT NOT NULL REFERENCES public.electronic_hire_position_requests(request_id) ON DELETE RESTRICT,
            action TEXT NOT NULL CHECK (action IN ('requested','resolved')),
            actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            details JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
        VALUES ('POSITION_RECONCILIATION_RESOLVE','Сопоставление должностей',
                'Адресное право разбирать запросы и создавать должности по запросу',
                'MANAGER',20,TRUE)
        ON CONFLICT(code) DO UPDATE SET is_active=TRUE,updated_at=now();
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM public.access_grants g JOIN public.access_roles r
                     ON r.access_role_id=g.access_role_id
                     WHERE r.code='POSITION_RECONCILIATION_RESOLVE') THEN
            RAISE EXCEPTION 'Revoke POSITION_RECONCILIATION_RESOLVE grants before downgrade';
          END IF;
        END $$;
        DELETE FROM public.access_roles WHERE code='POSITION_RECONCILIATION_RESOLVE';
        DROP TABLE public.electronic_hire_position_request_audit;
        DROP TABLE public.electronic_hire_position_requests;
    """)
