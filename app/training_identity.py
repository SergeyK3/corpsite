"""Resolve a training login against the current source password verifier.

The training database stores only source user IDs.  External source access is
read-only and opt-in; local links are useful for isolated integration tests.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import engine


class TrainingIdentityCollision(RuntimeError):
    """The same derived login points to more than one linked source."""


def _links_available(conn) -> bool:
    return bool(conn.execute(
        text("SELECT to_regclass('public.training_identity_links') IS NOT NULL")
    ).scalar_one())


def _source_engine(kind: str):
    if kind == "local":
        return engine
    url = (os.getenv("TRAINING_IDENTITY_SOURCE_URL") or "").strip()
    if not url:
        raise RuntimeError("TRAINING_IDENTITY_SOURCE_URL is not configured")
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def _source_row(kind: str, *, user_id: int | None = None, login: str | None = None) -> dict[str, Any] | None:
    if (user_id is None) == (login is None):
        raise ValueError("Exactly one source lookup key is required")
    source = _source_engine(kind)
    try:
        with source.connect() as conn:
            row = conn.execute(text("""
                SELECT user_id, login, password_hash, is_active, token_version,
                       locked_until, locked_at, must_change_password
                FROM public.users
                WHERE (:uid IS NOT NULL AND user_id=:uid)
                   OR (:login IS NOT NULL AND lower(login)=lower(:login))
            """), {"uid": user_id, "login": login}).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError as exc:
        if source is not engine:
            raise RuntimeError("Training identity source query failed") from exc
        raise
    finally:
        if source is not engine:
            source.dispose()


def link_for_target(target_user_id: int) -> dict[str, Any] | None:
    with engine.connect() as conn:
        if not _links_available(conn):
            return None
        row = conn.execute(text("""
            SELECT training_user_id, source_user_id, source_kind
            FROM public.training_identity_links
            WHERE training_user_id=:uid
        """), {"uid": target_user_id}).mappings().first()
    return dict(row) if row else None


def source_for_target(target_user_id: int) -> dict[str, Any] | None:
    link = link_for_target(target_user_id)
    if not link:
        return None
    return _source_row(link["source_kind"], user_id=int(link["source_user_id"]))


def target_for_login(training_login: str) -> tuple[str, dict[str, Any]] | None:
    if not training_login.casefold().endswith("_test"):
        return None
    with engine.connect() as conn:
        if not _links_available(conn):
            return None
    source_login = training_login[:-5]
    if not source_login:
        return None
    matches: list[tuple[str, dict[str, Any]]] = []
    for kind in ("local", "external"):
        if kind == "external" and not os.getenv("TRAINING_IDENTITY_SOURCE_URL"):
            continue
        source = _source_row(kind, login=source_login)
        if not source:
            continue
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT l.training_user_id, u.login AS target_login
                FROM public.training_identity_links l
                JOIN public.users u ON u.user_id=l.training_user_id
                WHERE l.source_kind=:kind AND l.source_user_id=:uid
            """), {"kind": kind, "uid": source["user_id"]}).mappings().first()
        if row:
            # The source login is authoritative even after it changes.
            matches.append((str(row["target_login"]), source))
    if len(matches) > 1:
        raise TrainingIdentityCollision("Ambiguous derived training login")
    return matches[0] if matches else None
