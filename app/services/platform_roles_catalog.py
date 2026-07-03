"""Platform Role catalog helpers (public.roles task roles)."""
from __future__ import annotations

import re
from typing import Any, Optional

PYTEST_ROLE_PREFIX = "pytest_"
PYTEST_ROLE_PATTERN = re.compile(r"^pytest_", re.IGNORECASE)


def is_pytest_test_role(*, role_code: Any = None, role_name: Any = None) -> bool:
    for raw in (role_code, role_name):
        s = str(raw or "").strip()
        if s and PYTEST_ROLE_PATTERN.match(s):
            return True
    return False


def pytest_role_exclusion_sql(*, code_expr: str, name_expr: str) -> str:
    """SQL fragment excluding pytest_* roles by code or name."""
    return f"""
        (
            LOWER(COALESCE(CAST({code_expr} AS TEXT), '')) NOT LIKE 'pytest\\_%' ESCAPE '\\'
            AND LOWER(COALESCE(CAST({name_expr} AS TEXT), '')) NOT LIKE 'pytest\\_%' ESCAPE '\\'
        )
    """.strip()
