#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Replay a scripted meeting transcript into a room (headless CI driver).

Logs in as a demo user, joins the target room, and sends each line of a
transcript with a small delay so the meetbot processes them in order. Lines
prefixed with ``/me `` are sent as m.emote.

Env:
  HS_URL       homeserver base URL (default http://localhost:8008)
  DRIVER_USER  demo user localpart (default alice)
  DRIVER_PASS  demo user password (default alice-pass)
  ROOM_ID      target room id (required)
  TRANSCRIPT   path to transcript file (required)
  LINE_DELAY   seconds between lines (default 0.6)
"""

import asyncio
import os
import sys


async def main() -> int:
    from nio import AsyncClient

    hs = os.environ.get("HS_URL", "http://localhost:8008")
    server = os.environ.get("SERVER_NAME", "meetbot.local")
    user = os.environ.get("DRIVER_USER", "alice")
    password = os.environ.get("DRIVER_PASS", "alice-pass")
    room_id = os.environ["ROOM_ID"]
    transcript = os.environ["TRANSCRIPT"]
    delay = float(os.environ.get("LINE_DELAY", "0.6"))

    with open(transcript, "r", encoding="utf-8") as handle:
        lines = [ln.rstrip("\n") for ln in handle if ln.strip()]

    client = AsyncClient(hs, f"@{user}:{server}")
    login = await client.login(password, device_name="DRIVER")
    if not getattr(login, "access_token", None):
        print(f"driver login failed: {login}", file=sys.stderr)
        await client.close()
        return 1

    await client.join(room_id)
    # Let the bot finish its initial sync before we start talking.
    await asyncio.sleep(3)

    for line in lines:
        if line.startswith("/me "):
            content = {"msgtype": "m.emote", "body": line[4:]}
        else:
            content = {"msgtype": "m.text", "body": line}
        await client.room_send(room_id, "m.room.message", content)
        print(f"  > {line}")
        await asyncio.sleep(delay)

    # Give the bot time to render and post the final minutes.
    await asyncio.sleep(4)
    await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
