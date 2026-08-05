# tests/test_access_resolver_temporal_evaluation.py
"""Regression tests for access grant resolver temporal evaluation."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.access_resolver_service import _load_active_grants
from tests.conftest import table_exists


def _require_access_tables() -> None:
    with engine.connect() as conn:
        for table in ("access_roles", "access_grants"):
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 table missing: {table}")


def _empty_subjects() -> dict[str, set[int]]:
    return {
        "USER": set(),
        "ROLE": set(),
        "EMPLOYEE": set(),
        "PERSON": set(),
        "ASSIGNMENT": set(),
        "POSITION": set(),
        "ORG_UNIT": set(),
    }


def _user_subjects(user_id: int, role_id: int) -> dict[str, set[int]]:
    subjects = _empty_subjects()
    subjects["USER"].add(int(user_id))
    subjects["ROLE"].add(int(role_id))
    return subjects


def _get_access_role_id(conn, code: str) -> int:
    return int(
        conn.execute(
            text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
            {"code": code},
        ).scalar_one()
    )


def _load_active_grants_with_transaction_now(
    conn,
    subjects: dict[str, set[int]],
) -> list[dict]:
    """Legacy temporal predicates (transaction-scoped now()) for regression comparison."""
    clauses: list[str] = []
    params: dict[str, object] = {}
    idx = 0
    for target_type, ids in subjects.items():
        if not ids:
            continue
        key = f"ids_{idx}"
        clauses.append(f"(g.target_type = :tt_{idx} AND g.target_id = ANY(:{key}))")
        params[f"tt_{idx}"] = target_type
        params[key] = list(ids)
        idx += 1
    if not clauses:
        return []
    where_targets = " OR ".join(clauses)
    rows = conn.execute(
        text(
            f"""
            SELECT g.grant_id, g.access_role_id, r.code AS access_role_code
            FROM public.access_grants g
            JOIN public.access_roles r ON r.access_role_id = g.access_role_id
            WHERE g.active_flag = TRUE
              AND g.starts_at <= now()
              AND (g.ends_at IS NULL OR g.ends_at > now())
              AND r.is_active = TRUE
              AND ({where_targets})
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _delete_user_grants(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.access_grants
                WHERE target_type = 'USER' AND target_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        )


def test_committed_grant_active_on_stale_transaction_connection(seed):
    """Grant committed after transaction start must not be excluded by frozen now()."""
    _require_access_tables()
    user_id = int(seed["executor_user_id"])
    role_id = int(seed["executor_role_id"])
    actor_id = int(seed["initiator_user_id"])
    subjects = _user_subjects(user_id, role_id)

    _delete_user_grants(user_id)
    try:
        with engine.connect() as resolver_conn:
            txn_now = resolver_conn.execute(text("SELECT now() AS ts")).scalar_one()

            with engine.begin() as grant_conn:
                role_id_db = _get_access_role_id(grant_conn, "ACCESS_OBSERVER")
                inserted = grant_conn.execute(
                    text(
                        """
                        INSERT INTO public.access_grants (
                            access_role_id, target_type, target_id, resource_key,
                            scope_type, starts_at, granted_by_user_id, reason
                        )
                        VALUES (
                            :access_role_id, 'USER', :user_id, '*', 'GLOBAL',
                            CAST(:txn_now AS timestamptz) + interval '1 microsecond',
                            :actor, 'temporal regression'
                        )
                        RETURNING grant_id, starts_at
                        """
                    ),
                    {
                        "access_role_id": role_id_db,
                        "user_id": user_id,
                        "actor": actor_id,
                        "txn_now": txn_now,
                    },
                ).mappings().one()

            starts_at = inserted["starts_at"]
            grant_id = int(inserted["grant_id"])
            assert starts_at > txn_now, (
                f"precondition failed: grant starts_at={starts_at!r} must be after "
                f"transaction now()={txn_now!r}"
            )

            legacy_grants = _load_active_grants_with_transaction_now(resolver_conn, subjects)
            assert not any(int(row["grant_id"]) == grant_id for row in legacy_grants), (
                "legacy now() predicates must reproduce the stale-transaction exclusion"
            )

            grants = _load_active_grants(resolver_conn, subjects)
            assert any(int(row["grant_id"]) == grant_id for row in grants), (
                "production resolver must treat committed grant as active on stale connection"
            )

            resolver_conn.rollback()
    finally:
        _delete_user_grants(user_id)


