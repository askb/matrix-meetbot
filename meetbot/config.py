# SPDX-License-Identifier: BSD-3-Clause
"""Configuration loading for the Matrix meetbot.

Values come from a YAML file (path in ``MEETBOT_CONFIG``) and/or environment
variables. Environment variables override the YAML file, which makes the bot
easy to drive from a GitHub Actions workflow without committing secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

# Mapping of config field -> environment variable override.
_ENV = {
    "homeserver": "MEETBOT_HOMESERVER",
    "user_id": "MEETBOT_USER_ID",
    "access_token": "MEETBOT_ACCESS_TOKEN",
    "device_id": "MEETBOT_DEVICE_ID",
    "output_dir": "MEETBOT_OUTPUT_DIR",
    "base_url": "MEETBOT_BASE_URL",
    "state_dir": "MEETBOT_STATE_DIR",
    "meeting_name": "MEETBOT_MEETING_NAME",
    "info_url": "MEETBOT_INFO_URL",
}


@dataclass
class Config:
    """Runtime configuration for the bot."""

    homeserver: str
    user_id: str
    access_token: str
    device_id: str = "MEETBOT"
    rooms: List[str] = field(default_factory=list)
    output_dir: str = "./meetings"
    base_url: str = ""  # becomes engine logUrlPrefix (absolute minute URLs)
    state_dir: str = "./state"
    meeting_name: str = "opendev-meeting"  # default engine "channel" / path slug
    info_url: str = "https://opendev.org/opendev/meetbot"

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load config from YAML (optional) with environment overrides."""
        data: dict = {}
        path = path or os.environ.get("MEETBOT_CONFIG")
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}

        for field_name, env_name in _ENV.items():
            value = os.environ.get(env_name)
            if value:
                data[field_name] = value

        rooms_env = os.environ.get("MEETBOT_ROOMS")
        if rooms_env:
            data["rooms"] = [r.strip() for r in rooms_env.split(",") if r.strip()]

        allowed = set(cls.__dataclass_fields__)
        kwargs = {k: v for k, v in data.items() if k in allowed}

        missing = [k for k in ("homeserver", "user_id", "access_token") if not kwargs.get(k)]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")

        return cls(**kwargs)
