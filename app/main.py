# app/main.py
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# -----------------------
# Env (single source of truth)
# -----------------------
# app/main.py находится в .../09 Corpsite/app/main.py
# корневой .env лежит в .../09 Corpsite/.env
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

from datetime import date
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.engine import engine
from app.meta import router as meta_router
from app.tasks import router as tasks_router
from .tg_bind import router as tg_bind_router


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="Corpsite MVP", default_response_class=UTF8JSONResponse)
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


class SubmitReportRequest(BaseModel):
    submitted_by: int
    report_link: str = Field(..., min_length=1, max_length=2000)
    current_comment: Optional[str] = None


class ApproveReportRequest(BaseModel):
    approved_by: int
    approve: bool = True
    current_comment: Optional[str] = None


# -----------------------
# Helpers
# -----------------------

def get_status_id(code: str) -> int:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status_id FROM task_statuses WHERE code = :code"),
            {"code": code},
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=400,
            detail=f"Missing task_statuses.code='{code}' (seed task_statuses first).",
        )
    return int(row[0])


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

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO reporting_periods (kind, date_start, date_end, label)
                VALUES ('MONTH', :ds, :de, :label)
                RETURNING period_id, kind, date_start, date_end, label, is_closed
            """),
            {"ds": payload.date_start, "de": payload.date_end, "label": payload.label},
        ).fetchone()

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
        row = conn.execute(
            text("SELECT generate_monthly_tasks(:pid, :initiator)"),
            {"pid": period_id, "initiator": payload.initiator_user_id},
        ).fetchone()

    created_count = int(row[0]) if row and row[0] is not None else 0
    return {"period_id": period_id, "created_tasks": created_count}


# -----------------------
# (3) Reports: submit and approve
# -----------------------

@app.post("/tasks/{task_id}/report")
def submit_report(task_id: int, payload: SubmitReportRequest) -> Dict[str, Any]:
    waiting_approval = get_status_id("WAITING_APPROVAL")

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM tasks WHERE task_id = :tid"),
            {"tid": task_id},
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Task not found")

        conn.execute(
            text("""
                INSERT INTO task_reports (task_id, report_link, submitted_at, submitted_by, current_comment)
                VALUES (:tid, :link, now(), :by, :comment)
                ON CONFLICT (task_id)
                DO UPDATE SET
                    report_link = EXCLUDED.report_link,
                    submitted_at = now(),
                    submitted_by = EXCLUDED.submitted_by,
                    approved_at = NULL,
                    approved_by = NULL,
                    current_comment = EXCLUDED.current_comment
            """),
            {
                "tid": task_id,
                "link": payload.report_link,
                "by": payload.submitted_by,
                "comment": payload.current_comment,
            },
        )

        conn.execute(
            text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
            {"sid": waiting_approval, "tid": task_id},
        )

        conn.execute(
            text("""
                INSERT INTO audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
                VALUES (:actor, 'task_reports', :eid, 'SUBMIT_REPORT', NULL, NULL)
            """),
            {"actor": payload.submitted_by, "eid": task_id},
        )

    return {"task_id": task_id, "status": "reported"}


@app.post("/tasks/{task_id}/approve")
def approve_report(task_id: int, payload: ApproveReportRequest) -> Dict[str, Any]:
    done_id = get_status_id("DONE")
    waiting_report = get_status_id("WAITING_REPORT")

    with engine.begin() as conn:
        rep = conn.execute(
            text("SELECT report_id FROM task_reports WHERE task_id = :tid"),
            {"tid": task_id},
        ).fetchone()
        if not rep:
            raise HTTPException(status_code=400, detail="No report submitted for this task")

        if payload.approve:
            conn.execute(
                text("""
                    UPDATE task_reports
                    SET approved_at = now(),
                        approved_by = :by,
                        current_comment = COALESCE(:comment, current_comment)
                    WHERE task_id = :tid
                """),
                {"by": payload.approved_by, "tid": task_id, "comment": payload.current_comment},
            )

            conn.execute(
                text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
                {"sid": done_id, "tid": task_id},
            )

            conn.execute(
                text("""
                    INSERT INTO audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
                    VALUES (:actor, 'task_reports', :eid, 'APPROVE_REPORT', NULL, NULL)
                """),
                {"actor": payload.approved_by, "eid": task_id},
            )
            return {"task_id": task_id, "status": "approved_done"}

        conn.execute(
            text("""
                UPDATE task_reports
                SET approved_at = NULL,
                    approved_by = NULL,
                    current_comment = COALESCE(:comment, current_comment)
                WHERE task_id = :tid
            """),
            {"tid": task_id, "comment": payload.current_comment},
        )

        conn.execute(
            text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
            {"sid": waiting_report, "tid": task_id},
        )

        conn.execute(
            text("""
                INSERT INTO audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
                VALUES (:actor, 'task_reports', :eid, 'RETURN_REPORT', NULL, NULL)
            """),
            {"actor": payload.approved_by, "eid": task_id},
        )

    return {"task_id": task_id, "status": "returned_for_rework"}
