"""Stateless XLSX formatter, not a data retrieval endpoint.

Clients fetch every page through the original table APIs, which enforce their
own read permissions. No database reads or writes occur here.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from app.auth import get_current_user
from app.services.table_export import build_table_workbook

router = APIRouter()
Cell = StrictStr | StrictInt | StrictFloat | StrictBool | None


class TableExport(BaseModel):
    headers: Annotated[list[str], Field(min_length=1, max_length=100)]
    rows: Annotated[list[list[Cell]], Field(max_length=1048575)]

    @model_validator(mode="after")
    def check_columns(self):
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Количество столбцов должно совпадать с заголовками")
        return self


@router.post("/exports/table.xlsx")
def export_table(body: TableExport, user=Depends(get_current_user)) -> Response:
    if not body.rows:
        raise HTTPException(404, "Нет записей для выгрузки по текущим фильтрам.")
    return Response(
        build_table_workbook(body.headers, body.rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="export.xlsx"', "Cache-Control": "no-store"},
    )
