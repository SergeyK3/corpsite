"""Single source of truth for dependencies that block Position deletion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection


_BLOCKING_DELETE_ACTIONS = {"a", "r"}  # PostgreSQL NO ACTION / RESTRICT

_ALLOWED_POSITION_FK_POLICY_IDENTITY = (
    "public",
    "org_unit_allowed_positions",
    "position_id",
    "org_unit_allowed_positions_position_id_fkey",
)

_DEPENDENCY_LABELS = {
    "employee_events.from_position_id": "Кадровые события: прежняя должность",
    "employee_events.to_position_id": "Кадровые события: новая должность",
    "employees.position_id": "Сотрудники и исторические назначения",
    "incoming_documents.addressee_position_id": "Входящие документы",
    "legacy_position_mapping.catalog_position_id": "Исторические соответствия должностей",
    "org_unique_position.catalog_position_id": "Штатные позиции",
    "org_unit_allowed_positions.position_id": "Разрешённые должности подразделений",
    "permission_template_contour_rule.catalog_position_id": "Шаблоны полномочий",
    "person_assignments.position_id": "Назначения сотрудников",
    "personnel_applications.intended_position_id": "Заявления кандидатов",
}


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


@dataclass(frozen=True)
class PositionForeignKeyDependency:
    constraint_name: str
    table_schema: str
    table_name: str
    column_name: str
    on_delete: str

    @property
    def key(self) -> str:
        return f"{self.table_name}.{self.column_name}"

    @property
    def policy_identity(self) -> tuple[str, str, str, str]:
        return (
            self.table_schema,
            self.table_name,
            self.column_name,
            self.constraint_name,
        )

    @property
    def label(self) -> str:
        return _DEPENDENCY_LABELS.get(self.key, self.key)

    @property
    def qualified_table_sql(self) -> str:
        return (
            f"{_quote_identifier(self.table_schema)}."
            f"{_quote_identifier(self.table_name)}"
        )

    @property
    def column_sql(self) -> str:
        return _quote_identifier(self.column_name)


def build_position_dependency_blocking_predicate_sql(
    dependency: PositionForeignKeyDependency,
    *,
    table_alias: str | None = None,
) -> str:
    """Return the reviewed row-level blocker predicate for one discovered FK.

    Unknown schema/table/column/constraint identities deliberately use the
    secure default: every referencing row blocks Position deletion.
    """
    if dependency.policy_identity != _ALLOWED_POSITION_FK_POLICY_IDENTITY:
        return "TRUE"
    qualifier = f"{_quote_identifier(table_alias)}." if table_alias else ""
    return f"{qualifier}{_quote_identifier('is_active')} = TRUE"


@dataclass(frozen=True)
class AllowedPositionDependencyLink:
    org_unit_allowed_position_id: int
    org_unit_id: int
    org_unit_name: str
    is_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_unit_allowed_position_id": int(self.org_unit_allowed_position_id),
            "org_unit_id": int(self.org_unit_id),
            "org_unit_name": self.org_unit_name,
            "is_active": bool(self.is_active),
        }


@dataclass(frozen=True)
class PositionDependencyItem:
    key: str
    label: str
    table: str
    column: str
    constraint: str
    count: int
    allowed_position_links: Sequence[AllowedPositionDependencyLink] = ()

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "key": self.key,
            "label": self.label,
            "table": self.table,
            "column": self.column,
            "constraint": self.constraint,
            "count": int(self.count),
        }
        if self.allowed_position_links:
            result["allowed_position_links"] = [
                link.to_dict() for link in self.allowed_position_links
            ]
        return result


def _load_allowed_position_dependency_links(
    conn: Connection,
    *,
    position_ids: Sequence[int],
) -> Mapping[int, Sequence[AllowedPositionDependencyLink]]:
    ids = list(dict.fromkeys(int(position_id) for position_id in position_ids))
    if not ids:
        return {}

    rows = conn.execute(
        text(
            """
            SELECT
                oap.position_id,
                oap.org_unit_allowed_position_id,
                oap.org_unit_id,
                ou.name AS org_unit_name,
                oap.is_active
            FROM public.org_unit_allowed_positions oap
            JOIN public.org_units ou ON ou.unit_id = oap.org_unit_id
            WHERE oap.position_id = ANY(:position_ids)
              AND oap.is_active = TRUE
            ORDER BY oap.position_id, oap.org_unit_allowed_position_id
            """
        ),
        {"position_ids": ids},
    ).mappings().all()

    links_by_position: Dict[int, List[AllowedPositionDependencyLink]] = {
        position_id: [] for position_id in ids
    }
    for row in rows:
        links_by_position[int(row["position_id"])].append(
            AllowedPositionDependencyLink(
                org_unit_allowed_position_id=int(
                    row["org_unit_allowed_position_id"]
                ),
                org_unit_id=int(row["org_unit_id"]),
                org_unit_name=str(row["org_unit_name"] or "").strip(),
                is_active=bool(row["is_active"]),
            )
        )
    return links_by_position


@dataclass(frozen=True)
class PositionDependencySummary:
    position_id: int
    dependencies: Sequence[PositionDependencyItem]

    @property
    def total_dependencies(self) -> int:
        return sum(int(item.count) for item in self.dependencies)

    @property
    def can_delete(self) -> bool:
        return self.total_dependencies == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": int(self.position_id),
            "can_delete": self.can_delete,
            "total_dependencies": self.total_dependencies,
            "dependencies": [item.to_dict() for item in self.dependencies if item.count > 0],
        }


def load_position_blocking_foreign_keys(
    conn: Connection,
) -> List[PositionForeignKeyDependency]:
    """Read the actual PostgreSQL FK rules that can reject DELETE positions."""
    rows = conn.execute(
        text(
            """
            SELECT
                c.conname AS constraint_name,
                child_ns.nspname AS table_schema,
                child.relname AS table_name,
                child_col.attname AS column_name,
                c.confdeltype AS on_delete
            FROM pg_constraint c
            JOIN pg_class parent ON parent.oid = c.confrelid
            JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
            JOIN pg_class child ON child.oid = c.conrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            JOIN unnest(c.conkey) WITH ORDINALITY AS child_key(attnum, ord) ON TRUE
            JOIN unnest(c.confkey) WITH ORDINALITY AS parent_key(attnum, ord)
              ON parent_key.ord = child_key.ord
            JOIN pg_attribute child_col
              ON child_col.attrelid = child.oid
             AND child_col.attnum = child_key.attnum
            WHERE c.contype = 'f'
              AND parent_ns.nspname = 'public'
              AND parent.relname = 'positions'
              AND c.confdeltype IN ('a', 'r')
            ORDER BY child_ns.nspname, child.relname, c.conname, child_key.ord
            """
        )
    ).mappings().all()
    return [
        PositionForeignKeyDependency(
            constraint_name=str(row["constraint_name"]),
            table_schema=str(row["table_schema"]),
            table_name=str(row["table_name"]),
            column_name=str(row["column_name"]),
            on_delete=str(row["on_delete"]),
        )
        for row in rows
        if str(row["on_delete"]) in _BLOCKING_DELETE_ACTIONS
    ]


def build_position_blocked_exists_sql(
    dependencies: Sequence[PositionForeignKeyDependency],
    *,
    position_expression: str,
) -> str:
    checks = []
    for dependency in dependencies:
        predicate_sql = build_position_dependency_blocking_predicate_sql(
            dependency,
            table_alias="dep",
        )
        checks.append(
            f"EXISTS (SELECT 1 FROM {dependency.qualified_table_sql} dep "
            f"WHERE dep.{dependency.column_sql} = {position_expression} "
            f"AND ({predicate_sql}))"
        )
    return " OR ".join(checks) if checks else "FALSE"


def check_position_dependencies(
    conn: Connection,
    *,
    position_id: int,
    dependencies: Sequence[PositionForeignKeyDependency] | None = None,
) -> PositionDependencySummary:
    specs = list(dependencies or load_position_blocking_foreign_keys(conn))
    allowed_links_by_position: Mapping[
        int, Sequence[AllowedPositionDependencyLink]
    ] = {}
    if any(
        dependency.policy_identity == _ALLOWED_POSITION_FK_POLICY_IDENTITY
        for dependency in specs
    ):
        allowed_links_by_position = _load_allowed_position_dependency_links(
            conn,
            position_ids=[int(position_id)],
        )
    found: List[PositionDependencyItem] = []
    for dependency in specs:
        predicate_sql = build_position_dependency_blocking_predicate_sql(
            dependency,
            table_alias="dep",
        )
        count = int(
            conn.execute(
                text(
                    f"SELECT COUNT(*)::int FROM {dependency.qualified_table_sql} dep "
                    f"WHERE dep.{dependency.column_sql} = :position_id "
                    f"AND ({predicate_sql})"
                ),
                {"position_id": int(position_id)},
            ).scalar_one()
        )
        if count > 0:
            found.append(
                PositionDependencyItem(
                    key=dependency.key,
                    label=dependency.label,
                    table=f"{dependency.table_schema}.{dependency.table_name}",
                    column=dependency.column_name,
                    constraint=dependency.constraint_name,
                    count=count,
                    allowed_position_links=(
                        allowed_links_by_position.get(int(position_id), ())
                        if dependency.policy_identity
                        == _ALLOWED_POSITION_FK_POLICY_IDENTITY
                        else ()
                    ),
                )
            )
    return PositionDependencySummary(position_id=int(position_id), dependencies=found)


def check_positions_dependencies(
    conn: Connection,
    *,
    position_ids: Iterable[int],
    dependencies: Sequence[PositionForeignKeyDependency] | None = None,
) -> Mapping[int, PositionDependencySummary]:
    ids = list(dict.fromkeys(int(position_id) for position_id in position_ids))
    specs = list(dependencies or load_position_blocking_foreign_keys(conn))
    items_by_position: Dict[int, List[PositionDependencyItem]] = {position_id: [] for position_id in ids}
    if not ids:
        return {}

    allowed_links_by_position: Mapping[
        int, Sequence[AllowedPositionDependencyLink]
    ] = {}
    if any(
        dependency.policy_identity == _ALLOWED_POSITION_FK_POLICY_IDENTITY
        for dependency in specs
    ):
        allowed_links_by_position = _load_allowed_position_dependency_links(
            conn,
            position_ids=ids,
        )

    for dependency in specs:
        predicate_sql = build_position_dependency_blocking_predicate_sql(
            dependency,
            table_alias="dep",
        )
        rows = conn.execute(
            text(
                f"SELECT dep.{dependency.column_sql} AS position_id, COUNT(*)::int AS count "
                f"FROM {dependency.qualified_table_sql} dep "
                f"WHERE dep.{dependency.column_sql} = ANY(:position_ids) "
                f"AND ({predicate_sql}) "
                f"GROUP BY dep.{dependency.column_sql}"
            ),
            {"position_ids": ids},
        ).mappings().all()
        for row in rows:
            position_id = int(row["position_id"])
            items_by_position[position_id].append(
                PositionDependencyItem(
                    key=dependency.key,
                    label=dependency.label,
                    table=f"{dependency.table_schema}.{dependency.table_name}",
                    column=dependency.column_name,
                    constraint=dependency.constraint_name,
                    count=int(row["count"]),
                    allowed_position_links=(
                        allowed_links_by_position.get(position_id, ())
                        if dependency.policy_identity
                        == _ALLOWED_POSITION_FK_POLICY_IDENTITY
                        else ()
                    ),
                )
            )

    return {
        position_id: PositionDependencySummary(
            position_id=position_id,
            dependencies=items_by_position[position_id],
        )
        for position_id in ids
    }
