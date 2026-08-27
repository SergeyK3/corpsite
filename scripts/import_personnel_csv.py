"""Personnel CSV loader with a read-only dry-run mode.

The loader never issues direct INSERT/UPDATE SQL.  `--apply` is deliberately
guarded: Corpsite creates employees through the personnel-order HIRE workflow
(person → primary assignment → employee → IIN/contact services), not an
ungoverned CSV mutation.  This task runs only `--dry-run`.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import text

from reconcile_personnel_csv import ROOT, normalized, normalized_iin, parse_date, text_value
from app.db.engine import engine
from app.personnel_applications.application.registration_service import _ensure_envelope_exists, _insert_person
from app.services.identity_reconciliation_service import _insert_employee_identity_iin
from app.services.operational_contact_service import ensure_operational_contact_for_employee
from app.services.personnel_orders_apply_service import apply_personnel_order_in_conn
from app.services.personnel_orders_command_service import (
    create_personnel_order_draft_tx,
    create_personnel_order_item_tx,
    register_personnel_order_tx,
)


DEFAULT_CSV = ROOT / "tmp" / "сотр слияние.csv"
DEFAULT_XLSX = ROOT / "tmp" / "спрКорпсайт.xlsx"
DEFAULT_INPUT_REPORT = ROOT / "tmp" / "personnel_reconciliation_report.csv"
DEFAULT_OUTPUT_REPORT = ROOT / "tmp" / "personnel_import_dry_run.csv"
DEFAULT_APPLY_REPORT = ROOT / "tmp" / "personnel_import_apply_result.csv"
PRODUCTION_ORDER_PREFIX = "PERSONNEL-IMPORT-2026"
STATUS_NEW = "новый сотрудник"
PILOT_ACTOR_USER_ID = 1

OUT_READY = "готово к созданию"
OUT_DATE_REQUIRED = "требуется date_from"
OUT_SERVICE_BLOCKED = "не проходит проверку сервиса"
OUT_EXISTS = "уже существует при повторной проверке"

FIELDS = (
    "csv_row",
    "full_name",
    "iin",
    "birth_date",
    "phone",
    "department_unit_id",
    "department_name",
    "position_id",
    "position_name",
    "date_from",
    "result",
    "reason",
    "planned_person",
    "planned_employee",
    "planned_primary_assignment",
    "planned_iin_identity",
    "planned_contact",
    "apply_service_path",
    "person_id",
    "employee_id",
    "order_id",
    "assignment_id",
    "identity_id",
    "contact_id",
)


def existing_match(conn, *, full_name: str, iin: str) -> tuple[str, str]:
    if len(iin) == 12:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT e.employee_id
                FROM public.employees e
                LEFT JOIN public.persons p ON p.person_id = e.person_id
                LEFT JOIN public.employee_identities ei
                  ON ei.employee_id = e.employee_id
                 AND ei.identity_type = 'IIN'
                 AND ei.valid_to IS NULL
                WHERE p.iin = :iin OR ei.identity_value = :iin
                ORDER BY e.employee_id
                """
            ),
            {"iin": iin},
        ).scalars().all()
        if rows:
            return "ИИН", ";".join(str(value) for value in rows)
    name_key = normalized(full_name)
    if name_key:
        rows = conn.execute(
            text(
                """
                SELECT employee_id
                FROM public.employees
                WHERE regexp_replace(lower(full_name), '[^[:alnum:]]+', '', 'g') = :name_key
                ORDER BY employee_id
                """
            ),
            {"name_key": name_key},
        ).scalars().all()
        if rows:
            return "нормализованное ФИО", ";".join(str(value) for value in rows)
    return "", ""


def order_number(*, source_row: str, prefix: str = PRODUCTION_ORDER_PREFIX) -> str:
    """Stable import identity: retries reuse the same personnel order number."""
    return f"{prefix}-{int(source_row)}"


def load_source_rows(report_path: Path, source_rows: set[int] | None = None) -> list[dict[str, str]]:
    with report_path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row.get("status") == STATUS_NEW]
    if source_rows is not None:
        rows = [row for row in rows if int(text_value(row.get("csv_row"))) in source_rows]
    return rows


