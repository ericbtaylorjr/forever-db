#!/usr/bin/env bash
# Scan the Forever client with wowsims/forever's db2tool, then ingest the result into data/.
#
#   FOREVER_REPO=~/dev/forever scripts/scan.sh            # local install (default)
#   FOREVER_REPO=~/dev/forever scripts/scan.sh --cdn      # current live build from Blizzard's CDN
#
# Env: FOREVER_REPO  checkout of github.com/wowsims/forever (required)
#      WOW_DIR       WoW root holding .build.info (default: /mnt/c/Program Files (x86)/World of Warcraft)
# Extra args are passed to db2tool. See docs/update-runbook.md.
set -euo pipefail

: "${FOREVER_REPO:?set FOREVER_REPO to a checkout of wowsims/forever}"
WOW_DIR="${WOW_DIR:-/mnt/c/Program Files (x86)/World of Warcraft}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${SCAN_WORK:-$HERE/.scan}"   # git-ignored scratch space: settings, raw SQLite, tool log
mkdir -p "$WORK"

# db2tool resolves paths relative to its own checkout, so the settings live there.
SETTINGS="$FOREVER_REPO/tools/database/forever-db-settings.json"
sed "s|__WOW_DIR__|$WOW_DIR|" "$HERE/scan/settings.template.json" > "$SETTINGS"

echo "db2tool @ $(git -C "$FOREVER_REPO" rev-parse --short HEAD)" | tee "$WORK/scan.log"
(cd "$FOREVER_REPO" && go run ./tools/db2tool -s "$SETTINGS" --output "$WORK/scan.db" "$@") 2>&1 | tee -a "$WORK/scan.log"

python3 -I "$HERE/pipeline/build_data.py" ingest --db "$WORK/scan.db" --scan-log "$WORK/scan.log"
