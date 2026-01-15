# app/directory.py
from __future__ import annotations

from typing import List, Optional, Literal
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/directory", tags=["directory"])


class Department(BaseModel):
    id: int
    name: str


class Position(BaseModel):
    id: int
    name: str


class EmployeeListItem(BaseModel):
    id: str
    full_name: str
    department: Department
    position: Position
    date_from: Optional[str]
    date_to: Optional[str]
    employment_rate: Optional[float]
    is_active: bool


class EmployeesResponse(BaseModel):
    items: List[EmployeeListItem] = Field(default_factory=list)
    total: int


@router.get("/departments", response_model=List[Department])
def departments() -> List[Department]:
    sql = text("""
        SELECT department_id AS id, name
        FROM public.departments
        ORDER BY name
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()
    return [Department(id=r["id"], name=r["name"]) for r in rows]


@router.get("/positions", response_model=List[Position])
def positions() -> List[Position]:
    sql = text("""
        SELECT position_id AS id, name
        FROM public.positions
        ORDER BY name
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()
    return [Position(id=r["id"], name=r["name"]) for r in rows]


@router.get("/employees", response_model=EmployeesResponse)
def employees(
    q: Optional[str] = Query(default=None),
    department_id: Optional[int] = Query(default=None, ge=1),
    position_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Literal["full_name", "id"] = Query(default="full_name"),
    order: Literal["asc", "desc"] = Query(default="asc"),
) -> EmployeesResponse:

    where = []
    params = {"limit": limit, "offset": offset}

    if q:
        where.append("e.full_name ILIKE :q")
        params["q"] = f"%{q}%"

    if department_id:
        where.append("e.department_id = :department_id")
        params["department_id"] = department_id

    if position_id:
        where.append("e.position_id = :position_id")
        params["position_id"] = position_id

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    order_sql = "ASC" if order == "asc" else "DESC"
    sort_sql = "e.full_name" if sort == "full_name" else "e.employee_id"

    sql_items = text(f"""
        SELECT
            e.employee_id AS id,
            e.full_name,
            d.department_id AS department_id,
            d.name AS department_name,
            p.position_id AS position_id,
            p.name AS position_name,
            e.date_from::text AS date_from,
            e.date_to::text AS date_to,
            e.employment_rate::float AS employment_rate,
            e.is_active
        FROM public.employees e
        JOIN public.departments d ON d.department_id = e.department_id
        JOIN public.positions p ON p.position_id = e.position_id
        {where_sql}
        ORDER BY {sort_sql} {order_sql}
        LIMIT :limit OFFSET :offset
    """)

    sql_total = text(f"""
        SELECT COUNT(*)
        FROM public.employees e
        {where_sql}
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql_items, params).mappings().all()
        total = int(conn.execute(sql_total, params).scalar() or 0)

    items = [
        EmployeeListItem(
            id=r["id"],
            full_name=r["full_name"],
            department=Department(id=r["department_id"], name=r["department_name"]),
            position=Position(id=r["position_id"], name=r["position_name"]),
            date_from=r["date_from"],
            date_to=r["date_to"],
            employment_rate=r["employment_rate"],
            is_active=bool(r["is_active"]),
        )
        for r in rows
    ]

    return EmployeesResponse(items=items, total=total)

@router.get("/_debug/db")
def _debug_db():
    from sqlalchemy import text
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT current_database() AS db, current_setting('port') AS port")
        ).mappings().one()
    return {"db": row["db"], "port": row["port"]}
