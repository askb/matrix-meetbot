# SPDX-License-Identifier: BSD-3-Clause
"""Dispatch Matrix events into the ported MeetBot engine.

This is the transport bridge. The engine (vendored ``meetbot.engine``) is
synchronous and IRC-shaped: it consumes lines via ``Meeting.addline(nick, line,
time_)`` and parses ``#commands`` itself. matrix-nio is async. This module
converts each ``m.room.message`` event into an engine line and flushes any
engine replies (start/end messages, minute URLs) back into the room.
"""

from __future__ import annotations

import time
from typing import Tuple

from .config import Config
from .engine import meeting as engine
from .identity import Identity
from .state import StateStore

_STARTMEETING_PREFIX = "#startmeeting"


def _strip_reply_fallback(body: str, is_reply: bool) -> str:
    """Remove Matrix's quoted reply fallback (lines beginning ``> ``)."""
    if not is_reply:
        return body
    lines = body.split("\n")
    idx = 0
    while idx < len(lines) and (lines[idx].startswith("> ") or lines[idx] == ""):
        idx += 1
    return "\n".join(lines[idx:]).strip() or body


class Dispatcher:
    """Routes room messages to per-room :class:`Meeting` engine instances."""

    def __init__(self, client, cfg: Config, identity: Identity, start_ts_ms: float) -> None:
        self.client = client
        self.cfg = cfg
        self.identity = identity
        self.start_ts_ms = start_ts_ms
        self.state = StateStore(cfg.state_dir, self._make_meeting)

    def _make_meeting(self, room_id: str, owner_nick: str) -> object:
        """Engine factory wiring sendReply/setTopic to per-meeting buffers."""
        reply_buf: list = []
        topic_buf: list = []
        meeting_obj = engine.Meeting(
            channel=self.cfg.meeting_name,
            owner=owner_nick,
            sendReply=reply_buf.append,
            setTopic=topic_buf.append,
            writeRawLog=True,  # also emit .log.txt for OpenDev parity
            extraConfig={
                "logFileDir": self.cfg.output_dir,
                "logUrlPrefix": self.cfg.base_url,
                "MeetBotInfoURL": self.cfg.info_url,
            },
            network="matrix",
        )
        meeting_obj._reply_buf = reply_buf
        meeting_obj._topic_buf = topic_buf
        meeting_obj._room_id = room_id
        return meeting_obj

    def resume(self) -> None:
        """Resume any meetings interrupted by a restart."""
        resumed = self.state.resume_all()
        for room_id in resumed:
            print(f"[meetbot] resumed in-progress meeting in {room_id}")

    @staticmethod
    def _extract(event) -> Tuple[str, bool, bool]:
        """Return (body, is_emote, is_reply) for a message event."""
        body = getattr(event, "body", "") or ""
        msgtype = (event.source.get("content", {}) or {}).get("msgtype", "")
        is_emote = msgtype == "m.emote"
        relates = (event.source.get("content", {}) or {}).get("m.relates_to", {}) or {}
        is_reply = "m.in_reply_to" in relates
        return body, is_emote, is_reply

    async def on_message(self, room, event) -> None:
        # Ignore our own messages and anything from before we started syncing.
        if event.sender == self.cfg.user_id:
            return
        if getattr(event, "server_timestamp", 0) < self.start_ts_ms:
            return

        body, is_emote, is_reply = self._extract(event)
        body = _strip_reply_fallback(body, is_reply).strip()
        if not body:
            return

        nick = self.identity.nick(event.sender)
        self.identity.remember(event.sender, getattr(event, "sender", nick))
        ts_epoch = event.server_timestamp / 1000.0
        ts = time.gmtime(ts_epoch)

        meeting_obj = self.state.get(room.room_id)
        if meeting_obj is None:
            if not body.lower().startswith(_STARTMEETING_PREFIX):
                return  # only log inside an active meeting
            meeting_obj = self.state.start(room.room_id, nick)

        line = ("ACTION " + body) if is_emote else body
        meeting_obj.addline(nick, line, time_=ts)
        self.state.journal(room.room_id, nick, line, ts_epoch)

        # Flush engine replies and topic changes back to the room.
        while meeting_obj._reply_buf:
            await self.client.send_text(room.room_id, meeting_obj._reply_buf.pop(0))
        while meeting_obj._topic_buf:
            await self.client.set_topic(room.room_id, meeting_obj._topic_buf.pop(0))

        if getattr(meeting_obj, "_meetingIsOver", False):
            self.state.end(room.room_id)
