"""WP-TD-002B approval foundation. No target deletion exists here."""
from __future__ import annotations

import hashlib, json, os, re, unicodedata, uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from app.db.engine import engine

POLICY_VERSION = "WP-TD-002C/v4"
MANIFEST_SCHEMA = "WP-TD-MANIFEST/v2"
MANIFEST_VERSION = 2
APPLICANT_PROCESS_TYPE = "APPLICANT_ONLY"
MAX_PREVIEW_RESULTS = 200
MAX_COMMENT_LENGTH = 500
REQUEST_PERMISSION = "TEST_PERSONNEL_DELETION_REQUEST"
APPROVE_PERMISSION = "TEST_PERSONNEL_DELETION_APPROVE"
AUDIT_PERMISSION = "TEST_PERSONNEL_DELETION_AUDIT_READ"
BLOCK, TOMBSTONE_REQUIRED, HR_ATTESTATION_REQUIRED, INFORMATIONAL = (
    "BLOCK", "TOMBSTONE_REQUIRED", "HR_ATTESTATION_REQUIRED", "INFORMATIONAL"
)
REASON_CODES = frozenset({"LEGACY_SYNTHETIC_TEST_DATA", "PROVENANCE_TEST_RUN_CLEANUP", "DUPLICATE_SYNTHETIC_FIXTURE", "OTHER_APPROVED_TEST_DATA"})
EARLY_LIFECYCLE_ACTIONS = ("registered", "intake_link_issued", "intake_opened", "intake_submitted", "intake_edited_on_behalf")


class TestPersonnelDeletionError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message); self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class RelationshipRule:
    code: str
    table: str
    category: str
    lookup: str
    keys: tuple[str, ...]
    state_digest: str
    sql: str
    create_allowed: bool
    submit_allowed: bool
    approval_allowed: bool
    future_execution_allowed: bool
    required_hr_decision: str | None = None


def _rule(code: str, table: str, category: str, where: str, *, lookup="person_id", keys=("person_id",), digest="SHA-256 of canonical full rows; raw values are never persisted", required_hr_decision: str | None = None) -> RelationshipRule:
    return RelationshipRule(code, table, category, lookup, keys, digest,
        f"SELECT to_jsonb(t) state FROM public.{table} t WHERE {where}",
        category != BLOCK, category != BLOCK, category != BLOCK, category == INFORMATIONAL,
        required_hr_decision)


