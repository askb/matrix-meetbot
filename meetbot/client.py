# SPDX-License-Identifier: BSD-3-Clause
"""Thin wrapper around matrix-nio's AsyncClient for the meetbot.

No encryption: meeting rooms are public and publicly logged, so we skip the
entire E2EE/olm/device-verification burden (the single biggest simplification).
"""

from __future__ import annotations

from typing import Awaitable, Callable

from nio import (
    AsyncClient,
    InviteMemberEvent,
    RoomMessageEmote,
    RoomMessageText,
)

from .config import Config


class MatrixClient:
    """Login-by-token Matrix client with helpers for sending notices/topics."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = AsyncClient(cfg.homeserver, cfg.user_id)

    async def login(self) -> None:
        """Restore a session from a long-lived access token (no password)."""
        self.client.restore_login(
            user_id=self.cfg.user_id,
            device_id=self.cfg.device_id,
            access_token=self.cfg.access_token,
        )

    async def join_rooms(self) -> None:
        for room in self.cfg.rooms:
            await self.client.join(room)

    async def send_text(self, room_id: str, text: str) -> None:
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"msgtype": "m.notice", "body": text},
        )

    async def set_topic(self, room_id: str, topic: str) -> None:
        await self.client.room_put_state(
            room_id=room_id,
            event_type="m.room.topic",
            content={"topic": topic},
        )

    def on_message(self, callback: Callable[..., Awaitable[None]]) -> None:
        self.client.add_event_callback(callback, RoomMessageText)
        self.client.add_event_callback(callback, RoomMessageEmote)

    def on_invite(self, callback: Callable[..., Awaitable[None]]) -> None:
        self.client.add_event_callback(callback, InviteMemberEvent)

    async def join(self, room_id: str) -> None:
        await self.client.join(room_id)

    async def sync_forever(self) -> None:
        await self.client.sync_forever(timeout=30000, full_state=False)

    async def close(self) -> None:
        await self.client.close()
