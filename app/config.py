# FILE: app/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)

FORBIDDEN_SECRETS: Set[str] = {
    "",
    "change-me",
    "dev-secret-change-me",
}


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_prod_env() -> bool:
    return env("APP_ENV", "dev").lower() in {"prod", "production"}


def cors_allowed_origins() -> List[str]:
    raw = env("CORS_ALLOWED_ORIGINS")
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    if is_prod_env():
        return []
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def validate_production_secrets() -> None:
    import sys

    if "pytest" in sys.modules:
        return

    if not is_prod_env():
        return

    required = {
        "AUTH_JWT_SECRET": env("AUTH_JWT_SECRET", "dev-secret-change-me"),
        "INTERNAL_API_TOKEN": env("INTERNAL_API_TOKEN"),
        "BOT_BIND_TOKEN": env("BOT_BIND_TOKEN"),
    }

    bad: List[str] = []
    for key, value in required.items():
        if value in FORBIDDEN_SECRETS:
            bad.append(key)

    if bad:
        raise RuntimeError(
            "Production env requires non-default secrets for: "
            + ", ".join(bad)
            + f". Configure them in {ENV_FILE}"
        )
