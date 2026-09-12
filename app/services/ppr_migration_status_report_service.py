"""Bounded read-only queries for PPR migration-status reporting."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.db.models.ppr_migration_status_projection import PPR_MIGRATION_SECTIONS

SECTIONS = PPR_MIGRATION_SECTIONS
SECTION_SET = frozenset(SECTIONS)
SECTION_ORDER_SQL = "ARRAY[" + ",".join(repr(section) for section in SECTIONS) + "]::text[]"
MAX_PAGE_SIZE = 100


class ProjectionIntegrityError(RuntimeError):
    """A visible person lacks one required persisted full-catalog cell."""
STATUS_LABELS = {
    "NOT_STARTED": "Не начато", "PROCESSING": "Обрабатывается",
    "AUTO_READY": "Готово к согласованию", "REVIEW_REQUIRED": "Требуется ручная проверка",
    "CORRECTED_BY_HR": "Исправлено кадровиком, требуется перепроверка",
    "ACCEPTED": "Согласовано", "NO_SOURCE_DATA": "Нет исходных данных",
    "NOT_APPLICABLE": "Не применимо", "BLOCKED": "Заблокировано",
    "STALE": "Требуется обновление", "ERROR": "Ошибка обработки",
    "REJECTED": "Отклонено",
}
REASON_LABELS = {
    "RUN_NO_SECTION_RESULT": "Для раздела ещё нет результата обработки.",
    "RUN_PREVIEW_READY": "Автоматический результат готов к согласованию.",
    "RUN_PARTICIPANT_ACCEPTED": "Результат сотрудника подтверждён.",
    "FINGERPRINT_SOURCE_CHANGED": "Изменились исходные сведения.",
    "FINGERPRINT_POLICY_CHANGED": "Изменились правила обработки.",
    "BINDING_EMPLOYEE_LINK_STALE": "Кадровая связь сотрудника изменилась.",
    "SECTION_PROCESSING_NOT_CONNECTED": "Обработка раздела ещё не подключена.",
    "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED": "Найдены импортированные записи раздела; требуется ручная проверка.",
    "IMPORT_NORMALIZED_RECORDS_AUTO_READY": "Все импортированные записи раздела однозначно распознаны и готовы к согласованию.",
    "IMPORT_NORMALIZED_RECORDS_REVIEWED": "Все активные импортированные записи раздела проверены.",
    "IMPORT_NORMALIZED_RECORDS_REJECTED": "Есть отклонённые импортированные записи раздела.",
    "IMPORT_RAW_SECTION_REVIEW_REQUIRED": "Есть исходные импортированные сведения; требуется содержательная проверка.",
    "NOTE_REQUIRES_MANUAL_REVIEW": "Примечание содержит неполные или нераспознанные сведения и требует ручной проверки.",
    "STATUS_DATE_MISSING": "В примечании отсутствует дата наступления статуса.",
    "DISABILITY_GROUP_MISSING": "В примечании не указана группа инвалидности.",
    "DISABILITY_ICD10_MISSING": "В примечании не указан код МКБ-10.",
    "POLICY_SECTION_NOT_APPLICABLE": "Раздел не применяется.",
}

# A single presentation catalog is shared by the persisted projection and the
# local fallback.  The technical status model deliberately remains intact;
# this only groups it into stable, readable report rows.
PRESENTATION_SECTIONS: tuple[dict[str, Any], ...] = (
    {"code": "general", "title": "Общие сведения", "order": 10},
    {"code": "education", "title": "Образование", "order": 20},
    {"code": "training", "title": "Обучение и повышение квалификации", "order": 30},
    {"code": "relatives", "title": "Родственники", "order": 40},
    {"code": "military", "title": "Воинский учёт", "order": 50},
    {"code": "foreign_languages", "title": "Знание иностранных языков", "order": 60},
    {"code": "additional", "title": "Дополнительные сведения", "order": 70},
    {"code": "employment_biography", "title": "Трудовая биография", "order": 80},
    {"code": "employment_history", "title": "Трудовая деятельность", "order": 90},
    {"code": "personnel_orders", "title": "Кадровые приказы", "order": 100},
    {"code": "personnel_appeals", "title": "Кадровые обращения", "order": 110},
    {"code": "adaptation", "title": "Адаптация", "order": 120},
    {"code": "awards", "title": "Награды и звания", "order": 130},
    {"code": "academic_degrees_titles", "title": "Учёные степени и звания", "order": 140},
)
PRESENTATION_STATUS_ROWS: tuple[dict[str, Any], ...] = (
    {"code": "AUTO_READY", "title": "Готово к согласованию / обработано автоматически", "order": 10},
    {"code": "REVIEW_REQUIRED", "title": "Требуется ручная проверка", "order": 20},
    {"code": "ACCEPTED", "title": "Проверено", "order": 30},
    {"code": "REJECTED", "title": "Отклонено", "order": 40},
    {"code": "STALE", "title": "Данные устарели", "order": 50},
    {"code": "NO_SOURCE_DATA", "title": "Нет данных или не обработано", "order": 60},
)


def presentation_status_code(status_code: str | None) -> str:
    """Map technical states to the one user-facing report catalog."""
    value = str(status_code or "NO_SOURCE_DATA")
    if value == "AUTO_READY":
        return "AUTO_READY"
    if value in {"REVIEW_REQUIRED", "CORRECTED_BY_HR", "PROCESSING", "BLOCKED", "ERROR"}:
        return "REVIEW_REQUIRED"
    if value == "ACCEPTED":
        return "ACCEPTED"
    if value in {"REJECTED", "DECLINED"}:
        return "REJECTED"
    if value == "STALE":
        return "STALE"
    return "NO_SOURCE_DATA"


def build_presentation_status_summary(
    items: list[dict[str, Any]], *, section: str | None = None
) -> dict[str, Any]:
    """Server-side full-set aggregate; never depends on page-sized rows."""
    sections = [entry for entry in PRESENTATION_SECTIONS if section in (None, entry["code"])]
    counts = {
        (entry["code"], status["code"]): 0
        for entry in sections
        for status in PRESENTATION_STATUS_ROWS
    }
    for item in items:
        cells = dict(item.get("cells") or {})
        for entry in sections:
            code = entry["code"]
            raw_status = (cells.get(code) or {}).get("status_code")
            counts[(code, presentation_status_code(raw_status))] += 1
    return {
        "sections": sections,
        "statuses": list(PRESENTATION_STATUS_ROWS),
        "counts": [
            {"section_code": entry["code"], "status_code": status["code"], "count": counts[(entry["code"], status["code"])]}
            for status in PRESENTATION_STATUS_ROWS
            for entry in sections
        ],
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
           reason: str | None, org_unit_id: int | None, q: str | None,
           org_group_id: int | None = None, position_id: int | None = None) -> dict[str, Any] | None:
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE or (section and section not in SECTION_SET):
        raise ValueError("invalid report filter")
    params: dict[str, Any] = {"universe_id": universe_id, "limit": page_size, "offset": (page - 1) * page_size}
    base_where = "x.universe_id=:universe_id" + _scope(scope, params)
    # Only a visible row proves the universe exists for this caller. This keeps
    # unknown and inaccessible universes indistinguishable.
    if connection.execute(text(f"SELECT 1 FROM ppr_migration_section_status_projection x WHERE {base_where} LIMIT 1"), params).scalar_one_or_none() is None:
        return None
    broken_person = connection.execute(text(f"""
        SELECT x.person_id
        FROM ppr_migration_section_status_projection x
        WHERE {base_where}
        GROUP BY x.person_id
        HAVING count(DISTINCT x.section_code) <> :expected_sections
        LIMIT 1
    """), {**params, "expected_sections": len(SECTIONS)}).scalar_one_or_none()
    if broken_person is not None:
        raise ProjectionIntegrityError("required persisted section cell is missing")

    filter_parts = ["true"]
    for name, value, column in (("section", section, "section_code"), ("status", status, "status_code"),
                                ("reason", reason, "reason_code"), ("org_unit_id", org_unit_id, "org_unit_id"),
                                ("org_group_id", org_group_id, "org_group_id"), ("position_id", position_id, "position_id")):
        if value is not None:
            params[name] = value
            filter_parts.append(f"{column}=:{name}")
    if q and q.strip():
        params["q"] = f"%{q.strip()}%"
        filter_parts.append("full_name ILIKE :q")
    cte = f"""
        WITH base AS (
          SELECT x.*, p.full_name, ou.group_id AS org_group_id,
                 assignment.position_id
          FROM ppr_migration_section_status_projection x
          JOIN persons p ON p.person_id=x.person_id
          LEFT JOIN LATERAL (
            SELECT pa.position_id
            FROM person_assignments pa
            WHERE pa.person_id=x.person_id AND pa.active_flag IS TRUE
              AND pa.is_primary IS TRUE AND pa.lifecycle_status='active'
              AND pa.start_date <= CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
            ORDER BY pa.start_date DESC, pa.assignment_id DESC LIMIT 1
          ) assignment ON TRUE
          LEFT JOIN org_units ou ON ou.unit_id=x.org_unit_id
          WHERE {base_where}
        ), matched AS (
          SELECT DISTINCT person_id FROM base WHERE {' AND '.join(filter_parts)}
        ), visible AS (
          SELECT base.* FROM base JOIN matched USING(person_id)
        )
    """
    rows = connection.execute(text(cte + """
        SELECT person_id, min(employee_context_id) AS employee_context_id, min(org_unit_id) AS org_unit_id,
               min(org_group_id) AS org_group_id, min(position_id) AS position_id, min(full_name) AS full_name,
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

    def ordered_cells(values: dict[str, Any]) -> dict[str, Any]:
        if set(values) != SECTION_SET:
            raise ProjectionIntegrityError("required persisted section cell is missing")
        return {section_code: cell(values[section_code]) for section_code in SECTIONS}

    items = [{"person_id": int(row["person_id"]), "employee_context_id": int(row["employee_context_id"]),
              "org_unit_id": row["org_unit_id"], "org_group_id": row["org_group_id"], "position_id": row["position_id"], "full_name": row["full_name"],
              "cells": ordered_cells(dict(row["cells"]))}
             for row in rows]
    aggregate_rows = connection.execute(text(cte + """
        SELECT person_id, min(employee_context_id) AS employee_context_id,
               min(org_unit_id) AS org_unit_id, min(org_group_id) AS org_group_id,
               min(position_id) AS position_id, min(full_name) AS full_name,
               jsonb_object_agg(section_code, jsonb_build_object(
                   'status_code', status_code, 'reason_code', reason_code,
                   'calculated_at', calculated_at)) AS cells
        FROM visible GROUP BY person_id
    """), params).mappings().all()
    aggregate_items = [{"person_id": int(row["person_id"]), "employee_context_id": int(row["employee_context_id"]),
                        "org_unit_id": row["org_unit_id"], "org_group_id": row["org_group_id"], "position_id": row["position_id"], "full_name": row["full_name"],
                        "cells": ordered_cells(dict(row["cells"]))}
                       for row in aggregate_rows]
    return {"universe_id": universe_id, "page": page, "page_size": page_size, "total": int(total),
            "items": items,
            "counts": [{"section_code": row["section_code"], "status_code": row["status_code"],
                        "status_label": STATUS_LABELS.get(row["status_code"], "Статус"), "count": int(row["n"])}
                       for row in sorted(counts, key=lambda row: (SECTIONS.index(row["section_code"]), row["status_code"]))],
            "status_summary": build_presentation_status_summary(aggregate_items, section=section)}


