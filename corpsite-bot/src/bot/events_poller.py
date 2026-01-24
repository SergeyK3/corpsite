# corpsite-bot/src/bot/events_poller.py

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

from telegram.ext import Application

from .events_renderer import render_event
from .integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot.events")


# ---------------------------
# Utils
# ---------------------------

def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _event_cursor_id(ev: Dict[str, Any]) -> int:
    """
    Cursor for polling:
      - prefer audit_id (backend cursor)
      - fallback to event_id (legacy)
    """
    return _safe_int(ev.get("audit_id")) or _safe_int(ev.get("event_id")) or 0


def _sort_key(ev: Dict[str, Any]) -> int:
    return _event_cursor_id(ev)


# ---------------------------
# JSON persistence
# ---------------------------

class JsonFileStore:
    """
    Simple JSON persistence.

    bindings.json:
      { "<chat_id>": <corpsite_user_id> }

    events_cursor.json:
      { "<chat_id>": <last_cursor_id> }
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            return json.loads(raw)
        except Exception:
            log.exception("Failed to load json store: %s", self.path)
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = json.dumps(data, ensure_ascii=False, indent=2)

        tmp_dir = str(self.path.parent)
        fd, tmp_path = tempfile.mkstemp(
            prefix=self.path.stem + ".",
            suffix=self.path.suffix + ".tmp",
            dir=tmp_dir,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.write("\n")
            os.replace(tmp_path, self.path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


# ---------------------------
# Bindings helpers
# ---------------------------

def _iter_bindings(bindings: Dict[str, Any]) -> Tuple[Tuple[int, int], ...]:
    """
    bindings format:
      { "<chat_id>": <user_id> }
    """
    out: List[Tuple[int, int]] = []
    for k, v in (bindings or {}).items():
        chat_id = _safe_int(k)
        user_id = _safe_int(v)
        if not chat_id or not user_id:
            continue
        out.append((chat_id, user_id))
    return tuple(out)


def _group_by_user(pairs: Tuple[Tuple[int, int], ...]) -> Dict[int, List[int]]:
    """
    user_id -> [chat_id, ...]
    """
    m: DefaultDict[int, List[int]] = defaultdict(list)
    for chat_id, user_id in pairs:
        m[user_id].append(chat_id)
    return dict(m)


# ---------------------------
# Cursor state migration
# ---------------------------

def _normalize_state_values(raw_state: Dict[str, Any]) -> Dict[str, int]:
    norm: Dict[str, int] = {}
    for k, v in (raw_state or {}).items():
        iv = _safe_int(v)
        if iv is None:
            continue
        norm[str(k)] = iv
    return norm


def _migrate_state_if_needed(
    *,
    raw_state: Dict[str, Any],
    pairs: Tuple[Tuple[int, int], ...],
) -> Dict[str, int]:
    """
    Target format:
      { "<chat_id>": last_cursor_id }

    Supports legacy formats:
      - user_id -> last_event_id
      - single last_event_id
    """
    if not raw_state or not pairs:
        return {}

    norm = _normalize_state_values(raw_state)

    bound_chat_ids = {chat_id for chat_id, _ in pairs}
    bound_user_ids = {user_id for _, user_id in pairs}

    fallback_last = int(norm.get("last_event_id", 0) or 0)

    keys_int = {_safe_int(k) for k in norm.keys()}
    keys_int.discard(None)

    user_key_hits = sum(1 for k in keys_int if k in bound_user_ids)
    chat_key_hits = sum(1 for k in keys_int if k in bound_chat_ids)

    out: Dict[str, int] = {}

    for chat_id in bound_chat_ids:
        v = norm.get(str(chat_id))
        if v is not None:
            out[str(chat_id)] = v

    if user_key_hits > 0 and chat_key_hits == 0:
        for chat_id, user_id in pairs:
            if str(user_id) in norm:
                out[str(chat_id)] = max(
                    out.get(str(chat_id), 0),
                    norm[str(user_id)],
                )

    if not out and fallback_last:
        for chat_id in bound_chat_ids:
            out[str(chat_id)] = fallback_last

    return out


# ---------------------------
# Polling loop
# ---------------------------

async def events_polling_loop(
    *,
    application: Application,
    backend: CorpsiteAPI,
    poll_interval_s: float,
    bindings_store: JsonFileStore,
    state_store: JsonFileStore,
    per_user_limit: int = 200,
    allowed_types: Optional[Set[str]] = None,
) -> None:
    """
    Events delivery loop.

    - Audience resolved on backend (/tasks/me/events)
    - Cursor = audit_id (fallback event_id)
    - Cursor stored per chat_id (state_store JSON)
    - Optional reset: EVENTS_CURSOR_RESET=1 -> clears cursor store (for E2E)
    """

    allowed_types = {
        t.upper().strip()
        for t in (allowed_types or set())
        if str(t).strip()
    }

    log.info(
        "Events polling started. interval=%ss limit=%s allowed_types=%s",
        poll_interval_s,
        per_user_limit,
        sorted(allowed_types) if allowed_types else "ALL",
    )

    last_no_bindings_log_ts = 0.0
    no_events_log_state: Dict[int, Tuple[int, float]] = {}

    did_reset = False

    while True:
        try:
            bindings_raw = bindings_store.load()
            pairs = _iter_bindings(bindings_raw)

            if not pairs:
                now = time.time()
                if now - last_no_bindings_log_ts >= 60.0:
                    last_no_bindings_log_ts = now
                    log.info("Events polling: no bindings")
                await asyncio.sleep(max(1.0, poll_interval_s))
                continue

            by_user = _group_by_user(pairs)

            raw_state = state_store.load()

            if not did_reset and _truthy_env("EVENTS_CURSOR_RESET"):
                did_reset = True
                raw_state = {}
                state_store.save({})
                log.info("Events cursor reset: store cleared (EVENTS_CURSOR_RESET=1)")

            state = _migrate_state_if_needed(
                raw_state=raw_state,
                pairs=pairs,
            )

            state_changed = False

            for user_id, chat_ids in by_user.items():
                last_ids = [
                    int(_safe_int(state.get(str(chat_id))) or 0)
                    for chat_id in chat_ids
                ]
                since_val = min(last_ids) if last_ids else 0

                resp = await backend.get_my_events(
                    user_id=user_id,
                    since_audit_id=since_val if since_val > 0 else None,
                    limit=per_user_limit,
                    offset=0,
                    event_type=None,
                )

                if resp.status_code != 200:
                    log.warning(
                        "get_my_events failed: user_id=%s status=%s",
                        user_id,
                        resp.status_code,
                    )
                    continue

                events = resp.json or []
                if not isinstance(events, list) or not events:
                    now = time.time()
                    prev = no_events_log_state.get(user_id)
                    prev_since = prev[0] if prev else -1
                    prev_ts = prev[1] if prev else 0.0

                    if since_val != prev_since or now - prev_ts >= 60.0:
                        log.info(
                            "No events: user_id=%s since=%s",
                            user_id,
                            since_val or None,
                        )
                        no_events_log_state[user_id] = (since_val, now)
                    continue

                no_events_log_state.pop(user_id, None)

                events_sorted = sorted(events, key=_sort_key)

                log.info(
                    "Fetched events: user_id=%s since=%s count=%s",
                    user_id,
                    since_val or None,
                    len(events_sorted),
                )

                for chat_id in chat_ids:
                    last_cursor = int(_safe_int(state.get(str(chat_id))) or 0)
                    max_cursor = last_cursor

                    for ev in events_sorted:
                        cursor_id = _event_cursor_id(ev)
                        if cursor_id <= last_cursor:
                            continue

                        ev_type = str(ev.get("event_type") or "").upper()

                        if allowed_types and ev_type not in allowed_types:
                            max_cursor = max(max_cursor, cursor_id)
                            continue

                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=render_event(ev),
                            )
                            max_cursor = max(max_cursor, cursor_id)
                        except Exception:
                            log.exception(
                                "Send failed: chat_id=%s user_id=%s cursor_id=%s",
                                chat_id,
                                user_id,
                                cursor_id,
                            )
                            break

                    if max_cursor > last_cursor:
                        state[str(chat_id)] = max_cursor
                        state_changed = True

            if state_changed:
                state_store.save(state)

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Events polling cancelled")
            raise
        except Exception:
            log.exception("Events polling failure (outer loop)")
            await asyncio.sleep(max(2.0, poll_interval_s))
