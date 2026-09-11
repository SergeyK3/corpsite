"""Bounded read-only queries for PPR migration-status reporting."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

SECTIONS = {"general", "education", "training"}
MAX_PAGE_SIZE = 100
STATUS_LABELS = {
    "NOT_STARTED": "Не начато", "PROCESSING": "Обрабатывается",
    "AUTO_READY": "Готово к согласованию", "REVIEW_REQUIRED": "Требуется ручная проверка",
    "CORRECTED_BY_HR": "Исправлено кадровиком, требуется перепроверка",
    "ACCEPTED": "Согласовано", "NO_SOURCE_DATA": "Нет исходных данных",
    "NOT_APPLICABLE": "Не применимо", "BLOCKED": "Заблокировано",
    "STALE": "Требуется обновление", "ERROR": "Ошибка обработки",
}
REASON_LABELS = {
    "RUN_NO_SECTION_RESULT": "Для раздела ещё нет результата обработки.",
    "RUN_PREVIEW_READY": "Автоматический результат готов к согласованию.",
    "RUN_PARTICIPANT_ACCEPTED": "Результат сотрудника подтверждён.",
    "FINGERPRINT_SOURCE_CHANGED": "Изменились исходные сведения.",
    "FINGERPRINT_POLICY_CHANGED": "Изменились правила обработки.",
    "BINDING_EMPLOYEE_LINK_STALE": "Кадровая связь сотрудника изменилась.",
}


def _scope(scope: dict[str, Any], params: dict[str, Any], alias: str = "x") -> str:
    if scope.get("privileged") or scope.get("scope_unit_ids") is None:
        return ""
    params["scope_units"] = [int(value) for value in scope.get("scope_unit_ids", [])]
    return f" AND {alias}.org_unit_id=ANY(:scope_units)"


def list_universes(connection: Connection, scope: dict[str, Any]) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    scope_sql = _scope(scope, params)
    rows = connection.execute(text(f"""
        SELECT u.universe_id, u.base_cohort_run_id, max(x.calculated_at) AS calculated_at,
               array_agg(DISTINCT uc.stage0_cohort_run_id) AS cohorts
        FROM ppr_migration_status_universes u
        JOIN ppr_migration_status_universe_cohorts uc USING(universe_id)
        JOIN ppr_migration_section_status_projection x USING(universe_id)
        WHERE true {scope_sql}
        GROUP BY u.universe_id, u.base_cohort_run_id
        ORDER BY max(x.calculated_at) DESC, u.universe_id DESC
    """), params).mappings()
    return [{
        "universe_id": int(row["universe_id"]),
        "base_cohort_run_id": int(row["base_cohort_run_id"]),
        "supplemental_cohort_run_ids": [int(value) for value in row["cohorts"] if int(value) != int(row["base_cohort_run_id"])],
        "calculated_at": row["calculated_at"],
    } for row in rows]


def matrix(connection: Connection, *, universe_id: int, scope: dict[str, Any], page: int,
           page_size: int, section: str | None, status: str | None,
           reason: str | None, org_unit_id: int | None, q: str | None) -> dict[str, Any] | None:
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE or (section and section not in SECTIONS):
        raise ValueError("invalid report filter")
    params: dict[str, Any] = {"universe_id": universe_id, "limit": page_size, "offset": (page - 1) * page_size}
    base_where = "x.universe_id=:universe_id" + _scope(scope, params)
    # Only a visible row proves the universe exists for this caller. This keeps
    # unknown and inaccessible universes indistinguishable.
    if connection.execute(text(f"SELECT 1 FROM ppr_migration_section_status_projection x WHERE {base_where} LIMIT 1"), params).scalar_one_or_none() is None:
        return None

    filter_parts = ["true"]
    for name, value, column in (("section", section, "section_code"), ("status", status, "status_code"),
                                ("reason", reason, "reason_code"), ("org_unit_id", org_unit_id, "org_unit_id")):
        if value is not None:
            params[name] = value
            filter_parts.append(f"{column}=:{name}")
    if q and q.strip():
        params["q"] = f"%{q.strip()}%"
        filter_parts.append("full_name ILIKE :q")
    cte = f"""
        WITH base AS (
          SELECT x.*, p.full_name
          FROM ppr_migration_section_status_projection x
          JOIN persons p ON p.person_id=x.person_id
          WHERE {base_where}
        ), matched AS (
          SELECT DISTINCT person_id FROM base WHERE {' AND '.join(filter_parts)}
        ), visible AS (
          SELECT base.* FROM base JOIN matched USING(person_id)
        )
    """
    rows = connection.execute(text(cte + """
        SELECT person_id, min(employee_context_id) AS employee_context_id, min(org_unit_id) AS org_unit_id,
               min(full_name) AS full_name,
               jsonb_object_agg(section_code, jsonb_build_object(
                   'status_code', status_code, 'reason_code', reason_code, 'calculated_at', calculated_at,
                   'stage_run_id', stage_run_id, 'stage1_run_id', stage1_run_id,
                   'stage_participant_id', stage_participant_id, 'stage1_participant_id', stage1_participant_id,
                   'pmf_run_id', pmf_run_id)) AS cells
        FROM visible GROUP BY person_id ORDER BY min(full_name), person_id LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    counts = connection.execute(text(cte + "SELECT section_code,status_code,count(*) AS n FROM visible GROUP BY section_code,status_code"), params).mappings().all()
    total = connection.execute(text(cte + "SELECT count(DISTINCT person_id) FROM visible"), params).scalar_one()

    def cell(value: dict[str, Any]) -> dict[str, Any]:
        return {**value, "status_label": STATUS_LABELS.get(value["status_code"], "Статус"),
                "reason_label": REASON_LABELS.get(value["reason_code"], "Требуется проверка.")}

    return {"universe_id": universe_id, "page": page, "page_size": page_size, "total": int(total),
            "items": [{"person_id": int(row["person_id"]), "employee_context_id": int(row["employee_context_id"]),
                       "org_unit_id": row["org_unit_id"], "full_name": row["full_name"],
                       "cells": {key: cell(value) for key, value in dict(row["cells"]).items()}}
                      for row in rows],
            "counts": [{"section_code": row["section_code"], "status_code": row["status_code"],
                        "status_label": STATUS_LABELS.get(row["status_code"], "Статус"), "count": int(row["n"])}
                       for row in counts]}


