# FILE: app/security/directory_scope.py

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine

# JWT decoder (единый, как в app/auth.py)
try:
    from app.auth import decode_and_verify_token  # type: ignore
except Exception:  # pragma: no cover
    decode_and_verify_token = None  # type: ignore


# ---------------------------
# Config
# ---------------------------

SYSTEM_ADMIN_ROLE_ID = 2


def _app_env() -> str:
    return (os.getenv("APP_ENV") or "dev").strip().lower()


def _internal_api_token() -> str:
    return (os.getenv("INTERNAL_API_TOKEN") or "").strip()


def legacy_x_user_id_enabled() -> bool:
    raw = (os.getenv("ENABLE_LEGACY_X_USER_ID") or "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return _app_env() not in {"prod", "production"}


def internal_api_token_enabled() -> bool:
    return bool(_internal_api_token())


def has_valid_internal_api_token(x_internal_api_token: Optional[str]) -> bool:
    token = _internal_api_token()
    if not token:
        return False
    return (x_internal_api_token or "").strip() == token


def rbac_mode() -> str:
    # off | dept | groups
    v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
    return v if v in ("off", "dept", "groups") else "dept"


def _parse_int_set_env(name: str) -> Set[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            out.add(int(s))
        except ValueError:
            continue
    return out


def privileged_user_ids() -> Set[int]:
    # Preferred: DIRECTORY_PRIVILEGED_USER_IDS
    # Backward-compat: DIRECTORY_PRIVILEGED_IDS
    s = set()
    s |= _parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")
    s |= _parse_int_set_env("DIRECTORY_PRIVILEGED_IDS")
    return s


def privileged_role_ids() -> Set[int]:
    # Preferred: DIRECTORY_PRIVILEGED_ROLE_IDS
    # Tech admin role is always privileged by code.
    s = _parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")
    s.add(SYSTEM_ADMIN_ROLE_ID)
    return s


def deputy_user_ids() -> Set[int]:
    # New: DIRECTORY_DEPUTY_USER_IDS
    # Backward-compat (если захотите): DIRECTORY_DEPUTY_IDS
    s = set()
    s |= _parse_int_set_env("DIRECTORY_DEPUTY_USER_IDS")
    s |= _parse_int_set_env("DIRECTORY_DEPUTY_IDS")
    return s


def deputy_role_ids() -> Set[int]:
    # New: DIRECTORY_DEPUTY_ROLE_IDS
    return _parse_int_set_env("DIRECTORY_DEPUTY_ROLE_IDS")


def is_system_admin_role_id(role_id: Any) -> bool:
    try:
        return int(role_id) == SYSTEM_ADMIN_ROLE_ID
    except Exception:
        return False


def is_system_admin(user_ctx: Dict[str, Any]) -> bool:
    return is_system_admin_role_id(user_ctx.get("role_id"))


# ---------------------------
# Requester context (JWT/X-User-Id)
# ---------------------------
def _token_from_authorization(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    a = str(authorization).strip()
    if not a:
        return None
    parts = a.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        return None
    return token


def user_id_from_authorization(authorization: Optional[str]) -> Optional[int]:
    """
    Возвращает user_id из Authorization: Bearer <jwt>.
    """
    if decode_and_verify_token is None:
        return None
    token = _token_from_authorization(authorization)
    if not token:
        return None
    try:
        payload = decode_and_verify_token(token) or {}
        sub = (payload.get("sub") or "").strip()
        if not sub:
            return None
        uid = int(sub)
        return uid if uid > 0 else None
    except Exception:
        return None


def require_user_id(x_user_id: Optional[str]) -> int:
    """
    LEGACY: X-User-Id.
    Оставлено для обратной совместимости на время миграции.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    s = str(x_user_id).strip()
    if not s:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    try:
        return int(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")


def require_uid(
    *,
    authorization: Optional[str],
    x_user_id: Optional[str] = None,
    x_internal_api_token: Optional[str] = None,
) -> int:
    """
    JWT-first (взрослый режим). X-User-Id — только fallback на период миграции.
    """
    uid = user_id_from_authorization(authorization)
    if uid is not None:
        return uid
    if x_internal_api_token is not None and not has_valid_internal_api_token(x_internal_api_token):
        raise HTTPException(status_code=403, detail="Invalid internal API token")
    if has_valid_internal_api_token(x_internal_api_token):
        return require_user_id(x_user_id)
    if not legacy_x_user_id_enabled():
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")
    # fallback legacy
    return require_user_id(x_user_id)


def load_user_ctx(user_id: int) -> Dict[str, Any]:
    q = text(
        """
        SELECT user_id, role_id, unit_id, is_active, login
        FROM public.users
        WHERE user_id = :uid
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"uid": user_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="Unknown user.")
    if not bool(row.get("is_active")):
        raise HTTPException(status_code=403, detail="User is inactive.")
    return dict(row)


def is_privileged(user_ctx: Dict[str, Any]) -> bool:
    if is_system_admin(user_ctx):
        return True

    uid = int(user_ctx["user_id"])
    rid = int(user_ctx["role_id"]) if user_ctx.get("role_id") is not None else -1
    if uid in privileged_user_ids():
        return True
    if rid in privileged_role_ids():
        return True
    return False


def is_deputy(user_ctx: Dict[str, Any]) -> bool:
    """
    'Зам' определяется через env:
      - DIRECTORY_DEPUTY_USER_IDS
      - DIRECTORY_DEPUTY_ROLE_IDS
    """
    if is_system_admin(user_ctx):
        return False

    uid = int(user_ctx["user_id"])
    rid = int(user_ctx["role_id"]) if user_ctx.get("role_id") is not None else -1
    if uid in deputy_user_ids():
        return True
    if rid in deputy_role_ids():
        return True
    return False


def _resolve_parent_unit_id(unit_id: int) -> Optional[int]:
    """
    Возвращает parent_unit_id для org_units.unit_id.
    Если не найдено или parent_unit_id NULL -> None.
    """
    q = text(
        """
        SELECT parent_unit_id
        FROM public.org_units
        WHERE unit_id = :uid
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"uid": int(unit_id)}).mappings().first()
    if not row:
        return None
    parent_id = row.get("parent_unit_id")
    if parent_id is None:
        return None
    try:
        return int(parent_id)
    except Exception:
        return None


def require_dept_scope(user_ctx: Dict[str, Any]) -> Optional[int]:
    """
    For RBAC_MODE=dept:

      - privileged / system admin -> no restriction (None)
      - deputy                   -> scope = parent(unit_id) if exists else unit_id
      - regular user             -> scope = unit_id
    """
    if is_privileged(user_ctx):
        return None

    unit_id = user_ctx.get("unit_id")
    if unit_id is None:
        raise HTTPException(
            status_code=403,
            detail="directory: cannot determine department scope for user (unit_id is null).",
        )
    try:
        own_unit_id = int(unit_id)
    except Exception:
        raise HTTPException(
            status_code=403,
            detail="directory: invalid unit_id for department scope.",
        )

    # "Зам" видит уровень выше (если есть parent_unit_id)
    if is_deputy(user_ctx):
        parent_unit_id = _resolve_parent_unit_id(own_unit_id)
        return parent_unit_id if parent_unit_id is not None else own_unit_id

    return own_unit_id


# ---------------------------
# RBAC helpers for services
# ---------------------------
def build_dept_scope_cte(
    *,
    scope_unit_id: Optional[int],
    alias: str = "e",
    column: str = "org_unit_id",
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Build CTE + WHERE fragment for dept RBAC scope.

    Returns:
      cte_sql      : string (WITH RECURSIVE ... or empty)
      where_sql    : string condition to be AND-ed
      params       : dict of SQL params

    If scope_unit_id is None -> returns empty fragments (no RBAC restriction).
    """
    if scope_unit_id is None:
        return "", "TRUE", {}

    cte_sql = """
    WITH RECURSIVE rbac_subtree AS (
        SELECT unit_id
        FROM public.org_units
        WHERE unit_id = :rbac_scope_unit_id
        UNION ALL
        SELECT ou.unit_id
        FROM public.org_units ou
        JOIN rbac_subtree s ON ou.parent_unit_id = s.unit_id
    )
    """.strip()

    where_sql = f"{alias}.{column} IN (SELECT unit_id FROM rbac_subtree)"
    params = {"rbac_scope_unit_id": int(scope_unit_id)}

    return cte_sql, where_sql, params