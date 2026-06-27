# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the Matrix->engine dispatch bridge using fakes (no real server)."""

import asyncio
import os
import time

import pytest

from meetbot.config import Config
from meetbot.dispatch import Dispatcher
from meetbot.identity import Identity


class FakeClient:
    def __init__(self):
        self.sent = []
        self.topics = []

    async def send_text(self, room_id, text):
        self.sent.append((room_id, text))

    async def set_topic(self, room_id, topic):
        self.topics.append((room_id, topic))


class FakeRoom:
    def __init__(self, room_id="!room:example.org"):
        self.room_id = room_id


class FakeEvent:
    def __init__(self, sender, body, ts_ms, msgtype="m.text", reply_to=None):
        self.sender = sender
        self.body = body
        self.server_timestamp = ts_ms
        content = {"msgtype": msgtype, "body": body}
        if reply_to:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
        self.source = {"content": content}


def make_dispatcher(tmp_path):
    cfg = Config(
        homeserver="https://h",
        user_id="@meetbot:example.org",
        access_token="t",
        rooms=["!room:example.org"],
        output_dir=str(tmp_path / "meetings"),
        state_dir=str(tmp_path / "state"),
        base_url="https://pages/",
        meeting_name="meetbot-poc",
    )
    os.makedirs(cfg.output_dir, exist_ok=True)
    os.makedirs(cfg.state_dir, exist_ok=True)
    client = FakeClient()
    disp = Dispatcher(client, cfg, Identity(), start_ts_ms=0)
    return disp, client, cfg


def feed(disp, room, events):
    for ev in events:
        asyncio.run(disp.on_message(room, ev))


def test_bridge_runs_full_meeting(tmp_path):
    disp, client, cfg = make_dispatcher(tmp_path)
    room = FakeRoom()
    ts = int(time.time() * 1000)
    events = [
        FakeEvent("@alice:example.org", "#startmeeting Weekly Sync", ts + 1),
        FakeEvent("@alice:example.org", "#topic CI status", ts + 2),
        FakeEvent("@bob:example.org", "CI is green", ts + 3),
        FakeEvent("@alice:example.org", "#action bob to upgrade nodepool", ts + 4),
        FakeEvent("@alice:example.org", "#endmeeting", ts + 5),
    ]
    feed(disp, room, events)

    # Engine replies were posted into the room (start + end + minute URLs).
    bodies = " ".join(t for _r, t in client.sent)
    assert "Meeting started" in bodies
    assert "Minutes" in bodies
    # Output files exist; meeting de-registered after endmeeting.
    assert disp.state.get(room.room_id) is None
    produced = [f for _r, _d, fs in os.walk(cfg.output_dir) for f in fs]
    assert any(f.endswith(".html") for f in produced)


def test_ignores_messages_outside_meeting(tmp_path):
    disp, client, _ = make_dispatcher(tmp_path)
    room = FakeRoom()
    ts = int(time.time() * 1000)
    feed(disp, room, [FakeEvent("@bob:example.org", "just chatting", ts + 1)])
    assert disp.state.get(room.room_id) is None
    assert client.sent == []


def test_ignores_own_messages_and_old_events(tmp_path):
    disp, client, cfg = make_dispatcher(tmp_path)
    disp.start_ts_ms = 1000
    room = FakeRoom()
    # Own message ignored even if it would start a meeting.
    feed(disp, room, [FakeEvent(cfg.user_id, "#startmeeting X", 2000)])
    assert disp.state.get(room.room_id) is None
    # Pre-start event ignored.
    feed(disp, room, [FakeEvent("@alice:example.org", "#startmeeting X", 500)])
    assert disp.state.get(room.room_id) is None


def test_reply_fallback_stripped(tmp_path):
    disp, _client, _cfg = make_dispatcher(tmp_path)
    room = FakeRoom()
    ts = int(time.time() * 1000)
    feed(disp, room, [FakeEvent("@alice:example.org", "#startmeeting X", ts + 1)])
    body = "> <@bob:example.org> earlier message\n\n#info real content"
    feed(
        disp,
        room,
        [FakeEvent("@alice:example.org", body, ts + 2, reply_to="$evt")],
    )
    meeting_obj = disp.state.get(room.room_id)
    rendered = " ".join(str(m) for m in meeting_obj.minutes)
    assert "real content" in rendered
    assert "earlier message" not in rendered


def test_restart_resume(tmp_path):
    disp, _client, cfg = make_dispatcher(tmp_path)
    room = FakeRoom()
    ts = int(time.time() * 1000)
    feed(
        disp,
        room,
        [
            FakeEvent("@alice:example.org", "#startmeeting Resumable", ts + 1),
            FakeEvent("@alice:example.org", "#info before crash", ts + 2),
        ],
    )
    # Simulate a fresh process: new dispatcher, same state dir.
    client2 = FakeClient()
    disp2 = Dispatcher(client2, cfg, Identity(), start_ts_ms=0)
    disp2.resume()
    resumed = disp2.state.get(room.room_id)
    assert resumed is not None
    rendered = " ".join(str(m) for m in resumed.minutes)
    assert "before crash" in rendered
    # Resume must not re-post the old replies.
    assert client2.sent == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