def person_cells(connection: Connection, *, universe_id: int, person_id: int, scope: dict[str, Any]) -> dict[str, Any] | None:
    """Safe, bounded card slice; deliberately contains no identity or fingerprints."""
    params: dict[str, Any] = {"universe_id": universe_id, "person_id": person_id}
    where = "x.universe_id=:universe_id AND x.person_id=:person_id" + _scope(scope, params)
    rows = connection.execute(text(f"""
        SELECT section_code,status_code,reason_code,calculated_at,stage_run_id,stage1_run_id,
               stage_participant_id,stage1_participant_id,pmf_run_id
        FROM ppr_migration_section_status_projection x WHERE {where}
        ORDER BY array_position({SECTION_ORDER_SQL}, section_code)
    """), params).mappings().all()
    if not rows:
        return None
    def safe(row: dict[str, Any]) -> dict[str, Any]:
        return {"status_code": row["status_code"], "status_label": STATUS_LABELS.get(row["status_code"], "Статус"),
                "reason_code": row["reason_code"], "reason_label": REASON_LABELS.get(row["reason_code"], "Требуется проверка."),
                "calculated_at": row["calculated_at"], "stage_run_id": row["stage_run_id"], "stage1_run_id": row["stage1_run_id"],
                "stage_participant_id": row["stage_participant_id"], "stage1_participant_id": row["stage1_participant_id"], "pmf_run_id": row["pmf_run_id"]}
    raw = {row["section_code"]: row for row in rows}
    if set(raw) != SECTION_SET:
        raise ProjectionIntegrityError("required persisted section cell is missing")
    return {"universe_id": universe_id, "cells": {section_code: safe(raw[section_code]) for section_code in SECTIONS}}
