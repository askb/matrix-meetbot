# SPDX-License-Identifier: BSD-3-Clause
"""Entry point: load config, build the client, run the sync loop.

Usage:
    python -m meetbot.main            # uses MEETBOT_* env / MEETBOT_CONFIG
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

from .client import MatrixClient
from .config import Config
from .dispatch import Dispatcher
from .identity import Identity

# The engine renders timestamps in UTC; make the process agree.
os.environ["TZ"] = "UTC"
try:
    time.tzset()
except AttributeError:  # pragma: no cover - non-POSIX
    pass


async def amain() -> None:
    cfg = Config.load(os.environ.get("MEETBOT_CONFIG"))
    os.makedirs(cfg.output_dir, exist_ok=True)
    os.makedirs(cfg.state_dir, exist_ok=True)

    client = MatrixClient(cfg)
    await client.login()
    print(f"[meetbot] logged in as {cfg.user_id} on {cfg.homeserver}")

    start_ts_ms = time.time() * 1000.0
    dispatcher = Dispatcher(client, cfg, Identity(), start_ts_ms)
    dispatcher.resume()

    await client.join_rooms()
    print(f"[meetbot] joined rooms: {', '.join(cfg.rooms) or '(none configured)'}")
    client.on_message(dispatcher.on_message)

    async def handle_invite(room, event):
        if event.state_key == cfg.user_id and event.membership == "invite":
            await client.join(room.room_id)
            print(f"[meetbot] auto-joined room via invite: {room.room_id}")
            await client.send_text(
                room.room_id,
                "MeetBot is here. Start with: #startmeeting <name>",
            )

    client.on_invite(handle_invite)

    sync_task = asyncio.ensure_future(client.sync_forever())

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - non-POSIX
            pass

    print("[meetbot] running; waiting for #startmeeting ...")
    await stop.wait()
    print("[meetbot] shutting down")
    sync_task.cancel()
    await client.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
