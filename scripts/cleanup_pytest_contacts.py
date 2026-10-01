#!/usr/bin/env python3
"""Safely soft-delete local Contacts whose displayed name starts with ``Pytest``."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

NAME_PREFIX = "Pytest"
LIKE_PATTERN = f"{NAME_PREFIX}%"
CONFIRMATION_PHRASE = "DELETE PYTEST CONTACTS"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PRODUCTION_LIKE_MARKERS = frozenset(
    {"prod", "production", "live", "master", "primary", "replica", "amazonaws", "cloudsql", "azure"}
)

IDENTITY_SQL = text(
    """
    /* cleanup:identity */
    SELECT
        current_database() AS database_name,
        inet_server_addr()::text AS server_address
    """
)
FIND_SQL = text(
    """
    /* cleanup:find */
    SELECT contact_id, full_name
    FROM public.contacts
    WHERE COALESCE(is_deleted, false) = false
      AND full_name LIKE :name_pattern
    ORDER BY contact_id
    """
)
FIND_FOR_UPDATE_SQL = text(
    """
    /* cleanup:find-for-update */
    SELECT contact_id, full_name
    FROM public.contacts
    WHERE COALESCE(is_deleted, false) = false
      AND full_name LIKE :name_pattern
    ORDER BY contact_id
    FOR UPDATE
    """
)
SOFT_DELETE_SQL = text(
    """
    /* cleanup:soft-delete */
    UPDATE public.contacts
    SET is_deleted = true,
        updated_at = NOW()
    WHERE contact_id IN :contact_ids
      AND COALESCE(is_deleted, false) = false
      AND full_name LIKE :name_pattern
    RETURNING contact_id, full_name
    """
).bindparams(bindparam("contact_ids", expanding=True))
COUNT_SQL = text(
    """
    /* cleanup:count */
    SELECT COUNT(*)
    FROM public.contacts
    WHERE COALESCE(is_deleted, false) = false
      AND full_name LIKE :name_pattern
    """
)
REFERENCING_FKS_SQL = text(
    """
    /* cleanup:referencing-fks */
    SELECT
        tc.table_schema,
        tc.table_name,
        kcu.column_name,
        tc.constraint_name,
        rc.delete_rule
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON kcu.constraint_schema = tc.constraint_schema
     AND kcu.constraint_name = tc.constraint_name
    JOIN information_schema.referential_constraints rc
      ON rc.constraint_schema = tc.constraint_schema
     AND rc.constraint_name = tc.constraint_name
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_schema = rc.unique_constraint_schema
     AND ccu.constraint_name = rc.unique_constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_schema = 'public'
      AND ccu.table_name = 'contacts'
    ORDER BY tc.table_schema, tc.table_name, tc.constraint_name
    """
)


class SafetyError(RuntimeError):
    """Raised when the configured database cannot be proven local."""


@dataclass(frozen=True)
class Contact:
    contact_id: int
    full_name: str


@dataclass(frozen=True)
class DatabaseIdentity:
    configured_host: str
    database_name: str
    server_address: str | None


def get_project_engine() -> tuple[Engine, str]:
    """Load the project's normal dotenv-backed SQLAlchemy engine lazily."""
    from app.db.engine import DATABASE_URL, engine

    return engine, DATABASE_URL


