"""Stage 2 audit-writer characterization for ADR-046 F2."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import exc, text

from app.db.engine import engine
from app.services import org_unit_allowed_positions_service
from app.services import security_audit_service
from app.services.org_unit_allowed_positions_service import (
    SORT_ORDER_OMITTED,
    AllowedPositionAuditError,
    AllowedPositionMutationNotFoundError,
    deactivate_allowed_position_link,
    upsert_allowed_position_link,
)
from app.services.position_dependencies_service import (
    PositionForeignKeyDependency,
    build_position_blocked_exists_sql,
    build_position_dependency_blocking_predicate_sql,
    check_position_dependencies,
    check_positions_dependencies,
    load_position_blocking_foreign_keys,
)
from app.services.security_audit_service import _ALLOWED_EVENT_TYPES, write_security_event

F2_EVENT_TYPES = (
    "ORG_UNIT_ALLOWED_POSITION_CREATED",
    "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
    "ORG_UNIT_ALLOWED_POSITION_UPDATED",
    "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
)
UNKNOWN_EVENT_TYPE = "ADR046_F2_UNKNOWN_SECURITY_EVENT"


def _migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "j7k8l9m0n1o2_adr046_f2_allowed_position_audit_events.py"
    )
    spec = spec_from_file_location("adr046_f2_allowed_position_audit_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audit_sqlstate(error: exc.IntegrityError) -> str | None:
    original = error.orig
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


def test_python_allowlist_has_exact_stage1_parity() -> None:
    migration = _migration_module()
    assert tuple(migration._F2_EVENT_TYPES) == F2_EVENT_TYPES
    assert _ALLOWED_EVENT_TYPES == frozenset(
        tuple(migration._PRE_F2_EVENT_TYPES) + F2_EVENT_TYPES
    )


@pytest.mark.parametrize("event_type", F2_EVENT_TYPES)
def test_existing_writer_persists_one_complete_f2_event(seed, event_type: str) -> None:
    marker = f"adr046-f2-stage2-{uuid4().hex}"
    actor_user_id = int(seed["initiator_user_id"])
    metadata = {
        "org_unit_allowed_position_id": 910001,
        "org_unit_id": 910002,
        "position_id": 910003,
        "previous_state": {"is_active": False, "sort_order": None},
        "current_state": {"is_active": True, "sort_order": 20},
        "stage2_marker": marker,
    }

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            transaction_timestamp = conn.execute(
                text("SELECT transaction_timestamp()")
            ).scalar_one()
            audit_id = write_security_event(
                event_type=event_type,
                actor_user_id=actor_user_id,
                success=True,
                metadata=metadata,
                request_id=marker,
                conn=conn,
            )

            assert audit_id is not None
            assert int(audit_id) > 0
            rows = conn.execute(
                text(
                    """
                    SELECT
                        audit_id,
                        event_type,
                        happened_at,
                        actor_user_id,
                        success,
                        metadata,
                        request_id
                    FROM public.security_audit_log
                    WHERE metadata ->> 'stage2_marker' = :marker
                    """
                ),
                {"marker": marker},
            ).mappings().all()

            assert len(rows) == 1
            row = rows[0]
            assert int(row["audit_id"]) == int(audit_id)
            assert row["event_type"] == event_type
            assert int(row["actor_user_id"]) == actor_user_id
            assert row["success"] is True
            assert row["metadata"] == metadata
            assert row["request_id"] == marker
            assert row["happened_at"] == transaction_timestamp
            assert conn.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'security_audit_log'
                      AND column_name = 'happened_at'
                    """
                )
            ).scalar_one() == "now()"
        finally:
            transaction.rollback()


