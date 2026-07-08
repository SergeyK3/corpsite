"""PMF domain plugin registry."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_migration import DOMAIN_CODE_EDUCATION
from app.services.personnel_migration_types import (
    PersonnelMigrationDomainPlugin,
    PersonnelMigrationNotFoundError,
    PersonnelMigrationValidationError,
)

_PLUGINS: dict[str, PersonnelMigrationDomainPlugin] = {}


def _load_plugins() -> None:
    if _PLUGINS:
        return
    from app.services.education_migration_plugin import EducationMigrationPlugin

    _PLUGINS[DOMAIN_CODE_EDUCATION] = EducationMigrationPlugin()


def get_domain_plugin(domain_code: str) -> PersonnelMigrationDomainPlugin:
    _load_plugins()
    plugin = _PLUGINS.get(domain_code)
    if plugin is None:
        raise PersonnelMigrationValidationError(f"Unknown PMF domain: {domain_code}")
    return plugin


def fetch_domain_row(conn: Connection, domain_code: str) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT domain_code, display_name, is_enabled
            FROM public.personnel_migration_domains
            WHERE domain_code = :domain_code
            """
        ),
        {"domain_code": domain_code},
    ).mappings().first()
    if row is None:
        raise PersonnelMigrationNotFoundError(f"PMF domain not found: {domain_code}")
    return dict(row)


def assert_domain_available(
    conn: Connection,
    domain_code: str,
    *,
    allow_disabled_domain: bool = False,
) -> dict[str, Any]:
    domain = fetch_domain_row(conn, domain_code)
    if not domain.get("is_enabled") and not allow_disabled_domain:
        raise PersonnelMigrationValidationError(
            f"PMF domain {domain_code!r} is disabled."
        )
    return domain
