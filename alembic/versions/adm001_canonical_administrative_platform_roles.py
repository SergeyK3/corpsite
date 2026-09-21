"""Seed missing canonical administrative Platform Roles without permissions.

Revision ID: adm001canonicalroles
Revises: qmt001trainingexpert
"""
from __future__ import annotations

from typing import Any

from alembic import op
from sqlalchemy import text


revision = "adm001canonicalroles"
down_revision = "qmt001trainingexpert"
branch_labels = None
depends_on = None


# These are the only DIRECTOR/DEP_* Platform Roles supported by the current
# application classifier and canonical seed.  This migration is catalog-only:
# it creates no users, access_grants, access_roles, or permissions.
CANONICAL_ADMINISTRATIVE_ROLES: tuple[tuple[str, str], ...] = (
    ("DIRECTOR", "Директор"),
    ("DEP_MED", "Зам по лечебной работе"),
    ("DEP_OUTPATIENT_AUDIT", "Зам по диспансеру и внутр экспертизе"),
    ("DEP_ADMIN", "Заместитель директора по административным вопросам"),
    ("DEP_STRATEGY", "Зам по стратегии"),
)

# Production has the expanded title while older local catalogues use the
# approved legacy abbreviation.  Existing rows are never rewritten.
DEP_ADMIN_PRODUCTION_NAME = "Заместитель директора по административным вопросам"
DEP_ADMIN_LEGACY_NAME = "Зам по адм вопросам"
_DEP_ADMIN_ALLOWED_NAMES = frozenset({DEP_ADMIN_PRODUCTION_NAME, DEP_ADMIN_LEGACY_NAME})

_MARKER_TABLE = "public.platform_role_migration_ownership"


def _ensure_marker_table(conn: Any) -> None:
    """Track only rows created by this migration for a conservative downgrade."""
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {_MARKER_TABLE} (
                migration_revision VARCHAR(64) NOT NULL,
                role_id BIGINT NOT NULL REFERENCES public.roles(role_id) ON DELETE CASCADE,
                PRIMARY KEY (migration_revision, role_id)
            )
            """
        )
    )


def _upgrade_connection(conn: Any) -> None:
    _ensure_marker_table(conn)
    for code, expected_name in CANONICAL_ADMINISTRATIVE_ROLES:
        existing = conn.execute(
            text("SELECT role_id, name FROM public.roles WHERE code=:code FOR UPDATE"),
            {"code": code},
        ).mappings().one_or_none()
        if existing is not None:
            allowed_names = _DEP_ADMIN_ALLOWED_NAMES if code == "DEP_ADMIN" else frozenset({expected_name})
            if existing["name"] not in allowed_names:
                raise RuntimeError(
                    f"Administrative Platform Role {code} has unexpected name; migration refuses to overwrite it."
                )
            continue

        role_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.roles (code, name, is_active)
                    VALUES (:code, :name, TRUE)
                    RETURNING role_id
                    """
                ),
                {"code": code, "name": expected_name},
            ).scalar_one()
        )
        conn.execute(
            text(
                f"""
                INSERT INTO {_MARKER_TABLE} (migration_revision, role_id)
                VALUES (:revision, :role_id)
                ON CONFLICT (migration_revision, role_id) DO NOTHING
                """
            ),
            {"revision": revision, "role_id": role_id},
        )


def upgrade() -> None:
    _upgrade_connection(op.get_bind())


def _downgrade_connection(conn: Any) -> None:
    _ensure_marker_table(conn)
    created_role_ids = conn.execute(
        text(
            f"""
            SELECT role_id
            FROM {_MARKER_TABLE}
            WHERE migration_revision=:revision
            FOR UPDATE
            """
        ),
        {"revision": revision},
    ).scalars().all()
    if not created_role_ids:
        return

    for role_id in created_role_ids:
        if conn.execute(
            text("SELECT 1 FROM public.users WHERE role_id=:role_id LIMIT 1"),
            {"role_id": int(role_id)},
        ).scalar_one_or_none() is not None:
            raise RuntimeError("Cannot remove administrative Platform Role while users reference it.")
        if conn.execute(
            text("SELECT 1 FROM public.access_grants WHERE target_type='ROLE' AND target_id=:role_id LIMIT 1"),
            {"role_id": int(role_id)},
        ).scalar_one_or_none() is not None:
            raise RuntimeError("Cannot remove administrative Platform Role while grants reference it.")

    conn.execute(
        text(
            f"""
            DELETE FROM public.roles
            WHERE role_id IN (
                SELECT role_id FROM {_MARKER_TABLE}
                WHERE migration_revision=:revision
            )
            """
        ),
        {"revision": revision},
    )


def downgrade() -> None:
    _downgrade_connection(op.get_bind())