def is_test_database_name(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered == "corpsite_test" or lowered.endswith("_test") or lowered.endswith("-test")


def preflight_database_url(configured_url: str, *, expected_database_name: str) -> None:
    """Reject unsafe targets before an engine is created or a connection is opened."""
    url = make_url(configured_url)
    host = (url.host or "").strip().lower()
    database = (url.database or "").strip()
    expected = expected_database_name.strip()
    lowered_url = configured_url.lower()

    if host not in LOCAL_HOSTS:
        raise SafetyError(
            f"Удаление заблокировано: host {host!r} не является локальным. "
            "Подключение к БД не выполнялось."
        )
    if not expected:
        raise SafetyError("Требуется точное --expected-database-name.")
    if database != expected:
        raise SafetyError(
            f"Имя БД из DATABASE_URL {database!r} не совпадает с ожидаемым {expected!r}."
        )
    if not is_test_database_name(database):
        raise SafetyError("Разрешены только явно test-БД (например, corpsite_test или *_test).")
    if any(marker in lowered_url for marker in PRODUCTION_LIKE_MARKERS):
        raise SafetyError("URL или имя БД содержит production-like marker.")


def inspect_database(
    conn: Connection,
    configured_url: str,
    *,
    expected_database_name: str,
) -> DatabaseIdentity:
    row = conn.execute(IDENTITY_SQL).mappings().one()
    url = make_url(configured_url)
    configured_database = (url.database or "").strip()
    actual_database = str(row["database_name"] or "").strip()
    if not actual_database or actual_database != configured_database:
        raise SafetyError(
            "Не удалось подтвердить целевую БД: фактическое имя БД не совпадает "
            "с DATABASE_URL."
        )
    if actual_database != expected_database_name.strip():
        raise SafetyError("Фактическое имя БД не совпадает с --expected-database-name.")
    if not is_test_database_name(actual_database):
        raise SafetyError("Фактическая БД не является явно test-БД.")
    return DatabaseIdentity(
        configured_host=(url.host or "").strip().lower(),
        database_name=actual_database,
        server_address=(str(row["server_address"]) if row["server_address"] else None),
    )


def require_local_database(identity: DatabaseIdentity) -> None:
    if identity.configured_host not in LOCAL_HOSTS:
        raise SafetyError(
            f"Удаление заблокировано: host {identity.configured_host!r} не является "
            "локальным. Разрешены только localhost, 127.0.0.1 и ::1."
        )
    if identity.server_address not in LOCAL_HOSTS:
        raise SafetyError(
            "Удаление заблокировано: PostgreSQL server address "
            f"{identity.server_address!r} не является loopback-адресом."
        )


def find_contacts(conn: Connection, *, lock: bool = False) -> list[Contact]:
    statement = FIND_FOR_UPDATE_SQL if lock else FIND_SQL
    rows = conn.execute(statement, {"name_pattern": LIKE_PATTERN}).mappings().all()
    return [Contact(int(row["contact_id"]), str(row["full_name"])) for row in rows]


def print_identity(identity: DatabaseIdentity, output: TextIO) -> None:
    print(f"DB host: {identity.configured_host or '<не указан>'}", file=output)
    print(f"DB name: {identity.database_name}", file=output)
    print(f"DB server address: {identity.server_address or '<не сообщён сервером>'}", file=output)


def print_contacts(contacts: Sequence[Contact], output: TextIO) -> None:
    for contact in contacts:
        print(f"{contact.contact_id}\t{contact.full_name}", file=output)
    print(f"Найдено записей: {len(contacts)}", file=output)


def soft_delete_contacts(conn: Connection, contacts: Sequence[Contact]) -> list[Contact]:
    if not contacts:
        return []
    rows = conn.execute(
        SOFT_DELETE_SQL,
        {
            "contact_ids": [contact.contact_id for contact in contacts],
            "name_pattern": LIKE_PATTERN,
        },
    ).mappings().all()
    deleted = [Contact(int(row["contact_id"]), str(row["full_name"])) for row in rows]
    if len(deleted) != len(contacts):
        raise RuntimeError(
            "Список контактов изменился во время операции; вся транзакция будет отменена."
        )
    return deleted


def count_contacts(conn: Connection) -> int:
    return int(conn.execute(COUNT_SQL, {"name_pattern": LIKE_PATTERN}).scalar_one())


def describe_referencing_fks(conn: Connection) -> list[str]:
    rows = conn.execute(REFERENCING_FKS_SQL).mappings().all()
    return [
        f"{row['table_schema']}.{row['table_name']}.{row['column_name']} "
        f"({row['constraint_name']}, ON DELETE {row['delete_rule']})"
        for row in rows
    ]


def run_cleanup(
    engine: Engine,
    configured_url: str,
    *,
    apply: bool,
    expected_database_name: str,
    input_fn: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> int:
    try:
        preflight_database_url(
            configured_url,
            expected_database_name=expected_database_name,
        )
    except Exception as exc:
        print(f"ОШИБКА: {exc}", file=output)
        return 1

    if not apply:
        with engine.connect() as conn:
            identity = inspect_database(
                conn,
                configured_url,
                expected_database_name=expected_database_name,
            )
            require_local_database(identity)
            contacts = find_contacts(conn)
        print_identity(identity, output)
        print_contacts(contacts, output)
        print("DRY RUN — записи не удалены", file=output)
        return 0

    deleted: list[Contact] = []
    try:
        with engine.begin() as conn:
            identity = inspect_database(
                conn,
                configured_url,
                expected_database_name=expected_database_name,
            )
            require_local_database(identity)
            contacts = find_contacts(conn, lock=True)
            print_identity(identity, output)
            print_contacts(contacts, output)
            confirmation = input_fn(
                f"Для удаления введите точную фразу {CONFIRMATION_PHRASE}: "
            )
            if confirmation != CONFIRMATION_PHRASE:
                print("Операция отменена — записи не удалены.", file=output)
                return 0
            deleted = soft_delete_contacts(conn, contacts)
    except Exception as exc:
        print(f"ОШИБКА: транзакция полностью отменена: {exc}", file=output)
        try:
            with engine.connect() as conn:
                blockers = describe_referencing_fks(conn)
            if blockers:
                print("Связи, которые могут блокировать удаление:", file=output)
                for blocker in blockers:
                    print(f"- {blocker}", file=output)
        except Exception:
            pass
        return 1

    with engine.connect() as conn:
        remaining = count_contacts(conn)
    print(f"Удалено записей (soft delete): {len(deleted)}", file=output)
    print(f"Осталось активных записей с префиксом {NAME_PREFIX!r}: {remaining}", file=output)
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить подтверждённый soft delete (по умолчанию только dry-run).",
    )
    parser.add_argument(
        "--expected-database-name",
        required=True,
        help="Точное имя локальной test-БД; должно совпадать с DATABASE_URL.",
    )
    return parser.parse_args(argv)


def get_configured_database_url() -> str:
    """Read the configured URL without importing the module that creates an engine."""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise SafetyError("DATABASE_URL is required.")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        configured_url = get_configured_database_url()
        preflight_database_url(
            configured_url,
            expected_database_name=args.expected_database_name,
        )
        engine, engine_url = get_project_engine()
        return run_cleanup(
            engine,
            engine_url,
            apply=bool(args.apply),
            expected_database_name=args.expected_database_name,
        )
    except Exception as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
