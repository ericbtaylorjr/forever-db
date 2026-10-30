#!/usr/bin/env bash
# Rebuild data/ from scratch out of historical builds, oldest first, then the live build.
#
#   FOREVER_REPO=~/dev/forever scripts/backfill.sh [--limit N]
#
# DESTRUCTIVE to data/: it is deleted first. Use only to (re)create the history; git has the old copy.
# Historical builds are base data without hotfixes (Raidbots only mirrors the current cache), so the
# step from a build's base to the same build with its hotfixes shows up as a separate version.
# Wago's build list is the only source of old config hashes; builds Blizzard has pruned from the CDN fail
# and are skipped with a note. See docs/update-runbook.md ("Backfilling history").
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
LIMIT=()
[ "${1:-}" = "--limit" ] && LIMIT=(--limit "${2:?}")

rm -rf "$HERE/data"
python3 -I "$HERE/pipeline/builds.py" list "${LIMIT[@]}" | while read -r VER BCFG CCFG; do
  echo "=== $VER ==="
  if ! "$HERE/scripts/scan.sh" --pin "$VER:$BCFG:$CCFG" </dev/null; then
    echo "!!! $VER failed; skipping (not on the CDN any more?)" >&2
  fi
done
echo "=== live build with hotfixes ==="
"$HERE/scripts/scan.sh" --cdn </dev/null
