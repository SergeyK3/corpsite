# corpsite-bot/src/bot/storage/bindings.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

# Храним рядом с проектом corpsite-bot (не внутри src), чтобы было очевидно и не попадало в package.
# .../corpsite-bot/bindings.json
_BINDINGS_FILE = Path(__file__).resolve().parents[3] / "bindings.json"

BINDINGS: Dict[int, int] = {}


def load_bindings() -> None:
    """
    Загружает bindings из bindings.json (если есть).
    Молча стартует с пустыми bindings, если файла нет или он повреждён.
    """
    global BINDINGS

    if not _BINDINGS_FILE.exists():
        BINDINGS = {}
        return

    try:
        raw = json.loads(_BINDINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            BINDINGS = {}
            return
        BINDINGS = {int(k): int(v) for k, v in raw.items()}
    except Exception:
        BINDINGS = {}


def save_bindings() -> None:
    """
    Атомарно сохраняет bindings в bindings.json.
    """
    data = {str(k): int(v) for k, v in BINDINGS.items()}

    tmp = _BINDINGS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_BINDINGS_FILE)


def set_binding(tg_user_id: int, user_id: int) -> None:
    BINDINGS[int(tg_user_id)] = int(user_id)
    save_bindings()


def get_binding(tg_user_id: int) -> int | None:
    return BINDINGS.get(int(tg_user_id))


def delete_binding(tg_user_id: int) -> bool:
    """
    Удаляет привязку. Возвращает True, если привязка была и удалена, иначе False.
    """
    tg_user_id = int(tg_user_id)
    if tg_user_id not in BINDINGS:
        return False
    del BINDINGS[tg_user_id]
    save_bindings()
    return True


# Автозагрузка при импорте — bot.py менять не нужно
load_bindings()
