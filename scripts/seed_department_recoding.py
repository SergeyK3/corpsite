#!/usr/bin/env python3
"""Seed department_recoding from scripts/data/department_recoding_seed.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.services.department_recoding_service import seed_department_recoding


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HR import department recoding table")
    parser.add_argument("--replace", action="store_true", help="Clear table before seeding")
    args = parser.parse_args()
    with engine.begin() as conn:
        result = seed_department_recoding(conn, replace=args.replace)
    print(result)


if __name__ == "__main__":
    main()
