# FILE: corpsite-bot/src/bot/storage/cursor_store.py

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class CursorStore:
    path: Path

    @staticmethod
    def default_path() -> Path:
        data_dir = (os.getenv("DATA_DIR") or "").strip()
        if not data_dir:
            data_dir = os.path.join(os.getcwd(), "data")
        p = Path(data_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        # IMPORTANT: bot-prefixed runtime file to avoid collisions with backend/runtime artifacts
        return p / "bot_events_cursor.json"

    def load_all(self) -> Dict[int, int]:
        if not self.path.exists():
            return {}

        raw_text = ""
        try:
            # utf-8-sig: на случай BOM (PowerShell/редакторы)
            raw_text = self.path.read_text(encoding="utf-8-sig")
            raw = json.loads(raw_text)
        except Exception:
            try:
                bad = self.path.with_name(f"{self.path.name}.bad.{_utc_now_compact()}")
                bad.write_text(raw_text or "", encoding="utf-8")
            except Exception:
                pass
            return {}

        cursors = raw.get("cursors") if isinstance(raw, dict) else None
        if not isinstance(cursors, dict):
            return {}

        out: Dict[int, int] = {}
        for k, v in cursors.items():
            try:
                uid = int(k)
                cur = int(v)
                # разрешаем uid == 0 для shared cursor (delivery-queue mode)
                if uid >= 0 and cur >= 0:
                    out[uid] = cur
            except Exception:
                continue
        return out

    def get(self, user_id: int, default: int = 0) -> int:
        allc = self.load_all()
        return int(allc.get(int(user_id), int(default)))

    def set(self, user_id: int, cursor: int) -> None:
        user_id = int(user_id)
        cursor = int(cursor)

        if user_id < 0 or cursor < 0:
            return

        allc = self.load_all()
        prev = int(allc.get(user_id, 0))

        # не даём курсору откатиться назад
        if cursor < prev:
            return

        allc[user_id] = cursor
        payload = {
            "version": 1,
            "updated_at": _utc_now_iso(),
            "cursors": {str(k): int(v) for k, v in sorted(allc.items(), key=lambda x: x[0])},
        }

        self._atomic_write(payload)

    def _atomic_write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            encoding="utf-8",
            dir=str(self.path.parent),
            prefix=".tmp_",
            suffix=".json",
        ) as f:
            tmp_name = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_name, self.path)
