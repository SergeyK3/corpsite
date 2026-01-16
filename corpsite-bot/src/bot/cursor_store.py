# corpsite-bot/src/bot/cursor_store.py
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CursorConfig:
    data_dir: Path
    filename: str = "events_cursor.json"
    key: str = "since_audit_id"  # или "after_id" / "last_event_id" — что у вас реально используется


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def get_cursor_config() -> CursorConfig:
    data_dir = Path(os.getenv("DATA_DIR") or "data")
    filename = (os.getenv("EVENTS_CURSOR_FILE") or "events_cursor.json").strip()
    key = (os.getenv("EVENTS_CURSOR_KEY") or "since_audit_id").strip()
    return CursorConfig(data_dir=data_dir, filename=filename, key=key)


def _cursor_path(cfg: CursorConfig) -> Path:
    return cfg.data_dir / cfg.filename


def load_cursor(cfg: Optional[CursorConfig] = None) -> int:
    """
    Возвращает сохранённый cursor (int).
    Если файла нет/битый/ключ отсутствует — возвращает 0.
    Если выставлен EVENTS_CURSOR_RESET=1 — всегда возвращает 0 (удобно для E2E).
    """
    if _truthy_env("EVENTS_CURSOR_RESET"):
        return 0

    cfg = cfg or get_cursor_config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    path = _cursor_path(cfg)

    if not path.exists():
        return 0

    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return 0
        obj = json.loads(raw)
        v = obj.get(cfg.key, 0)
        n = int(v)
        return n if n > 0 else 0
    except Exception:
        return 0


def save_cursor(value: int, cfg: Optional[CursorConfig] = None) -> None:
    """
    Атомарная запись cursor в JSON.
    Пишем во временный файл и делаем replace, чтобы не получить битый JSON при рестарте.
    """
    cfg = cfg or get_cursor_config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    path = _cursor_path(cfg)

    v = int(value)
    if v < 0:
        v = 0

    payload: Dict[str, Any] = {cfg.key: v}

    tmp_dir = str(cfg.data_dir)
    fd, tmp_path = tempfile.mkstemp(prefix=path.stem + ".", suffix=".tmp", dir=tmp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
