# SPDX-License-Identifier: BSD-3-Clause
# Mirrors the matrix-eavesdrop approach: a small Python image running a
# matrix-nio bot. No E2EE extras (rooms are public/unencrypted).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=UTC \
    MEETBOT_OUTPUT_DIR=/var/meetbot/meetings \
    MEETBOT_STATE_DIR=/var/meetbot/state

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY meetbot/ ./meetbot/

# Minutes/logs volume — mount the same path the publisher serves from.
VOLUME ["/var/meetbot"]

# Config comes from MEETBOT_* env vars or a mounted MEETBOT_CONFIG yaml.
ENTRYPOINT ["python", "-u", "-m", "meetbot.main"]
