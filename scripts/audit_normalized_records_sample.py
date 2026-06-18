#!/usr/bin/env python3
"""ADR-039 Phase 3E.1 — sample data quality audit for hr_import_normalized_records."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_normalized_record_service import normalized_records_available

KINDS = ("training", "certificate", "category", "education")
SAMPLE_LIMIT = 20


def main() -> int:
    with engine.connect() as conn:
        if not normalized_records_available(conn):
            print("hr_import_normalized_records table missing")
            return 1

        summary = {}
        for kind in KINDS:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        normalized_record_id,
                        record_kind,
                        source_field,
                        title,
                        LEFT(source_text, 120) AS source_preview,
                        review_status
                    FROM public.hr_import_normalized_records
                    WHERE record_kind = :kind
                    ORDER BY normalized_record_id
                    LIMIT :limit
                    """
                ),
                {"kind": kind, "limit": SAMPLE_LIMIT},
            ).mappings().all()
            summary[kind] = [dict(row) for row in rows]

        counts = conn.execute(
            text(
                """
                SELECT record_kind, source_field, COUNT(*) AS cnt
                FROM public.hr_import_normalized_records
                GROUP BY record_kind, source_field
                ORDER BY record_kind, source_field
                """
            )
        ).mappings().all()

    print(json.dumps({"samples": summary, "by_kind_source_field": [dict(r) for r in counts]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
