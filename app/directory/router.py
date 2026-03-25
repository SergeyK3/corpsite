# FILE: app/directory/router.py
from __future__ import annotations

import os

from fastapi import APIRouter

from .contacts_routes import router as contacts_router
from .debug_routes import router as debug_router
from .org_units_routes import router as org_units_router
from .employees_routes import router as employees_router
from .import_routes import router as import_router
from .roles_routes import router as roles_router
from .positions_routes import router as positions_router
from .working_contacts_routes import router as working_contacts_router

router = APIRouter(prefix="/directory", tags=["directory"])


def _debug_routes_enabled() -> bool:
    raw = (os.getenv("ENABLE_DIRECTORY_DEBUG") or "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    env_name = (os.getenv("APP_ENV") or "dev").strip().lower()
    return env_name not in {"prod", "production"}


if _debug_routes_enabled():
    router.include_router(debug_router)

router.include_router(org_units_router)
router.include_router(employees_router)
router.include_router(import_router)
router.include_router(roles_router)
router.include_router(positions_router)
router.include_router(contacts_router)
router.include_router(working_contacts_router)