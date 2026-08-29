from __future__ import annotations

from typing import Any

import pytest

from app.services import directory_service
from app.services.personnel_position_ordering import (
    RANK_ADMIN_CLERICAL,
    RANK_ADMIN_DEPUTY,
    RANK_ADMIN_LEADER,
    RANK_ADMIN_OTHER,
    RANK_ADMIN_SERVICE,
    RANK_ADMIN_SENIOR_SPECIALIST,
    RANK_ADMIN_SPECIALIST,
    RANK_ADMIN_TECHNICAL,
    RANK_OTHER,
    normalize_position_name,
    personnel_position_rank,
    personnel_position_rank_sql,
    personnel_position_sort_key,
)


@pytest.mark.parametrize("group_id", [1, 2])
def test_medical_groups_use_canonical_seven_rank_hierarchy(group_id: int) -> None:
    positions = [
        ("Неизвестная должность", None),
        ("Санитар", None),
        ("Сестра-хозяйка", None),
        ("Медицинская сестра", None),
        ("Старшая медицинская сестра", None),
        ("Врач-терапевт", None),
        ("Врач — заведующий отделением", None),
    ]

    ranked = sorted(
        positions,
        key=lambda item: personnel_position_rank(
            group_id=group_id,
            position_name=item[0],
            position_category=item[1],
        ),
    )

    assert [name for name, _ in ranked] == list(reversed([name for name, _ in positions]))


def test_specific_position_checks_precede_general_checks_and_normalize_variants() -> None:
    assert normalize_position_name("  СТАРШАЯ-МЕДИЦИНСКАЯ  СЕСТРА, ёлка ") == (
        "старшая медицинская сестра елка"
    )
    assert personnel_position_rank(
        group_id=1,
        position_name="Врач — заведующий отделением",
        position_category=None,
    ) == 0
    assert personnel_position_rank(
        group_id=1,
        position_name="Старшая медицинская сестра",
        position_category=None,
    ) == 2
    assert personnel_position_rank(
        group_id=1,
        position_name="Сестра-хозяйка",
        position_category=None,
    ) == 4


@pytest.mark.parametrize(
    ("position_name", "category", "expected_rank"),
    [
        ("Руководитель отдела", "leaders", RANK_ADMIN_LEADER),
        ("Главный бухгалтер", "admin", RANK_ADMIN_LEADER),
        ("Заведующая прачечной", "leaders", RANK_ADMIN_LEADER),
        ("Заместитель руководителя", "leaders", RANK_ADMIN_DEPUTY),
        ("зам рук-ля отдела статистики", "leaders", RANK_ADMIN_DEPUTY),
        ("Зам по административным вопросам", "leaders", RANK_ADMIN_DEPUTY),
        ("Главный специалист", "admin", RANK_ADMIN_SENIOR_SPECIALIST),
        ("Ведущий специалист", "admin", RANK_ADMIN_SENIOR_SPECIALIST),
        ("Старший менеджер", "admin", RANK_ADMIN_SENIOR_SPECIALIST),
        ("Менеджер", "admin", RANK_ADMIN_SPECIALIST),
        ("Бухгалтер-кассир", "admin", RANK_ADMIN_SPECIALIST),
        ("экономист1", "admin", RANK_ADMIN_SPECIALIST),
        ("Аналитик ЭРОБ", "admin", RANK_ADMIN_SPECIALIST),
        ("Переводчик казахского языка", "admin", RANK_ADMIN_SPECIALIST),
        ("Секретарь-референт", "admin", RANK_ADMIN_CLERICAL),
        ("Архивариус", "admin", RANK_ADMIN_CLERICAL),
        ("Техник", "technical", RANK_ADMIN_TECHNICAL),
        ("Водитель", "technical", RANK_ADMIN_TECHNICAL),
        ("Уборщик помещений", "service", RANK_ADMIN_SERVICE),
        ("Санитар", "medical", RANK_ADMIN_SERVICE),
        ("Неизвестная должность", "other", RANK_ADMIN_OTHER),
    ],
)
def test_administrative_eight_rank_hierarchy(
    position_name: str, category: str, expected_rank: int
) -> None:
    assert personnel_position_rank(
        group_id=3,
        position_name=position_name,
        position_category=category,
    ) == expected_rank


def test_missing_assignment_fallback_depends_on_effective_displayed_position() -> None:
    assert personnel_position_rank(
        group_id=1, position_name="Неизвестная должность", position_category=None
    ) == RANK_OTHER
    assert personnel_position_rank(
        group_id=3,
        position_name="Руководитель",
        position_category="leaders",
        has_current_assignment=False,
    ) == RANK_ADMIN_LEADER
    assert personnel_position_rank(
        group_id=3,
        position_name="Менеджер",
        position_category="admin",
        has_current_assignment=False,
    ) == RANK_ADMIN_SPECIALIST
    assert personnel_position_rank(
        group_id=3,
        position_name="Секретарь-референт",
        position_category="admin",
        has_current_assignment=False,
    ) == RANK_ADMIN_CLERICAL
    assert personnel_position_rank(
        group_id=3,
        position_name=None,
        position_category=None,
        has_current_assignment=False,
    ) == RANK_ADMIN_OTHER
    assert personnel_position_rank(
        group_id=1,
        position_name="Врач",
        position_category="medical",
        has_current_assignment=False,
    ) == RANK_OTHER


def test_administrative_same_rank_orders_by_fio_then_employee_id() -> None:
    rows = [
        (10, "Борисов", "Менеджер"),
        (20, "Антонов", "Экономист"),
        (3, "Антонов", "Юрист"),
    ]
    ordered = sorted(
        rows,
        key=lambda row: personnel_position_sort_key(
            group_id=3,
            position_name=row[2],
            position_category="admin",
            full_name=row[1],
            employee_id=row[0],
        ),
    )
    assert [row[0] for row in ordered] == [3, 20, 10]


