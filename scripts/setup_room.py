#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Log the bot in (password -> token) and create the meeting room.

Prints shell-evaluable assignments so a workflow can `eval "$(... )"`:
    MEETBOT_USER_ID=... MEETBOT_DEVICE_ID=... MEETBOT_ACCESS_TOKEN=... ROOM_ID=...

Env:
  HS_URL          homeserver base URL (default http://localhost:8008)
  BOT_USER        bot localpart (default meetbot)
  BOT_PASS        bot password (default meetbot-pass)
  ROOM_ALIAS      optional room alias localpart (default meetbot-poc)
  INVITE          comma-separated MXIDs to invite
"""

import asyncio
import os
import sys

from nio import AsyncClient, RoomCreateResponse, RoomPreset


async def main() -> int:
    hs = os.environ.get("HS_URL", "http://localhost:8008")
    server = os.environ.get("SERVER_NAME", "meetbot.local")
    bot_user = os.environ.get("BOT_USER", "meetbot")
    bot_pass = os.environ.get("BOT_PASS", "meetbot-pass")
    alias = os.environ.get("ROOM_ALIAS", "")
    invite = [m for m in os.environ.get("INVITE", "").split(",") if m]

    mxid = f"@{bot_user}:{server}"
    client = AsyncClient(hs, mxid)
    login = await client.login(bot_pass, device_name="MEETBOT")
    if not getattr(login, "access_token", None):
        print(f"login failed: {login}", file=sys.stderr)
        await client.close()
        return 1

    create_kwargs = dict(
        name="MeetBot POC (unofficial — not an OpenDev service)",
        topic="Personal MeetBot POC — not affiliated with OpenDev. Use #startmeeting <name>.",
        preset=RoomPreset.public_chat,
        invite=invite,
    )
    if alias:
        create_kwargs["alias"] = alias
    resp = await client.room_create(**create_kwargs)
    await client.close()
    if not isinstance(resp, RoomCreateResponse):
        print(f"room_create failed: {resp}", file=sys.stderr)
        return 1

    print(f"MEETBOT_USER_ID={mxid}")
    print(f"MEETBOT_DEVICE_ID={login.device_id}")
    print(f"MEETBOT_ACCESS_TOKEN={login.access_token}")
    print(f"ROOM_ID={resp.room_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
