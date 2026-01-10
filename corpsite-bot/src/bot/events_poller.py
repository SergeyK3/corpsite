# corpsite-bot/src/bot/events_poller.py
from __future__ import annotations

import asyncio
import json
import logging
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
        return int(v)
    except Exception:
        return None


class JsonFileStore:
    """
    JSON persistence store:
      - bindings: chat_id -> corpsite_user_id
      - state: chat_id -> last_event_id
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
    for k, v in bindings.items():
        chat_id = _safe_int(k)
        user_id = _safe_int(v)
        # chat_id может быть отрицательным для групп/каналов; валидируем != 0
        if chat_id is None or user_id is None:
            continue
        if chat_id == 0:
            continue
        if user_id <= 0:
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
        norm[str(k)] = iv
    return norm


def _migrate_state_if_needed(
    *,
    raw_state: Dict[str, Any],
    pairs: Tuple[Tuple[int, int], ...],
) -> Dict[str, int]:
    """
    Приводим state к целевому формату:
      TARGET: { "<chat_id>": last_event_id }

    Допустимые входные варианты:
      A) старый: { "<corpsite_user_id>": last_event_id }
      B) новый:  { "<chat_id>": last_event_id }
      C) смешанный, включая { "last_event_id": N, ... }

    Правило выхода:
      - вернуть только ключи "<chat_id>" из bindings
      - "last_event_id" не сохраняем никогда (можем использовать как fallback)
    """
    if not pairs:
        return {}

    bound_chat_ids = {chat_id for chat_id, _ in pairs}
    bound_user_ids = {user_id for _, user_id in pairs}

    if not raw_state:
        return {}

    norm = _normalize_state_values(raw_state)
    fallback_last = norm.get("last_event_id", 0)

    keys_int = {_safe_int(k) for k in norm.keys()}
    keys_int.discard(None)

    user_key_hits = sum(1 for k in keys_int if k in bound_user_ids)
    chat_key_hits = sum(1 for k in keys_int if k in bound_chat_ids)

    out: Dict[str, int] = {}

    # 1) если есть значения по chat_id — берём их
    for chat_id in bound_chat_ids:
        v = norm.get(str(chat_id))
        if v is not None:
            out[str(chat_id)] = v

    # 2) если это старый формат (user_id -> cursor) и chat ключей нет — мигрируем
    if user_key_hits > 0 and chat_key_hits == 0:
        for chat_id, user_id in pairs:
            ukey = str(user_id)
            if ukey in norm:
                out[str(chat_id)] = max(out.get(str(chat_id), 0), norm[ukey])

    # 3) если вообще ничего не получили, но есть fallback_last — применяем его ко всем chat_id
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
    Poll /tasks/me/events for each bound user and send notifications to their chat(s).

    State:
      - tracked per chat_id: since_audit_id (event_id)

    Filtering:
      - if allowed_types is None or empty -> send all types
      - if allowed_types has values -> send only those
        (cursor still advances for skipped types to avoid replay loops)
    """
    allowed_types = set(
        t.upper().strip() for t in (allowed_types or set()) if str(t).strip()
    )

    if allowed_types:
        log.info("Events polling filter enabled: %s", sorted(allowed_types))
    else:
        log.info("Events polling filter disabled (send all types).")

    log.info("Events polling loop started. interval=%ss limit=%s", poll_interval_s, per_user_limit)

    while True:
        try:
            bindings_raw = bindings_store.load()
            pairs = _iter_bindings(bindings_raw)

            # DBG (по умолчанию скрыто на INFO)
            log.debug("bindings_raw=%s", bindings_raw)
            log.debug("pairs=%s", pairs)

            if not pairs:
                await asyncio.sleep(max(1.0, poll_interval_s))
                continue

            by_user = _group_by_user(pairs)
            log.debug("by_user=%s", by_user)

            raw_state = state_store.load()
            state = _migrate_state_if_needed(raw_state=raw_state, pairs=pairs)  # chat_id -> last_event_id

            state_changed = False

            for user_id, chat_ids in by_user.items():
                # since = минимум по чатам (чтобы не потерять события)
                last_ids = [(_safe_int(state.get(str(chat_id))) or 0) for chat_id in chat_ids]
                min_last_id = min(last_ids) if last_ids else 0

                resp = await backend.get_my_events(
                    user_id=user_id,
                    since_audit_id=(min_last_id if min_last_id > 0 else None),
                    limit=per_user_limit,
                    offset=0,
                    event_type=None,  # фильтруем клиентом по allowed_types
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
                    log.info("No events: user_id=%s since=%s", user_id, (min_last_id if min_last_id > 0 else None))
                    continue

                events = resp.json
                # backend отдаёт DESC; доставляем oldest-first
                events_sorted = sorted(events, key=lambda e: int(e.get("event_id") or 0))
                log.info(
                    "Fetched events: user_id=%s since=%s count=%s",
                    user_id,
                    (min_last_id if min_last_id > 0 else None),
                    len(events_sorted),
                )

                for chat_id in chat_ids:
                    last_id = _safe_int(state.get(str(chat_id))) or 0
                    max_event_id = last_id

                    for ev in events_sorted:
                        ev_id = _safe_int(ev.get("event_id")) or 0
                        if ev_id <= last_id:
                            continue

                        ev_type = str(ev.get("event_type") or "").upper().strip()

                        # если фильтр включён — пропускаем "не наши" события,
                        # но курсор двигаем, чтобы не крутить одну и ту же пачку.
                        if allowed_types and ev_type not in allowed_types:
                            if ev_id > max_event_id:
                                max_event_id = ev_id
                            continue

                        text = render_event(ev)
                        try:
                            await application.bot.send_message(chat_id=chat_id, text=text)
                            if ev_id > max_event_id:
                                max_event_id = ev_id
                        except Exception:
                            # курсор НЕ двигаем для этого чата, если не доставили сообщение
                            log.exception(
                                "Failed to send event_id=%s to chat_id=%s (user_id=%s)",
                                ev_id,
                                chat_id,
                                user_id,
                            )
                            break

                    if max_event_id > last_id:
                        state[str(chat_id)] = max_event_id
                        state_changed = True

            if state_changed:
                # сохраняем ТОЛЬКО chat_id -> cursor
                state_store.save(state)

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Events polling loop cancelled.")
            raise
        except Exception:
            log.exception("Polling loop failure (outer). Backing off.")
            await asyncio.sleep(max(2.0, poll_interval_s))
