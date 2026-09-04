"""WP-TD-002D: indexes for batched relationship lookup predicates.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
"""
from __future__ import annotations

from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_td002d_incoming_sender_person", "incoming_documents", "sender_person_id"),
    ("ix_td002d_incoming_sender_employee", "incoming_documents", "sender_employee_id"),
    ("ix_td002d_incoming_addressee_employee", "incoming_documents", "addressee_employee_id"),
    ("ix_td002d_incoming_addressee_user", "incoming_documents", "addressee_user_id"),
    ("ix_td002d_incoming_controller_user", "incoming_documents", "controller_user_id"),
    ("ix_td002d_incoming_created_by_user", "incoming_documents", "created_by_user_id"),
    ("ix_td002d_incoming_updated_by_user", "incoming_documents", "updated_by_user_id"),
    ("ix_td002d_incoming_closed_by_user", "incoming_documents", "closed_by_user_id"),
    ("ix_td002d_incoming_cancelled_by_user", "incoming_documents", "cancelled_by_user_id"),
    ("ix_td002d_incoming_transferred_by_user", "incoming_documents", "transferred_by_user_id"),
    ("ix_td002d_incoming_external_recipient_user", "incoming_documents", "external_recipient_user_id"),
    ("ix_td002d_employees_import_stage_employee", "employees_import_stage", "employee_id"),
    ("ix_td002d_hr_import_rows_employee", "hr_import_rows", "employee_id"),
    ("ix_td002d_hr_baseline_entries_employee", "hr_baseline_entries", "employee_id"),
    ("ix_td002d_hr_monthly_reference_entries_employee", "hr_monthly_reference_entries", "employee_id"),
    ("ix_td002d_personnel_migration_runs_person", "personnel_migration_runs", "person_id"),
    ("ix_td002d_personnel_migration_runs_employee_context", "personnel_migration_runs", "employee_context_id"),
    ("ix_td002d_persons_merged_into", "persons", "merged_into_person_id"),
    ("ix_td002d_personnel_orders_signatory", "personnel_orders", "signed_by_employee_id"),
    ("ix_td002d_operational_signing_actor", "operational_order_signing_attestations", "actor_employee_id"),
    ("ix_td002d_personnel_order_item_bases_subject", "personnel_order_item_bases", "subject_employee_id"),
    ("ix_td002d_onboarding_notifications_onboarding", "employee_onboarding_notifications", "onboarding_id"),
    ("ix_td002d_onboarding_task_audit_onboarding", "employee_onboarding_task_audit", "onboarding_id"),
    ("ix_td002d_termination_audit_record", "employee_termination_record_audit", "termination_record_id"),
    ("ix_td002d_user_linkage_decisions_employee", "user_linkage_review_decisions", "proposed_employee_id"),
    ("ix_td002d_access_grants_target_all", "access_grants", "target_type, target_id"),
    ("ix_td002d_visibility_target_user_all", "personnel_visibility_assignments", "target_user_id"),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX {name} ON public.{table} ({columns})")


def downgrade() -> None:
    for name, _table, _columns in reversed(INDEXES):
        op.execute(f"DROP INDEX public.{name}")
