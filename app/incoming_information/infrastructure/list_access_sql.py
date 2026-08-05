"""SQL visibility predicates for incoming document list queries."""
from __future__ import annotations

from app.incoming_information.domain.status import ACCESS_LEVEL_RESTRICTED


def restricted_participant_predicate_sql(
    *,
    user_id_param: str = "access_user_id",
    employee_id_param: str = "access_employee_id",
) -> str:
    """Active RESTRICTED participants (assignee/addressee/controller/creator)."""
    return f"""
    d.created_by_user_id = :{user_id_param}
    OR d.controller_user_id = :{user_id_param}
    OR d.addressee_user_id = :{user_id_param}
    OR (
        :{employee_id_param} IS NOT NULL
        AND d.addressee_employee_id = :{employee_id_param}
    )
    OR EXISTS (
        SELECT 1
        FROM public.incoming_document_assignments a
        WHERE a.incoming_document_id = d.incoming_document_id
          AND a.assignee_user_id = :{user_id_param}
          AND a.completed_at IS NULL
          AND a.cancelled_at IS NULL
    )
    """


def document_list_visibility_sql(
    *,
    user_id_param: str = "access_user_id",
    employee_id_param: str = "access_employee_id",
    bypass_param: str = "restricted_bypass",
) -> str:
    """List visibility aligned with detail access: NORMAL in scope; RESTRICTED for participants or bypass."""
    participant = restricted_participant_predicate_sql(
        user_id_param=user_id_param,
        employee_id_param=employee_id_param,
    )
    return f"""
    (
        d.access_level <> '{ACCESS_LEVEL_RESTRICTED}'
        OR (
            d.access_level = '{ACCESS_LEVEL_RESTRICTED}'
            AND (
                ({participant})
                OR :{bypass_param} = TRUE
            )
        )
    )
    """


def document_list_scope_sql(
    *,
    scope_param: str = "scope_unit_ids",
    user_id_param: str = "access_user_id",
    employee_id_param: str = "access_employee_id",
    bypass_param: str = "restricted_bypass",
) -> str:
    """Org scope for NORMAL; RESTRICTED participants or bypass may appear outside responsible org scope."""
    participant = restricted_participant_predicate_sql(
        user_id_param=user_id_param,
        employee_id_param=employee_id_param,
    )
    return f"""
    (
        d.responsible_org_unit_id = ANY(:{scope_param})
        OR (
            d.access_level = '{ACCESS_LEVEL_RESTRICTED}'
            AND (
                ({participant})
                OR :{bypass_param} = TRUE
            )
        )
    )
    """


def restricted_document_visible_sql(
    *,
    user_id_param: str = "access_user_id",
    employee_id_param: str = "access_employee_id",
    bypass_param: str = "restricted_bypass",
) -> str:
    """Backward-compatible alias for document_list_visibility_sql."""
    return document_list_visibility_sql(
        user_id_param=user_id_param,
        employee_id_param=employee_id_param,
        bypass_param=bypass_param,
    )