def dry_run(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    report: list[dict[str, str]] = []
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                raise RuntimeError("PostgreSQL transaction is not read-only")
            for source in rows:
                row = {field: "" for field in FIELDS}
                row.update(
                    {
                        "csv_row": text_value(source.get("csv_row")),
                        "full_name": text_value(source.get("full_name")),
                        "iin": text_value(source.get("iin")),
                        "birth_date": text_value(source.get("birth_date")),
                        "phone": text_value(source.get("phone")),
                        "department_unit_id": text_value(source.get("found_department_unit_id")),
                        "department_name": text_value(source.get("found_department_name")),
                        "position_id": text_value(source.get("found_position_id")),
                        "position_name": text_value(source.get("found_position_name")),
                        "date_from": text_value(source.get("date_from")),
                        "apply_service_path": "personnel-order HIRE workflow + identity/contact services",
                    }
                )
                iin = normalized_iin(row["iin"])
                match_by, existing_ids = existing_match(connection, full_name=row["full_name"], iin=iin)
                if existing_ids:
                    row["result"] = OUT_EXISTS
                    row["reason"] = f"повторная проверка: {match_by}, employee_id={existing_ids}"
                elif parse_date(row["date_from"]) is None:
                    row["result"] = OUT_DATE_REQUIRED
                    row["reason"] = "date_from отсутствует или имеет неверный формат; дата не подставляется"
                elif not row["department_unit_id"] or not row["position_id"]:
                    row["result"] = OUT_SERVICE_BLOCKED
                    row["reason"] = "нет подтверждённого org_unit_id или position_id"
                else:
                    unit_exists = connection.execute(
                        text("SELECT 1 FROM public.org_units WHERE unit_id = :id"),
                        {"id": int(row["department_unit_id"])},
                    ).first()
                    position_exists = connection.execute(
                        text("SELECT 1 FROM public.positions WHERE position_id = :id"),
                        {"id": int(row["position_id"])},
                    ).first()
                    if unit_exists is None or position_exists is None:
                        row["result"] = OUT_SERVICE_BLOCKED
                        row["reason"] = "подтверждённая ссылка справочника больше не существует"
                    else:
                        row["result"] = OUT_READY
                        row["planned_person"] = "создать через HIRE workflow"
                        row["planned_employee"] = "создать через HIRE workflow"
                        row["planned_primary_assignment"] = (
                            f"org_unit_id={row['department_unit_id']}; position_id={row['position_id']}; "
                            f"start_date={row['date_from']}"
                        )
                        row["planned_iin_identity"] = "создать" if len(iin) == 12 else "не создавать: ИИН не указан"
                        row["planned_contact"] = "создать с телефоном" if row["phone"] else "создать без телефона"
                report.append(row)
        finally:
            transaction.rollback()
    return report


def _source_date(value: str) -> date:
    result = parse_date(value)
    if result is None:
        raise ValueError("date_from is required")
    return result


def _row_from_source(source: dict[str, str]) -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row.update(
        {
            "csv_row": text_value(source.get("csv_row")),
            "full_name": text_value(source.get("full_name")),
            "iin": text_value(source.get("iin")),
            "birth_date": text_value(source.get("birth_date")),
            "phone": text_value(source.get("phone")),
            "department_unit_id": text_value(source.get("found_department_unit_id")),
            "department_name": text_value(source.get("found_department_name")),
            "position_id": text_value(source.get("found_position_id")),
            "position_name": text_value(source.get("found_position_name")),
            "date_from": text_value(source.get("date_from")),
            "apply_service_path": "Person + HIRE order + assignment + IIN identity + contact services",
        }
    )
    return row


def _repeat_check(*, full_name: str, iin: str) -> tuple[str, str]:
    with engine.connect() as connection:
        return existing_match(connection, full_name=full_name, iin=iin)


def _verify_created(
    *, row: dict[str, str], require_identity_and_contact: bool, order_prefix: str
) -> dict[str, int | None]:
    """Read back only the objects created by this deterministic pilot row."""
    with engine.connect() as connection:
        employee = connection.execute(
            text(
                """
                SELECT e.employee_id, e.person_id
                FROM public.employees e
                JOIN public.employee_events ev ON ev.employee_id = e.employee_id
                JOIN public.personnel_orders po ON po.order_id = ev.order_id
                WHERE po.order_number = :order_number
                  AND ev.event_type = 'HIRE'
                """
            ),
            {"order_number": order_number(source_row=row["csv_row"], prefix=order_prefix)},
        ).mappings().all()
        if len(employee) != 1:
            raise RuntimeError(f"expected exactly one HIRE employee, found {len(employee)}")
        employee_row = dict(employee[0])
        assignment = connection.execute(
            text(
                """
                SELECT assignment_id
                FROM public.person_assignments
                WHERE person_id = :person_id
                  AND org_unit_id = :org_unit_id
                  AND position_id = :position_id
                  AND start_date = :start_date
                  AND is_primary = TRUE
                  AND active_flag = TRUE
                """
            ),
            {
                "person_id": int(employee_row["person_id"]),
                "org_unit_id": int(row["department_unit_id"]),
                "position_id": int(row["position_id"]),
                "start_date": _source_date(row["date_from"]),
            },
        ).scalars().all()
        if len(assignment) != 1:
            raise RuntimeError(f"expected exactly one primary assignment, found {len(assignment)}")
        iin = normalized_iin(row["iin"])
        identity_id = connection.execute(
            text(
                """
                SELECT identity_id FROM public.employee_identities
                WHERE employee_id = :employee_id AND identity_type = 'IIN'
                  AND identity_value = :iin AND valid_to IS NULL
                """
            ),
            {"employee_id": int(employee_row["employee_id"]), "iin": iin},
        ).scalar_one_or_none()
        contact_sql = """
            SELECT contact_id FROM public.contacts
            WHERE person_id = :person_id
              AND COALESCE(is_deleted, FALSE) = FALSE
        """
        contact_params = {"person_id": int(employee_row["person_id"])}
        if row["phone"]:
            contact_sql += " AND phone = :phone"
            contact_params["phone"] = row["phone"]
        else:
            contact_sql += " AND NULLIF(trim(COALESCE(phone, '')), '') IS NULL"
        contact_id = connection.execute(text(contact_sql), contact_params).scalar_one_or_none()
        order_id = connection.execute(
            text("SELECT order_id FROM public.personnel_orders WHERE order_number = :order_number"),
            {"order_number": order_number(source_row=row["csv_row"], prefix=order_prefix)},
        ).scalar_one()
    if require_identity_and_contact and (contact_id is None or (len(iin) == 12 and identity_id is None)):
        raise RuntimeError("IIN identity or phone contact was not saved")
    return {
        "person_id": int(employee_row["person_id"]),
        "employee_id": int(employee_row["employee_id"]),
        "order_id": int(order_id),
        "assignment_id": int(assignment[0]),
        "identity_id": int(identity_id),
        "contact_id": int(contact_id),
    }


def apply_one(
    source: dict[str, str], *, fail_after_draft: bool = False,
    order_prefix: str = PRODUCTION_ORDER_PREFIX,
) -> dict[str, str]:
    """Apply one row; all mutations go through existing Corpsite services."""
    row = _row_from_source(source)
    iin = normalized_iin(row["iin"])
    if not row["department_unit_id"] or not row["position_id"]:
        raise RuntimeError("confirmed org unit and position are required")
    match_by, existing_ids = _repeat_check(full_name=row["full_name"], iin=iin)
    if existing_ids:
        row["result"] = OUT_EXISTS
        row["reason"] = f"repeat check: {match_by}, employee_id={existing_ids}"
        return row

    effective_date = _source_date(row["date_from"])
    birth_date = parse_date(row["birth_date"])
    try:
        # One transaction owns every object.  Service internals accept this
        # connection and therefore cannot commit a partial CSV row.
        with engine.begin() as connection:
            person = None
            if len(iin) == 12:
                person = connection.execute(
                    text(
                        """
                        SELECT person_id, full_name, birth_date
                        FROM public.persons
                        WHERE iin = :iin AND person_status = 'active'
                        ORDER BY person_id
                        LIMIT 1
                        FOR UPDATE
                        """
                    ),
                    {"iin": iin},
                ).mappings().first()
            if person is None:
                person_id = _insert_person(
                    connection,
                    full_name=row["full_name"],
                    iin=iin or None,
                    birth_date=birth_date,
                )
                is_new_person = True
            else:
                person_id = int(person["person_id"])
                if normalized(str(person["full_name"] or "")) != normalized(row["full_name"]):
                    raise RuntimeError("existing Person with this IIN has a different full name")
                if birth_date is not None and person["birth_date"] not in (None, birth_date):
                    raise RuntimeError("existing Person with this IIN has a different birth date")
                is_new_person = False
            _ensure_envelope_exists(
                connection,
                person_id=person_id,
                is_new_person=is_new_person,
                actor_id=f"csv-pilot:{PILOT_ACTOR_USER_ID}",
            )
            order_id = create_personnel_order_draft_tx(
                connection,
                created_by=PILOT_ACTOR_USER_ID,
                order_number=order_number(source_row=row["csv_row"], prefix=order_prefix),
                order_date=effective_date,
                order_type_code="HIRE",
                comment=f"Local CSV pilot import, source row {row['csv_row']}",
            )
            if fail_after_draft:
                raise RuntimeError("test failure after HIRE draft")
            create_personnel_order_item_tx(
                connection,
                order_id=order_id,
                item_type_code="HIRE",
                effective_date=effective_date,
                payload={
                    "person_id": person_id,
                    "org_unit_id": int(row["department_unit_id"]),
                    "position_id": int(row["position_id"]),
                    "employment_rate": 1.0,
                },
            )
            register_personnel_order_tx(connection, order_id=order_id, target_status="SIGNED")
            apply_personnel_order_in_conn(connection, order_id=order_id, created_by=PILOT_ACTOR_USER_ID)
            employee_id = connection.execute(
                text("SELECT employee_id FROM public.employees WHERE person_id = :person_id"),
                {"person_id": person_id},
            ).scalar_one()
            if len(iin) == 12:
                _insert_employee_identity_iin(
                    connection,
                    employee_id=int(employee_id),
                    iin=iin,
                    created_by=PILOT_ACTOR_USER_ID,
                )
            ensure_operational_contact_for_employee(
                connection,
                employee_id=int(employee_id),
                full_name=row["full_name"],
                phone=row["phone"],
            )
        verification = _verify_created(
            row=row,
            require_identity_and_contact=True,
            order_prefix=order_prefix,
        )
        row.update({key: str(value or "") for key, value in verification.items()})
        row["result"] = "created"
        row["reason"] = "HIRE order applied and verified"
        return row
    except Exception:
        # Do not hide a failed first/next row: the caller stops immediately.
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="source personnel CSV (provenance check)")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX, help="department mapping XLSX (provenance check)")
    parser.add_argument("--report", type=Path, default=DEFAULT_INPUT_REPORT, help="reconciliation report CSV to import")
    parser.add_argument("--output-report", type=Path, default=None, help="dry-run/apply result CSV")
    parser.add_argument(
        "--dry-run-report",
        type=Path,
        default=DEFAULT_OUTPUT_REPORT,
        help="previous dry-run result; bulk --apply accepts only rows marked ready there",
    )
    parser.add_argument("--order-prefix", default=PRODUCTION_ORDER_PREFIX, help="stable personnel order number prefix")
    parser.add_argument(
        "--source-rows",
        help="comma-separated original CSV row numbers; required for --apply",
    )
    parser.add_argument(
        "--fail-after-draft",
        action="store_true",
        help="test-only: abort inside the row transaction after creating a draft",
    )
    args = parser.parse_args()
    for label, path in (("--csv", args.csv), ("--xlsx", args.xlsx), ("--report", args.report)):
        if not path.is_file():
            raise SystemExit(f"{label} file not found: {path}")
    order_prefix = str(args.order_prefix or "").strip().upper()
    if not order_prefix or any(char.isspace() for char in order_prefix):
        raise SystemExit("--order-prefix must be a non-empty token without whitespace")
    output_report = args.output_report or (DEFAULT_APPLY_REPORT if args.apply else DEFAULT_OUTPUT_REPORT)
    selected = None
    if args.source_rows:
        try:
            selected = {int(value.strip()) for value in args.source_rows.split(",") if value.strip()}
        except ValueError as exc:
            raise SystemExit("--source-rows must contain comma-separated integers") from exc
    if args.apply and not selected:
        if not args.dry_run_report.is_file():
            raise SystemExit("run --dry-run before bulk --apply")
        with args.dry_run_report.open("r", encoding="utf-8-sig", newline="") as report_file:
            selected = {
                int(report["csv_row"])
                for report in csv.DictReader(report_file)
                if report.get("result") == OUT_READY
            }
        if not selected:
            print("No rows currently ready for creation.")
            return

    source_rows = load_source_rows(args.report, selected)
    if selected is None and not source_rows:
        raise SystemExit("No rows with status 'новый сотрудник' were found in --report")
    if selected is not None and {int(row['csv_row']) for row in source_rows} != selected:
        raise SystemExit("one or more --source-rows are not current rows with status «новый сотрудник»")
    if args.apply:
        applied: list[dict[str, str]] = []
        for source in source_rows:
            try:
                applied.append(apply_one(source, fail_after_draft=args.fail_after_draft, order_prefix=order_prefix))
            except Exception as exc:
                raise RuntimeError(f"source row {source['csv_row']}: {exc}") from exc
        with output_report.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(applied)
        print(f"Apply report: {output_report}")
        for row in applied:
            print(f"source row {row['csv_row']}: {row['result']} employee_id={row['employee_id']}")
        return
    report_rows = dry_run(source_rows)
    with output_report.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(report_rows)
    counts = Counter(row["result"] for row in report_rows)
    print(f"Отчёт: {output_report}")
    for result in (OUT_READY, OUT_DATE_REQUIRED, OUT_SERVICE_BLOCKED, OUT_EXISTS):
        print(f"{result}: {counts[result]}")


if __name__ == "__main__":
    main()
