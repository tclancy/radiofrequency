#!/usr/bin/env bash
# Publish devices.json as a GitHub Release asset for the given tag.
#
# Local:  TAG=v0.1.0 scripts/publish-devices-release.sh
# CI:     TAG="$GITHUB_REF_NAME" scripts/publish-devices-release.sh
#
# When TAG is unset locally, falls back to the exact tag pointing at HEAD.
#
# Idempotent: creates the release if missing, overwrites the devices.json
# asset if it already exists on the release.

set -euo pipefail

TAG="${TAG:-}"
if [[ -z "$TAG" ]]; then
    TAG="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"
fi
if [[ -z "$TAG" ]]; then
    echo "ERROR: TAG env var not set and HEAD has no exact tag." >&2
    echo "Usage: TAG=vX.Y.Z $0" >&2
    exit 2
fi

echo "==> Publishing devices.json for tag: $TAG"

echo "==> Running exporter regression fence"
uv run pytest tests/test_export_web_devices.py -x

echo "==> Building devices.json"
uv run python scripts/export_web_devices.py > devices.json

echo "==> Sanity-checking JSON"
uv run python - <<'PY'
import json
import sys

data = json.load(open("devices.json"))
lights = data.get("lights")
if not lights:
    print("devices.json has no lights", file=sys.stderr)
    sys.exit(1)
bad = [l for l in lights if not (l.get("unit") and l.get("commands"))]
if bad:
    print(f"devices.json entries missing unit/commands: {bad}", file=sys.stderr)
    sys.exit(1)
print(f"devices.json: {len(lights)} lights")
PY

echo "==> Creating release (idempotent) and uploading devices.json"
gh release create "$TAG" --generate-notes --title "$TAG" || true
gh release upload "$TAG" devices.json --clobber

echo "==> Done."
