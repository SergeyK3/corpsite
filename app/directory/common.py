# FILE: app/directory/common.py
from __future__ import annotations

import inspect
from typing import Any, Dict

from fastapi import HTTPException


def as_http500(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"directory error: {type(e).__name__}: {str(e)}",
    )


def call_service(fn, **kwargs):
    sig = inspect.signature(fn)
    params = sig.parameters

    for p in params.values():
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            return fn(**kwargs)

    filtered: Dict[str, Any] = {k: v for k, v in kwargs.items() if k in params}
    return fn(**filtered)
