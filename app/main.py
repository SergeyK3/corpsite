# app/main.py
from __future__ import annotations

from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# -----------------------
# Env (single source of truth)
# -----------------------
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.meta import router as meta_router
from app.tasks import router as tasks_router
from .tg_bind import router as tg_bind_router

from app.errors import raise_error, ErrorCode


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="Corpsite MVP", default_response_class=UTF8JSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta_router)
app.include_router(tasks_router)
app.include_router(tg_bind_router)


# -----------------------
# Models (minimal)
# -----------------------

class PeriodCreate(BaseModel):
    date_start: date
    date_end: date
    label: str = Field(..., min_length=1, max_length=50)


class PeriodOut(BaseModel):
    period_id: int
    kind: str
    date_start: date
    date_end: date
    label: str
    is_closed: bool


class GenerateTasksRequest(BaseModel):
    initiator_user_id: int


# -----------------------
# Health
# -----------------------

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


# -----------------------
# (1) Periods: create/list (MONTH only for MVP)
# -----------------------

@app.post("/periods", response_model=PeriodOut)
def create_period(payload: PeriodCreate):
    if payload.date_start > payload.date_end:
        raise HTTPException(status_code=400, detail="date_start must be <= date_end")

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO reporting_periods (kind, date_start, date_end, label)
                    VALUES ('MONTH', :ds, :de, :label)
                    RETURNING period_id, kind, date_start, date_end, label, is_closed
                """),
                {"ds": payload.date_start, "de": payload.date_end, "label": payload.label},
            ).fetchone()
    except IntegrityError:
        # 409 по контракту: период уже существует (уникальный индекс/ограничение в БД)
        raise_error(
            ErrorCode.PERIODS_CONFLICT_EXISTS,
            extra={
                "kind": "MONTH",
                "date_start": payload.date_start.isoformat(),
                "date_end": payload.date_end.isoformat(),
            },
        )

    return PeriodOut(
        period_id=int(row[0]),
        kind=str(row[1]),
        date_start=row[2],
        date_end=row[3],
        label=str(row[4]),
        is_closed=bool(row[5]),
    )


@app.get("/periods", response_model=List[PeriodOut])
def list_periods():
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT period_id, kind, date_start, date_end, label, is_closed
                FROM reporting_periods
                WHERE kind = 'MONTH'
                ORDER BY date_start DESC
            """)
        ).fetchall()

    return [
        PeriodOut(
            period_id=int(r[0]),
            kind=str(r[1]),
            date_start=r[2],
            date_end=r[3],
            label=str(r[4]),
            is_closed=bool(r[5]),
        )
        for r in rows
    ]


# -----------------------
# (2) Generate monthly tasks for a period
# -----------------------

@app.post("/periods/{period_id}/generate-tasks")
def generate_tasks(period_id: int, payload: GenerateTasksRequest) -> Dict[str, Any]:
    with engine.begin() as conn:
        # до генерации: есть ли уже задачи по периоду
        existing_before = conn.execute(
            text("SELECT COUNT(1) FROM tasks WHERE period_id = :pid"),
            {"pid": int(period_id)},
        ).scalar() or 0

        row = conn.execute(
            text("SELECT generate_monthly_tasks(:pid, :initiator)"),
            {"pid": int(period_id), "initiator": payload.initiator_user_id},
        ).fetchone()

        created_count = int(row[0]) if row and row[0] is not None else 0

        # 409 по контракту: задачи уже есть и новых не создали
        if int(existing_before) > 0 and created_count == 0:
            raise_error(
                ErrorCode.PERIODS_CONFLICT_TASKS_ALREADY_GENERATED,
                extra={"period_id": int(period_id)},
            )

    return {"period_id": period_id, "created_tasks": created_count}
