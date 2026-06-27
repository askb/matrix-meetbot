#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 The Linux Foundation
##############################################################################
# OpenDev/Zuul functional test driver.
#
# This is the Zuul equivalent of the "functional" job in
# .github/workflows/ci.yaml. It boots a disposable Synapse homeserver, runs the
# Matrix meetbot against it, replays a scripted meeting, and asserts that
# OpenDev-format minutes/logs were produced. It reuses the same scripts/ that
# the GitHub Actions workflow uses, so there is a single source of truth.
#
# Run locally:   bash contrib/opendev/run-functional.sh
# Run in Zuul:   invoked by contrib/opendev/playbooks/functional/run.yaml
##############################################################################
set -euo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Disposable homeserver identity (same defaults as the GHA functional job).
export SYNAPSE_SERVER_NAME="${SYNAPSE_SERVER_NAME:-meetbot.local}"
export SYNAPSE_PORT="${SYNAPSE_PORT:-8008}"
export SYNAPSE_SHARED_SECRET="${SYNAPSE_SHARED_SECRET:-ci-poc-shared-secret}"
export SERVER_NAME="$SYNAPSE_SERVER_NAME"
HS_URL="http://localhost:${SYNAPSE_PORT}"

echo "::group::install deps"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo "::endgroup::"

echo "--- boot disposable Synapse ---"
./scripts/setup-synapse.sh

echo "--- register bot + driver accounts (shared-secret; open reg stays off) ---"
./scripts/create-accounts.sh meetbot alice bob

echo "--- create room + bot token ---"
eval "$(BOT_USER=meetbot BOT_PASS=meetbot-pass python3 scripts/setup_room.py)"

export MEETBOT_HOMESERVER="$HS_URL"
export MEETBOT_OUTPUT_DIR="$ROOT/meetings"
export MEETBOT_STATE_DIR="$ROOT/state"
# In production this is https://meetings.opendev.org/ so minute links resolve.
export MEETBOT_BASE_URL="${MEETBOT_BASE_URL:-https://meetings.opendev.org/}"
export MEETBOT_MEETING_NAME="meetbot-poc"
export MEETBOT_ROOMS="$ROOM_ID"

echo "--- start meetbot ---"
nohup python3 -u -m meetbot.main > bot.log 2>&1 &
BOT_PID=$!
trap 'kill "$BOT_PID" 2>/dev/null || true' EXIT
sleep 8
echo "--- bot.log ---"; cat bot.log || true

echo "--- replay scripted meeting ---"
DRIVER_USER=alice DRIVER_PASS=alice-pass \
  TRANSCRIPT="$ROOT/tests/replay/sample-meeting.txt" \
  python3 scripts/replay_client.py

echo "--- assert minutes + logs ---"
base="meetings/meetbot-poc"
echo "Produced files:"; find "$base" -type f | sort
for ext in .html .txt .log.html .log.txt; do
  test -n "$(find "$base" -name "*$ext" -print -quit)" \
    || { echo "MISSING $ext"; exit 1; }
done
html="$(find "$base" -name '*.html' ! -name '*.log.html' | head -1)"
log="$(find "$base" -name '*.log.txt' | head -1)"
grep -q "Weekly Team Sync" "$log" \
  || { echo "log missing startmeeting name"; exit 1; }
for needle in "Weekly coordination" "ACTION" "AGREED" "bob to upgrade nodepool"; do
  grep -qi "$needle" "$html" \
    || { echo "minutes missing: $needle"; exit 1; }
done
echo "functional OK: OpenDev-format minutes and logs produced."
