#!/usr/bin/env bash
# Scan the Forever client with wowsims/forever's db2tool, then ingest the result into data/.
#
#   scripts/scan.sh                       # local install (uses the game's own DBCache.bin hotfixes)
#   scripts/scan.sh --cdn                 # live build from Blizzard's CDN + Raidbots' hotfix mirror (what CI does)
#   scripts/scan.sh --pin VER:BCFG:CCFG   # a historical build from the CDN, base data only (see scripts/backfill.sh)
#
# Env: FOREVER_REPO       checkout of github.com/wowsims/forever (required)
#      WOW_DIR            WoW root holding .build.info (local mode; default /mnt/c/Program Files (x86)/World of Warcraft)
#      SCAN_WORK          scratch dir (default <repo>/.scan, git-ignored)
#      HOTFIX_CACHE_URL   override the Raidbots mirror
#      INGEST_ARGS        extra args for `build_data.py ingest`, e.g. "--allow-schema-change"
# See docs/update-runbook.md.
set -euo pipefail

: "${FOREVER_REPO:?set FOREVER_REPO to a checkout of wowsims/forever}"
WOW_DIR="${WOW_DIR:-/mnt/c/Program Files (x86)/World of Warcraft}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${SCAN_WORK:-$HERE/.scan}"
HOTFIX_CACHE_URL="${HOTFIX_CACHE_URL:-https://storage.googleapis.com/raidbots-static/wow/forever/enUS/DBCache.bin}"
mkdir -p "$WORK"

MODE=local PIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --cdn) MODE=cdn ;;
    --pin) MODE=pin; PIN="${2:?--pin needs VERSION:BUILDCFG:CDNCFG}"; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

# Pinning a historical build needs a small db2tool patch (not upstream yet).
if ! grep -q -- '--cdn-pin' "$FOREVER_REPO/tools/db2tool/main.go"; then
  git -C "$FOREVER_REPO" apply "$HERE/scan/patches/db2tool-cdn-pin.patch"
fi

# The shield block table is not in the game files; we vendor wowsims' copy. Stop if their pinned copy moved.
if ! cmp -s "$HERE/scan/gametables/ShieldBlockRegular.txt" "$FOREVER_REPO/tools/database/dbc/GameTables/ShieldBlockRegular.txt"; then
  echo "scan/gametables/ShieldBlockRegular.txt differs from the pinned wowsims copy; see scan/gametables/README.md" >&2
  exit 1
fi

# db2tool resolves paths relative to its own checkout, so the settings live there.
SETTINGS="$FOREVER_REPO/tools/database/forever-db-settings.json"
sed "s|__WOW_DIR__|$WOW_DIR|" "$HERE/scan/settings.template.json" > "$SETTINGS"

TAG="${PIN%%:*}"; DB="$WORK/scan${TAG:+-$TAG}.db"; LOG="$WORK/scan${TAG:+-$TAG}.log"
FLAGS=() INGEST=()
case "$MODE" in
  cdn)
    curl -fsSL "$HOTFIX_CACHE_URL" -o "$WORK/DBCache.bin"
    FLAGS=(--cdn --dbcache "$WORK/DBCache.bin" --carry-hotfixes)
    INGEST=(--hotfix-cache "$WORK/DBCache.bin") ;;
  pin)
    FLAGS=(--cdn-pin "$PIN")
    INGEST=(--allow-no-hotfixes) ;;
esac

echo "db2tool @ $(git -C "$FOREVER_REPO" rev-parse --short HEAD) mode=$MODE" | tee "$LOG"
(cd "$FOREVER_REPO" && go run ./tools/db2tool -s "$SETTINGS" --output "$DB" "${FLAGS[@]}") 2>&1 | tee -a "$LOG"

# shellcheck disable=SC2086
python3 -I "$HERE/pipeline/build_data.py" ingest --db "$DB" --scan-log "$LOG" \
  --summary-file "$WORK/summary.md" "${INGEST[@]}" ${INGEST_ARGS:-}

# Icon file names for the site live in a side file (records stay a pure function of the scan); refresh it with the listfile db2tool just used.
python3 -I "$HERE/pipeline/icon_names.py" "$FOREVER_REPO/tools/db2tool/listfile.csv"
