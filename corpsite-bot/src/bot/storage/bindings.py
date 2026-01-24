# corpsite-bot/src/bot/storage/bindings.py
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("corpsite-bot")

# Невидимые символы, которые ломают int(k)
_INVISIBLE = ("\u200b", "\ufeff", "\u00a0")  # ZWSP, BOM, NBSP

BINDINGS: Dict[int, int] = {}


def _clean_str(s: str) -> str:
    s = s.strip()
    for ch in _INVISIBLE:
        s = s.replace(ch, "")
    return s.strip()


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        s = _clean_str(str(v))
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _bindings_path() -> Path:
    data_dir = (os.getenv("DATA_DIR") or "").strip()
    if not data_dir:
        data_dir = os.path.join(os.getcwd(), "data")
    p = Path(data_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p / "bindings.json"


_BINDINGS_FILE = _bindings_path()


def load_bindings() -> None:
    global BINDINGS

    if not _BINDINGS_FILE.exists():
        BINDINGS = {}
        return

    try:
        raw_text = _BINDINGS_FILE.read_text(encoding="utf-8") or ""
        raw = json.loads(raw_text) if raw_text.strip() else {}
        if not isinstance(raw, dict):
            BINDINGS = {}
            return

        out: Dict[int, int] = {}
        for k, v in raw.items():
            ik = _safe_int(k)
            iv = _safe_int(v)
            if ik is None or iv is None:
                continue
            if ik <= 0 or iv <= 0:
                continue
            out[int(ik)] = int(iv)

        BINDINGS = out
    except Exception:
        BINDINGS = {}


def save_bindings() -> None:
    _BINDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {str(k): int(v) for k, v in sorted(BINDINGS.items(), key=lambda x: x[0])}

    payload = json.dumps(data, ensure_ascii=False, indent=2)

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        encoding="utf-8",
        dir=str(_BINDINGS_FILE.parent),
        prefix=".tmp_",
        suffix=".json",
    ) as f:
        tmp_name = f.name
        f.write(payload)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_name, _BINDINGS_FILE)


def set_binding(tg_user_id: int, user_id: int) -> None:
    load_bindings()
    BINDINGS[int(tg_user_id)] = int(user_id)
    save_bindings()


def get_binding(tg_user_id: int) -> Optional[int]:
    load_bindings()
    return BINDINGS.get(int(tg_user_id))


def get_all_bindings() -> Dict[int, int]:
    load_bindings()
    return dict(BINDINGS)


def remove_binding(tg_user_id: int) -> bool:
    load_bindings()
    tid = int(tg_user_id)
    if tid not in BINDINGS:
        return False
    del BINDINGS[tid]
    save_bindings()
    return True


load_bindings()
log.info("BINDINGS_FILE=%s (exists=%s) loaded_keys=%s", str(_BINDINGS_FILE), _BINDINGS_FILE.exists(), sorted(BINDINGS.keys()))
