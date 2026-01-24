# app/tasks.py
from __future__ import annotations

# Backward-compatible import path:
# app.main.py делает: from app.tasks import router as tasks_router
from app.services.tasks_router import router  # noqa: F401