def test_existing_writer_rejects_unknown_event_type(seed) -> None:
    marker = f"adr046-f2-stage2-unknown-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            with pytest.raises(ValueError, match="Unsupported event_type"):
                write_security_event(
                    event_type=UNKNOWN_EVENT_TYPE,
                    actor_user_id=int(seed["initiator_user_id"]),
                    metadata={"stage2_marker": marker},
                    conn=conn,
                )
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.security_audit_log
                    WHERE metadata ->> 'stage2_marker' = :marker
                    """
                ),
                {"marker": marker},
            ).scalar_one() == 0
        finally:
            transaction.rollback()


def test_existing_writer_returns_none_when_storage_is_unavailable(
    seed,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security_audit_service,
        "security_audit_log_available",
        lambda conn: False,
    )
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            assert write_security_event(
                event_type=F2_EVENT_TYPES[0],
                actor_user_id=int(seed["initiator_user_id"]),
                metadata={"stage2_marker": f"missing-{uuid4().hex}"},
                conn=conn,
            ) is None
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
        finally:
            transaction.rollback()


def test_existing_writer_propagates_audit_sql_errors(seed) -> None:
    marker = f"adr046-f2-stage2-sql-error-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            missing_actor_user_id = int(
                conn.execute(
                    text("SELECT COALESCE(MAX(user_id), 0) + 1000000000 FROM public.users")
                ).scalar_one()
            )
            with pytest.raises(exc.IntegrityError) as exc_info:
                with conn.begin_nested():
                    write_security_event(
                        event_type=F2_EVENT_TYPES[0],
                        actor_user_id=missing_actor_user_id,
                        metadata={"stage2_marker": marker},
                        conn=conn,
                    )

            assert _audit_sqlstate(exc_info.value) == "23503"
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.security_audit_log
                    WHERE metadata ->> 'stage2_marker' = :marker
                    """
                ),
                {"marker": marker},
            ).scalar_one() == 0
        finally:
            transaction.rollback()


def _insert_stage3_position(conn, marker: str) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.positions (name, category)
                VALUES (:name, 'other')
                RETURNING position_id
                """
            ),
            {"name": marker},
        ).scalar_one()
    )


def _assert_dependency_blocks_all_detector_entry_points(
    conn,
    *,
    dependency: PositionForeignKeyDependency,
    position_id: int,
) -> None:
    single = check_position_dependencies(
        conn,
        position_id=position_id,
        dependencies=[dependency],
    )
    assert single.can_delete is False
    assert single.total_dependencies == 1
    assert single.dependencies[0].key == "org_unit_allowed_positions.position_id"

    multiple = check_positions_dependencies(
        conn,
        position_ids=[position_id],
        dependencies=[dependency],
    )
    assert multiple[position_id].can_delete is False
    assert multiple[position_id].total_dependencies == 1

    exists_sql = build_position_blocked_exists_sql(
        [dependency],
        position_expression=":position_id",
    )
    assert conn.execute(
        text(f"SELECT ({exists_sql})"),
        {"position_id": position_id},
    ).scalar_one() is True


def test_exact_public_allowed_position_fk_is_the_only_active_only_policy() -> None:
    with engine.connect() as conn:
        dependencies = load_position_blocking_foreign_keys(conn)

    exact = [
        dependency
        for dependency in dependencies
        if dependency.policy_identity
        == (
            "public",
            "org_unit_allowed_positions",
            "position_id",
            "org_unit_allowed_positions_position_id_fkey",
        )
    ]
    assert len(exact) == 1
    assert build_position_dependency_blocking_predicate_sql(
        exact[0],
        table_alias="dep",
    ) == '"dep"."is_active" = TRUE'
    for dependency in dependencies:
        if dependency != exact[0]:
            assert build_position_dependency_blocking_predicate_sql(
                dependency,
                table_alias="dep",
            ) == "TRUE"


def test_unknown_constraint_identity_uses_secure_default(seed) -> None:
    marker = f"adr046-f2-stage3-unknown-constraint-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            position_id = _insert_stage3_position(conn, marker)
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:org_unit_id, :position_id, FALSE)
                    """
                ),
                {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
            )
            dependency = PositionForeignKeyDependency(
                constraint_name="unknown_replacement_position_fk",
                table_schema="public",
                table_name="org_unit_allowed_positions",
                column_name="position_id",
                on_delete="r",
            )
            assert build_position_dependency_blocking_predicate_sql(
                dependency,
                table_alias="dep",
            ) == "TRUE"
            _assert_dependency_blocks_all_detector_entry_points(
                conn,
                dependency=dependency,
                position_id=position_id,
            )
        finally:
            transaction.rollback()


