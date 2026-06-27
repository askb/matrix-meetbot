# matrix-meetbot (POC)

> ⚠️ **Unofficial personal proof-of-concept.** This is **not** an OpenDev project
> or service and is **not affiliated with, endorsed by, or connected to** OpenDev,
> OpenInfra, or `opendev.org`. It runs on a throwaway homeserver with **federation
> disabled** — it cannot reach or affect any real OpenDev Matrix room or IRC channel.
> It *ports* OpenDev's open-source `MeetBot` (BSD) purely as engineering attribution.

A **Matrix-native meeting bot** that ports OpenDev's IRC `MeetBot` to Matrix,
designed to run a **live proof-of-concept on a GitHub Actions runner**. It
reuses OpenDev's battle-tested meeting **engine** (minute/log rendering) and adds
a fresh [`matrix-nio`](https://github.com/matrix-nio/matrix-nio) transport, so
minutes land in the exact OpenDev layout (`meetings.opendev.org`-compatible) and
the command vocabulary is identical to the IRC bot.

> Status: **proof of concept.** The same bot code later migrates to OpenInfra/
> OpenDev's Matrix homeserver by changing only the homeserver URL + access token.

## Why this design

OpenDev's MeetBot already separates **meeting logic** (`ircmeeting/` — state
machine, item types, writers) from the **IRC transport**. This repo:

- **Vendors** `ircmeeting` as [`meetbot/engine/`](meetbot/engine) (3-clause BSD,
  unchanged logic) — so minute/log formatting is identical, for free.
- **Adds** a small async transport that converts each Matrix `m.room.message`
  into the engine's line input `Meeting.addline(nick, line, time_)`. The engine
  parses the `#commands` itself, exactly as on IRC.

```
You (Element) ─┐
OpenDev team ──┼─► Matrix room ──► meetbot ──► OpenDev-format minutes (.html/.txt/.log.*)
(Element)      ┘   (Synapse)        │  posts start/end + minute URLs back to the room
```

## Two ways to run

### 1. Self-contained CI test (no accounts, no tunnel)
[`.github/workflows/ci.yaml`](.github/workflows/ci.yaml) boots a **disposable
Synapse** on the runner, registers throwaway accounts, starts the bot, replays a
scripted meeting ([`tests/replay/sample-meeting.txt`](tests/replay/sample-meeting.txt)),
and asserts the minutes/logs are produced. Runs on every push/PR. Plus pure unit
tests over the engine and dispatch bridge.

### 2. Live interactive demo (cloudflared tunnel)
[`.github/workflows/live-demo.yaml`](.github/workflows/live-demo.yaml) (run it
from the **Actions** tab) boots the disposable Synapse, exposes it via a public
`*.trycloudflare.com` HTTPS tunnel, pre-creates demo accounts, starts the bot,
and prints **join instructions** to the job summary. You and the OpenDev team:

1. Open <https://app.element.io>, set the homeserver to the printed tunnel URL.
2. Register a throwaway account (open registration) or use a demo account
   (`@alice:<host>` / `alice-pass`).
3. Join `#<meeting_name>:<host>` (or invite the bot to your own room — it
   auto-joins).
4. Run a real meeting; on `#endmeeting` the bot posts minute links and the files
   are uploaded as a workflow artifact.

Everything is destroyed when the job ends (max ~6h). **What lives on the runner
can't be reached from the internet without the tunnel** — that's why the demo
uses cloudflared.

## Commands (ported vocabulary)

Core: `#startmeeting [name]`, `#endmeeting`, `#topic`, `#agreed`, `#accepted`,
`#rejected`, `#info`, `#idea`, `#action`, `#help`, `#link`, `#nick`, `#chair`,
`#unchair`, `#undo`, `#meetingname`, `#meetingtopic`, `#lurk`/`#unlurk`, `#save`.
Voting: `#startvote`, `#vote`, `#showvote`, `#endvote`.

Authorization: anyone may `#startmeeting` and becomes the initial chair;
chair-only commands check the sender's **MXID localpart** against the chair set.

## Matrix-specific decisions (per the spec)

- **No encryption** — meeting rooms are public/logged. Biggest simplification.
- **Identity = MXID**, nick = MXID localpart (stable, no spaces, `#chair alice`
  works). Display-name rendering is a future enhancement.
- **Parse `event.body`** (plaintext); reply fallbacks stripped; `m.emote` → action.
- **Edits/redactions/threads/reactions ignored** (MVP) — original event is
  authoritative, matching IRC semantics.
- **Restart resilience** — every accepted line is journaled to disk; an
  interrupted meeting resumes on restart (replies suppressed during replay).

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest tests/ -q          # unit + dispatch bridge tests

# Full functional run against a real local Synapse (Docker required):
export SYNAPSE_SERVER_NAME=meetbot.local SERVER_NAME=meetbot.local
./scripts/setup-synapse.sh
./scripts/create-accounts.sh meetbot alice bob
eval "$(BOT_USER=meetbot BOT_PASS=meetbot-pass python scripts/setup_room.py)"
MEETBOT_HOMESERVER=http://localhost:8008 MEETBOT_ROOMS="$ROOM_ID" \
  MEETBOT_OUTPUT_DIR=$PWD/meetings python -u -m meetbot.main &
DRIVER_USER=alice DRIVER_PASS=alice-pass \
  TRANSCRIPT=$PWD/tests/replay/sample-meeting.txt python scripts/replay_client.py
find meetings -type f
docker rm -f synapse
```

## Configuration

All fields accept a `MEETBOT_*` env override (env wins over YAML). See
[`config.example.yaml`](config.example.yaml).

| Field | Env | Purpose |
|-------|-----|---------|
| `homeserver` | `MEETBOT_HOMESERVER` | Client-Server API base URL |
| `user_id` | `MEETBOT_USER_ID` | Bot MXID |
| `access_token` | `MEETBOT_ACCESS_TOKEN` | Long-lived token (secret) |
| `rooms` | `MEETBOT_ROOMS` | Comma-separated rooms to join |
| `output_dir` | `MEETBOT_OUTPUT_DIR` | Where minutes/logs are written |
| `base_url` | `MEETBOT_BASE_URL` | Absolute URL prefix for minute links |
| `state_dir` | `MEETBOT_STATE_DIR` | Restart journals |
| `meeting_name` | `MEETBOT_MEETING_NAME` | Path slug |

## Migration to OpenInfra/OpenDev

The bot is transport-clean. To move from the POC to production:

1. Register a bot account on the OpenDev homeserver; store a long-lived token.
2. Point `MEETBOT_HOMESERVER`/`MEETBOT_USER_ID`/`MEETBOT_ACCESS_TOKEN` at it.
3. Mount the shared logs volume so minutes publish to `meetings.opendev.org`
   (set `MEETBOT_BASE_URL` accordingly). The [`Dockerfile`](Dockerfile) mirrors
   the matrix-eavesdrop image pattern for `system-config` wiring.

No code changes — only configuration.

## License

3-clause BSD. The vendored engine under `meetbot/engine/` is © 2009 Richard
Darst and contributors (BSD); new transport code © 2026 Anil Belur (BSD). See
[LICENSE](LICENSE).
