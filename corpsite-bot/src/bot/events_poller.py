# corpsite-bot/src/bot/events_poller.py
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from telegram.ext import Application

from .events_renderer import render_event
from .integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot.events")


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


class JsonFileStore:
    """
    JSON persistence store:
      - bindings: chat_id -> corpsite_user_id
      - state: corpsite_user_id -> last_event_id (audit_id)
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
      {
        "123456789": 1,
        "987654321": 2
      }
    where key=telegram chat_id, value=corpsite user_id
    """
    out: List[Tuple[int, int]] = []
    for k, v in bindings.items():
        chat_id = _safe_int(k)
        user_id = _safe_int(v)
        if chat_id and user_id and chat_id > 0 and user_id > 0:
            out.append((chat_id, user_id))
    return tuple(out)


async def events_polling_loop(
    *,
    application: Application,
    backend: CorpsiteAPI,
    poll_interval_s: float,
    bindings_store: JsonFileStore,
    state_store: JsonFileStore,
    per_user_limit: int = 200,
) -> None:
    """
    Poll /tasks/me/events for each bound user and send notifications to their chat_id.
    State is tracked by since_audit_id per corpsite_user_id.
    """
    log.info("Events polling loop started. interval=%ss limit=%s", poll_interval_s, per_user_limit)

    while True:
        try:
            bindings = bindings_store.load()
            pairs = _iter_bindings(bindings)

            if not pairs:
                await asyncio.sleep(max(1.0, poll_interval_s))
                continue

            state = state_store.load()  # { "corpsite_user_id": last_event_id }

            for chat_id, corpsite_user_id in pairs:
                last_id = _safe_int(state.get(str(corpsite_user_id))) or 0

                resp = await backend.get_my_events(
                    user_id=corpsite_user_id,
                    since_audit_id=(last_id if last_id > 0 else None),
                    limit=per_user_limit,
                    offset=0,
                    event_type=None,
                )

                if resp.status_code != 200:
                    log.warning(
                        "get_my_events failed: status=%s user_id=%s text=%s",
                        resp.status_code,
                        corpsite_user_id,
                        (resp.text or "")[:300],
                    )
                    continue

                if not isinstance(resp.json, list) or not resp.json:
                    continue

                events = resp.json  # list[dict]
                # backend returns ORDER BY audit_id DESC; deliver oldest-first
                events_sorted = sorted(events, key=lambda e: int(e.get("event_id") or 0))

                max_event_id = last_id
                for ev in events_sorted:
                    ev_id = _safe_int(ev.get("event_id")) or 0
                    if ev_id <= last_id:
                        continue

                    text = render_event(ev)
                    try:
                        await application.bot.send_message(chat_id=chat_id, text=text)
                        if ev_id > max_event_id:
                            max_event_id = ev_id
                    except Exception:
                        # do not advance cursor if send failed
                        log.exception(
                            "Failed to send event_id=%s to chat_id=%s (user_id=%s)",
                            ev_id,
                            chat_id,
                            corpsite_user_id,
                        )
                        break

                if max_event_id > last_id:
                    state[str(corpsite_user_id)] = max_event_id
                    state_store.save(state)

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Events polling loop cancelled.")
            raise
        except Exception:
            log.exception("Polling loop failure (outer). Backing off.")
            await asyncio.sleep(max(2.0, poll_interval_s))
