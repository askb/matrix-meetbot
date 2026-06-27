# SPDX-License-Identifier: BSD-3-Clause
"""Identity handling: Matrix MXID <-> meeting "nick".

The ported engine keys chairs, attendees and ``#action`` assignment on a short
"nick" string (IRC heritage). On Matrix the stable, unspoofable identifier is
the MXID (``@user:server``). For the POC we use the MXID *localpart* as the nick
because it is stable, contains no spaces (so ``#chair alice`` works), and reads
naturally in minutes. Display-name rendering is a documented future enhancement.
"""

from __future__ import annotations

from typing import Dict


def mxid_localpart(mxid: str) -> str:
    """Return the localpart of an MXID, e.g. ``@alice:opendev.org`` -> ``alice``."""
    if not mxid:
        return mxid
    return mxid.lstrip("@").split(":", 1)[0]


class Identity:
    """Resolve MXIDs to meeting nicks and track display names."""

    def __init__(self) -> None:
        self._display: Dict[str, str] = {}

    def remember(self, mxid: str, display_name: str) -> None:
        if display_name:
            self._display[mxid] = display_name

    def nick(self, mxid: str) -> str:
        """Stable nick used by the engine (MXID localpart)."""
        return mxid_localpart(mxid)

    def display(self, mxid: str) -> str:
        """Human-friendly name (display name if known, else localpart)."""
        return self._display.get(mxid, mxid_localpart(mxid))
