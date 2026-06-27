# SPDX-License-Identifier: BSD-3-Clause
"""Unit tests over the vendored engine (no Matrix required)."""

import os
import time

import pytest

from meetbot.engine import meeting as engine


def run_meeting(lines, outdir, name="opendev-meeting", owner="alice"):
    replies = []
    meeting_obj = engine.Meeting(
        channel=name,
        owner=owner,
        sendReply=replies.append,
        setTopic=lambda _t: None,
        writeRawLog=True,
        extraConfig={"logFileDir": str(outdir), "logUrlPrefix": "https://x/"},
        network="matrix",
    )
    t = time.gmtime()
    for nick, line in lines:
        meeting_obj.addline(nick, line, time_=t)
    return meeting_obj, replies


def test_full_meeting_writes_outputs(tmp_path):
    meeting_obj, replies = run_meeting(
        [
            ("alice", "#startmeeting Weekly Sync"),
            ("alice", "#topic CI status"),
            ("bob", "CI looks green"),
            ("alice", "#info gate queue short"),
            ("alice", "#action bob to upgrade nodepool"),
            ("alice", "#agreed proceed"),
            ("alice", "#endmeeting"),
        ],
        tmp_path,
    )
    assert meeting_obj._meetingIsOver is True
    produced = []
    for root, _dirs, files in os.walk(tmp_path):
        produced += [f for f in files]
    # OpenDev parity: html, txt, log.html, log.txt
    joined = " ".join(produced)
    for ext in (".html", ".txt", ".log.html", ".log.txt"):
        assert any(p.endswith(ext) for p in produced), f"missing {ext} in {produced}"
    # Minute URLs are posted on endmeeting
    assert any("Minutes" in r for r in replies)


def test_chair_authorization(tmp_path):
    # mallory is not a chair; her #endmeeting before time should be ignored.
    meeting_obj, _ = run_meeting(
        [
            ("alice", "#startmeeting Test"),
            ("mallory", "#endmeeting"),
        ],
        tmp_path,
    )
    assert meeting_obj._meetingIsOver is False


def test_undo_removes_last_item(tmp_path):
    meeting_obj, _ = run_meeting(
        [
            ("alice", "#startmeeting Test"),
            ("alice", "#info first"),
            ("alice", "#info second"),
            ("alice", "#undo"),
        ],
        tmp_path,
    )
    rendered = " ".join(str(m) for m in meeting_obj.minutes)
    assert "second" not in rendered
    assert "first" in rendered


def test_emote_logged_as_action(tmp_path):
    meeting_obj, _ = run_meeting(
        [
            ("alice", "#startmeeting Test"),
            ("carol", "ACTION waves hello"),
        ],
        tmp_path,
    )
    assert any("* carol waves hello" in line for line in meeting_obj.lines)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