def test_same_named_other_schema_fk_remains_fully_blocking() -> None:
    marker = uuid4().hex
    schema_name = f"adr046_f2_stage3_{marker}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            position_id = _insert_stage3_position(
                conn,
                f"adr046-f2-stage3-other-schema-{marker}",
            )
            conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE "{schema_name}".org_unit_allowed_positions (
                        row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        position_id BIGINT NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT FALSE,
                        CONSTRAINT org_unit_allowed_positions_position_id_fkey
                            FOREIGN KEY (position_id)
                            REFERENCES public.positions (position_id)
                            ON DELETE RESTRICT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO "{schema_name}".org_unit_allowed_positions (
                        position_id, is_active
                    )
                    VALUES (:position_id, FALSE)
                    """
                ),
                {"position_id": position_id},
            )

            dependencies = load_position_blocking_foreign_keys(conn)
            dependency = next(
                item
                for item in dependencies
                if item.table_schema == schema_name
                and item.table_name == "org_unit_allowed_positions"
                and item.column_name == "position_id"
            )
            assert build_position_dependency_blocking_predicate_sql(
                dependency,
                table_alias="dep",
            ) == "TRUE"
            _assert_dependency_blocks_all_detector_entry_points(
                conn,
                dependency=dependency,
                position_id=position_id,
            )
        finally:
            transaction.rollback()


def _stage4_actor_user_id(conn) -> int:
    actor_user_id = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE role_id = 2
            ORDER BY user_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    assert actor_user_id is not None, "isolated test DB must contain canonical role_id=2 user"
    return int(actor_user_id)


def _insert_stage4_link(
    conn,
    *,
    org_unit_id: int,
    position_id: int,
    is_active: bool,
    sort_order: int | None,
) -> dict:
    return dict(
        conn.execute(
            text(
                """
                INSERT INTO public.org_unit_allowed_positions (
                    org_unit_id,
                    position_id,
                    sort_order,
                    is_active,
                    updated_at
                )
                VALUES (
                    :org_unit_id,
                    :position_id,
                    :sort_order,
                    :is_active,
                    TIMESTAMPTZ '2000-01-01 00:00:00+00'
                )
                RETURNING
                    org_unit_allowed_position_id,
                    org_unit_id,
                    position_id,
                    sort_order,
                    is_active,
                    created_at,
                    updated_at
                """
            ),
            {
                "org_unit_id": int(org_unit_id),
                "position_id": int(position_id),
                "sort_order": sort_order,
                "is_active": bool(is_active),
            },
        ).mappings().one()
    )


def _stage4_link_rows(conn, *, org_unit_id: int, position_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT
                    org_unit_allowed_position_id,
                    org_unit_id,
                    position_id,
                    sort_order,
                    is_active,
                    created_at,
                    updated_at,
                    xmin::text AS xmin
                FROM public.org_unit_allowed_positions
                WHERE org_unit_id = :org_unit_id
                  AND position_id = :position_id
                """
            ),
            {"org_unit_id": int(org_unit_id), "position_id": int(position_id)},
        ).mappings()
    ]


