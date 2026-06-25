# tests/test_ops026_events_poller_render_event.py
# -*- coding: utf-8 -*-
"""OPS-026.1a — events_poller must import render_event (delivery + legacy poll paths)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Iterable

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT_SRC = ROOT / "corpsite-bot" / "src"


def _import_events_poller():
    bot_src = str(BOT_SRC)
    if bot_src not in sys.path:
        sys.path.insert(0, bot_src)
    import bot.events_poller as events_poller  # noqa: WPS433

    return events_poller


def test_events_poller_module_imports_without_name_error() -> None:
    mod = _import_events_poller()
    assert callable(getattr(mod, "render_event", None))


def _assert_render_structure(
    rendered: str,
    *,
    emoji: str,
    task_id: int,
    title: str,
    required_fragments: Iterable[str] = (),
) -> None:
    assert isinstance(rendered, str)
    assert rendered.strip()
    assert emoji in rendered
    assert f"№{task_id}" in rendered
    assert title in rendered
    assert "\n" in rendered
    for fragment in required_fragments:
        assert fragment in rendered


@pytest.mark.parametrize(
    ("event", "emoji", "title", "required_fragments"),
    [
        (
            {
                "audit_id": 10,
                "task_id": 100,
                "event_type": "REPORT_SUBMITTED",
                "payload": {
                    "task_title": "Pilot task report",
                    "report_link": "https://example.com/r",
                },
            },
            "🟦",
            "Pilot task report",
            ("https://example.com/r",),
        ),
        (
            {
                "audit_id": 11,
                "task_id": 101,
                "event_type": "APPROVED",
                "user_id": 2,
                "payload": {"task_title": "Pilot task approved", "current_comment": "OK"},
            },
            "🟩",
            "Pilot task approved",
            ("DONE", "OK"),
        ),
        (
            {
                "audit_id": 12,
                "task_id": 102,
                "event_type": "REJECTED",
                "user_id": 3,
                "payload": {"task_title": "Pilot task rejected", "current_comment": "Fix report"},
            },
            "🟥",
            "Pilot task rejected",
            ("WAITING_REPORT", "Fix report"),
        ),
    ],
)
def test_render_event_delivery_and_legacy_poll_shapes(
    event: Dict[str, Any],
    emoji: str,
    title: str,
    required_fragments: tuple[str, ...],
) -> None:
    mod = _import_events_poller()
    rendered = mod.render_event(event)
    _assert_render_structure(
        rendered,
        emoji=emoji,
        task_id=int(event["task_id"]),
        title=title,
        required_fragments=required_fragments,
    )
