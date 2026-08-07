# FILE: app/directory/positions_routes.py
from __future__ import annotations

from typing import Any, Dict, Literal, Optional, List, Sequence, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy
from app.security.directory_scope import (
    is_privileged as _is_privileged,
    is_system_admin as _is_system_admin,
)

from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.services.org_unit_allowed_positions_service import (
    SORT_ORDER_OMITTED,
    AllowedPositionMutationNotFoundError,
    build_allowed_positions_exists_sql,
    build_allowed_positions_order_sql,
    deactivate_allowed_position_link,
    upsert_allowed_position_link,
)
from app.services.position_dependencies_service import (
    PositionForeignKeyDependency,
    build_position_blocked_exists_sql,
    check_position_dependencies,
    check_positions_dependencies,
    load_position_blocking_foreign_keys,
)

router = APIRouter()

ALLOWED_CATEGORIES = {"leaders", "medical", "admin", "technical", "other"}
POSITION_LIST_SCOPES = {"used", "allowed"}
POSITION_DELETE_STATUSES = {"deletable", "blocked"}


class PositionUpsert(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)


class AllowedPositionPutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sort_order: Optional[StrictInt] = None


class AllowedPositionStateOut(BaseModel):
    is_active: bool
    sort_order: Optional[int]


class AllowedPositionLinkOut(BaseModel):
    org_unit_allowed_position_id: int
    org_unit_id: int
    position_id: int
    sort_order: Optional[int]
    is_active: bool


class AllowedPositionMutationOut(BaseModel):
    link: AllowedPositionLinkOut
    transition: Literal["created", "reactivated", "updated", "noop"]
    previous_state: Optional[AllowedPositionStateOut]
    current_state: AllowedPositionStateOut


class HttpErrorOut(BaseModel):
    detail: str


class AllowedPositionNotFoundDetailOut(BaseModel):
    error_code: Literal[
        "POSITION_NOT_FOUND",
        "ORG_UNIT_NOT_FOUND",
        "ALLOWED_POSITION_LINK_NOT_FOUND",
    ]


class AllowedPositionNotFoundOut(BaseModel):
    detail: AllowedPositionNotFoundDetailOut


class PositionDeleteOut(BaseModel):
    ok: Literal[True]
    position_id: int


class AllowedPositionDependencyLinkOut(BaseModel):
    org_unit_allowed_position_id: int
    org_unit_id: int
    org_unit_name: str
    is_active: bool


class PositionDependencyOut(BaseModel):
    key: str
    label: str
    table: str
    column: str
    constraint: str
    count: int
    allowed_position_links: Optional[List[AllowedPositionDependencyLinkOut]] = None


class PositionDependencyConflictDetailOut(BaseModel):
    error_code: Literal["POSITION_HAS_DEPENDENCIES"]
    position_id: int
    can_delete: bool
    total_dependencies: int
    dependencies: List[PositionDependencyOut]
    race_detected: Optional[Literal[True]] = None


class PositionDefensiveFkConflictDetailOut(BaseModel):
    error_code: Literal["POSITION_HAS_DEPENDENCIES"]
    race_detected: Literal[True]


class PositionDependencyConflictOut(BaseModel):
    detail: Union[
        PositionDependencyConflictDetailOut,
        PositionDefensiveFkConflictDetailOut,
    ]


class _ConfirmedPositionDeleteFkRace(RuntimeError):
    """Internal signal raised only from the direct Position DELETE site."""


def _normalize_name(value: str) -> str:
    return " ".join((value or "").replace(" -", "-").replace("- ", "-").split()).strip()


def _normalize_category(value: Optional[str]) -> str:
    s = str(value or "").strip().lower()
    if s not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail="category must be one of: leaders, medical, admin, technical, other.",
        )
    return s


def _allowed_position_link_response(link: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "org_unit_allowed_position_id": int(link["org_unit_allowed_position_id"]),
        "org_unit_id": int(link["org_unit_id"]),
        "position_id": int(link["position_id"]),
        "sort_order": link["sort_order"],
        "is_active": bool(link["is_active"]),
    }


def _allowed_position_not_found(exc: AllowedPositionMutationNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error_code": exc.code},
    )


def _is_position_delete_fk_race(
    exc: IntegrityError,
    dependencies: Sequence[PositionForeignKeyDependency],
) -> bool:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate != "23503":
        return False

    diag = getattr(original, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if not constraint_name:
        return False

    schema_name = getattr(diag, "schema_name", None)
    table_name = getattr(diag, "table_name", None)
    matches = [
        dependency
        for dependency in dependencies
        if dependency.constraint_name == str(constraint_name)
        and (schema_name is None or dependency.table_schema == str(schema_name))
        and (table_name is None or dependency.table_name == str(table_name))
    ]
    return len(matches) == 1


def _get_columns(rel: str, schema: str = "public") -> List[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :rel
        ORDER BY ordinal_position
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema, "rel": rel}).fetchall()
    return [str(r[0]) for r in rows]


