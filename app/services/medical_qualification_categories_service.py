"""Read-only directory of the four medical qualification categories."""
from sqlalchemy import text
from app.db.engine import engine


def list_categories(*, q=None):
    params = {}
    where = ""
    if q and q.strip():
        where = " WHERE name ILIKE :q ESCAPE '\\' OR name_kk ILIKE :q ESCAPE '\\'"
        params["q"] = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT qualification_category_id, code, name, name_kk "
            "FROM public.medical_qualification_categories" + where + " ORDER BY code"
        ), params).mappings().all()
    return {"items": [dict(row) for row in rows], "total": len(rows)}
