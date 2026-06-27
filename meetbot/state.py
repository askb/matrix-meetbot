# SPDX-License-Identifier: BSD-3-Clause
"""Per-room meeting state with restart resilience.

IRC MeetBot loses an in-progress meeting on restart. We get a cheap reliability
upgrade on Matrix: every accepted line is journaled to disk (JSONL per room).
On startup, any journal left behind is replayed into a fresh engine instance
(with replies suppressed) so an interrupted meeting resumes transparently.
"""

from __future__ import annotations

import json
import os
import time
from typing import Callable, Dict, Optional

# factory(room_id, owner_nick) -> engine Meeting object
MeetingFactory = Callable[[str, str], object]


def _safe_name(room_id: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in room_id)


class StateStore:
    """Tracks active meetings keyed by room id, with on-disk journaling."""

    def __init__(self, state_dir: str, factory: MeetingFactory) -> None:
        self.state_dir = state_dir
        self.factory = factory
        self.meetings: Dict[str, object] = {}
        os.makedirs(state_dir, exist_ok=True)

    def _journal_path(self, room_id: str) -> str:
        return os.path.join(self.state_dir, f"{_safe_name(room_id)}.jsonl")

    def get(self, room_id: str) -> Optional[object]:
        return self.meetings.get(room_id)

    def start(self, room_id: str, owner_nick: str) -> object:
        """Create and register a new meeting for a room."""
        meeting = self.factory(room_id, owner_nick)
        self.meetings[room_id] = meeting
        with open(self._journal_path(room_id), "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"_meta": {"owner": owner_nick, "room_id": room_id}}) + "\n"
            )
        return meeting

    def journal(self, room_id: str, nick: str, line: str, ts: float) -> None:
        """Append an accepted line to the room journal."""
        path = self._journal_path(room_id)
        if not os.path.exists(path):
            return
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"nick": nick, "line": line, "ts": ts}) + "\n")

    def end(self, room_id: str) -> None:
        """Finish a meeting and remove its journal."""
        self.meetings.pop(room_id, None)
        path = self._journal_path(room_id)
        if os.path.exists(path):
            os.remove(path)

    def resume_all(self) -> Dict[str, object]:
        """Replay any leftover journals into suppressed engine instances."""
        resumed: Dict[str, object] = {}
        if not os.path.isdir(self.state_dir):
            return resumed
        for fname in os.listdir(self.state_dir):
            if not fname.endswith(".jsonl"):
                continue
            path = os.path.join(self.state_dir, fname)
            records = []
            owner = "unknown"
            room_id = None
            with open(path, "r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    rec = json.loads(raw)
                    if "_meta" in rec:
                        owner = rec["_meta"].get("owner", owner)
                        room_id = rec["_meta"].get("room_id", room_id)
                    else:
                        records.append(rec)
            if not records or not room_id:
                continue
            meeting = self.factory(room_id, owner)
            meeting._lurk = True  # suppress re-posting replies during replay
            for rec in records:
                meeting.addline(rec["nick"], rec["line"], time_=time.gmtime(rec["ts"]))
            meeting._lurk = False
            self.meetings[room_id] = meeting
            resumed[room_id] = meeting
        return resumed
