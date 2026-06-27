#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 Anil Belur
##############################################################################
# Register accounts on the disposable Synapse using the shared secret.
# Creates the bot plus any demo/test users passed as arguments.
#   usage: create-accounts.sh meetbot alice bob
# Passwords default to "<user>-pass".
##############################################################################
set -euo pipefail

PORT="${SYNAPSE_PORT:-8008}"
SHARED_SECRET="${SYNAPSE_SHARED_SECRET:-meetbot-poc-shared-secret}"
HS_URL="http://localhost:${PORT}"

register_user() {
  local user="$1"
  local pass="$2"
  local admin_flag="$3"  # --admin or --no-admin
  echo "[accounts] registering @${user}"
  docker exec synapse register_new_matrix_user \
    -u "$user" -p "$pass" "$admin_flag" \
    -k "$SHARED_SECRET" \
    "$HS_URL" >/dev/null 2>&1 || {
      # Already exists is fine for idempotent reruns.
      echo "[accounts] note: ${user} may already exist"
    }
}

for user in "$@"; do
  if [ "$user" = "meetbot" ]; then
    register_user "$user" "${user}-pass" "--admin"
  else
    register_user "$user" "${user}-pass" "--no-admin"
  fi
done

echo "[accounts] done"
