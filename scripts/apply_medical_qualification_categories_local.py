"""Apply only the independent classifier schema to the local application DB."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import engine
from app.db.medical_qualification_categories_schema import upgrade
from app.services.medical_qualification_categories_service import list_categories


def main():
    if engine.url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("This script only accepts a loopback database host")
    with engine.begin() as connection:
        upgrade(connection)
    result = list_categories()
    assert result["total"] == 4
    print(f"Local classifier ready: {result['total']} categories")


if __name__ == "__main__":
    main()
