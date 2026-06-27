#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 Anil Belur
##############################################################################
# Boot a disposable Synapse homeserver in Docker for POC / CI use.
# Registration is wide open ON PURPOSE: this server is throwaway and lives only
# for the duration of one workflow run. Never point this at production.
##############################################################################
set -euo pipefail

SERVER_NAME="${SYNAPSE_SERVER_NAME:-meetbot.local}"
DATA_DIR="${SYNAPSE_DATA_DIR:-$PWD/.synapse}"
IMAGE="${SYNAPSE_IMAGE:-matrixdotorg/synapse:latest}"
PORT="${SYNAPSE_PORT:-8008}"
SHARED_SECRET="${SYNAPSE_SHARED_SECRET:-meetbot-poc-shared-secret}"

mkdir -p "$DATA_DIR"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

echo "[synapse] generating config for ${SERVER_NAME}"
docker run --rm \
  -e SYNAPSE_SERVER_NAME="$SERVER_NAME" \
  -e SYNAPSE_REPORT_STATS=no \
  -e UID="$HOST_UID" \
  -e GID="$HOST_GID" \
  -v "$DATA_DIR:/data" \
  "$IMAGE" generate >/dev/null

CONFIG="$DATA_DIR/homeserver.yaml"

# Registration: shared-secret registration (used by create-accounts.sh) always
# works. Open self-service registration is OFF by default for privacy; set
# SYNAPSE_OPEN_REGISTRATION=true only if you want anyone with the URL to sign up.
OPEN_REG="${SYNAPSE_OPEN_REGISTRATION:-false}"
{
  echo ""
  echo "enable_registration: ${OPEN_REG}"
  echo "enable_registration_without_verification: ${OPEN_REG}"
  echo "registration_shared_secret: \"${SHARED_SECRET}\""
  echo "suppress_key_server_warning: true"
  echo "rc_message:"
  echo "  per_second: 1000"
  echo "  burst_count: 1000"
} >> "$CONFIG"

# When reached through a tunnel, clients need the public base URL.
if [ -n "${SYNAPSE_PUBLIC_BASEURL:-}" ]; then
  echo "public_baseurl: \"${SYNAPSE_PUBLIC_BASEURL}\"" >> "$CONFIG"
fi

echo "[synapse] starting container on port ${PORT}"
docker run -d --name synapse \
  -e UID="$HOST_UID" \
  -e GID="$HOST_GID" \
  -p "${PORT}:8008" \
  -v "$DATA_DIR:/data" \
  "$IMAGE" >/dev/null

echo -n "[synapse] waiting for homeserver to be ready"
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:${PORT}/_matrix/client/versions" >/dev/null 2>&1; then
    echo " - ready"
    exit 0
  fi
  echo -n "."
  sleep 2
done
echo
echo "[synapse] ERROR: homeserver did not become ready" >&2
docker logs synapse 2>&1 | tail -40 >&2
exit 1