# Single server-owned matrix. Identifiers and predicates are constants, never client input.
RELATIONSHIP_MATRIX: tuple[RelationshipRule, ...] = (
    _rule("ALL_APPLICATIONS_PRESENT", "personnel_applications", INFORMATIONAL, "t.person_id=:person_id"),
    _rule("SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED", "personnel_applications", HR_ATTESTATION_REQUIRED, "t.application_id=:application_id AND t.status='intake_submitted'", lookup="selected application status", keys=("application_id",), required_hr_decision="submitted_synthetic_confirmed=true"),
    _rule("APPLICATION_STATUS_NOT_ELIGIBLE", "personnel_applications", BLOCK, "t.application_id=:application_id AND t.status NOT IN ('intake_pending','intake_submitted')", lookup="selected application status", keys=("application_id",)),
    _rule("PERSONNEL_ORDER_PRESENT", "personnel_applications", BLOCK, "t.application_id=:application_id AND t.personnel_order_id IS NOT NULL", lookup="selected application order link", keys=("application_id",)),
    _rule("DIRECTOR_RESOLUTION_PRESENT", "personnel_applications", BLOCK, "t.application_id=:application_id AND t.director_resolution_status IS NOT NULL", lookup="selected application director resolution", keys=("application_id",)),
    _rule("EMPLOYEE_PRESENT", "employees", BLOCK, "t.person_id=:person_id"),
    _rule("LEGACY_PERSONNEL_PRESENT", "personnel", BLOCK, "t.person_id=:person_id", lookup="logical person_id"),
    _rule("CONTACT_PRESENT", "contacts", BLOCK, "t.person_id=:person_id", lookup="logical person_id"),
    _rule("CONTACT_ACCESS_PRESENT", "contact_access", BLOCK, "t.person_id=:person_id", lookup="logical person_id access mapping"),
    _rule("KEY_CONTACT_PRESENT", "key_contacts", BLOCK, "t.person_id=:person_id", lookup="logical person_id key-contact row"),
    _rule("ORG_UNIT_KEY_STAFF_PRESENT", "org_unit_key_staff", BLOCK, "t.person_id=:person_id", lookup="logical person_id organizational key-staff row"),
    _rule("ASSIGNMENT_PRESENT", "person_assignments", BLOCK, "t.person_id=:person_id"),
    _rule("ENROLLMENT_QUEUE_PRESENT", "enrollment_queue", BLOCK, "t.person_id=:person_id"),
    _rule("PPR_EVENT_TOMBSTONE_REQUIRED", "personnel_record_events", TOMBSTONE_REQUIRED, "t.person_id=:person_id"),
    _rule("PPR_COMMAND_TOMBSTONE_REQUIRED", "ppr_command_executions", TOMBSTONE_REQUIRED, "t.person_id=:person_id"),
    _rule("PPR_METADATA_PRESENT", "personnel_record_metadata", INFORMATIONAL, "t.person_id=:person_id"),
    _rule("PPR_EDUCATION_PRESENT", "person_education", BLOCK, "t.person_id=:person_id"),
    _rule("PPR_TRAINING_PRESENT", "person_training", BLOCK, "t.person_id=:person_id"),
    _rule("PPR_RELATIVE_PRESENT", "person_relatives", BLOCK, "t.person_id=:person_id"),
    _rule("PPR_EXTERNAL_EMPLOYMENT_PRESENT", "person_external_employment", BLOCK, "t.person_id=:person_id"),
    _rule("PPR_MILITARY_PRESENT", "person_military_service", BLOCK, "t.person_id=:person_id"),
    _rule("PHOTO_PRESENT", "person_photos", BLOCK, "t.person_id=:person_id"),
    _rule("PHOTO_PROVENANCE_PRESENT", "person_photo_sources", BLOCK, "t.person_id=:person_id OR t.source_application_id=ANY(:application_ids)", lookup="Person or all applications", keys=("person_id", "application_ids")),
    _rule("TELEGRAM_BINDING_PRESENT", "person_telegram_bindings", BLOCK, "t.person_id=:person_id"),
    _rule("TELEGRAM_ACTIVATION_PRESENT", "person_telegram_bot_activations", BLOCK, "t.person_id=:person_id"),
    _rule("VERIFICATION_TASK_PRESENT", "verification_tasks", BLOCK, "t.person_id=:person_id"),
    _rule("VERIFICATION_ATTESTATION_PRESENT", "verification_attestations", BLOCK, "t.person_id=:person_id"),
    _rule("IDENTITY_RECONCILIATION_PRESENT", "identity_reconciliation_items", BLOCK, "t.person_id=:person_id"),
    _rule("HR_CHANGE_EVENT_PRESENT", "hr_personnel_change_events", BLOCK, "t.person_id=:person_id"),
    _rule("INCOMING_DOCUMENT_PRESENT", "incoming_documents", BLOCK, "t.sender_person_id=:person_id"),
    _rule("MERGED_PERSON_REFERENCE_PRESENT", "persons", BLOCK, "t.merged_into_person_id=:person_id", lookup="inbound merged_into_person_id"),
    _rule("INTAKE_REVIEW_PRESENT", "personnel_intake_section_reviews", BLOCK, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",)),
    _rule("INTAKE_TRANSFER_PRESENT", "personnel_intake_transfers", BLOCK, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",)),
    _rule("INTAKE_RECONCILIATION_PRESENT", "personnel_intake_reconciliation_decisions", BLOCK, "t.person_id=:person_id OR t.application_id=ANY(:application_ids)", lookup="Person or all applications", keys=("person_id", "application_ids")),
    _rule("APPLICATION_BLOCKER_PRESENT", "personnel_application_blockers", BLOCK, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",)),
    _rule("APPLICATION_EARLY_LIFECYCLE_TOMBSTONE_REQUIRED", "personnel_application_lifecycle_audit", TOMBSTONE_REQUIRED, "t.application_id=ANY(:application_ids) AND t.action=ANY(:early_actions)", lookup="all applications + early action allowlist", keys=("application_ids",)),
    _rule("APPLICATION_OFFICIAL_LIFECYCLE_PRESENT", "personnel_application_lifecycle_audit", BLOCK, "t.application_id=ANY(:application_ids) AND NOT (t.action=ANY(:early_actions))", lookup="all applications + official actions", keys=("application_ids",)),
    _rule("APPLICATION_RESOLUTION_AUDIT_PRESENT", "personnel_application_resolution_audit", BLOCK, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",)),
    _rule("ONBOARDING_PRESENT", "employee_onboardings", BLOCK, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",)),
    _rule("INTAKE_LINK_PRESENT", "personnel_intake_links", INFORMATIONAL, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",), digest="SHA-256 includes status, timestamps, token hash and encrypted-token digest"),
    _rule("INTAKE_DRAFT_PRESENT", "personnel_intake_drafts", INFORMATIONAL, "t.application_id=ANY(:application_ids)", lookup="all Person applications", keys=("application_ids",), digest="SHA-256 includes status, timestamps and payload digest"),
    _rule("ENROLLMENT_HISTORY_RETAINED", "enrollment_history", INFORMATIONAL, "t.person_id=:person_id"),
    _rule("HR_REVIEW_OVERRIDE_RETAINED", "hr_review_overrides", INFORMATIONAL, "t.person_id=:person_id"),
    _rule("SECURITY_AUDIT_RETAINED", "security_audit_log", INFORMATIONAL, "t.target_person_id=:person_id"),
    RelationshipRule(
        "PROVENANCE_STATE_RETAINED", "test_personnel_provenance", INFORMATIONAL,
        "current environment + exact Person/Application target", ("environment", "person_id", "application_id"),
        "SHA-256 of safe provenance identity, version, artifact hash, expiry and DB-time validity",
        """SELECT jsonb_build_object(
            'provenance_id', t.provenance_id, 'target_type', t.target_type,
            'target_id', t.target_id, 'environment', t.environment,
            'source_artifact_hash', t.source_artifact_hash,
            'provenance_version', t.provenance_version, 'created_at', t.created_at,
            'expires_at', t.expires_at,
            'active', (t.expires_at IS NULL OR t.expires_at > transaction_timestamp())
        ) state
        FROM public.test_personnel_provenance t
        WHERE t.environment=:environment AND (
            (t.target_type='PERSON' AND t.target_id=:person_id) OR
            (t.target_type='APPLICATION' AND t.target_id=:application_id)
        )""",
        True, True, True, True, None,
    ),
)


def _joined_rule(code, table, category, lookup, sql, *, keys=("person_id",), digest="SHA-256 of canonical joined rows; raw values are never persisted", required_hr_decision=None):
    return RelationshipRule(code, table, category, lookup, keys, digest, sql, category != BLOCK, category != BLOCK, category != BLOCK, category == INFORMATIONAL, required_hr_decision)


_INCOMING_DOCUMENT_IDS_SQL = """SELECT d.incoming_document_id FROM public.incoming_documents d WHERE
    d.sender_person_id=:person_id OR
    d.sender_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR
    d.addressee_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR
    d.addressee_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.controller_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.created_by_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.updated_by_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.closed_by_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.cancelled_by_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.transferred_by_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
    d.external_recipient_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id)
"""


RELATIONSHIP_MATRIX += (
    _joined_rule("HR_REVIEW_OVERRIDE_HISTORY_RETAINED", "hr_review_override_history", INFORMATIONAL, "join override.person_id", "SELECT to_jsonb(t) state FROM public.hr_review_override_history t JOIN public.hr_review_overrides o ON o.override_id=t.override_id WHERE o.person_id=:person_id"),
    _joined_rule("HR_IMPORT_ROW_RETAINED", "hr_import_rows", INFORMATIONAL, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_import_rows t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("HR_IMPORT_NORMALIZED_RETAINED", "hr_import_normalized_records", INFORMATIONAL, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_import_normalized_records t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("USER_IDENTITY_PRESENT", "users", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.users t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("EMPLOYEE_DOCUMENT_PRESENT", "employee_documents", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_documents t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("EMPLOYEE_ASSIGNMENT_LINK_PRESENT", "employee_assignment_links", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_assignment_links t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("EMPLOYEE_EVENT_PRESENT", "employee_events", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_events t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("EMPLOYEE_IDENTITY_PRESENT", "employee_identities", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_identities t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("EMPLOYEE_PROFILE_OVERRIDE_PRESENT", "employee_import_profile_overrides", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_import_profile_overrides t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("TERMINATION_RECORD_PRESENT", "employee_termination_records", BLOCK, "join employee.person_id", "SELECT to_jsonb(t) state FROM public.employee_termination_records t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("TERMINATION_AUDIT_RETAINED", "employee_termination_record_audit", INFORMATIONAL, "termination record -> employee -> person", "SELECT to_jsonb(t) state FROM public.employee_termination_record_audit t JOIN public.employee_termination_records r ON r.termination_record_id=t.termination_record_id JOIN public.employees e ON e.employee_id=r.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("ONBOARDING_ITEM_PRESENT", "employee_onboarding_checklist_items", BLOCK, "onboarding -> application/employee", "SELECT to_jsonb(t) state FROM public.employee_onboarding_checklist_items t JOIN public.employee_onboardings o ON o.onboarding_id=t.onboarding_id LEFT JOIN public.employees e ON e.employee_id=o.employee_id WHERE o.application_id=ANY(:application_ids) OR e.person_id=:person_id"),
    _joined_rule("ONBOARDING_ATTACHMENT_PRESENT", "employee_onboarding_checklist_attachments", BLOCK, "item -> onboarding -> application/employee", "SELECT to_jsonb(t) state FROM public.employee_onboarding_checklist_attachments t JOIN public.employee_onboarding_checklist_items i ON i.item_id=t.item_id JOIN public.employee_onboardings o ON o.onboarding_id=i.onboarding_id LEFT JOIN public.employees e ON e.employee_id=o.employee_id WHERE o.application_id=ANY(:application_ids) OR e.person_id=:person_id"),
    _joined_rule("PERSONNEL_ORDER_ITEM_PRESENT", "personnel_order_items", BLOCK, "item.employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.personnel_order_items t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("PERSONNEL_ORDER_SIGNATORY_PRESENT", "personnel_orders", BLOCK, "signed_by_employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.personnel_orders t JOIN public.employees e ON e.employee_id=t.signed_by_employee_id WHERE e.person_id=:person_id"),
    _joined_rule("PERSONNEL_ORDER_AUDIT_RETAINED", "personnel_order_lifecycle_audit", INFORMATIONAL, "order item/signatory -> employee.person_id", "SELECT to_jsonb(t) state FROM public.personnel_order_lifecycle_audit t JOIN public.personnel_orders o ON o.order_id=t.order_id WHERE o.signed_by_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR EXISTS (SELECT 1 FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE i.order_id=o.order_id AND e.person_id=:person_id)"),
    _joined_rule("OPERATIONAL_ORDER_SIGNING_PRESENT", "operational_order_signing_attestations", BLOCK, "actor_employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.operational_order_signing_attestations t JOIN public.employees e ON e.employee_id=t.actor_employee_id WHERE e.person_id=:person_id"),
    _joined_rule("ACCESS_GRANT_RETAINED", "access_grants", INFORMATIONAL, "polymorphic Person/Employee/User", "SELECT to_jsonb(t) state FROM public.access_grants t WHERE (t.target_type='PERSON' AND t.target_id=:person_id) OR (t.target_type='EMPLOYEE' AND t.target_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id)) OR (t.target_type='USER' AND t.target_id IN (SELECT user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id))"),
    _joined_rule("PERSONNEL_VISIBILITY_RETAINED", "personnel_visibility_assignments", INFORMATIONAL, "target_user -> employee.person_id", "SELECT to_jsonb(t) state FROM public.personnel_visibility_assignments t JOIN public.users u ON u.user_id=t.target_user_id JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("LEGACY_IMPORT_STAGE_RETAINED", "employees_import_stage", INFORMATIONAL, "logical employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.employees_import_stage t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("PERSONNEL_MIGRATION_RUN_PRESENT", "personnel_migration_runs", BLOCK, "person_id or employee_context_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.personnel_migration_runs t WHERE t.person_id=:person_id OR t.employee_context_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id)"),
    _joined_rule("HR_BASELINE_ENTRY_RETAINED", "hr_baseline_entries", INFORMATIONAL, "employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_baseline_entries t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("HR_CHANGE_EVENT_RETAINED", "hr_change_events", INFORMATIONAL, "employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_change_events t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED", "hr_import_document_candidates", INFORMATIONAL, "employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_import_document_candidates t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("HR_MONTHLY_REFERENCE_ENTRY_RETAINED", "hr_monthly_reference_entries", INFORMATIONAL, "employee_id -> employee.person_id", "SELECT to_jsonb(t) state FROM public.hr_monthly_reference_entries t JOIN public.employees e ON e.employee_id=t.employee_id WHERE e.person_id=:person_id"),
    _joined_rule("INCOMING_DOCUMENT_PARTICIPATION_PRESENT", "incoming_documents", BLOCK, "Person, Employee or linked User participation", f"SELECT to_jsonb(t) state FROM public.incoming_documents t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("INCOMING_DOCUMENT_ASSIGNMENT_PRESENT", "incoming_document_assignments", BLOCK, "document participation or assignee Employee/User", f"""SELECT to_jsonb(t) state FROM public.incoming_document_assignments t WHERE
        t.assignee_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR
        t.assignee_user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR
        t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"""),
    _joined_rule("INCOMING_DOCUMENT_ATTACHMENT_PRESENT", "incoming_document_attachments", BLOCK, "incoming document participation", f"SELECT to_jsonb(t) state FROM public.incoming_document_attachments t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("INCOMING_DOCUMENT_AUDIT_RETAINED", "incoming_document_audit", BLOCK, "incoming document participation; legal audit retained", f"SELECT to_jsonb(t) state FROM public.incoming_document_audit t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("INCOMING_DOCUMENT_DEADLINE_CHANGE_PRESENT", "incoming_document_deadline_changes", BLOCK, "incoming document participation", f"SELECT to_jsonb(t) state FROM public.incoming_document_deadline_changes t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("INCOMING_DOCUMENT_OPERATIONAL_ORDER_LINK_PRESENT", "incoming_document_operational_order_links", BLOCK, "incoming document participation", f"SELECT to_jsonb(t) state FROM public.incoming_document_operational_order_links t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("INCOMING_DOCUMENT_PERSONNEL_ORDER_LINK_PRESENT", "incoming_document_personnel_order_links", BLOCK, "incoming document participation or personnel order involving Employee", f"""SELECT to_jsonb(t) state FROM public.incoming_document_personnel_order_links t WHERE
        t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL}) OR
        t.personnel_order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id)"""),
    _joined_rule("INCOMING_DOCUMENT_TRANSFER_PRESENT", "incoming_document_transfers", BLOCK, "incoming document participation", f"SELECT to_jsonb(t) state FROM public.incoming_document_transfers t WHERE t.incoming_document_id IN ({_INCOMING_DOCUMENT_IDS_SQL})"),
    _joined_rule("PERSONNEL_ORDER_ATTACHMENT_PRESENT", "personnel_order_attachments", BLOCK, "order -> item/signatory Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_attachments t WHERE t.order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id UNION SELECT o.order_id FROM public.personnel_orders o JOIN public.employees e ON e.employee_id=o.signed_by_employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("PERSONNEL_ORDER_EDITORIAL_BLOCK_PRESENT", "personnel_order_editorial_blocks", BLOCK, "order -> item/signatory Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_editorial_blocks t WHERE t.order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id UNION SELECT o.order_id FROM public.personnel_orders o JOIN public.employees e ON e.employee_id=o.signed_by_employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("PERSONNEL_ORDER_EVIDENCE_SCOPE_PRESENT", "personnel_order_evidence_scopes", BLOCK, "order -> item/signatory Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_evidence_scopes t WHERE t.order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id UNION SELECT o.order_id FROM public.personnel_orders o JOIN public.employees e ON e.employee_id=o.signed_by_employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("PERSONNEL_ORDER_ITEM_BASIS_PRESENT", "personnel_order_item_bases", BLOCK, "subject Employee or order item Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_item_bases t WHERE t.subject_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR t.order_item_id IN (SELECT i.item_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("PERSONNEL_ORDER_LOCALIZED_TEXT_PRESENT", "personnel_order_localized_texts", BLOCK, "order -> item/signatory Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_localized_texts t WHERE t.order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id UNION SELECT o.order_id FROM public.personnel_orders o JOIN public.employees e ON e.employee_id=o.signed_by_employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("PERSONNEL_ORDER_PRINT_PRESENT", "personnel_order_prints", BLOCK, "order -> item/signatory Employee -> Person", "SELECT to_jsonb(t) state FROM public.personnel_order_prints t WHERE t.order_id IN (SELECT i.order_id FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE e.person_id=:person_id UNION SELECT o.order_id FROM public.personnel_orders o JOIN public.employees e ON e.employee_id=o.signed_by_employee_id WHERE e.person_id=:person_id)"),
    _joined_rule("ONBOARDING_NOTIFICATION_PRESENT", "employee_onboarding_notifications", BLOCK, "onboarding -> all Person applications/Employee", "SELECT to_jsonb(t) state FROM public.employee_onboarding_notifications t JOIN public.employee_onboardings o ON o.onboarding_id=t.onboarding_id LEFT JOIN public.employees e ON e.employee_id=o.employee_id WHERE o.application_id=ANY(:application_ids) OR e.person_id=:person_id", keys=("person_id", "application_ids")),
    _joined_rule("ONBOARDING_TASK_AUDIT_PRESENT", "employee_onboarding_task_audit", BLOCK, "onboarding -> all Person applications/Employee", "SELECT to_jsonb(t) state FROM public.employee_onboarding_task_audit t JOIN public.employee_onboardings o ON o.onboarding_id=t.onboarding_id LEFT JOIN public.employees e ON e.employee_id=o.employee_id WHERE o.application_id=ANY(:application_ids) OR e.person_id=:person_id", keys=("person_id", "application_ids")),
    _joined_rule("USER_LINKAGE_EXECUTE_ITEM_PRESENT", "user_linkage_execute_items", BLOCK, "proposed Employee, source decision or linked User -> Person", "SELECT to_jsonb(t) state FROM public.user_linkage_execute_items t WHERE t.proposed_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR t.user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id) OR t.source_decision_id IN (SELECT d.decision_id FROM public.user_linkage_review_decisions d WHERE d.proposed_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id))"),
    _joined_rule("USER_LINKAGE_REVIEW_DECISION_PRESENT", "user_linkage_review_decisions", BLOCK, "proposed Employee or linked User -> Person", "SELECT to_jsonb(t) state FROM public.user_linkage_review_decisions t WHERE t.proposed_employee_id IN (SELECT employee_id FROM public.employees WHERE person_id=:person_id) OR t.user_id IN (SELECT u.user_id FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id WHERE e.person_id=:person_id)"),
)


def relationship_matrix_contract():
    return [{"code": r.code, "table": r.table, "category": r.category, "lookup": r.lookup, "keys": list(r.keys), "state_digest": r.state_digest, "create_allowed": r.create_allowed, "submit_allowed": r.submit_allowed, "approval_allowed": r.approval_allowed, "future_execution_allowed": r.future_execution_allowed, "required_hr_decision": r.required_hr_decision} for r in RELATIONSHIP_MATRIX]


def _stage_admissibility(rules: Iterable[RelationshipRule]) -> dict[str, bool]:
    present = tuple(rules)
    return {
        "create": all(rule.create_allowed for rule in present),
        "submit": all(rule.submit_allowed for rule in present),
        "approve": all(rule.approval_allowed for rule in present),
        "future_execution": all(rule.future_execution_allowed for rule in present),
    }


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _canonical_state_digest(states: Iterable[Any]) -> str:
    """Order-independent digest of complete row states."""
    return _canonical_hash(sorted(_canonical_hash(state) for state in states))


def _masked_iin(value: Any) -> str | None:
    digits = str(value or "").strip()
    return "********" + digits[-4:] if len(digits) == 12 and digits.isdigit() else None


def _missing_subject(person_id: int) -> str:
    return f"Запись #{int(person_id)} недоступна"


def normalize_mask(mask: str) -> str:
    value = " ".join(unicodedata.normalize("NFC", mask or "").strip().split())
    if not 3 <= len(value) <= 100: raise TestPersonnelDeletionError("TD_MASK_LENGTH", "Mask length must be between 3 and 100.", 422)
    if sum(c in "*?" for c in value) > 10: raise TestPersonnelDeletionError("TD_MASK_WILDCARDS", "Mask may contain at most 10 wildcards.", 422)
    if sum(c.isalnum() for c in value) < 3: raise TestPersonnelDeletionError("TD_MASK_TOO_BROAD", "Mask needs at least 3 alphanumeric literals.", 422)
    return value


def glob_to_ilike(mask: str) -> str:
    out=[]
    for c in normalize_mask(mask):
        out.append("\\"+c if c in "\\%_" else "%" if c == "*" else "_" if c == "?" else c)
    return "".join(out)


def validate_comment(comment: str | None) -> str | None:
    if comment is None: return None
    value=comment.strip()
    if not value or len(value)>MAX_COMMENT_LENGTH: raise TestPersonnelDeletionError("TD_COMMENT_INVALID", "Comment length must be 1..500.", 422)
    patterns=(r"(?<!\d)\d{12}(?!\d)", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", r"(?<!\d)(?:\+?\d[\s().-]*){7,15}(?!\d)")
    if any(re.search(p,value,re.I) for p in patterns): raise TestPersonnelDeletionError("TD_COMMENT_PII_FORBIDDEN", "Comment contains forbidden personal data.", 422)
    return value


def actor_role_code(user_id: int) -> str:
    with engine.connect() as c: return _actor_role_code(c,user_id)


def _actor_role_code(conn: Connection, user_id: int) -> str:
    value=conn.execute(text("SELECT r.code FROM users u JOIN roles r ON r.role_id=u.role_id WHERE u.user_id=:id AND u.is_active=TRUE"),{"id":user_id}).scalar_one_or_none()
    if value is None: raise TestPersonnelDeletionError("TD_ACTOR_NOT_FOUND", "Active actor was not found.",403)
    return str(value)


def _applications(conn, person_id):
    return [dict(r) for r in conn.execute(text("SELECT * FROM personnel_applications WHERE person_id=:id ORDER BY application_id"),{"id":person_id}).mappings()]


def _batch_rule_sql(rule: RelationshipRule) -> str:
    """Evaluate one server-owned rule once for every selected target."""
    rule_sql = rule.sql
    for parameter, expression in (
        (":application_ids", "s.application_ids"),
        (":application_id", "s.application_id"),
        (":person_id", "s.person_id"),
    ):
        rule_sql = rule_sql.replace(parameter, expression)
    return f"""
        WITH selected AS (
            SELECT
                (item->>'person_id')::bigint AS person_id,
                (item->>'application_id')::bigint AS application_id,
                ARRAY(
                    SELECT jsonb_array_elements_text(item->'application_ids')::bigint
                ) AS application_ids
            FROM jsonb_array_elements(CAST(:selected_targets AS jsonb)) item
        )
        SELECT s.person_id, s.application_id, matched.state
        FROM selected s
        CROSS JOIN LATERAL ({rule_sql}) matched
    """


def _relationship_batch_sql(rules: Iterable[RelationshipRule] = RELATIONSHIP_MATRIX) -> str:
    """Evaluate the complete server-owned matrix in one PostgreSQL round trip."""
    branches = []
    for rule in rules:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", rule.code):
            raise AssertionError(f"Unsafe relationship rule code: {rule.code!r}")
        rule_sql = rule.sql
        for parameter, expression in (
            (":application_ids", "s.application_ids"),
            (":application_id", "s.application_id"),
            (":person_id", "s.person_id"),
        ):
            rule_sql = rule_sql.replace(parameter, expression)
        branches.append(f"""SELECT s.person_id, s.application_id,
            '{rule.code}'::text AS rule_code, matched.state
            FROM selected s
            CROSS JOIN LATERAL ({rule_sql}) matched""")
    # PostgreSQL can otherwise spend tens of seconds JIT-compiling the large,
    # deliberately finite UNION tree.  Keep this transaction-local and in the
    # same protocol round trip as the SELECT; no database/global setting is
    # changed and the cursor result remains the final SELECT result.
    return """SET LOCAL jit=off;
        WITH selected AS (
            SELECT
                (item->>'person_id')::bigint AS person_id,
                (item->>'application_id')::bigint AS application_id,
                ARRAY(
                    SELECT jsonb_array_elements_text(item->'application_ids')::bigint
                ) AS application_ids
            FROM jsonb_array_elements(CAST(:selected_targets AS jsonb)) item
        )
    """ + "\nUNION ALL\n".join(branches)


def _evaluate_candidates(conn: Connection, pairs: Iterable[tuple[int, int]]) -> list[dict[str, Any]]:
    selected_pairs = sorted({(int(person_id), int(application_id)) for person_id, application_id in pairs})
    if not selected_pairs:
        return []
    person_ids = sorted({person_id for person_id, _ in selected_pairs})
    people = {
        int(row["person_id"]): dict(row)
        for row in conn.execute(text("""SELECT person_id,full_name,person_status,source,updated_at,to_jsonb(p) raw
            FROM persons p WHERE person_id=ANY(:person_ids)"""), {"person_ids": person_ids}).mappings()
    }
    applications_by_person: dict[int, list[dict[str, Any]]] = {person_id: [] for person_id in person_ids}
    applications_by_id: dict[int, dict[str, Any]] = {}
    for row in conn.execute(text("""SELECT * FROM personnel_applications
            WHERE person_id=ANY(:person_ids) ORDER BY person_id,application_id"""), {"person_ids": person_ids}).mappings():
        application = dict(row)
        applications_by_person[int(application["person_id"])].append(application)
        applications_by_id[int(application["application_id"])] = application
    selected_payload = []
    for person_id, application_id in selected_pairs:
        person = people.get(person_id)
        application = applications_by_id.get(application_id)
        if not person or not application or int(application["person_id"]) != person_id:
            raise TestPersonnelDeletionError("TD_TARGET_STATE_MISSING", "Target state is no longer available.", 409)
        selected_payload.append({
            "person_id": person_id,
            "application_id": application_id,
            "application_ids": [int(item["application_id"]) for item in applications_by_person[person_id]],
        })

    states_by_target: dict[tuple[int, int], dict[str, list[Any]]] = {
        pair: {} for pair in selected_pairs
    }
    environment = (os.getenv("APP_ENV") or "dev").strip().lower()
    params = {
        "selected_targets": json.dumps(selected_payload, separators=(",", ":")),
        "early_actions": list(EARLY_LIFECYCLE_ACTIONS),
        "environment": environment,
    }
    rules_by_code = {rule.code: rule for rule in RELATIONSHIP_MATRIX}
    for row in conn.execute(text(_relationship_batch_sql()), params).mappings():
        pair = (int(row["person_id"]), int(row["application_id"]))
        code = str(row["rule_code"])
        if pair not in states_by_target or code not in rules_by_code:
            raise AssertionError("Relationship batch returned an unknown target or rule.")
        states_by_target[pair].setdefault(code, []).append(row["state"])

    candidates = []
    provenance_code = "PROVENANCE_STATE_RETAINED"
    for person_id, application_id in selected_pairs:
        person = people[person_id]
        application = applications_by_id[application_id]
        applications = applications_by_person[person_id]
        app_ids = [int(item["application_id"]) for item in applications]
        target_states = states_by_target[(person_id, application_id)]
        relationships: dict[str, Any] = {}
        categories = {category: [] for category in (BLOCK, TOMBSTONE_REQUIRED, HR_ATTESTATION_REQUIRED, INFORMATIONAL)}
        for code, states in target_states.items():
            rule = rules_by_code[code]
            relationships[code] = {
                "table": rule.table, "category": rule.category, "count": len(states),
                "state_digest": _canonical_state_digest(states),
                "create_allowed": rule.create_allowed, "submit_allowed": rule.submit_allowed,
                "approval_allowed": rule.approval_allowed,
                "future_execution_allowed": rule.future_execution_allowed,
                "required_hr_decision": rule.required_hr_decision,
            }
            categories[rule.category].append(code)
        category_codes = {category: sorted(set(codes)) for category, codes in categories.items()}
        snapshot = {
            "policy_version": POLICY_VERSION, "environment": environment,
            "person": {"person_id": person_id, "person_status": person["person_status"],
                "source": person["source"], "updated_at": person["updated_at"],
                "row_digest": _canonical_hash(person["raw"])},
            "application": {"application_id": application_id, "status": str(application["status"]),
                "row_digest": _canonical_hash(application)},
            "all_application_ids": app_ids,
            "all_applications_digest": _canonical_state_digest(applications),
            "relationships": dict(sorted(relationships.items())),
            "category_codes": category_codes,
        }
        snapshot["fingerprint"] = _canonical_hash(snapshot)
        provenance_states = target_states.get(provenance_code, [])
        has_provenance = any(bool(state.get("active")) for state in provenance_states if isinstance(state, Mapping))
        present_rules = [rules_by_code[code] for code in target_states]
        stage_admissibility = _stage_admissibility(present_rules)
        eligibility = "BLOCKED" if category_codes[BLOCK] else "HR_ATTESTATION_REQUIRED" if category_codes[HR_ATTESTATION_REQUIRED] else "TOMBSTONE_REQUIRED" if category_codes[TOMBSTONE_REQUIRED] else "ELIGIBLE"
        candidates.append({"target_type": "APPLICANT", "person_id": person_id,
            "application_id": application_id,
            "subject": str(person["full_name"]).strip() if person["full_name"] else _missing_subject(person_id),
            "masked_iin": _masked_iin(person["raw"].get("iin")),
            "person_status": person["person_status"], "application_status": str(application["status"]),
            "has_test_provenance": has_provenance, "eligibility_status": eligibility,
            "stage_admissibility": stage_admissibility,
            "blocking_codes": category_codes[BLOCK], "tombstone_required_codes": category_codes[TOMBSTONE_REQUIRED],
            "hr_attestation_codes": category_codes[HR_ATTESTATION_REQUIRED],
            "informational_codes": category_codes[INFORMATIONAL], "relationship_summary": snapshot["relationships"],
            "requires_hr_synthetic_confirmation": bool(category_codes[HR_ATTESTATION_REQUIRED]),
            "relationship_fingerprint": snapshot["fingerprint"], "relationship_snapshot": snapshot})
    return candidates


def _candidate(conn,person_id,application_id):
    return _evaluate_candidates(conn, [(person_id, application_id)])[0]


def preview_candidates(*,mask,field,person_ids,application_ids):
    if field!="full_name": raise TestPersonnelDeletionError("TD_SEARCH_FIELD_FORBIDDEN","Only full_name is searchable.",422)
    if not mask and not person_ids and not application_ids: raise TestPersonnelDeletionError("TD_PREVIEW_EMPTY","Mask or exact IDs are required.",422)
    params={"limit":MAX_PREVIEW_RESULTS+1}; clauses=[]
    if mask: params["pattern"]=glob_to_ilike(mask); clauses.append("normalize(p.full_name,NFC) COLLATE \"und-x-icu\" ILIKE :pattern ESCAPE E'\\\\'")
    if person_ids: params["person_ids"]=sorted(set(map(int,person_ids))); clauses.append("p.person_id=ANY(:person_ids)")
    if application_ids: params["application_ids"]=sorted(set(map(int,application_ids))); clauses.append("a.application_id=ANY(:application_ids)")
    with engine.connect() as conn:
        rows=conn.execute(text(f"SELECT p.person_id,a.application_id FROM persons p JOIN personnel_applications a USING(person_id) WHERE ({' OR '.join(clauses)}) ORDER BY p.person_id,a.application_id LIMIT :limit"),params).mappings().all()
        if len(rows)>MAX_PREVIEW_RESULTS: raise TestPersonnelDeletionError("TD_PREVIEW_TOO_BROAD","Preview exceeds 200 candidates.",422)
        items=_evaluate_candidates(conn, [(int(r["person_id"]), int(r["application_id"])) for r in rows])
    return {"items":items,"count":len(items),"normalized_mask":normalize_mask(mask) if mask else None}


def _manifest_v2_roots(targets: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    application_ids_by_person: dict[int, set[int]] = {}
    for target in targets:
        person_id = int(target["person_id"])
        application_id = int(target["application_id"])
        application_ids_by_person.setdefault(person_id, set()).add(application_id)
    return [
        {
            "root_type": "PERSON",
            "person_id": person_id,
            "application_ids": sorted(application_ids),
        }
        for person_id, application_ids in sorted(application_ids_by_person.items())
    ]


def _target_set_hash(targets: Iterable[Mapping[str, Any]]) -> str:
    return _canonical_hash({
        "schema": MANIFEST_SCHEMA,
        "manifest_version": MANIFEST_VERSION,
        "process_type": APPLICANT_PROCESS_TYPE,
        "targets": _manifest_v2_roots(targets),
    })


def _aggregate_fingerprint(candidates): return _canonical_hash({"policy_version":POLICY_VERSION,"targets":sorted((int(c["person_id"]),int(c["application_id"]),c["relationship_fingerprint"]) for c in candidates)})
def _command_hash(action,request_id,payload): return _canonical_hash({"action":action,"request_id":str(request_id) if request_id else None,"payload":payload})


def _find_idempotent(conn,actor,action,key,cmd_hash,request_id):
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:v,0))"),{"v":f"WP-TD-002B:{actor}:{action}:{key}"})
    row=conn.execute(text("SELECT request_id,command_payload_hash,result_code,result_projection FROM test_personnel_deletion_history WHERE actor_user_id=:a AND action=:x AND idempotency_key=:k"),{"a":actor,"x":action,"k":key}).mappings().first()
    if row and (row["command_payload_hash"]!=cmd_hash or (request_id is not None and str(row["request_id"])!=str(request_id))): raise TestPersonnelDeletionError("TD_IDEMPOTENCY_PAYLOAD_CONFLICT","Idempotency key was used for another command payload.",409)
    return dict(row) if row else None


def _command_result_projection(conn: Connection, request_id, result_code: str) -> dict[str, Any]:
    request=_effective(_request_row(conn,request_id))
    targets=[dict(row) for row in conn.execute(text("""SELECT target_type,person_id,application_id,
        eligibility_status,blocking_codes,tombstone_required_codes,hr_attestation_codes,
        informational_codes,manifest_order,requires_hr_synthetic_confirmation
        FROM test_personnel_deletion_targets WHERE request_id=:id ORDER BY manifest_order"""),{"id":request_id}).mappings()]
    manifest_targets=[dict(row) for row in conn.execute(text("""SELECT root_type,person_id,
        application_ids,manifest_order FROM test_personnel_deletion_manifest_v2_targets
        WHERE request_id=:id ORDER BY manifest_order"""),{"id":request_id}).mappings()] if request["manifest_version"] == MANIFEST_VERSION else []
    history=[dict(row) for row in conn.execute(text("""SELECT actor_user_id,actor_role_code,
        permission_code,action,old_status,new_status,old_version,new_version,target_set_hash,
        idempotency_key,command_payload_hash,occurred_at,result_code
        FROM test_personnel_deletion_history WHERE request_id=:id ORDER BY history_id"""),{"id":request_id}).mappings()]
    decisions=[dict(row) for row in conn.execute(text("""SELECT decision_id,decision,
        actor_user_id,actor_role_code,permission_code,request_version,target_set_hash,
        submitted_synthetic_confirmed,decided_at
        FROM test_personnel_deletion_decisions WHERE request_id=:id ORDER BY decision_id"""),{"id":request_id}).mappings()]
    projection={
        "request_id":str(request["request_id"]), "request_number":request["request_number"],
        "status":request["status"], "stored_status":request["stored_status"],
        "approval_valid":request["approval_valid"], "basis":request["basis"],
        "reason_code":request["reason_code"], "target_set_hash":request["target_set_hash"],
        "manifest_version":request["manifest_version"], "process_type":request["process_type"],
        "manifest_read_only":request["manifest_read_only"],
        "approval_eligible":request["approval_eligible"],
        "execution_eligible":request["execution_eligible"],
        "execution_block_code":request["execution_block_code"],
        "relationship_fingerprint":request["relationship_fingerprint"],
        "version":request["version"], "initiated_by_user_id":request["initiated_by_user_id"],
        "created_at":request["created_at"], "submitted_at":request["submitted_at"],
        "expires_at":request["expires_at"], "last_checked_at":request["last_checked_at"],
        "approved_at":request["approved_at"], "approval_expires_at":request["approval_expires_at"],
        "result_code":result_code, "targets":targets, "manifest_targets":manifest_targets,
        "history":history, "decisions":decisions,
    }
    return json.loads(json.dumps(projection,default=str))


def _history(conn,*,request_id,actor,role,permission,action,old_status,new_status,old_version,new_version,target_hash,comment,key,command_hash,result):
    projection=_command_result_projection(conn,request_id,result)
    conn.execute(text("INSERT INTO test_personnel_deletion_history(request_id,actor_user_id,actor_role_code,permission_code,action,old_status,new_status,old_version,new_version,target_set_hash,comment,idempotency_key,command_payload_hash,result_code,result_projection) VALUES(:request_id,:actor,:role,:permission,:action,:old_status,:new_status,:old_version,:new_version,:target_hash,:comment,:key,:command_hash,:result,CAST(:projection AS jsonb))"),{**locals(),"projection":json.dumps(projection,sort_keys=True,separators=(",",":"))})
    return projection


T=TypeVar("T")
def _serialization_failure(e):
    orig=getattr(e,"orig",None); return getattr(orig,"pgcode",None)=="40001" or getattr(orig,"sqlstate",None)=="40001"
def _serializable(work: Callable[[Connection],T])->T:
    for attempt in range(3):
        try:
            with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
                with conn.begin(): return work(conn)
        except DBAPIError as e:
            if not _serialization_failure(e): raise
            if attempt==2: raise TestPersonnelDeletionError("TD_SERIALIZATION_RETRY_EXHAUSTED","Concurrent state change; retry command.",409) from e
    raise AssertionError


def _request_row(conn,rid,lock=False):
    row=conn.execute(text(f"SELECT r.*,statement_timestamp() db_now FROM test_personnel_deletion_requests r WHERE request_id=:id{' FOR UPDATE' if lock else ''}"),{"id":rid}).mappings().first()
    if not row: raise TestPersonnelDeletionError("TD_REQUEST_NOT_FOUND","Request was not found.",404)
    return dict(row)
def _effective(row):
    now=row.pop("db_now",None); row["stored_status"]=row["status"]; row["approval_valid"]=bool(row["status"]=="APPROVED" and row.get("approval_expires_at") and now and row["approval_expires_at"]>now)
    if row["status"]=="APPROVED" and not row["approval_valid"]: row["status"]="EXPIRED"
    manifest_version=int(row.get("manifest_version") or 1)
    row["manifest_version"]=manifest_version
    row["process_type"]=row.get("process_type") or APPLICANT_PROCESS_TYPE
    row["manifest_read_only"]=manifest_version < MANIFEST_VERSION
    row["approval_eligible"]=manifest_version == MANIFEST_VERSION
    row["execution_eligible"]=False
    row["execution_block_code"]=(
        "TD_MANIFEST_V1_READ_ONLY"
        if row["manifest_read_only"]
        else "TD_EXECUTION_NOT_IMPLEMENTED"
    )
    return row


def _identity_projections(conn: Connection, person_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    ids = sorted({int(person_id) for person_id in person_ids})
    projections = {
        person_id: {"subject": _missing_subject(person_id), "masked_iin": None}
        for person_id in ids
    }
    if not ids:
        return projections
    for row in conn.execute(text("""SELECT person_id,full_name,iin FROM public.persons
            WHERE person_id=ANY(:person_ids)"""), {"person_ids": ids}).mappings():
        person_id = int(row["person_id"])
        projections[person_id] = {
            "subject": str(row["full_name"]).strip() if row["full_name"] else _missing_subject(person_id),
            "masked_iin": _masked_iin(row["iin"]),
        }
    return projections


def _user_display_names(conn: Connection, user_ids: Iterable[int]) -> dict[int, str]:
    ids = sorted({int(user_id) for user_id in user_ids})
    names = {user_id: f"Пользователь #{user_id}" for user_id in ids}
    if not ids:
        return names
    for row in conn.execute(text("""SELECT user_id,full_name FROM public.users
            WHERE user_id=ANY(:user_ids)"""), {"user_ids": ids}).mappings():
        user_id = int(row["user_id"])
        value = str(row["full_name"] or "").strip()
        if value:
            names[user_id] = value
    return names


def _decorate_request_read_projection(conn: Connection, detail: dict[str, Any]) -> dict[str, Any]:
    targets = detail.get("targets") or []
    identities = _identity_projections(conn, (int(target["person_id"]) for target in targets))
    for target in targets:
        target.update(identities[int(target["person_id"])])
    decisions = detail.get("decisions") or []
    participant_ids = [int(detail["initiated_by_user_id"])]
    participant_ids.extend(int(decision["actor_user_id"]) for decision in decisions)
    names = _user_display_names(conn, participant_ids)
    detail["initiated_by_display_name"] = names[int(detail["initiated_by_user_id"])]
    for decision in decisions:
        decision["actor_display_name"] = names[int(decision["actor_user_id"])]
    return detail


def _request_detail(conn,rid):
    out=_effective(_request_row(conn,rid)); out["targets"]=[dict(r) for r in conn.execute(text("SELECT * FROM test_personnel_deletion_targets WHERE request_id=:id ORDER BY manifest_order"),{"id":rid}).mappings()]; out["manifest_targets"]=[dict(r) for r in conn.execute(text("SELECT root_type,person_id,application_ids,manifest_order,created_at FROM test_personnel_deletion_manifest_v2_targets WHERE request_id=:id ORDER BY manifest_order"),{"id":rid}).mappings()] if out["manifest_version"] == MANIFEST_VERSION else []; out["decisions"]=[dict(r) for r in conn.execute(text("SELECT * FROM test_personnel_deletion_decisions WHERE request_id=:id ORDER BY decision_id"),{"id":rid}).mappings()]; out["history"]=[dict(r) for r in conn.execute(text("SELECT * FROM test_personnel_deletion_history WHERE request_id=:id ORDER BY history_id"),{"id":rid}).mappings()]; return _decorate_request_read_projection(conn,out)
def get_request(rid):
    with engine.connect() as c:return _request_detail(c,rid)
def list_requests(*,pending_only=False,initiator_user_id=None):
    clauses=[]; params={}
    if pending_only: clauses.append("status='PENDING_HR_APPROVAL'")
    if initiator_user_id is not None: clauses.append("initiated_by_user_id=:i");params["i"]=initiator_user_id
    with engine.connect() as c:
        rows=[_effective(dict(r)) for r in c.execute(text("SELECT r.*,statement_timestamp() db_now FROM test_personnel_deletion_requests r"+(" WHERE "+" AND ".join(clauses) if clauses else "")+" ORDER BY created_at DESC,request_id"),params).mappings()]
        names=_user_display_names(c,(int(row["initiated_by_user_id"]) for row in rows))
        for row in rows:row["initiated_by_display_name"]=names[int(row["initiated_by_user_id"])]
        return rows
def safe_identity(person_id):
    with engine.connect() as c:return _identity_projections(c,[int(person_id)])[int(person_id)]


def _validate_manifest(conn,pairs):
    chosen={}
    for p,a in pairs:chosen.setdefault(p,set()).add(a)
    actual_by_person={person_id:set() for person_id in chosen}
    rows=conn.execute(text("""SELECT person_id,application_id
        FROM personnel_applications
        WHERE person_id=ANY(:person_ids)
        ORDER BY person_id,application_id"""),{"person_ids":sorted(chosen)}).all()
    for person_id,application_id in rows:
        actual_by_person[int(person_id)].add(int(application_id))
    if any(not actual_by_person[person_id] or actual_by_person[person_id]!=application_ids
           for person_id,application_ids in chosen.items()):
        raise TestPersonnelDeletionError("TD_MANIFEST_APPLICATION_SET_INCOMPLETE","Manifest must contain every application for each Person.",409)


def _manifest_v2_pairs(conn: Connection, request_id: Any) -> list[tuple[int, int]]:
    roots = conn.execute(text("""SELECT person_id,application_ids
        FROM test_personnel_deletion_manifest_v2_targets
        WHERE request_id=:id ORDER BY manifest_order"""), {"id": request_id}).mappings().all()
    if not roots:
        raise TestPersonnelDeletionError(
            "TD_MANIFEST_V2_ROOTS_MISSING",
            "Manifest v2 must contain at least one PERSON root.",
            409,
        )
    pairs = [
        (int(root["person_id"]), int(application_id))
        for root in roots
        for application_id in root["application_ids"]
    ]
    projection_pairs = [
        (int(row[0]), int(row[1]))
        for row in conn.execute(text("""SELECT person_id,application_id
            FROM test_personnel_deletion_targets
            WHERE request_id=:id ORDER BY manifest_order"""), {"id": request_id})
    ]
    if sorted(pairs) != sorted(projection_pairs):
        raise TestPersonnelDeletionError(
            "TD_MANIFEST_V2_PROJECTION_MISMATCH",
            "Manifest v2 PERSON roots do not match application projections.",
            409,
        )
    _validate_manifest(conn, pairs)
    return pairs


def create_draft(*,actor_user_id,basis,reason_code,preview_criteria,original_mask,targets,idempotency_key,process_type=APPLICANT_PROCESS_TYPE):
    if process_type != APPLICANT_PROCESS_TYPE:raise TestPersonnelDeletionError("TD_PROCESS_TYPE_INVALID","Only applicant-only requests are supported.",422)
    if basis not in {"PROVENANCE","LEGACY_MANIFEST"}:raise TestPersonnelDeletionError("TD_BASIS_INVALID","Unsupported request basis.",422)
    if reason_code not in REASON_CODES:raise TestPersonnelDeletionError("TD_REASON_CODE_INVALID","Unsupported reason code.",422)
    if not targets or len(targets)>MAX_PREVIEW_RESULTS:raise TestPersonnelDeletionError("TD_TARGET_COUNT","Request must contain 1..200 targets.",422)
    key=idempotency_key.strip(); mask=normalize_mask(original_mask) if original_mask else None; pairs=sorted({(int(t["person_id"]),int(t["application_id"])) for t in targets})
    if len(pairs)!=len(targets):raise TestPersonnelDeletionError("TD_TARGET_DUPLICATE","Manifest contains duplicate targets.",422)
    cmd=_command_hash("CREATE",None,{"manifest_version":MANIFEST_VERSION,"process_type":process_type,"basis":basis,"reason_code":reason_code,"criteria":dict(preview_criteria),"mask":mask,"targets":pairs})
    def work(conn):
        old=_find_idempotent(conn,actor_user_id,"CREATE",key,cmd,None)
        if old:return dict(old["result_projection"])
        role=_actor_role_code(conn,actor_user_id);_validate_manifest(conn,pairs); candidates=_evaluate_candidates(conn,pairs)
        if any(not c["stage_admissibility"]["create"] for c in candidates):raise TestPersonnelDeletionError("TD_TARGET_BLOCKED","Target has blocking relationships.",409)
        if basis=="PROVENANCE" and any(not c["has_test_provenance"] for c in candidates):raise TestPersonnelDeletionError("TD_PROVENANCE_REQUIRED","Protected provenance is missing.",409)
        rid=uuid.uuid4(); th=_target_set_hash(candidates); fp=_aggregate_fingerprint(candidates); number="TD-"+rid.hex[:16].upper()
        conn.execute(text("INSERT INTO test_personnel_deletion_requests(request_id,request_number,basis,reason_code,preview_criteria,original_mask,target_set_hash,relationship_fingerprint,manifest_version,process_type,initiated_by_user_id) VALUES(:id,:n,:b,:r,CAST(:c AS jsonb),:m,:h,:f,:mv,:pt,:a)"),{"id":rid,"n":number,"b":basis,"r":reason_code,"c":json.dumps(dict(preview_criteria)),"m":mask,"h":th,"f":fp,"mv":MANIFEST_VERSION,"pt":process_type,"a":actor_user_id})
        for order,root in enumerate(_manifest_v2_roots(candidates)):conn.execute(text("INSERT INTO test_personnel_deletion_manifest_v2_targets(request_id,root_type,person_id,application_ids,manifest_order) VALUES(:request_id,:root_type,:person_id,:application_ids,:manifest_order)"),{**root,"request_id":rid,"manifest_order":order})
        for order,c in enumerate(candidates):conn.execute(text("INSERT INTO test_personnel_deletion_targets(request_id,target_type,person_id,application_id,eligibility_status,blocking_codes,tombstone_required_codes,hr_attestation_codes,informational_codes,relationship_snapshot,relationship_fingerprint,manifest_order,requires_hr_synthetic_confirmation) VALUES(:request_id,'APPLICANT',:person_id,:application_id,:eligibility_status,:blocking_codes,:tombstone_required_codes,:hr_attestation_codes,:informational_codes,CAST(:snapshot AS jsonb),:relationship_fingerprint,:manifest_order,:requires_hr_synthetic_confirmation)"),{**c,"request_id":rid,"snapshot":json.dumps(c["relationship_snapshot"],default=str),"manifest_order":order})
        return _history(conn,request_id=rid,actor=actor_user_id,role=role,permission=REQUEST_PERMISSION,action="CREATE",old_status=None,new_status="DRAFT",old_version=None,new_version=1,target_hash=th,comment=None,key=key,command_hash=cmd,result="TD_DRAFT_CREATED")
    return _serializable(work)


def _current(conn,rid):
    request=conn.execute(text("SELECT manifest_version,process_type FROM test_personnel_deletion_requests WHERE request_id=:id"),{"id":rid}).mappings().one()
    if int(request["manifest_version"]) != MANIFEST_VERSION:
        raise TestPersonnelDeletionError("TD_MANIFEST_V1_READ_ONLY","Manifest v1 is retained for viewing only.",409)
    if request["process_type"] != APPLICANT_PROCESS_TYPE:
        raise TestPersonnelDeletionError("TD_PROCESS_TYPE_INVALID","Only applicant-only requests are supported.",409)
    return _evaluate_candidates(conn,_manifest_v2_pairs(conn,rid))
def _mark_drift(conn,request,*,actor,role,permission,action,key,cmd):
    try: changed=_aggregate_fingerprint(_current(conn,request["request_id"]))!=request["relationship_fingerprint"];code="TD_FINGERPRINT_CHANGED"
    except TestPersonnelDeletionError as e:
        if e.code not in {"TD_TARGET_STATE_MISSING","TD_MANIFEST_APPLICATION_SET_INCOMPLETE"}:raise
        changed=True;code="TD_TARGET_STATE_MISSING"
    if not changed:return None,None
    nv=int(request["version"])+1;conn.execute(text("UPDATE test_personnel_deletion_requests SET status='REAPPROVAL_REQUIRED',version=:v,last_checked_at=statement_timestamp(),approved_at=NULL,approval_expires_at=NULL WHERE request_id=:id AND version=:old"),{"v":nv,"id":request["request_id"],"old":request["version"]});projection=_history(conn,request_id=request["request_id"],actor=actor,role=role,permission=permission,action=action,old_status=request["status"],new_status="REAPPROVAL_REQUIRED",old_version=request["version"],new_version=nv,target_hash=request["target_set_hash"],comment=None,key=key,command_hash=cmd,result=code);return projection,code
def _refresh(conn,request):
    cs=_current(conn,request["request_id"])
    if any(not c["stage_admissibility"]["submit"] for c in cs):raise TestPersonnelDeletionError("TD_TARGET_BLOCKED","Target has blocking relationships.",409)
    if request["basis"]=="PROVENANCE" and any(not c["has_test_provenance"] for c in cs):raise TestPersonnelDeletionError("TD_PROVENANCE_REQUIRED","Protected provenance is missing.",409)
    for order,c in enumerate(cs):conn.execute(text("UPDATE test_personnel_deletion_targets SET eligibility_status=:eligibility_status,blocking_codes=:blocking_codes,tombstone_required_codes=:tombstone_required_codes,hr_attestation_codes=:hr_attestation_codes,informational_codes=:informational_codes,relationship_snapshot=CAST(:snapshot AS jsonb),relationship_fingerprint=:relationship_fingerprint,requires_hr_synthetic_confirmation=:requires_hr_synthetic_confirmation WHERE request_id=:rid AND manifest_order=:ord"),{**c,"snapshot":json.dumps(c["relationship_snapshot"],default=str),"rid":request["request_id"],"ord":order})
    return _aggregate_fingerprint(cs)


def submit_request(*,request_id,actor_user_id,expected_version,idempotency_key):
    key=idempotency_key.strip();cmd=_command_hash("SUBMIT",request_id,{"expected_version":expected_version})
    def work(conn):
        old=_find_idempotent(conn,actor_user_id,"SUBMIT",key,cmd,request_id)
        if old:return dict(old["result_projection"]),(None if old["result_code"]=="TD_SUBMITTED" else old["result_code"])
        r=_request_row(conn,request_id,True);role=_actor_role_code(conn,actor_user_id)
        if int(r["manifest_version"]) != MANIFEST_VERSION:raise TestPersonnelDeletionError("TD_MANIFEST_V1_READ_ONLY","Manifest v1 cannot be submitted for a new approval.",409)
        if r["process_type"] != APPLICANT_PROCESS_TYPE:raise TestPersonnelDeletionError("TD_PROCESS_TYPE_INVALID","Only applicant-only requests are supported.",409)
        if r["initiated_by_user_id"]!=actor_user_id:raise TestPersonnelDeletionError("TD_NOT_INITIATOR","Only the initiator may submit this request.",403)
        if r["status"] not in {"DRAFT","REAPPROVAL_REQUIRED"}:raise TestPersonnelDeletionError("TD_STATUS_CONFLICT","Request cannot be submitted in its current status.")
        if r["version"]!=expected_version:raise TestPersonnelDeletionError("TD_VERSION_CONFLICT","Request version has changed.")
        if r["status"]=="REAPPROVAL_REQUIRED":fp=_refresh(conn,r)
        else:
            drift,code=_mark_drift(conn,r,actor=actor_user_id,role=role,permission=REQUEST_PERMISSION,action="SUBMIT",key=key,cmd=cmd)
            if drift:return drift,code
            fp=r["relationship_fingerprint"]
        nv=expected_version+1;conn.execute(text("UPDATE test_personnel_deletion_requests SET status='PENDING_HR_APPROVAL',version=:v,submitted_at=statement_timestamp(),expires_at=statement_timestamp()+interval '24 hours',last_checked_at=statement_timestamp(),relationship_fingerprint=:fp WHERE request_id=:id AND version=:old"),{"v":nv,"fp":fp,"id":request_id,"old":expected_version});projection=_history(conn,request_id=request_id,actor=actor_user_id,role=role,permission=REQUEST_PERMISSION,action="SUBMIT",old_status=r["status"],new_status="PENDING_HR_APPROVAL",old_version=expected_version,new_version=nv,target_hash=r["target_set_hash"],comment=None,key=key,command_hash=cmd,result="TD_SUBMITTED");return projection,None
    return _serializable(work)


def cancel_request(*,request_id,actor_user_id,expected_version,idempotency_key,comment):
    key=idempotency_key.strip();comment=validate_comment(comment);cmd=_command_hash("CANCEL",request_id,{"expected_version":expected_version,"comment":comment})
    def work(conn):
        old=_find_idempotent(conn,actor_user_id,"CANCEL",key,cmd,request_id)
        if old:return dict(old["result_projection"])
        r=_request_row(conn,request_id,True);role=_actor_role_code(conn,actor_user_id)
        if r["initiated_by_user_id"]!=actor_user_id:raise TestPersonnelDeletionError("TD_NOT_INITIATOR","Only the initiator may cancel this request.",403)
        if r["status"] not in {"DRAFT","PENDING_HR_APPROVAL","APPROVED","REAPPROVAL_REQUIRED"}:raise TestPersonnelDeletionError("TD_STATUS_CONFLICT","Request cannot be cancelled.")
        if r["version"]!=expected_version:raise TestPersonnelDeletionError("TD_VERSION_CONFLICT","Request version has changed.")
        nv=expected_version+1;conn.execute(text("UPDATE test_personnel_deletion_requests SET status='CANCELLED',version=:v,approved_at=NULL,approval_expires_at=NULL WHERE request_id=:id AND version=:old"),{"v":nv,"id":request_id,"old":expected_version});return _history(conn,request_id=request_id,actor=actor_user_id,role=role,permission=REQUEST_PERMISSION,action="CANCEL",old_status=r["status"],new_status="CANCELLED",old_version=expected_version,new_version=nv,target_hash=r["target_set_hash"],comment=comment,key=key,command_hash=cmd,result="TD_CANCELLED")
    return _serializable(work)


def decide_request(*,request_id,actor_user_id,expected_version,decision,idempotency_key,comment,submitted_synthetic_confirmed):
    action=decision.upper()
    if action not in {"APPROVE","REJECT"}:raise TestPersonnelDeletionError("TD_DECISION_INVALID","Decision must be APPROVE or REJECT.",422)
    key=idempotency_key.strip();comment=validate_comment(comment);cmd=_command_hash(action,request_id,{"expected_version":expected_version,"comment":comment,"submitted_synthetic_confirmed":submitted_synthetic_confirmed})
    def work(conn):
        old=_find_idempotent(conn,actor_user_id,action,key,cmd,request_id)
        if old:return dict(old["result_projection"]),(None if old["result_code"] in {"TD_APPROVED","TD_REJECTED"} else old["result_code"])
        r=_request_row(conn,request_id,True);role=_actor_role_code(conn,actor_user_id)
        if r["initiated_by_user_id"]==actor_user_id:raise TestPersonnelDeletionError("TD_SEPARATION_OF_DUTIES","The initiator cannot decide this request.",403)
        if r["status"]!="PENDING_HR_APPROVAL":raise TestPersonnelDeletionError("TD_STATUS_CONFLICT","Request is not pending HR approval.")
        if r["version"]!=expected_version:raise TestPersonnelDeletionError("TD_VERSION_CONFLICT","Request version has changed.")
        if action=="APPROVE" and int(r["manifest_version"]) != MANIFEST_VERSION:raise TestPersonnelDeletionError("TD_MANIFEST_V1_READ_ONLY","Manifest v1 cannot receive a new approval.",409)
        if action=="APPROVE" and r["process_type"] != APPLICANT_PROCESS_TYPE:raise TestPersonnelDeletionError("TD_PROCESS_TYPE_INVALID","Only applicant-only requests are supported.",409)
        if r["expires_at"] and r["expires_at"]<=r["db_now"]:
            nv=expected_version+1;conn.execute(text("UPDATE test_personnel_deletion_requests SET status='EXPIRED',version=:v WHERE request_id=:id AND version=:old"),{"v":nv,"id":request_id,"old":expected_version});projection=_history(conn,request_id=request_id,actor=actor_user_id,role=role,permission=APPROVE_PERMISSION,action=action,old_status="PENDING_HR_APPROVAL",new_status="EXPIRED",old_version=expected_version,new_version=nv,target_hash=r["target_set_hash"],comment=None,key=key,command_hash=cmd,result="TD_APPROVAL_WINDOW_EXPIRED");return projection,"TD_APPROVAL_WINDOW_EXPIRED"
        if action=="APPROVE":
            needs=conn.execute(text("SELECT EXISTS(SELECT 1 FROM test_personnel_deletion_targets WHERE request_id=:id AND requires_hr_synthetic_confirmation)"),{"id":request_id}).scalar_one()
            if needs and not submitted_synthetic_confirmed:raise TestPersonnelDeletionError("TD_SUBMITTED_ATTESTATION_REQUIRED","HR_HEAD must confirm submitted records are synthetic.",409)
            drift,code=_mark_drift(conn,r,actor=actor_user_id,role=role,permission=APPROVE_PERMISSION,action=action,key=key,cmd=cmd)
            if drift:return drift,code
        status="APPROVED" if action=="APPROVE" else "REJECTED";nv=expected_version+1
        if action=="APPROVE":conn.execute(text("UPDATE test_personnel_deletion_requests SET status='APPROVED',version=:v,approved_at=statement_timestamp(),approval_expires_at=statement_timestamp()+interval '24 hours',last_checked_at=statement_timestamp() WHERE request_id=:id AND version=:old"),{"v":nv,"id":request_id,"old":expected_version})
        else:conn.execute(text("UPDATE test_personnel_deletion_requests SET status='REJECTED',version=:v,last_checked_at=statement_timestamp() WHERE request_id=:id AND version=:old"),{"v":nv,"id":request_id,"old":expected_version})
        conn.execute(text("INSERT INTO test_personnel_deletion_decisions(request_id,decision,actor_user_id,actor_role_code,permission_code,request_version,target_set_hash,comment,submitted_synthetic_confirmed) VALUES(:id,:d,:a,:r,:p,:v,:h,:c,:s)"),{"id":request_id,"d":action,"a":actor_user_id,"r":role,"p":APPROVE_PERMISSION,"v":nv,"h":r["target_set_hash"],"c":comment,"s":submitted_synthetic_confirmed});projection=_history(conn,request_id=request_id,actor=actor_user_id,role=role,permission=APPROVE_PERMISSION,action=action,old_status="PENDING_HR_APPROVAL",new_status=status,old_version=expected_version,new_version=nv,target_hash=r["target_set_hash"],comment=None,key=key,command_hash=cmd,result="TD_"+status);return projection,None
    return _serializable(work)


def legacy_hard_delete_enabled() -> bool:
    return False
