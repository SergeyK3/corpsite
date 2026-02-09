# FILE: corpsite-bot/src/bot/events_poller.py

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
from .storage.cursor_store import CursorStore

log = logging.getLogger("corpsite-bot.events")


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
    return _safe_int(ev.get("audit_id")) or _safe_int(ev.get("event_id")) or 0


def _sort_key(ev: Dict[str, Any]) -> int:
    return _event_cursor_id(ev)


def _sort_key_delivery(d: Dict[str, Any]) -> Tuple[int, int]:
    # Композитный порядок: (audit_id, user_id)
    return int(_safe_int(d.get("audit_id")) or 0), int(_safe_int(d.get("user_id")) or 0)


class JsonFileStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            # ВАЖНО: PowerShell/Set-Content может писать UTF-8 с BOM.
            # json.loads падает на BOM, поэтому читаем как utf-8-sig.
            raw = self.path.read_text(encoding="utf-8-sig").strip()
            if not raw:
                return {}
            val = json.loads(raw)
            return val if isinstance(val, dict) else {}
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
            # Пишем без BOM (обычный utf-8) и фиксируем переносы строк.
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(payload)
                f.write("\n")
            os.replace(tmp_path, self.path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


def _iter_bindings(bindings: Dict[str, Any]) -> Tuple[Tuple[int, int], ...]:
    """
    bindings store format (existing):
      { "<chat_id>": <user_id>, ... }
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
    m: DefaultDict[int, List[int]] = defaultdict(list)
    for chat_id, user_id in pairs:
        m[user_id].append(chat_id)
    return dict(m)


def _cursor_reset(cursor_store: CursorStore) -> None:
    try:
        if cursor_store.path.exists():
            cursor_store.path.unlink()
    except Exception:
        log.exception("Events cursor reset failed: %s", cursor_store.path)


def _extract_items_and_cursor(payload: Any) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Contract v1: {"items":[...], "next_cursor": <int>}
    Legacy fallback: [...]
    """
    if isinstance(payload, dict):
        items = payload.get("items")
        next_cursor = _safe_int(payload.get("next_cursor"))
        if isinstance(items, list):
            out: List[Dict[str, Any]] = [x for x in items if isinstance(x, dict)]
            return out, next_cursor
        return [], next_cursor

    if isinstance(payload, list):
        out2: List[Dict[str, Any]] = [x for x in payload if isinstance(x, dict)]
        return out2, None

    return [], None


def _extract_items_and_delivery_cursor(
    payload: Any,
) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int], Optional[int]]:
    """
    Delivery queue response (new):
      {"items":[...], "next_cursor_audit_id": int, "next_cursor_user_id": int, "next_cursor": int(legacy)}
    Also supports legacy:
      {"items":[...], "next_cursor": int}
    """
    if not isinstance(payload, dict):
        items, nc = _extract_items_and_cursor(payload)
        return items, nc, None, None

    items_raw = payload.get("items")
    items: List[Dict[str, Any]] = [x for x in items_raw if isinstance(x, dict)] if isinstance(items_raw, list) else []

    next_cursor = _safe_int(payload.get("next_cursor"))
    next_audit = _safe_int(payload.get("next_cursor_audit_id"))
    next_user = _safe_int(payload.get("next_cursor_user_id"))

    # если отдали только legacy next_cursor — считаем, что user_id = 0
    if next_audit is None and next_cursor is not None:
        next_audit = next_cursor
        next_user = 0

    return items, next_cursor, next_audit, next_user


def _use_delivery_queue_mode() -> bool:
    # recommended: EVENTS_USE_DELIVERY_QUEUE=1
    return _truthy_env("EVENTS_USE_DELIVERY_QUEUE")


def _delivery_internal_user_id() -> int:
    # who can call /tasks/internal/...
    v = _safe_int(os.getenv("EVENTS_INTERNAL_API_USER_ID"))
    return int(v or 1)


