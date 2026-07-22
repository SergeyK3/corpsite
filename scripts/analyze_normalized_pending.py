"""Ad-hoc analytics for pending normalized records in an import batch."""
from __future__ import annotations

import sys
from collections import Counter
from statistics import mean

from sqlalchemy import text

from app.db.engine import engine


def analyze_batch(conn, batch_id: int) -> None:
    batch = conn.execute(
        text(
            """
            SELECT batch_id, import_code, status, comparison_baseline_id, comparison_publication_origin_id
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if not batch:
        print(f"batch {batch_id} not found")
        return

    print(f"=== Batch {batch_id} ({batch['import_code']}) status={batch['status']} ===")
    print(f"comparison_baseline_id={batch['comparison_baseline_id']}")

    rows = conn.execute(
        text(
            """
            SELECT
                nr.normalized_record_id,
                nr.row_id,
                nr.record_kind,
                nr.review_status,
                nr.diff_status,
                nr.employee_id AS nr_employee_id,
                r.employee_id AS row_employee_id,
                r.normalized_payload->>'iin' AS iin,
                r.normalized_payload->>'full_name' AS full_name
            FROM public.hr_import_normalized_records nr
            LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
              AND nr.review_status = 'pending'
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    total = len(rows)
    print(f"pending normalized records: {total}")
    if not total:
        return

    def employee_key(row) -> str:
        emp = row["nr_employee_id"] or row["row_employee_id"]
        if emp:
            return f"employee:{emp}"
        iin = (row["iin"] or "").strip()
        if iin:
            return f"iin:{iin}"
        name = (row["full_name"] or "").strip()
        return f"row:{row['row_id']}:{name or 'unknown'}"

    by_employee: Counter[str] = Counter()
    by_diff: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    for row in rows:
        by_employee[employee_key(row)] += 1
        by_diff[str(row["diff_status"] or "NULL")] += 1
        by_kind[str(row["record_kind"] or "unknown")] += 1

    counts = list(by_employee.values())
    print(f"unique employees (by employee_id/iin/row): {len(by_employee)}")
    print(f"records per employee: avg={mean(counts):.2f}, max={max(counts)}, min={min(counts)}")
    print("top employees by record count:")
    for key, cnt in by_employee.most_common(8):
        print(f"  {key}: {cnt}")

    binding = conn.execute(
        text(
            """
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE nr.employee_id IS NOT NULL) AS with_nr_employee_id,
              COUNT(DISTINCT nr.employee_id) FILTER (WHERE nr.employee_id IS NOT NULL) AS distinct_nr_employee_id,
              COUNT(*) FILTER (WHERE r.employee_id IS NOT NULL) AS with_row_employee_id,
              COUNT(DISTINCT r.employee_id) FILTER (WHERE r.employee_id IS NOT NULL) AS distinct_row_employee_id,
              COUNT(DISTINCT NULLIF(TRIM(r.normalized_payload->>'iin'), '')) AS distinct_iin
            FROM public.hr_import_normalized_records nr
            LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
              AND nr.review_status = 'pending'
            """
        ),
        {"batch_id": batch_id},
    ).mappings().one()
    print("employee binding stats:", dict(binding))

    print("diff_status distribution (pending review only):")
    for status, cnt in by_diff.most_common():
        print(f"  {status}: {cnt}")

    print("record_kind distribution:")
    for kind, cnt in by_kind.most_common():
        print(f"  {kind}: {cnt}")

    needs_decision = sum(1 for r in rows if str(r["diff_status"] or "") in {"CHANGED", "CONFLICT", "REMOVED"})
    new_only = sum(1 for r in rows if str(r["diff_status"] or "") == "NEW")
    unchanged = sum(1 for r in rows if str(r["diff_status"] or "") == "UNCHANGED")
    null_diff = sum(1 for r in rows if r["diff_status"] is None)

    print("--- decision workload estimate ---")
    print(f"CHANGED/CONFLICT/REMOVED (likely need human review): {needs_decision}")
    print(f"NEW (first baseline / no prior canonical): {new_only}")
    print(f"UNCHANGED: {unchanged}")
    print(f"diff_status NULL: {null_diff}")

    if batch["comparison_baseline_id"] is None:
        print("NOTE: no comparison baseline on batch -> monthly diff treats records as NEW")
    else:
        baseline_id = int(batch["comparison_baseline_id"])
        baseline = conn.execute(
            text(
                """
                SELECT baseline_id, entry_count, report_period
                FROM public.hr_control_list_baselines
                WHERE baseline_id = :baseline_id
                """
            ),
            {"baseline_id": baseline_id},
        ).mappings().first()
        print("comparison baseline:", dict(baseline) if baseline else None)
        kinds = conn.execute(
            text(
                """
                SELECT record_kind, COUNT(*) AS cnt
                FROM public.hr_baseline_entries
                WHERE baseline_id = :baseline_id
                GROUP BY record_kind
                ORDER BY cnt DESC
                """
            ),
            {"baseline_id": baseline_id},
        ).mappings().all()
        print("baseline entry kinds:", [dict(k) for k in kinds])

    hist = Counter(counts)
    print("histogram records/employee:", dict(sorted(hist.items())))


def find_candidate_batches(conn, target: int = 1975) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT b.batch_id, COUNT(*) AS pending
            FROM public.hr_import_batches b
            JOIN public.hr_import_normalized_records nr ON nr.batch_id = b.batch_id
            WHERE nr.review_status = 'pending'
            GROUP BY b.batch_id
            ORDER BY ABS(COUNT(*) - :target), COUNT(*) DESC
            LIMIT 5
            """
        ),
        {"target": target},
    ).mappings().all()
    return [int(r["batch_id"]) for r in rows]


if __name__ == "__main__":
    batch_ids: list[int] = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else []
    with engine.connect() as conn:
        if not batch_ids:
            batch_ids = find_candidate_batches(conn)
            print("candidate batches:", batch_ids)
        for bid in batch_ids:
            analyze_batch(conn, bid)
            print()