def _stage4_audit_rows(conn, *, request_id: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT
                    audit_id,
                    event_type,
                    happened_at,
                    actor_user_id,
                    ip_address::text AS ip_address,
                    user_agent,
                    success,
                    metadata,
                    request_id
                FROM public.security_audit_log
                WHERE request_id = :request_id
                ORDER BY audit_id
                """
            ),
            {"request_id": request_id},
        ).mappings()
    ]


def _assert_stage4_audit(
    conn,
    *,
    request_id: str,
    event_type: str,
    actor_user_id: int,
    link: dict,
    previous_state: dict | None,
    current_state: dict,
) -> None:
    rows = _stage4_audit_rows(conn, request_id=request_id)
    assert len(rows) == 1
    row = rows[0]
    assert int(row["audit_id"]) > 0
    assert row["event_type"] == event_type
    assert int(row["actor_user_id"]) == actor_user_id
    assert row["success"] is True
    assert row["request_id"] == request_id
    assert row["ip_address"] == "127.0.0.1/32"
    assert row["user_agent"] == "adr046-f2-stage4-test"
    assert row["happened_at"] is not None
    expected_metadata = {
        "org_unit_allowed_position_id": int(link["org_unit_allowed_position_id"]),
        "org_unit_id": int(link["org_unit_id"]),
        "position_id": int(link["position_id"]),
        "previous_state": previous_state,
        "current_state": current_state,
    }
    if event_type == "ORG_UNIT_ALLOWED_POSITION_UPDATED":
        expected_metadata["previous_sort_order"] = previous_state["sort_order"]
        expected_metadata["new_sort_order"] = current_state["sort_order"]
    assert row["metadata"] == expected_metadata


def _stage4_upsert(
    conn,
    *,
    org_unit_id: int,
    position_id: int,
    actor_user_id: int,
    request_id: str,
    sort_input,
):
    kwargs = {}
    if sort_input is not SORT_ORDER_OMITTED:
        kwargs["sort_order"] = sort_input
    return upsert_allowed_position_link(
        conn,
        org_unit_id=org_unit_id,
        position_id=position_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address="127.0.0.1",
        user_agent="adr046-f2-stage4-test",
        **kwargs,
    )


@pytest.mark.parametrize(
    ("sort_input", "expected_sort"),
    ((SORT_ORDER_OMITTED, None), (None, None), (17, 17)),
    ids=("omitted", "null", "integer"),
)
def test_stage4_create_covers_all_sort_order_states(
    seed,
    sort_input,
    expected_sort,
) -> None:
    request_id = f"adr046-f2-stage4-create-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, request_id)
            result = _stage4_upsert(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                sort_input=sort_input,
            )

            assert result.transition == "created"
            assert result.previous_state is None
            assert result.current_state == {
                "is_active": True,
                "sort_order": expected_sort,
            }
            assert result.link["is_active"] is True
            assert result.link["sort_order"] == expected_sort
            rows = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert len(rows) == 1
            assert int(rows[0]["org_unit_allowed_position_id"]) == int(
                result.link["org_unit_allowed_position_id"]
            )
            _assert_stage4_audit(
                conn,
                request_id=request_id,
                event_type="ORG_UNIT_ALLOWED_POSITION_CREATED",
                actor_user_id=actor_user_id,
                link=result.link,
                previous_state=None,
                current_state=result.current_state,
            )
        finally:
            transaction.rollback()


@pytest.mark.parametrize(
    ("sort_input", "expected_sort"),
    ((SORT_ORDER_OMITTED, 9), (None, None), (17, 17)),
    ids=("omitted-preserves", "null-clears", "integer-replaces"),
)
def test_stage4_reactivate_covers_all_sort_order_states_and_preserves_id(
    seed,
    sort_input,
    expected_sort,
) -> None:
    request_id = f"adr046-f2-stage4-reactivate-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, request_id)
            before = _insert_stage4_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                is_active=False,
                sort_order=9,
            )
            result = _stage4_upsert(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                sort_input=sort_input,
            )

            assert result.transition == "reactivated"
            assert result.previous_state == {"is_active": False, "sort_order": 9}
            assert result.current_state == {
                "is_active": True,
                "sort_order": expected_sort,
            }
            assert int(result.link["org_unit_allowed_position_id"]) == int(
                before["org_unit_allowed_position_id"]
            )
            assert len(
                _stage4_link_rows(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
            ) == 1
            _assert_stage4_audit(
                conn,
                request_id=request_id,
                event_type="ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
                actor_user_id=actor_user_id,
                link=result.link,
                previous_state=result.previous_state,
                current_state=result.current_state,
            )
        finally:
            transaction.rollback()


@pytest.mark.parametrize(
    ("sort_input", "expected_transition", "expected_sort"),
    (
        (SORT_ORDER_OMITTED, "noop", 9),
        (None, "updated", None),
        (17, "updated", 17),
        (9, "noop", 9),
    ),
    ids=("omitted-noop", "null-update", "integer-update", "integer-noop"),
)
def test_stage4_active_link_update_and_noop_contract(
    seed,
    sort_input,
    expected_transition,
    expected_sort,
) -> None:
    request_id = f"adr046-f2-stage4-active-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, request_id)
            before = _insert_stage4_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                is_active=True,
                sort_order=9,
            )
            before_row = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )[0]
            result = _stage4_upsert(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                sort_input=sort_input,
            )
            after_row = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )[0]

            assert result.transition == expected_transition
            assert result.previous_state == {"is_active": True, "sort_order": 9}
            assert result.current_state == {
                "is_active": True,
                "sort_order": expected_sort,
            }
            assert int(result.link["org_unit_allowed_position_id"]) == int(
                before["org_unit_allowed_position_id"]
            )
            assert len(
                _stage4_link_rows(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
            ) == 1

            if expected_transition == "noop":
                assert result.previous_state == result.current_state
                assert result.link["updated_at"] == before["updated_at"]
                assert after_row["updated_at"] == before_row["updated_at"]
                assert after_row["xmin"] == before_row["xmin"]
                assert _stage4_audit_rows(conn, request_id=request_id) == []
            else:
                assert result.link["updated_at"] > before["updated_at"]
                _assert_stage4_audit(
                    conn,
                    request_id=request_id,
                    event_type="ORG_UNIT_ALLOWED_POSITION_UPDATED",
                    actor_user_id=actor_user_id,
                    link=result.link,
                    previous_state=result.previous_state,
                    current_state=result.current_state,
                )
        finally:
            transaction.rollback()


def test_stage4_repeated_create_is_noop_with_one_row_and_one_audit(seed) -> None:
    create_request_id = f"adr046-f2-stage4-repeat-create-{uuid4().hex}"
    retry_request_id = f"adr046-f2-stage4-repeat-retry-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, create_request_id)
            created = _stage4_upsert(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                actor_user_id=actor_user_id,
                request_id=create_request_id,
                sort_input=SORT_ORDER_OMITTED,
            )
            before_retry = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )[0]
            retried = _stage4_upsert(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
                actor_user_id=actor_user_id,
                request_id=retry_request_id,
                sort_input=SORT_ORDER_OMITTED,
            )
            after_retry = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )

            assert created.transition == "created"
            assert retried.transition == "noop"
            assert int(retried.link["org_unit_allowed_position_id"]) == int(
                created.link["org_unit_allowed_position_id"]
            )
            assert retried.previous_state == retried.current_state
            assert len(after_retry) == 1
            assert after_retry[0]["updated_at"] == before_retry["updated_at"]
            assert after_retry[0]["xmin"] == before_retry["xmin"]
            assert len(_stage4_audit_rows(conn, request_id=create_request_id)) == 1
            assert _stage4_audit_rows(conn, request_id=retry_request_id) == []
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.security_audit_log
                    WHERE event_type = 'ORG_UNIT_ALLOWED_POSITION_CREATED'
                      AND metadata ->> 'org_unit_allowed_position_id' = :link_id
                    """
                ),
                {"link_id": str(created.link["org_unit_allowed_position_id"])},
            ).scalar_one() == 1
        finally:
            transaction.rollback()


