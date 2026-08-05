"""WP-II-001 — Incoming Information foundation schema, seed, permissions."""
from __future__ import annotations

from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None

_SENDER_KINDS = ("EXTERNAL_TEXT", "PERSON", "EMPLOYEE", "ORG_UNIT")
_ADDRESSEE_KINDS = ("TEXT", "USER", "EMPLOYEE", "ORG_UNIT", "POSITION")
_ACCESS_LEVELS = ("NORMAL", "RESTRICTED")
_ASSIGNMENT_ROLES = ("PRIMARY", "COEXECUTOR")
_STORAGE_TYPES = ("LOCAL_SHARE",)
_AUDIT_ACTIONS = ("CREATED", "FIELD_CHANGED", "STATUS_CHANGED", "ASSIGNMENT_CHANGED", "LINK_ADDED", "LINK_REMOVED", "ATTACHMENT_ADDED", "ATTACHMENT_REMOVED")

_II_PERMISSIONS = (
    "INCOMING_INFO_REGISTER",
    "INCOMING_INFO_READ",
    "INCOMING_INFO_RESOLVE",
    "INCOMING_INFO_EXECUTE",
    "INCOMING_INFO_CONTROL",
    "INCOMING_INFO_ADMIN",
)

_DOCUMENT_TYPES = (
    ("LETTER", "Письмо"),
    ("SERVICE_NOTE", "Служебная записка"),
    ("MEMO", "Докладная записка"),
    ("EXPLANATORY_NOTE", "Объяснительная записка"),
    ("REPORT", "Рапорт"),
    ("EMPLOYEE_APPLICATION", "Заявление работника"),
    ("COMPLAINT", "Жалоба / обращение"),
    ("REPRESENTATION", "Представление"),
    ("ACT", "Акт"),
    ("PRESCRIPTION", "Предписание"),
    ("PROTOCOL", "Протокол"),
    ("REQUEST_FORM", "Заявка"),
    ("NOTIFICATION", "Уведомление"),
    ("INQUIRY", "Запрос"),
    ("MANAGER_DIRECTIVE", "Поручение руководителя"),
    ("REGULATOR_DOCUMENT", "Документ контролирующего органа"),
    ("COURT_DOCUMENT", "Судебный / исполнительный документ"),
    ("OTHER", "Иной документ"),
)

_PLANNED_RESULTS = (
    ("ACKNOWLEDGE", "Принять к сведению"),
    ("REPLY", "Дать ответ"),
    ("INSPECTION", "Провести проверку"),
    ("DRAFT_OPERATIONAL_ORDER", "Подготовить приказ"),
    ("DRAFT_SERVICE_NOTE", "Подготовить служебную записку"),
    ("REMEDY_VIOLATION", "Устранить нарушение"),
    ("DISCIPLINARY_REVIEW", "Рассмотреть вопрос об ответственности"),
    ("ALLOCATE_FUNDS", "Выплатить / выделить средства"),
    ("AMEND_DOCUMENT", "Внести изменения в документ"),
    ("TRANSFER_COMPETENCE", "Передать по компетенции"),
    ("REFUSE", "Отказать с обоснованием"),
    ("NO_ACTION", "Оставить без дальнейшего действия"),
    ("OTHER", "Иной результат"),
)

_STATUSES = (
    ("REGISTERED", "Зарегистрировано", False),
    ("UNDER_REVIEW", "На рассмотрении", False),
    ("EXECUTOR_ASSIGNED", "Назначен исполнитель", False),
    ("IN_PROGRESS", "В работе", False),
    ("AWAITING_INFO", "Ожидает информации", False),
    ("DRAFT_PREPARED", "Подготовлен проект", False),
    ("ON_APPROVAL", "На согласовании", False),
    ("EXECUTED", "Исполнено", False),
    ("CLOSED", "Закрыто", True),
    ("TRANSFERRED", "Передано по компетенции", True),
    ("CANCELLED", "Отменено", True),
)