def test_starts_at_equal_to_effective_timestamp_is_active(seed):
    _require_access_tables()
    user_id = int(seed["executor_user_id"])
    role_id = int(seed["executor_role_id"])
    actor_id = int(seed["initiator_user_id"])
    subjects = _user_subjects(user_id, role_id)

    _delete_user_grants(user_id)
    try:
        with engine.begin() as conn:
            role_id_db = _get_access_role_id(conn, "ACCESS_OBSERVER")
            inserted = conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id, target_type, target_id, resource_key,
                        scope_type, starts_at, granted_by_user_id, reason
                    )
                    SELECT
                        :access_role_id, 'USER', :user_id, '*', 'GLOBAL',
                        statement_timestamp(), :actor, 'starts_at boundary'
                    RETURNING grant_id
                    """
                ),
                {
                    "access_role_id": role_id_db,
                    "user_id": user_id,
                    "actor": actor_id,
                },
            ).scalar_one()
            grants = _load_active_grants(conn, subjects)
            assert any(int(row["grant_id"]) == int(inserted) for row in grants)
    finally:
        _delete_user_grants(user_id)


def test_ends_at_equal_to_effective_timestamp_is_inactive(seed):
    _require_access_tables()
    user_id = int(seed["executor_user_id"])
    role_id = int(seed["executor_role_id"])
    actor_id = int(seed["initiator_user_id"])
    subjects = _user_subjects(user_id, role_id)

    _delete_user_grants(user_id)
    try:
        with engine.begin() as conn:
            role_id_db = _get_access_role_id(conn, "ACCESS_OBSERVER")
            inserted = conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id, target_type, target_id, resource_key,
                        scope_type, starts_at, ends_at, granted_by_user_id, reason
                    )
                    SELECT
                        :access_role_id, 'USER', :user_id, '*', 'GLOBAL',
                        statement_timestamp() - interval '1 day',
                        statement_timestamp(),
                        :actor,
                        'ends_at boundary equal'
                    RETURNING grant_id
                    """
                ),
                {
                    "access_role_id": role_id_db,
                    "user_id": user_id,
                    "actor": actor_id,
                },
            ).scalar_one()
            grants = _load_active_grants(conn, subjects)
            assert not any(int(row["grant_id"]) == int(inserted) for row in grants)
    finally:
        _delete_user_grants(user_id)


def test_ends_at_after_effective_timestamp_is_active(seed):
    _require_access_tables()
    user_id = int(seed["executor_user_id"])
    role_id = int(seed["executor_role_id"])
    actor_id = int(seed["initiator_user_id"])
    subjects = _user_subjects(user_id, role_id)

    _delete_user_grants(user_id)
    try:
        with engine.begin() as conn:
            role_id_db = _get_access_role_id(conn, "ACCESS_OBSERVER")
            inserted = conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id, target_type, target_id, resource_key,
                        scope_type, starts_at, ends_at, granted_by_user_id, reason
                    )
                    SELECT
                        :access_role_id, 'USER', :user_id, '*', 'GLOBAL',
                        statement_timestamp() - interval '1 day',
                        statement_timestamp() + interval '1 day',
                        :actor,
                        'ends_at boundary future'
                    RETURNING grant_id
                    """
                ),
                {
                    "access_role_id": role_id_db,
                    "user_id": user_id,
                    "actor": actor_id,
                },
            ).scalar_one()
            grants = _load_active_grants(conn, subjects)
            assert any(int(row["grant_id"]) == int(inserted) for row in grants)
    finally:
        _delete_user_grants(user_id)