def test_stage4_deactivate_only_selected_pair_and_repeat_is_noop(seed) -> None:
    request_id = f"adr046-f2-stage4-deactivate-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            selected_position_id = _insert_stage3_position(conn, request_id)
            other_position_id = _insert_stage3_position(conn, f"{request_id}-other")
            selected_before = _insert_stage4_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=selected_position_id,
                is_active=True,
                sort_order=4,
            )
            other_before = _insert_stage4_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=other_position_id,
                is_active=True,
                sort_order=8,
            )

            result = deactivate_allowed_position_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=selected_position_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                ip_address="127.0.0.1",
                user_agent="adr046-f2-stage4-test",
            )
            assert int(result["org_unit_allowed_position_id"]) == int(
                selected_before["org_unit_allowed_position_id"]
            )
            assert result["is_active"] is False
            assert result["sort_order"] == 4
            _assert_stage4_audit(
                conn,
                request_id=request_id,
                event_type="ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
                actor_user_id=actor_user_id,
                link=result,
                previous_state={"is_active": True, "sort_order": 4},
                current_state={"is_active": False, "sort_order": 4},
            )
            other_after = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=other_position_id,
            )[0]
            assert other_after["is_active"] is True
            assert int(other_after["org_unit_allowed_position_id"]) == int(
                other_before["org_unit_allowed_position_id"]
            )

            first_updated_at = result["updated_at"]
            repeated = deactivate_allowed_position_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=selected_position_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            assert repeated["updated_at"] == first_updated_at
            assert len(_stage4_audit_rows(conn, request_id=request_id)) == 1
        finally:
            transaction.rollback()