def person_cells(connection: Connection, *, universe_id: int, person_id: int, scope: dict[str, Any]) -> dict[str, Any] | None:
    """Safe, bounded card slice; deliberately contains no identity or fingerprints."""
    params: dict[str, Any] = {"universe_id": universe_id, "person_id": person_id}
    where = "x.universe_id=:universe_id AND x.person_id=:person_id" + _scope(scope, params)
    rows = connection.execute(text(f"""
        SELECT section_code,status_code,reason_code,calculated_at,stage_run_id,stage1_run_id,
               stage_participant_id,stage1_participant_id,pmf_run_id
        FROM ppr_migration_section_status_projection x WHERE {where}
        ORDER BY section_code
    """), params).mappings().all()
    if not rows:
        return None
    def safe(row: dict[str, Any]) -> dict[str, Any]:
        return {"status_code": row["status_code"], "status_label": STATUS_LABELS.get(row["status_code"], "Статус"),
                "reason_code": row["reason_code"], "reason_label": REASON_LABELS.get(row["reason_code"], "Требуется проверка."),
                "calculated_at": row["calculated_at"], "stage_run_id": row["stage_run_id"], "stage1_run_id": row["stage1_run_id"],
                "stage_participant_id": row["stage_participant_id"], "stage1_participant_id": row["stage1_participant_id"], "pmf_run_id": row["pmf_run_id"]}
    return {"universe_id": universe_id, "cells": {row["section_code"]: safe(row) for row in rows}}