_RECEIPT_CHANNELS = (
    ("PAPER", "Бумага"),
    ("EMAIL", "Электронная почта"),
    ("INTERNAL_SYSTEM", "Внутренняя система"),
    ("IN_PERSON", "Лично"),
    ("PHONE", "Телефон / устное обращение"),
    ("OTHER", "Иное"),
)

_LINK_TYPES = (
    ("BASIS", "Основание"),
    ("RESULT", "Результат"),
    ("DISCIPLINARY", "Дисциплинарный итог"),
    ("OTHER", "Иное"),
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    sender_kinds_sql = _in_list(_SENDER_KINDS)
    addressee_kinds_sql = _in_list(_ADDRESSEE_KINDS)
    access_levels_sql = _in_list(_ACCESS_LEVELS)
    assignment_roles_sql = _in_list(_ASSIGNMENT_ROLES)
    storage_types_sql = _in_list(_STORAGE_TYPES)
    audit_actions_sql = _in_list(_AUDIT_ACTIONS)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_registration_counters (
            registration_year INTEGER PRIMARY KEY,
            last_seq INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_incoming_document_registration_counters_year
                CHECK (registration_year >= 2000 AND registration_year <= 2100),
            CONSTRAINT chk_incoming_document_registration_counters_seq
                CHECK (last_seq >= 0)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_types (
            document_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_statuses (
            status_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_planned_results (
            planned_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_receipt_channels (
            receipt_channel_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_link_types (
            link_type_code TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.incoming_documents (
            incoming_document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            registration_number TEXT NOT NULL,
            registration_year INTEGER NOT NULL,
            registration_seq INTEGER NOT NULL,
            received_at DATE NOT NULL,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            document_type_id BIGINT NOT NULL
                REFERENCES public.incoming_document_types (document_type_id) ON DELETE RESTRICT,
            receipt_channel_id BIGINT NOT NULL
                REFERENCES public.incoming_receipt_channels (receipt_channel_id) ON DELETE RESTRICT,
            status_id BIGINT NOT NULL
                REFERENCES public.incoming_document_statuses (status_id) ON DELETE RESTRICT,
            planned_result_id BIGINT NULL
                REFERENCES public.incoming_planned_results (planned_result_id) ON DELETE RESTRICT,
            summary TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'NORMAL',
            sender_kind TEXT NOT NULL,
            sender_person_id BIGINT NULL
                REFERENCES public.persons (person_id) ON DELETE RESTRICT,
            sender_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            sender_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            sender_text TEXT NULL,
            addressee_kind TEXT NOT NULL,
            addressee_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            addressee_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            addressee_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            addressee_position_id BIGINT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            addressee_text TEXT NULL,
            registration_org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            responsible_org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            resolution_text TEXT NULL,
            due_date DATE NULL,
            planned_result_note TEXT NULL,
            executed_at DATE NULL,
            execution_result TEXT NULL,
            closed_at TIMESTAMPTZ NULL,
            note TEXT NULL,
            priority_level TEXT NULL,
            is_control_document BOOLEAN NOT NULL DEFAULT FALSE,
            received_after_registration_exception BOOLEAN NOT NULL DEFAULT FALSE,
            exception_comment TEXT NULL,
            transfer_comment TEXT NULL,
            cancellation_reason TEXT NULL,
            controller_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            updated_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_incoming_documents_registration_number UNIQUE (registration_number),
            CONSTRAINT uq_incoming_documents_year_seq UNIQUE (registration_year, registration_seq),
            CONSTRAINT chk_incoming_documents_access_level
                CHECK (access_level IN ({access_levels_sql})),
            CONSTRAINT chk_incoming_documents_sender_kind
                CHECK (sender_kind IN ({sender_kinds_sql})),
            CONSTRAINT chk_incoming_documents_addressee_kind
                CHECK (addressee_kind IN ({addressee_kinds_sql})),
            CONSTRAINT chk_incoming_documents_sender_external_text
                CHECK (
                    (sender_kind = 'EXTERNAL_TEXT' AND sender_text IS NOT NULL AND btrim(sender_text) <> '')
                    OR (sender_kind <> 'EXTERNAL_TEXT' AND sender_text IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_sender_person
                CHECK (
                    (sender_kind = 'PERSON' AND sender_person_id IS NOT NULL)
                    OR (sender_kind <> 'PERSON' AND sender_person_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_sender_employee
                CHECK (
                    (sender_kind = 'EMPLOYEE' AND sender_employee_id IS NOT NULL)
                    OR (sender_kind <> 'EMPLOYEE' AND sender_employee_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_sender_org_unit
                CHECK (
                    (sender_kind = 'ORG_UNIT' AND sender_org_unit_id IS NOT NULL)
                    OR (sender_kind <> 'ORG_UNIT' AND sender_org_unit_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_addressee_text
                CHECK (
                    (addressee_kind = 'TEXT' AND addressee_text IS NOT NULL AND btrim(addressee_text) <> '')
                    OR (addressee_kind <> 'TEXT' AND addressee_text IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_addressee_user
                CHECK (
                    (addressee_kind = 'USER' AND addressee_user_id IS NOT NULL)
                    OR (addressee_kind <> 'USER' AND addressee_user_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_addressee_employee
                CHECK (
                    (addressee_kind = 'EMPLOYEE' AND addressee_employee_id IS NOT NULL)
                    OR (addressee_kind <> 'EMPLOYEE' AND addressee_employee_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_addressee_org_unit
                CHECK (
                    (addressee_kind = 'ORG_UNIT' AND addressee_org_unit_id IS NOT NULL)
                    OR (addressee_kind <> 'ORG_UNIT' AND addressee_org_unit_id IS NULL)
                ),
            CONSTRAINT chk_incoming_documents_addressee_position
                CHECK (
                    (addressee_kind = 'POSITION' AND addressee_position_id IS NOT NULL)
                    OR (addressee_kind <> 'POSITION' AND addressee_position_id IS NULL)
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_documents_registered_at
            ON public.incoming_documents (registered_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_documents_responsible_org_unit
            ON public.incoming_documents (responsible_org_unit_id, registered_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_documents_status
            ON public.incoming_documents (status_id, registered_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.incoming_document_assignments (
            assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            assignee_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            assignee_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE RESTRICT,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            role TEXT NOT NULL,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            assigned_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            due_date DATE NULL,
            completed_at TIMESTAMPTZ NULL,
            cancelled_at TIMESTAMPTZ NULL,
            CONSTRAINT chk_incoming_document_assignments_role
                CHECK (role IN ({assignment_roles_sql})),
            CONSTRAINT chk_incoming_document_assignments_active_window
                CHECK (completed_at IS NULL OR cancelled_at IS NULL)
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_incoming_document_assignments_one_primary
            ON public.incoming_document_assignments (incoming_document_id)
            WHERE role = 'PRIMARY' AND completed_at IS NULL AND cancelled_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_document_assignments_assignee
            ON public.incoming_document_assignments (assignee_user_id, assigned_at DESC)
            WHERE completed_at IS NULL AND cancelled_at IS NULL
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.incoming_document_attachments (
            attachment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            storage_type TEXT NOT NULL DEFAULT 'LOCAL_SHARE',
            file_id TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            uploaded_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_incoming_document_attachments_storage_type
                CHECK (storage_type IN ({storage_types_sql})),
            CONSTRAINT chk_incoming_document_attachments_file_id
                CHECK (file_id ~ '^[a-f0-9]{32}$'),
            CONSTRAINT chk_incoming_document_attachments_size
                CHECK (size_bytes > 0),
            CONSTRAINT uq_incoming_document_attachments_file
                UNIQUE (incoming_document_id, file_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_operational_order_links (
            link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            operational_order_document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id) ON DELETE RESTRICT,
            link_type_code TEXT NOT NULL
                REFERENCES public.incoming_document_link_types (link_type_code) ON DELETE RESTRICT,
            comment TEXT NULL,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_incoming_document_operational_order_links
                UNIQUE (incoming_document_id, operational_order_document_id, link_type_code)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.incoming_document_personnel_order_links (
            link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            personnel_order_id BIGINT NOT NULL
                REFERENCES public.personnel_orders (order_id) ON DELETE RESTRICT,
            link_type_code TEXT NOT NULL
                REFERENCES public.incoming_document_link_types (link_type_code) ON DELETE RESTRICT,
            comment TEXT NULL,
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_incoming_document_personnel_order_links
                UNIQUE (incoming_document_id, personnel_order_id, link_type_code)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.incoming_document_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incoming_document_id BIGINT NOT NULL
                REFERENCES public.incoming_documents (incoming_document_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            field_name TEXT NULL,
            old_value TEXT NULL,
            new_value TEXT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            comment TEXT NULL,
            metadata JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_incoming_document_audit_action
                CHECK (action IN ({audit_actions_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incoming_document_audit_document
            ON public.incoming_document_audit (incoming_document_id, created_at DESC)
        """
    )

    for sort_order, (code, label) in enumerate(_DOCUMENT_TYPES, start=1):
        op.execute(
            f"""
            INSERT INTO public.incoming_document_types (code, label, sort_order)
            VALUES ('{code}', '{label}', {sort_order})
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for sort_order, (code, label, is_terminal) in enumerate(_STATUSES, start=1):
        terminal_sql = "TRUE" if is_terminal else "FALSE"
        op.execute(
            f"""
            INSERT INTO public.incoming_document_statuses (code, label, is_terminal, sort_order)
            VALUES ('{code}', '{label}', {terminal_sql}, {sort_order})
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                is_terminal = EXCLUDED.is_terminal,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for sort_order, (code, label) in enumerate(_PLANNED_RESULTS, start=1):
        op.execute(
            f"""
            INSERT INTO public.incoming_planned_results (code, label, sort_order)
            VALUES ('{code}', '{label}', {sort_order})
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for sort_order, (code, label) in enumerate(_RECEIPT_CHANNELS, start=1):
        op.execute(
            f"""
            INSERT INTO public.incoming_receipt_channels (code, label, sort_order)
            VALUES ('{code}', '{label}', {sort_order})
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for code, label in _LINK_TYPES:
        op.execute(
            f"""
            INSERT INTO public.incoming_document_link_types (link_type_code, label)
            VALUES ('{code}', '{label}')
            ON CONFLICT (link_type_code) DO UPDATE SET
                label = EXCLUDED.label,
                is_active = TRUE,
                updated_at = now()
            """
        )

    for permission_code in _II_PERMISSIONS:
        display_name = permission_code.replace("_", " ").title()
        op.execute(
            f"""
            INSERT INTO public.access_roles (
                code, name, description, access_level, level_rank, is_system
            )
            VALUES (
                '{permission_code}',
                '{display_name}',
                'WP-II-001 Incoming Information ({permission_code})',
                'MANAGER', 20, TRUE
            )
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                access_level = EXCLUDED.access_level,
                level_rank = EXCLUDED.level_rank,
                is_system = EXCLUDED.is_system,
                is_active = TRUE,
                updated_at = now()
            """
        )


def downgrade() -> None:
    for permission_code in reversed(_II_PERMISSIONS):
        op.execute(
            f"""
            DELETE FROM public.access_grants g
            USING public.access_roles ar
            WHERE g.access_role_id = ar.access_role_id
              AND ar.code = '{permission_code}'
            """
        )
        op.execute(
            f"""
            DELETE FROM public.access_roles ar
            WHERE ar.code = '{permission_code}'
            """
        )

    op.execute("DROP TABLE IF EXISTS public.incoming_document_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_personnel_order_links CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_operational_order_links CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_link_types CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_receipt_channels CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_planned_results CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_statuses CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_types CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incoming_document_registration_counters CASCADE")
