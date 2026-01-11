# corpsite-bot/src/bot/events_poller.py
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

from telegram.ext import Application

from .events_renderer import render_event
from .integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot.events")


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        # avoid bool being treated as int
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _event_cursor_id(ev: Dict[str, Any]) -> int:
    """
    Cursor for since_audit_id:
    - Prefer audit_id (backend cursor)
    - Fallback to event_id for backward compatibility
    """
    return _safe_int(ev.get("audit_id")) or _safe_int(ev.get("event_id")) or 0


def _sort_key(ev: Dict[str, Any]) -> int:
    return _event_cursor_id(ev)


class JsonFileStore:
    """
    JSON persistence store:
      - bindings: chat_id -> corpsite_user_id
      - state: chat_id -> last_cursor_id
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def _iter_bindings(bindings: Dict[str, Any]) -> Tuple[Tuple[int, int], ...]:
    """
    bindings json format:
      { "<chat_id>": <corpsite_user_id> }
    """
    out: List[Tuple[int, int]] = []
    for k, v in (bindings or {}).items():
        chat_id = _safe_int(k)
        user_id = _safe_int(v)
        if chat_id is None or user_id is None:
            continue
        if chat_id == 0 or user_id <= 0:
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


def _normalize_state_values(raw_state: Dict[str, Any]) -> Dict[str, int]:
    norm: Dict[str, int] = {}
    for k, v in (raw_state or {}).items():
        iv = _safe_int(v)
        if iv is None:
            continue
        norm[str(k)] = int(iv)
    return norm


def _migrate_state_if_needed(
    *,
    raw_state: Dict[str, Any],
    pairs: Tuple[Tuple[int, int], ...],
) -> Dict[str, int]:
    """
    TARGET: { "<chat_id>": last_cursor_id }

    NOTE: historically this was called last_event_id, but now it represents a cursor:
      - preferred: audit_id
      - fallback: event_id
    """
    if not pairs or not raw_state:
        return {}

    bound_chat_ids = {chat_id for chat_id, _ in pairs}
    bound_user_ids = {user_id for _, user_id in pairs}

    norm = _normalize_state_values(raw_state)
    fallback_last = int(norm.get("last_event_id", 0) or 0)

    keys_int = {_safe_int(k) for k in norm.keys()}
    keys_int.discard(None)

    user_key_hits = sum(1 for k in keys_int if k in bound_user_ids)
    chat_key_hits = sum(1 for k in keys_int if k in bound_chat_ids)

    out: Dict[str, int] = {}

    # 1) chat_id -> cursor (already in target form)
    for chat_id in bound_chat_ids:
        v = norm.get(str(chat_id))
        if v is not None:
            out[str(chat_id)] = int(v)

    # 2) migrate old user_id -> cursor (if state was keyed by user_id previously)
    if user_key_hits > 0 and chat_key_hits == 0:
        for chat_id, user_id in pairs:
            ukey = str(user_id)
            if ukey in norm:
                out[str(chat_id)] = max(int(out.get(str(chat_id), 0)), int(norm[ukey]))

    # 3) fallback_last: replicate to all bound chats (legacy single cursor)
    if not out and fallback_last:
        for chat_id in bound_chat_ids:
            out[str(chat_id)] = fallback_last

    return out


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
    Delivery policy (Variant A):
      - Audience is computed on backend via /tasks/me/events.
      - Bot only delivers to chats bound to user_id.
      - Cursor is audit_id (fallback event_id), stored per chat_id.
    """
    allowed_types = set(
        t.upper().strip() for t in (allowed_types or set()) if str(t).strip()
    )

    if allowed_types:
        log.info("Events polling filter enabled: %s", sorted(allowed_types))
    else:
        log.info("Events polling filter disabled (send all types).")

    log.info(
        "Events polling loop started. interval=%ss limit=%s",
        poll_interval_s,
        per_user_limit,
    )

    # Throttle logs when there are no bindings
    last_no_bindings_log_ts = 0.0

    # Throttle "No events" log per user_id when since cursor does not change
    # user_id -> (last_since, last_log_ts)
    no_events_log_state: Dict[int, Tuple[int, float]] = {}

    while True:
        try:
            bindings_raw = bindings_store.load()
            pairs = _iter_bindings(bindings_raw)

            if not pairs:
                now_ts = time.time()
                if now_ts - last_no_bindings_log_ts >= 60.0:
                    last_no_bindings_log_ts = now_ts
                    log.info(
                        "Events polling: no bindings found. bindings_path=%s",
                        str(bindings_store.path),
                    )
                await asyncio.sleep(max(1.0, poll_interval_s))
                continue

            by_user = _group_by_user(pairs)

            raw_state = state_store.load()
            state = _migrate_state_if_needed(raw_state=raw_state, pairs=pairs)

            state_changed = False

            for user_id, chat_ids in by_user.items():
                # Use the most advanced cursor among chats for this user_id to avoid re-fetching old pages.
                last_ids = [int(_safe_int(state.get(str(chat_id))) or 0) for chat_id in chat_ids]
                max_last_id = max(last_ids) if last_ids else 0
                since_val = int(max_last_id) if max_last_id > 0 else 0

                resp = await backend.get_my_events(
                    user_id=int(user_id),
                    since_audit_id=(int(max_last_id) if max_last_id > 0 else None),
                    limit=int(per_user_limit),
                    offset=0,
                    event_type=None,
                )

                if resp.status_code != 200:
                    log.warning(
                        "get_my_events failed: status=%s user_id=%s text=%s",
                        resp.status_code,
                        user_id,
                        (resp.text or "")[:300],
                    )
                    continue

                if not isinstance(resp.json, list) or not resp.json:
                    # Throttle identical "No events" lines
                    now_ts = time.time()
                    prev = no_events_log_state.get(int(user_id))
                    prev_since = prev[0] if prev else -1
                    prev_ts = prev[1] if prev else 0.0

                    # Log immediately if since changed; otherwise at most once per 60 seconds
                    if since_val != prev_since or (now_ts - prev_ts) >= 60.0:
                        log.info(
                            "No events: user_id=%s since=%s",
                            user_id,
                            (int(max_last_id) if max_last_id > 0 else None),
                        )
                        no_events_log_state[int(user_id)] = (since_val, now_ts)

                    continue

                # We have events: reset "No events" throttle for this user
                if int(user_id) in no_events_log_state:
                    no_events_log_state.pop(int(user_id), None)

                events_sorted = sorted(resp.json, key=_sort_key)

                log.info(
                    "Fetched events: user_id=%s since=%s count=%s",
                    user_id,
                    (int(max_last_id) if max_last_id > 0 else None),
                    len(events_sorted),
                )

                # Guardrail: ensure cursor ids are present; if not, log once per batch
                if events_sorted and _event_cursor_id(events_sorted[-1]) == 0:
                    log.warning(
                        "Events cursor_id is 0 (missing audit_id/event_id). user_id=%s",
                        user_id,
                    )

                for chat_id in chat_ids:
                    last_id = int(_safe_int(state.get(str(chat_id))) or 0)
                    max_cursor_id = last_id

                    for ev in events_sorted:
                        cursor_id = int(_event_cursor_id(ev))
                        if cursor_id <= last_id:
                            continue

                        ev_type = str(ev.get("event_type") or "").upper().strip()

                        # IMPORTANT: even if we filter out by allowed_types,
                        # we still advance cursor to avoid re-processing forever.
                        if allowed_types and ev_type not in allowed_types:
                            max_cursor_id = max(max_cursor_id, cursor_id)
                            continue

                        try:
                            await application.bot.send_message(
                                chat_id=int(chat_id),
                                text=render_event(ev),
                            )
                            max_cursor_id = max(max_cursor_id, cursor_id)
                        except Exception:
                            log.exception(
                                "Failed to send event_id=%s cursor_id=%s to chat_id=%s (user_id=%s)",
                                int(_safe_int(ev.get("event_id")) or 0),
                                cursor_id,
                                chat_id,
                                user_id,
                            )
                            # Stop this chat delivery on first failure to preserve ordering and avoid cursor skip.
                            break

                    if max_cursor_id > last_id:
                        state[str(chat_id)] = int(max_cursor_id)
                        state_changed = True

            if state_changed:
                state_store.save(state)

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Events polling loop cancelled.")
            raise
        except Exception:
            log.exception("Polling loop failure (outer). Backing off.")
            await asyncio.sleep(max(2.0, poll_interval_s))
