# corpsite-bot/src/bot/storage/bindings.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

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
        if isinstance(v, int):
            return v
        s = _clean_str(str(v))
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _resolve_repo_root() -> Path:
    """
    Возвращает корень репозитория (папка "09 Corpsite"), т.е. родитель папки "corpsite-bot".

    Надёжнее, чем parents[N], потому что глубина может меняться.
    Ожидаем путь вида:
      .../09 Corpsite/corpsite-bot/src/bot/storage/bindings.py
    """
    p = Path(__file__).resolve()
    parts = [x.lower() for x in p.parts]
    if "corpsite-bot" in parts:
        idx = parts.index("corpsite-bot")
        return Path(*p.parts[:idx])  # родитель corpsite-bot
    # fallback (если структура другая) — как было ранее
    return p.parents[4]


_REPO_ROOT = _resolve_repo_root()
_BINDINGS_FILE = _REPO_ROOT / ".botdata" / "bindings.json"


def load_bindings() -> None:
    """
    Загружает bindings из .botdata/bindings.json (если есть).
    Молча стартует с пустыми bindings, если файла нет или он повреждён.
    """
    global BINDINGS

    if not _BINDINGS_FILE.exists():
        BINDINGS = {}
        return

    try:
        raw = json.loads(_BINDINGS_FILE.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict):
            BINDINGS = {}
            return

        out: Dict[int, int] = {}
        for k, v in raw.items():
            ik = _safe_int(k)
            iv = _safe_int(v)
            if ik is None or iv is None:
                continue
            if ik == 0 or iv <= 0:
                continue
            out[ik] = iv

        BINDINGS = out
    except Exception:
        BINDINGS = {}


def save_bindings() -> None:
    """
    Атомарно сохраняет bindings в .botdata/bindings.json.
    """
    _BINDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {str(k): int(v) for k, v in BINDINGS.items()}

    tmp = _BINDINGS_FILE.with_suffix(_BINDINGS_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_BINDINGS_FILE)


def set_binding(tg_user_id: int, user_id: int) -> None:
    """
    ВАЖНО: всегда reload перед модификацией, чтобы не терять остальные привязки.
    """
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
    tg_user_id = int(tg_user_id)
    if tg_user_id not in BINDINGS:
        return False
    del BINDINGS[tg_user_id]
    save_bindings()
    return True


# Автозагрузка при импорте + явный лог "куда пишем"
load_bindings()
log.info("BINDINGS_FILE=%s (exists=%s) loaded_keys=%s", str(_BINDINGS_FILE), _BINDINGS_FILE.exists(), sorted(BINDINGS.keys()))