def test_stage4_parent_and_pair_not_found_precedence(seed) -> None:
    request_id = f"adr046-f2-stage4-not-found-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, request_id)
            missing_position_id = int(
                conn.execute(
                    text("SELECT COALESCE(MAX(position_id), 0) + 1000000 FROM public.positions")
                ).scalar_one()
            )
            missing_org_unit_id = int(
                conn.execute(
                    text("SELECT COALESCE(MAX(unit_id), 0) + 1000000 FROM public.org_units")
                ).scalar_one()
            )

            with pytest.raises(AllowedPositionMutationNotFoundError) as both:
                upsert_allowed_position_link(
                    conn,
                    org_unit_id=missing_org_unit_id,
                    position_id=missing_position_id,
                    actor_user_id=actor_user_id,
                )
            assert both.value.code == "POSITION_NOT_FOUND"

            with pytest.raises(AllowedPositionMutationNotFoundError) as org_unit:
                upsert_allowed_position_link(
                    conn,
                    org_unit_id=missing_org_unit_id,
                    position_id=position_id,
                    actor_user_id=actor_user_id,
                )
            assert org_unit.value.code == "ORG_UNIT_NOT_FOUND"

            with pytest.raises(AllowedPositionMutationNotFoundError) as pair:
                deactivate_allowed_position_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    actor_user_id=actor_user_id,
                )
            assert pair.value.code == "ALLOWED_POSITION_LINK_NOT_FOUND"

            with pytest.raises(AllowedPositionMutationNotFoundError) as deactivate_parent:
                deactivate_allowed_position_link(
                    conn,
                    org_unit_id=missing_org_unit_id,
                    position_id=missing_position_id,
                    actor_user_id=actor_user_id,
                )
            assert deactivate_parent.value.code == "POSITION_NOT_FOUND"
            assert _stage4_audit_rows(conn, request_id=request_id) == []
        finally:
            transaction.rollback()


@pytest.mark.parametrize(
    "failure_case",
    ("writer_none", "missing_storage", "null_audit_id", "audit_sql_error"),
)
def test_stage4_every_audit_failure_rolls_back_domain_mutation(
    seed,
    monkeypatch: pytest.MonkeyPatch,
    failure_case: str,
) -> None:
    request_id = f"adr046-f2-stage4-audit-failure-{failure_case}-{uuid4().hex}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            actor_user_id = _stage4_actor_user_id(conn)
            position_id = _insert_stage3_position(conn, request_id)

            if failure_case == "writer_none":
                before_rows = []
                monkeypatch.setattr(
                    org_unit_allowed_positions_service,
                    "write_security_event",
                    lambda **kwargs: None,
                )
                operation = lambda: upsert_allowed_position_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                )
                expected_error = AllowedPositionAuditError
            elif failure_case == "missing_storage":
                _insert_stage4_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    is_active=False,
                    sort_order=5,
                )
                before_rows = _stage4_link_rows(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
                monkeypatch.setattr(
                    security_audit_service,
                    "security_audit_log_available",
                    lambda audit_conn: False,
                )
                operation = lambda: upsert_allowed_position_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                )
                expected_error = AllowedPositionAuditError
            elif failure_case == "null_audit_id":
                _insert_stage4_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    is_active=True,
                    sort_order=5,
                )
                before_rows = _stage4_link_rows(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
                monkeypatch.setattr(
                    org_unit_allowed_positions_service,
                    "write_security_event",
                    lambda **kwargs: None,
                )
                operation = lambda: upsert_allowed_position_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    actor_user_id=actor_user_id,
                    sort_order=6,
                    request_id=request_id,
                )
                expected_error = AllowedPositionAuditError
            else:
                _insert_stage4_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    is_active=True,
                    sort_order=5,
                )
                before_rows = _stage4_link_rows(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
                missing_actor_user_id = int(
                    conn.execute(
                        text("SELECT COALESCE(MAX(user_id), 0) + 1000000000 FROM public.users")
                    ).scalar_one()
                )
                operation = lambda: deactivate_allowed_position_link(
                    conn,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                    actor_user_id=missing_actor_user_id,
                    request_id=request_id,
                )
                expected_error = exc.IntegrityError

            with pytest.raises(expected_error) as error:
                operation()
            if failure_case == "audit_sql_error":
                assert _audit_sqlstate(error.value) == "23503"

            after_rows = _stage4_link_rows(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert after_rows == before_rows
            assert _stage4_audit_rows(conn, request_id=request_id) == []
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
        finally:
            transaction.rollback()
