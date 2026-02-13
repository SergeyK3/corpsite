# FILE: app/directory/router.py
from __future__ import annotations

from fastapi import APIRouter

from .debug_routes import router as debug_router
from .org_units_routes import router as org_units_router
from .employees_routes import router as employees_router
from .import_routes import router as import_router

router = APIRouter(prefix="/directory", tags=["directory"])

# order here is not critical
router.include_router(debug_router)
router.include_router(org_units_router)
router.include_router(employees_router)
router.include_router(import_router)
