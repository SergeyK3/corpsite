from fastapi import APIRouter
from sqlalchemy import text
from app.db.engine import engine 

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/task-statuses")
def get_task_statuses():
    sql = """
    SELECT code, name_ru, sort_order
    FROM task_statuses
    ORDER BY sort_order;
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()
    return {"items": list(rows)}
