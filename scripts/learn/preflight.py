"""Fail closed if a training service points at a non-training database."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "corpsite_learn":
        raise SystemExit("Training database must be corpsite_learn on loopback")
    for flag in ("TRAINING_SERVER_ENABLED", "TRAINING_MODE", "TRAINING_DISABLE_EXTERNAL", "LEARNING_PILOT_ENABLED"):
        if os.getenv(flag) != "1":
            raise SystemExit(f"{flag}=1 is required")
    if os.getenv("BOT_TOKEN") or os.getenv("SMTP_PASSWORD"):
        raise SystemExit("External delivery credentials must not be configured")
    files = Path(os.environ["PERSONNEL_FILE_STORAGE_ROOT"]).resolve()
    photos = Path(os.environ["PERSONNEL_PHOTO_STORAGE_ROOT"]).resolve()
    if files == photos or files == Path("/") or photos == Path("/"):
        raise SystemExit("Separate private evidence and photo storage roots are required")
    for path in (files, photos):
        if not path.is_dir():
            raise SystemExit(f"Storage root missing: {path}")
    with create_engine(url, pool_pre_ping=True).connect() as conn:
        if conn.execute(text("SELECT current_database()")).scalar_one() != "corpsite_learn":
            raise SystemExit("Connected to the wrong database")
        if conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "ehalt20261123":
            raise SystemExit("Run Alembic migrations through ehalt20261123 first")
        for variable, table, column in (
            ("CORPSITE_TRAINING_UNIT_ID", "org_units", "unit_id"),
            ("CORPSITE_TRAINING_PARENT_UNIT_ID", "org_units", "unit_id"),
            ("CORPSITE_TRAINING_POSITION_ID", "positions", "position_id"),
        ):
            value = int(os.environ[variable])
            if conn.execute(text(f"SELECT 1 FROM public.{table} WHERE {column}=:id"), {"id": value}).first() is None:
                raise SystemExit(f"Missing training fixture for {variable}")
        if conn.execute(text("""
            SELECT 1 FROM public.users WHERE login='training_hr_partner_20261121'
              AND password_hash IS NULL AND is_active=TRUE
        """)).first() is None:
            raise SystemExit("The training HR partner account is missing")
    print("Training preflight OK")


if __name__ == "__main__":
    main()