def _delivery_channel() -> str:
    ch = (os.getenv("EVENTS_DELIVERY_CHANNEL") or "telegram").strip()
    return ch or "telegram"


def _delivery_cursor_key() -> int:
    # cursor_store key; default 0 (shared cursor)
    v = _safe_int(os.getenv("EVENTS_DELIVERY_CURSOR_KEY"))
    return int(v or 0)


def _ack_on_partial_success() -> bool:
    # if user has multiple chat_ids and at least one succeeded -> SENT
    return _truthy_env("EVENTS_ACK_ON_PARTIAL_SUCCESS")


def _data_dir() -> Path:
    # backend style: DATA_DIR, но у бота может быть не задан — дефолт ./data
    raw = (os.getenv("DATA_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path("data")


def _delivery_cursor_file(channel: str) -> JsonFileStore:
    # совместимо с тем, что ты руками создавал: events_cursor_telegram.json
    fname = f"events_cursor_{(channel or 'telegram').strip().lower()}.json"
    return JsonFileStore(_data_dir() / fname)


def _load_delivery_cursor(store: JsonFileStore) -> Tuple[int, int]:
    d = store.load() or {}
    a = _safe_int(d.get("cursor_audit_id")) or 0
    u = _safe_int(d.get("cursor_user_id")) or 0
    if a < 0:
        a = 0
    if u < 0:
        u = 0
    return int(a), int(u)


def _save_delivery_cursor(store: JsonFileStore, audit_id: int, user_id: int) -> None:
    store.save({"cursor_audit_id": int(max(0, audit_id)), "cursor_user_id": int(max(0, user_id))})


def _cursor_gt(a1: Tuple[int, int], a2: Tuple[int, int]) -> bool:
    # True if a1 > a2 lexicographically (audit_id, user_id)
    return a1[0] > a2[0] or (a1[0] == a2[0] and a1[1] > a2[1])


def _cursor_le(a1: Tuple[int, int], a2: Tuple[int, int]) -> bool:
    # True if a1 <= a2
    return (a1[0] < a2[0]) or (a1[0] == a2[0] and a1[1] <= a2[1])


async def _poll_per_user_events(
    *,
    application: Application,
    backend: CorpsiteAPI,
    poll_interval_s: float,
    bindings_store: JsonFileStore,
    state_store: Optional[JsonFileStore],
    cursor_store: CursorStore,
    per_user_limit: int,
    allowed_types: Set[str],
) -> None:
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

            if not did_reset and _truthy_env("EVENTS_CURSOR_RESET"):
                did_reset = True
                _cursor_reset(cursor_store)
                if state_store is not None:
                    try:
                        state_store.save({})
                    except Exception:
                        pass
                log.info("Events cursor reset: store cleared (EVENTS_CURSOR_RESET=1)")

            for user_id, chat_ids in by_user.items():
                since_val = cursor_store.get(int(user_id), default=0)

                resp = await backend.get_my_events(
                    user_id=int(user_id),
                    since_audit_id=since_val if since_val > 0 else None,
                    limit=int(per_user_limit),
                    offset=0,
                    event_type=None,
                )

                if resp.status_code != 200:
                    log.warning("get_my_events failed: user_id=%s status=%s", user_id, resp.status_code)
                    continue

                events, next_cursor = _extract_items_and_cursor(resp.json)

                if not events:
                    now = time.time()
                    prev = no_events_log_state.get(user_id)
                    prev_since = prev[0] if prev else -1
                    prev_ts = prev[1] if prev else 0.0

                    if since_val != prev_since or now - prev_ts >= 60.0:
                        log.info("No events: user_id=%s since=%s next_cursor=%s", user_id, since_val or None, next_cursor)
                        no_events_log_state[user_id] = (since_val, now)

                    if next_cursor is not None and next_cursor > since_val:
                        cursor_store.set(int(user_id), int(next_cursor))
                    continue

                no_events_log_state.pop(user_id, None)

                events_sorted = sorted(events, key=_sort_key)

                log.info(
                    "Fetched events: user_id=%s since=%s count=%s next_cursor=%s",
                    user_id,
                    since_val or None,
                    len(events_sorted),
                    next_cursor,
                )

                last_cursor = int(since_val or 0)
                max_seen_cursor = last_cursor
                delivery_ok = True

                for ev in events_sorted:
                    cursor_id = _event_cursor_id(ev)
                    if cursor_id <= last_cursor:
                        continue

                    ev_type = str(ev.get("event_type") or "").upper()

                    if allowed_types and ev_type not in allowed_types:
                        max_seen_cursor = max(max_seen_cursor, cursor_id)
                        continue

                    rendered = render_event(ev)

                    for chat_id in chat_ids:
                        try:
                            await application.bot.send_message(chat_id=int(chat_id), text=rendered)
                        except Exception:
                            log.exception("Send failed: chat_id=%s user_id=%s cursor_id=%s", chat_id, user_id, cursor_id)
                            delivery_ok = False
                            break

                    if not delivery_ok:
                        break

                    max_seen_cursor = max(max_seen_cursor, cursor_id)

                if not delivery_ok:
                    continue

                candidate_cursor = max_seen_cursor
                if next_cursor is not None:
                    candidate_cursor = max(candidate_cursor, int(next_cursor))

                if candidate_cursor > last_cursor:
                    cursor_store.set(int(user_id), int(candidate_cursor))

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Events polling cancelled")
            raise
        except Exception:
            log.exception("Events polling failure (per-user loop)")
            await asyncio.sleep(max(2.0, poll_interval_s))


async def _poll_delivery_queue(
    *,
    application: Application,
    backend: CorpsiteAPI,
    poll_interval_s: float,
    bindings_store: JsonFileStore,
    cursor_store: CursorStore,
    per_user_limit: int,
    allowed_types: Set[str],
) -> None:
    """
    Delivery-queue mode:
      - fetch pending deliveries for channel=telegram via internal endpoint
      - send to chat_id resolved by payload.telegram_chat_id (preferred) or bindings fallback
      - ack SENT/FAILED in backend to resolve telegram/PENDING
      - maintain shared composite cursor (audit_id,user_id) in DATA_DIR/events_cursor_<channel>.json
    """
    last_no_bindings_log_ts = 0.0
    did_reset = False

    internal_user_id = _delivery_internal_user_id()
    channel = _delivery_channel()
    cursor_key = _delivery_cursor_key()
    partial_ok = _ack_on_partial_success()

    cursor_file = _delivery_cursor_file(channel)

    log.info(
        "Delivery queue polling enabled. internal_user_id=%s channel=%s cursor_key=%s partial_ok=%s cursor_file=%s",
        internal_user_id,
        channel,
        cursor_key,
        partial_ok,
        str(cursor_file.path),
    )

    while True:
        try:
            bindings_raw = bindings_store.load()
            pairs = _iter_bindings(bindings_raw)

            by_user: Dict[int, List[int]] = {}
            if pairs:
                by_user = _group_by_user(pairs)
            else:
                now = time.time()
                if now - last_no_bindings_log_ts >= 60.0:
                    last_no_bindings_log_ts = now
                    log.info("Delivery queue polling: no bindings (will rely on telegram_chat_id from backend)")

            if not did_reset and _truthy_env("EVENTS_CURSOR_RESET"):
                did_reset = True
                _cursor_reset(cursor_store)
                try:
                    if cursor_file.path.exists():
                        cursor_file.path.unlink()
                except Exception:
                    log.exception("Delivery queue cursor reset failed: %s", cursor_file.path)
                log.info("Delivery queue cursor reset: stores cleared (EVENTS_CURSOR_RESET=1)")

            cur_audit, cur_user = _load_delivery_cursor(cursor_file)
            since_tuple = (int(cur_audit), int(cur_user))

            legacy_since = int(cursor_store.get(int(cursor_key), default=0) or 0)
            if legacy_since > since_tuple[0]:
                since_tuple = (legacy_since, 0)
                _save_delivery_cursor(cursor_file, since_tuple[0], since_tuple[1])

            try:
                resp = await backend.get_pending_deliveries(
                    user_id=int(internal_user_id),
                    channel=str(channel),
                    cursor_from=int(since_tuple[0]),
                    cursor_user_id=int(since_tuple[1]),
                    limit=int(per_user_limit),
                )
            except TypeError:
                resp = await backend.get_pending_deliveries(
                    user_id=int(internal_user_id),
                    channel=str(channel),
                    cursor_from=int(since_tuple[0]),
                    limit=int(per_user_limit),
                )

            if resp.status_code != 200:
                log.warning(
                    "get_pending_deliveries failed: status=%s internal_user_id=%s channel=%s since=%s",
                    resp.status_code,
                    internal_user_id,
                    channel,
                    since_tuple,
                )
                await asyncio.sleep(max(2.0, poll_interval_s))
                continue

            items, next_cursor_legacy, next_audit, next_user = _extract_items_and_delivery_cursor(resp.json)

            if not items:
                candidate = since_tuple
                if next_audit is not None and next_user is not None:
                    nc = (int(next_audit), int(next_user))
                    if _cursor_gt(nc, candidate):
                        candidate = nc
                elif next_cursor_legacy is not None:
                    nc2 = (int(next_cursor_legacy), 0)
                    if _cursor_gt(nc2, candidate):
                        candidate = nc2

                if _cursor_gt(candidate, since_tuple):
                    _save_delivery_cursor(cursor_file, candidate[0], candidate[1])
                    cursor_store.set(int(cursor_key), int(candidate[0]))
                await asyncio.sleep(max(1.0, poll_interval_s))
                continue

            items_sorted = sorted(items, key=_sort_key_delivery)

            log.info(
                "Fetched pending deliveries: channel=%s since=%s count=%s next=(%s,%s) legacy_next=%s",
                channel,
                since_tuple,
                len(items_sorted),
                next_audit,
                next_user,
                next_cursor_legacy,
            )

            current_cursor = since_tuple

            for d in items_sorted:
                audit_id = int(_safe_int(d.get("audit_id")) or 0)
                delivery_user_id = int(_safe_int(d.get("user_id")) or 0)
                item_tuple = (audit_id, delivery_user_id)

                if _cursor_le(item_tuple, current_cursor):
                    continue

                ev_type = str(d.get("event_type") or "").upper()
                if allowed_types and ev_type not in allowed_types:
                    current_cursor = item_tuple
                    _save_delivery_cursor(cursor_file, current_cursor[0], current_cursor[1])
                    cursor_store.set(int(cursor_key), int(current_cursor[0]))
                    continue

                tg_chat_id = _safe_int(d.get("telegram_chat_id"))

                if tg_chat_id:
                    chat_ids = [int(tg_chat_id)]
                else:
                    chat_ids = by_user.get(int(delivery_user_id)) or []

                if not chat_ids:
                    try:
                        await backend.ack_delivery(
                            user_id=int(internal_user_id),
                            audit_id=int(audit_id),
                            delivery_user_id=int(delivery_user_id),
                            channel=str(channel),
                            status="FAILED",
                            error_code="NO_BINDING",
                            error_text=f"no telegram_chat_id and no local binding for user_id={delivery_user_id}",
                        )
                    except Exception:
                        log.exception("ack_delivery failed: audit_id=%s delivery_user_id=%s status=FAILED", audit_id, delivery_user_id)

                    current_cursor = item_tuple
                    _save_delivery_cursor(cursor_file, current_cursor[0], current_cursor[1])
                    cursor_store.set(int(cursor_key), int(current_cursor[0]))
                    continue

                rendered = render_event(d)

                ok_count = 0
                fail_count = 0
                first_err: Optional[str] = None

                for chat_id in chat_ids:
                    try:
                        await application.bot.send_message(chat_id=int(chat_id), text=rendered)
                        ok_count += 1
                    except Exception as e:
                        fail_count += 1
                        if first_err is None:
                            first_err = repr(e)
                        log.exception(
                            "Send failed: chat_id=%s delivery_user_id=%s audit_id=%s",
                            chat_id,
                            delivery_user_id,
                            audit_id,
                        )

                delivered_ok = (ok_count > 0) if partial_ok else (fail_count == 0)

                if delivered_ok:
                    try:
                        await backend.ack_delivery(
                            user_id=int(internal_user_id),
                            audit_id=int(audit_id),
                            delivery_user_id=int(delivery_user_id),
                            channel=str(channel),
                            status="SENT",
                        )
                    except Exception:
                        log.exception("ack_delivery failed: audit_id=%s delivery_user_id=%s status=SENT", audit_id, delivery_user_id)
                else:
                    try:
                        await backend.ack_delivery(
                            user_id=int(internal_user_id),
                            audit_id=int(audit_id),
                            delivery_user_id=int(delivery_user_id),
                            channel=str(channel),
                            status="FAILED",
                            error_code="SEND_ERROR",
                            error_text=f"send failed ok={ok_count} fail={fail_count} err={first_err or 'unknown'}",
                        )
                    except Exception:
                        log.exception("ack_delivery failed: audit_id=%s delivery_user_id=%s status=FAILED", audit_id, delivery_user_id)

                # ВАЖНО: курсор двигаем после обработки элемента (успех/ошибка) — чтобы не слать повторно
                current_cursor = item_tuple
                _save_delivery_cursor(cursor_file, current_cursor[0], current_cursor[1])
                cursor_store.set(int(cursor_key), int(current_cursor[0]))

            # optional jump by next_cursor_* (без регресса)
            candidate = current_cursor
            if next_audit is not None and next_user is not None:
                nc = (int(next_audit), int(next_user))
                if _cursor_gt(nc, candidate):
                    candidate = nc
            elif next_cursor_legacy is not None:
                nc2 = (int(next_cursor_legacy), 0)
                if _cursor_gt(nc2, candidate):
                    candidate = nc2

            if _cursor_gt(candidate, current_cursor):
                current_cursor = candidate
                _save_delivery_cursor(cursor_file, current_cursor[0], current_cursor[1])
                cursor_store.set(int(cursor_key), int(current_cursor[0]))

            await asyncio.sleep(max(1.0, poll_interval_s))

        except asyncio.CancelledError:
            log.info("Delivery queue polling cancelled")
            raise
        except Exception:
            log.exception("Delivery queue polling failure (outer loop)")
            await asyncio.sleep(max(2.0, poll_interval_s))


async def events_polling_loop(
    *,
    application: Application,
    backend: CorpsiteAPI,
    poll_interval_s: float,
    bindings_store: JsonFileStore,
    state_store: Optional[JsonFileStore] = None,
    cursor_store: CursorStore,
    per_user_limit: int = 200,
    allowed_types: Optional[Set[str]] = None,
) -> None:
    allowed_types_norm = {t.upper().strip() for t in (allowed_types or set()) if str(t).strip()}

    log.info(
        "Events polling started. mode=%s interval=%ss limit=%s allowed_types=%s cursor_file=%s",
        "delivery-queue" if _use_delivery_queue_mode() else "per-user",
        poll_interval_s,
        per_user_limit,
        sorted(allowed_types_norm) if allowed_types_norm else "ALL",
        str(cursor_store.path),
    )

    if _use_delivery_queue_mode():
        await _poll_delivery_queue(
            application=application,
            backend=backend,
            poll_interval_s=poll_interval_s,
            bindings_store=bindings_store,
            cursor_store=cursor_store,
            per_user_limit=per_user_limit,
            allowed_types=allowed_types_norm,
        )
        return

    await _poll_per_user_events(
        application=application,
        backend=backend,
        poll_interval_s=poll_interval_s,
        bindings_store=bindings_store,
        state_store=state_store,
        cursor_store=cursor_store,
        per_user_limit=per_user_limit,
        allowed_types=allowed_types_norm,
    )
