#!/bin/bash
# Morning nudge for the Sofucor fan RF project. Fired by
# ~/Library/LaunchAgents/com.tomclancy.rf-nudge.plist at 09:00 local time.
#
# Intentionally simple: a fixed reminder pointing at the findings doc plus
# the current highest-priority action from it. Update the MSG as the
# project's bottleneck shifts.

set -euo pipefail

NTFY_URL="https://notifications.tomclancy.info/claude"
NTFY_TOKEN="tk_97t85yxi0lj8gtu1kupx2f7pnd53n"

MSG='RF fans: first move is TX module VCC wiring — VIN (5V) or 3V3? See docs/fan-debugging-2026-04-19.md on claude/generic-firmware branch.'

curl -fsS -u ":${NTFY_TOKEN}" -d "$MSG" "$NTFY_URL" >/dev/null
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] nudge sent"
