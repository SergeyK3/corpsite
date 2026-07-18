"""PostgreSQL sequence sync helpers for tests only."""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


def get_owned_sequence(
    conn: Connection,
    table_name: str,
    pk_column: str,
    *,
    schema: str = "public",
) -> Optional[str]:
    row = conn.execute(
        text("SELECT pg_get_serial_sequence(:table_ref, :pk_column) AS seq_name"),
        {"table_ref": f"{schema}.{table_name}", "pk_column": pk_column},
    ).mappings().first()
    if not row:
        return None
    seq_name = row.get("seq_name")
    return str(seq_name) if seq_name else None


def _max_pk(conn: Connection, *, schema: str, table_name: str, pk_column: str) -> int:
    value = conn.execute(
        text(f"SELECT COALESCE(MAX({pk_column}), 0) FROM {schema}.{table_name}"),
    ).scalar_one()
    return int(value)


def _sequence_next_value(conn: Connection, seq_name: str) -> int:
    row = conn.execute(
        text(f"SELECT last_value, is_called FROM {seq_name}"),
    ).mappings().first()
    if row is None:
        return 0
    last_value = int(row["last_value"])
    is_called = bool(row["is_called"])
    return last_value + 1 if is_called else last_value


def sync_owned_sequence(
    conn: Connection,
    table_name: str,
    pk_column: str,
    *,
    schema: str = "public",
) -> Optional[str]:
    seq_name = get_owned_sequence(conn, table_name, pk_column, schema=schema)
    if not seq_name:
        return None

    max_pk = _max_pk(conn, schema=schema, table_name=table_name, pk_column=pk_column)
    if max_pk <= 0:
        conn.execute(
            text("SELECT setval(CAST(:seq_name AS regclass), 1, false)"),
            {"seq_name": seq_name},
        )
    else:
        conn.execute(
            text("SELECT setval(CAST(:seq_name AS regclass), :max_pk, true)"),
            {"seq_name": seq_name, "max_pk": max_pk},
        )
    return seq_name


def sync_sequences(
    conn: Connection,
    pairs: Iterable[tuple[str, str]],
    *,
    schema: str = "public",
) -> list[str]:
    synced: list[str] = []
    for table_name, pk_column in pairs:
        seq_name = sync_owned_sequence(conn, table_name, pk_column, schema=schema)
        if seq_name:
            synced.append(seq_name)
    return synced


def assert_sequence_not_behind(
    conn: Connection,
    table_name: str,
    pk_column: str,
    *,
    schema: str = "public",
) -> None:
    seq_name = get_owned_sequence(conn, table_name, pk_column, schema=schema)
    if not seq_name:
        return

    max_pk = _max_pk(conn, schema=schema, table_name=table_name, pk_column=pk_column)
    next_value = _sequence_next_value(conn, seq_name)
    if max_pk <= 0:
        assert next_value >= 1, (
            f"{schema}.{table_name}.{pk_column}: empty table expects next sequence value >= 1, got {next_value}"
        )
        return

    assert next_value > max_pk, (
        f"{schema}.{table_name}.{pk_column}: sequence {seq_name!r} next value {next_value} "
        f"is not greater than MAX({pk_column})={max_pk}"
    )


SEED_SEQUENCE_TABLES: tuple[tuple[str, str], ...] = (
    ("roles", "role_id"),
    ("users", "user_id"),
    ("org_units", "unit_id"),
    ("units", "unit_id"),
    ("persons", "person_id"),
    ("contacts", "contact_id"),
    ("employees", "employee_id"),
    ("positions", "position_id"),
    ("tasks", "task_id"),
)


def _table_exists(conn: Connection, table_name: str, *, schema: str = "public") -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table_name},
    ).first()
    return row is not None


def sync_common_seed_sequences(conn: Connection, *, schema: str = "public") -> list[str]:
    pairs = [
        (table_name, pk_column)
        for table_name, pk_column in SEED_SEQUENCE_TABLES
        if _table_exists(conn, table_name, schema=schema)
        and pk_column in _table_columns(conn, table_name, schema=schema)
    ]
    return sync_sequences(conn, pairs, schema=schema)


def _table_columns(conn: Connection, table_name: str, *, schema: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            """
        ),
        {"schema": schema, "table": table_name},
    ).fetchall()
    return {str(row[0]) for row in rows}
