"""Register signed operational orders."""
from alembic import op

revision = "oo005dregistration"
down_revision = ("ooar001return", "td013employeeevidence")
branch_labels = None
depends_on = None

_PREVIOUS_ACTIONS = (
    "SIGNING_AUTHORITY_ASSIGNED",
    "SIGNING_AUTHORITY_SUPERSEDED",
    "SIGNATURE_READINESS_VALIDATED",
    "SIGNATURE_READINESS_FAILED",
    "DOCUMENT_READY_FOR_SIGNATURE",
    "READY_FOR_SIGNATURE_REPLAY",
    "DOCUMENT_RETURNED_TO_CREATED",
    "DOCUMENT_SIGNED",
)


def _set_audit_actions(actions: tuple[str, ...]) -> None:
    values = ", ".join(f"'{action}'" for action in actions)
    op.execute(
        f"""
        ALTER TABLE public.operational_order_lifecycle_audit
            DROP CONSTRAINT chk_oo_lifecycle_audit_action,
            ADD CONSTRAINT chk_oo_lifecycle_audit_action CHECK (action IN ({values}))
        """
    )


def upgrade() -> None:
    _set_audit_actions((*_PREVIOUS_ACTIONS, "DOCUMENT_REGISTERED"))
    op.execute(
        """
        INSERT INTO public.access_roles (code, name, description, access_level, level_rank, is_system)
        VALUES ('OPERATIONAL_ORDERS_REGISTER', 'Регистрация производственных приказов',
                'Регистрация подписанных производственных приказов', 'MANAGER', 20, TRUE)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    _set_audit_actions(_PREVIOUS_ACTIONS)
    op.execute(
        """
        DELETE FROM public.access_roles
        WHERE code = 'OPERATIONAL_ORDERS_REGISTER'
        """
    )
