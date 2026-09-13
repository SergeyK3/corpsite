"""Create/rebuild the local canonical PPR migration-status universe.

This command is deliberately limited to loopback PostgreSQL.  It only writes
PPR cohort/universe/projection tables and reads canonical personnel relations.
"""
from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import text

from app.db.engine import DATABASE_URL, engine
from app.services.ppr_migration_status_projection_service import (
    ensure_canonical_base_cohort,
    ensure_universe,
    rebuild_universe,
)


def _assert_local_target() -> None:
    parsed = urlparse(DATABASE_URL.replace("postgresql+psycopg2", "postgresql"))
    if (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Refusing non-local database target")


def main() -> None:
    _assert_local_target()
    with engine.begin() as conn:
        database = conn.execute(text("SELECT current_database()")).scalar_one()
        cohort_id = ensure_canonical_base_cohort(conn)
        universe_id = ensure_universe(conn, base_cohort_run_id=cohort_id)
        rows = rebuild_universe(conn, universe_id=universe_id)
        participants = conn.execute(text("SELECT count(*) FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id"), {"id": cohort_id}).scalar_one()
        print({"database": database, "cohort_id": cohort_id, "universe_id": universe_id, "participants": int(participants), "projection_rows": rows})


if __name__ == "__main__":
    main()