def test_same_rank_orders_by_fio_then_numeric_employee_id() -> None:
    rows = [
        (10, "Борисов", "Врач"),
        (20, "Антонов", "Врач"),
        (3, "Антонов", "Врач"),
    ]

    ordered = sorted(
        rows,
        key=lambda row: personnel_position_sort_key(
            group_id=1,
            position_name=row[2],
            position_category=None,
            full_name=row[1],
            employee_id=row[0],
        ),
    )

    assert [row[0] for row in ordered] == [3, 20, 10]


def test_department_head_cannot_move_to_second_page_due_to_alphabetical_name() -> None:
    rows = [
        (1, "Абдулов Врач", "Врач"),
        (2, "Беков Врач", "Врач"),
        (3, "Яковлев Заведующий", "Заведующий отделением"),
    ]
    ordered = sorted(
        rows,
        key=lambda row: personnel_position_sort_key(
            group_id=1,
            position_name=row[2],
            position_category=None,
            full_name=row[1],
            employee_id=row[0],
        ),
    )

    first_page = ordered[:2]
    assert first_page[0][0] == 3
    assert all(row[2] != "Заведующий отделением" for row in ordered[2:])


def test_multiple_departments_form_business_ordered_blocks() -> None:
    rows = [
        (2, "Бета", 1, "Абдулов", "Врач"),
        (1, "Альфа", 4, "Яковлев", "Врач — заведующий отделением"),
        (1, "Альфа", 3, "Абдулов", "Санитар"),
        (2, "Бета", 2, "Яковлев", "Врач — заведующий отделением"),
    ]

    ordered = sorted(
        rows,
        key=lambda row: (
            row[0],
            row[1].casefold(),
            *personnel_position_sort_key(
                group_id=row[0],
                position_name=row[4],
                position_category=None,
                full_name=row[3],
                employee_id=row[2],
            ),
        ),
    )

    assert [(row[1], row[4]) for row in ordered] == [
        ("Альфа", "Врач — заведующий отделением"),
        ("Альфа", "Санитар"),
        ("Бета", "Врач — заведующий отделением"),
        ("Бета", "Врач"),
    ]


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self.rows)


class _Connection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []

    def execute(self, statement: Any, params: dict[str, Any]) -> _Result:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(dict(params))
        return _Result([{"cnt": 7}]) if "COUNT(*)" in sql else _Result([])


class _Begin:
    def __init__(self, conn: _Connection) -> None:
        self.conn = conn

    def __enter__(self) -> _Connection:
        return self.conn

    def __exit__(self, *_: Any) -> None:
        return None


class _Engine:
    def __init__(self) -> None:
        self.connection = _Connection()

    def begin(self) -> _Begin:
        return _Begin(self.connection)


def test_directory_sql_ranks_after_filters_and_before_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = _Engine()
    columns = [
        "employee_id",
        "person_id",
        "full_name",
        "org_unit_id",
        "position_id",
        "is_active",
    ]
    monkeypatch.setattr(directory_service, "engine", fake_engine)
    monkeypatch.setattr(directory_service, "_employees_relation", lambda: ("employees", columns))
    monkeypatch.setattr(
        directory_service,
        "_employee_select_sql",
        lambda *_: (
            "SELECT e.employee_id AS e_id FROM public.employees e "
            "LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id "
            "LEFT JOIN public.positions p ON p.position_id = e.position_id",
            {
                "position_expr": "p.name",
                "position_id_expr": "e.position_id",
                "position_category_expr": "p.category",
                "has_current_assignment_expr": "FALSE",
                "department_expr": "ou.name",
                "rate_col": None,
                "status_col": "is_active",
            },
        ),
    )
    monkeypatch.setattr(directory_service, "build_dept_scope_cte", lambda **_: ("", "TRUE", {}))

    result = directory_service.list_employees(
        status="active",
        q="Иванов",
        department_id=None,
        position_id=12,
        limit=2,
        offset=2,
        sort=None,
        order=None,
    )

    list_sql = next(sql for sql in fake_engine.connection.statements if "COUNT(*)" not in sql)
    assert result == {"items": [], "total": 7}
    assert "LOWER(CAST(e.full_name AS TEXT)) LIKE :q" in list_sql
    assert "CAST(e.position_id AS TEXT) = :position_id_text" in list_sql
    assert "p.category" in list_sql
    assert "ou.group_id IN (1, 2) AND NOT (FALSE)" in list_sql
    assert list_sql.index("WHERE") < list_sql.index("ORDER BY") < list_sql.index("LIMIT")
    assert fake_engine.connection.params[-1]["limit"] == 2
    assert fake_engine.connection.params[-1]["offset"] == 2


def test_sql_rank_expression_matches_shared_categories() -> None:
    sql = personnel_position_rank_sql(
        group_id_expr="ou.group_id",
        position_name_expr="p.name",
        position_category_expr="p.category",
        has_current_assignment_expr="has_assignment",
    )

    assert "ou.group_id IN (1, 2) AND NOT (has_assignment)" in sql
    assert sql.index("заместител") < sql.index("руководител")
    assert sql.index("главн") < sql.index("менеджер")
    assert sql.index("менеджер") < sql.index("секретар")
    assert sql.index("секретар") < sql.index("техник")
    assert sql.index("техник") < sql.index("уборщ")
    assert sql.index("заведующ") < sql.index("врач")
    assert sql.index("старш") < sql.index("медсестр")
    assert "WHEN p.category" not in sql  # category is normalized, not compared raw