def _pick_first(existing: List[str], candidates: List[str]) -> Optional[str]:
    s = set(existing)
    for c in candidates:
        if c in s:
            return c
    return None


def _employees_org_meta() -> Dict[str, str]:
    cols = _get_columns("employees", "public")
    if not cols:
        raise HTTPException(status_code=500, detail="employees table not found.")

    position_col = _pick_first(cols, ["position_id"])
    org_unit_col = _pick_first(cols, ["org_unit_id", "unit_id"])

    if not position_col or not org_unit_col:
        raise HTTPException(
            status_code=500,
            detail="employees table must contain position_id and org_unit_id (or unit_id).",
        )

    return {
        "position_col": position_col,
        "org_unit_col": org_unit_col,
    }


def _get_org_unit_caption(org_unit_id: int) -> str:
    q = text(
        """
        SELECT COALESCE(NULLIF(TRIM(name), ''), CONCAT('unit #', CAST(unit_id AS TEXT))) AS unit_name
        FROM public.org_units
        WHERE unit_id = :org_unit_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"org_unit_id": int(org_unit_id)}).mappings().first()

    if not row:
        return f"unit #{int(org_unit_id)}"

    return str(row.get("unit_name") or f"unit #{int(org_unit_id)}").strip()


def _normalize_list_scope(
    scope: Optional[str],
    *,
    org_group_id: Optional[int],
    org_unit_id: Optional[int],
) -> str:
    normalized = str(scope or "used").strip().lower()
    if normalized not in POSITION_LIST_SCOPES:
        raise HTTPException(
            status_code=422,
            detail="scope must be one of: used, allowed.",
        )
    if normalized == "allowed" and org_group_id is None and org_unit_id is None:
        raise HTTPException(
            status_code=422,
            detail="scope=allowed requires org_unit_id and/or org_group_id.",
        )
    return normalized


@router.put(
    "/org-units/{org_unit_id}/allowed-positions/{position_id}",
    response_model=AllowedPositionMutationOut,
    responses={
        201: {"model": AllowedPositionMutationOut},
        403: {"model": HttpErrorOut},
        404: {"model": AllowedPositionNotFoundOut},
    },
)
def put_org_unit_allowed_position(
    org_unit_id: int,
    position_id: int,
    request: Request,
    response: Response,
    payload: Optional[AllowedPositionPutIn] = Body(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    sort_order = SORT_ORDER_OMITTED
    if payload is not None and "sort_order" in payload.model_fields_set:
        sort_order = payload.sort_order

    try:
        with engine.begin() as conn:
            result = upsert_allowed_position_link(
                conn,
                org_unit_id=int(org_unit_id),
                position_id=int(position_id),
                actor_user_id=int(user["user_id"]),
                sort_order=sort_order,
                request_id=request.headers.get("x-request-id"),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
    except AllowedPositionMutationNotFoundError as exc:
        raise _allowed_position_not_found(exc) from exc

    response.status_code = 201 if result.transition == "created" else 200
    return {
        "link": _allowed_position_link_response(result.link),
        "transition": result.transition,
        "previous_state": result.previous_state,
        "current_state": result.current_state,
    }


@router.delete(
    "/org-units/{org_unit_id}/allowed-positions/{position_id}",
    response_model=AllowedPositionLinkOut,
    responses={
        403: {"model": HttpErrorOut},
        404: {"model": AllowedPositionNotFoundOut},
    },
)
def delete_org_unit_allowed_position(
    org_unit_id: int,
    position_id: int,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        with engine.begin() as conn:
            link = deactivate_allowed_position_link(
                conn,
                org_unit_id=int(org_unit_id),
                position_id=int(position_id),
                actor_user_id=int(user["user_id"]),
                request_id=request.headers.get("x-request-id"),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
    except AllowedPositionMutationNotFoundError as exc:
        raise _allowed_position_not_found(exc) from exc

    return _allowed_position_link_response(link)


@router.get("/positions")
def list_positions_crud(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    org_group_id: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by top-level org group of employee's unit.",
    ),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    scope: Optional[str] = Query(
        default=None,
        description="Org-unit filter semantics: used (employees) or allowed (junction table). Default: used.",
    ),
    delete_status: Optional[str] = Query(
        default=None,
        description="Sysadmin-only deletion assessment filter: deletable or blocked.",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    visibility_scope = compute_scope(uid, user)
    require_personnel_visibility_or_403(user, visibility_scope)

    normalized_delete_status = str(delete_status or "").strip().lower() or None
    if normalized_delete_status is not None:
        if not _is_system_admin(user):
            raise HTTPException(status_code=403, detail="Forbidden.")
        if normalized_delete_status not in POSITION_DELETE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail="delete_status must be one of: deletable, blocked.",
            )

    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    where_parts = ["TRUE"]
    with_prefix = ""
    filter_org_unit_name: Optional[str] = None
    order_sql = "p.name ASC, p.position_id ASC"

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append("LOWER(CAST(p.name AS TEXT)) LIKE :q")

    if category and category.strip():
        params["category"] = _normalize_category(category)
        where_parts.append("p.category = :category")

    if scope is not None and str(scope).strip().lower() == "allowed":
        if org_group_id is None and org_unit_id is None:
            raise HTTPException(
                status_code=422,
                detail="scope=allowed requires org_unit_id and/or org_group_id.",
            )

    if org_group_id is not None or org_unit_id is not None:
        list_scope = _normalize_list_scope(
            scope,
            org_group_id=org_group_id,
            org_unit_id=org_unit_id,
        )
        if org_unit_id is not None:
            filter_org_unit_name = _get_org_unit_caption(int(org_unit_id))

        if list_scope == "allowed":
            allowed_exists, allowed_params = build_allowed_positions_exists_sql(
                org_group_id=int(org_group_id) if org_group_id is not None else None,
                org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
            )
            params.update(allowed_params)
            where_parts.append(allowed_exists)
            allowed_order, allowed_order_params = build_allowed_positions_order_sql(
                org_group_id=int(org_group_id) if org_group_id is not None else None,
                org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
            )
            params.update(allowed_order_params)
            order_sql = allowed_order
        else:
            emp_meta = _employees_org_meta()
            org_scope = apply_org_scope(
                strategy=OrgScopeStrategy.OWNER_UNIT,
                params=OrgScopeParams(
                    org_group_id=int(org_group_id) if org_group_id is not None else None,
                    org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
                ),
                regular_task_alias="e",
                owner_unit_column=emp_meta["org_unit_col"],
            )
            params.update(org_scope.params)
            with_prefix = f"{org_scope.cte_sql}\n" if org_scope.cte_sql else ""

            where_parts.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM public.employees e
                    WHERE e.{emp_meta['position_col']} = p.position_id
                      AND ({org_scope.where_sql})
                )
                """.strip()
            )

    with engine.begin() as conn:
        dependency_specs = []
        if _is_system_admin(user):
            dependency_specs = load_position_blocking_foreign_keys(conn)
            if normalized_delete_status is not None:
                blocked_sql = build_position_blocked_exists_sql(
                    dependency_specs,
                    position_expression="p.position_id",
                )
                where_parts.append(
                    f"({blocked_sql})"
                    if normalized_delete_status == "blocked"
                    else f"NOT ({blocked_sql})"
                )

        where_sql = " AND ".join(where_parts)
        q_total = text(
            f"""
            {with_prefix}
            SELECT COUNT(*) AS cnt
            FROM public.positions p
            WHERE {where_sql}
            """
        )
        q_list = text(
            f"""
            {with_prefix}
            SELECT p.position_id, p.name, p.category
            FROM public.positions p
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT :limit OFFSET :offset
            """
        )
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()
        assessments = (
            check_positions_dependencies(
                conn,
                position_ids=[int(row["position_id"]) for row in rows],
                dependencies=dependency_specs,
            )
            if _is_system_admin(user)
            else {}
        )

    items = []
    for r in rows:
        position_id = int(r["position_id"])
        item = {
            "position_id": int(r["position_id"]),
            "name": str(r["name"] or "").strip(),
            "category": str(r["category"] or "").strip(),
        }
        assessment = assessments.get(position_id)
        if assessment is not None:
            item["delete_assessment"] = assessment.to_dict()
        items.append(item)
    return {
        "items": items,
        "total": total,
        "filter_org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "filter_org_unit_name": filter_org_unit_name,
    }


@router.get("/positions/{position_id}")
def get_position(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    visibility_scope = compute_scope(uid, user)
    require_personnel_visibility_or_403(user, visibility_scope)

    q_one = text(
        """
        SELECT position_id, name, category
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_one, {"position_id": position_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Position not found.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.get("/positions/{position_id}/dependencies")
def get_position_dependencies(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM public.positions
                WHERE position_id = :position_id
                LIMIT 1
                """
            ),
            {"position_id": int(position_id)},
        ).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Position not found.")
        summary = check_position_dependencies(conn, position_id=int(position_id))
    return summary.to_dict()


@router.post("/positions")
def create_position(
    payload: PositionUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    name = _normalize_name(payload.name)
    category = _normalize_category(payload.category)

    if not name:
        raise HTTPException(status_code=422, detail="name is required.")

    q_exists = text(
        """
        SELECT position_id, name
        FROM public.positions
        WHERE lower(name) = lower(:name)
        LIMIT 1
        """
    )

    q_insert = text(
        """
        INSERT INTO public.positions(name, category)
        VALUES (:name, :category)
        RETURNING position_id, name, category
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"name": name}).mappings().first()
            if exists:
                raise HTTPException(status_code=409, detail="Position already exists.")

            row = conn.execute(
                q_insert,
                {"name": name, "category": category},
            ).mappings().first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Position already exists or conflicts with existing data.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.put("/positions/{position_id}")
def update_position(
    position_id: int,
    payload: PositionUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    name = _normalize_name(payload.name)
    category = _normalize_category(payload.category)

    if not name:
        raise HTTPException(status_code=422, detail="name is required.")

    q_exists = text(
        """
        SELECT position_id, name
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )

    q_dup = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE lower(name) = lower(:name)
          AND position_id <> :position_id
        LIMIT 1
        """
    )

    q_update = text(
        """
        UPDATE public.positions
        SET name = :name,
            category = :category
        WHERE position_id = :position_id
        RETURNING position_id, name, category
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"position_id": position_id}).mappings().first()
            if not exists:
                raise HTTPException(status_code=404, detail="Position not found.")

            dup = conn.execute(q_dup, {"position_id": position_id, "name": name}).first()
            if dup:
                raise HTTPException(status_code=409, detail="Position already exists.")

            row = conn.execute(
                q_update,
                {"position_id": position_id, "name": name, "category": category},
            ).mappings().first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Position update conflicts with existing data.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.delete(
    "/positions/{position_id}",
    response_model=PositionDeleteOut,
    responses={
        403: {"model": HttpErrorOut},
        404: {"model": HttpErrorOut},
        409: {"model": PositionDependencyConflictOut},
    },
)
def delete_position(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    q_exists = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        FOR UPDATE
        """
    )

    q_lock_allowed_links = text(
        """
        SELECT org_unit_allowed_position_id, is_active
        FROM public.org_unit_allowed_positions
        WHERE position_id = :position_id
        ORDER BY org_unit_allowed_position_id
        FOR UPDATE
        """
    )

    q_delete_inactive_links = text(
        """
        DELETE FROM public.org_unit_allowed_positions
        WHERE position_id = :position_id
          AND is_active = FALSE
        RETURNING org_unit_allowed_position_id
        """
    )

    q_delete = text(
        """
        DELETE FROM public.positions
        WHERE position_id = :position_id
        RETURNING position_id
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"position_id": position_id}).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Position not found.")

            allowed_links = conn.execute(
                q_lock_allowed_links,
                {"position_id": int(position_id)},
            ).mappings().all()
            if any(bool(row["is_active"]) for row in allowed_links):
                summary = check_position_dependencies(conn, position_id=int(position_id))
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "POSITION_HAS_DEPENDENCIES",
                        **summary.to_dict(),
                    },
                )

            inactive_link_ids = {
                int(row["org_unit_allowed_position_id"])
                for row in allowed_links
            }
            deleted_inactive_link_ids = {
                int(row["org_unit_allowed_position_id"])
                for row in conn.execute(
                    q_delete_inactive_links,
                    {"position_id": int(position_id)},
                ).mappings().all()
            }
            if deleted_inactive_link_ids != inactive_link_ids:
                raise RuntimeError("INACTIVE_ALLOWED_POSITION_CLEANUP_MISMATCH")

            summary = check_position_dependencies(conn, position_id=int(position_id))
            if not summary.can_delete:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "POSITION_HAS_DEPENDENCIES",
                        **summary.to_dict(),
                    },
                )

            try:
                with conn.begin_nested():
                    deleted_position_id = conn.execute(
                        q_delete,
                        {"position_id": int(position_id)},
                    ).scalar_one_or_none()
            except IntegrityError as exc:
                dependencies = load_position_blocking_foreign_keys(conn)
                if _is_position_delete_fk_race(exc, dependencies):
                    raise _ConfirmedPositionDeleteFkRace from exc
                raise
            if deleted_position_id is None:
                raise RuntimeError("POSITION_DELETE_STALE_WRITE")
    except _ConfirmedPositionDeleteFkRace as exc:
        # The request transaction has rolled back before this assessment. Keep
        # the refreshed production result internal to the defensive branch.
        with engine.begin() as conn:
            check_position_dependencies(conn, position_id=int(position_id))
        # Keep the defensive response closed: PostgreSQL diagnostics and the
        # discovered constraint identity are internal classifier evidence.
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "POSITION_HAS_DEPENDENCIES",
                "race_detected": True,
            },
        ) from exc

    return {"ok": True, "position_id": position_id}
