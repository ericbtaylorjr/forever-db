#!/usr/bin/env python3
"""Find out which Forever builds exist and whether data/ is out of date.

    builds.py check [--cache-out FILE] [--github-output]   is there a new build or hotfix push?
    builds.py list [--limit N]                              historical builds, oldest first, as `version buildConfig cdnConfig`

Sources (both public, no auth):
  * Blizzard's version service names the build `wowf` is on right now (US).
  * wago.tools/api/builds lists past builds with their CDN config hashes. We
    need those hashes to extract a historical build.
  * Raidbots mirrors the live game's DBCache.bin (the server-pushed hotfixes).

Python stdlib only. See docs/update-runbook.md.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT = "wowf"
VERSION_URL = f"https://us.version.battle.net/{PRODUCT}/versions"
WAGO_URL = "https://wago.tools/api/builds"
HOTFIX_CACHE_URL = os.environ.get("HOTFIX_CACHE_URL", "https://storage.googleapis.com/raidbots-static/wow/forever/enUS/DBCache.bin")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "forever-db (github.com/wowsims)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def live_version():
    """Version string the US version service reports for the product, e.g. 1.60.1.70685."""
    header, rows = None, {}
    for line in fetch(VERSION_URL).decode().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if header is None:
            header = [f.split("!")[0] for f in fields]
        else:
            row = dict(zip(header, fields))
            rows[row["Region"]] = row
    return rows["us"]["VersionsName"]


def build_number(version):
    return int(version.rsplit(".", 1)[1])


def historical_builds():
    """Past builds up to the US live one, oldest first. Later regions (e.g. CN) can be ahead of US; skip those."""
    ceiling = build_number(live_version())
    rows = json.loads(fetch(WAGO_URL))[PRODUCT]
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: build_number(r["version"])):
        if build_number(r["version"]) <= ceiling and r["version"] not in seen and not r.get("is_bgdl"):
            seen.add(r["version"])
            out.append(r)
    return out


def cmd_list(args):
    for r in historical_builds()[-args.limit:] if args.limit else historical_builds():
        print(f"{r['version']} {r['build_config']} {r['cdn_config']}")
    return 0


def cmd_check(args):
    state_path = ROOT / "data" / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    live = live_version()
    cache = fetch(HOTFIX_CACHE_URL)
    if args.cache_out:
        Path(args.cache_out).write_bytes(cache)
    sha = hashlib.sha256(cache).hexdigest()
    known_sha = state.get("scan", {}).get("hotfixCacheSha256")
    reasons = []
    if live != state.get("version"):
        reasons.append(f"new build {live} (data is at {state.get('version')})")
    if sha != known_sha:
        reasons.append("hotfix cache changed")
    changed = bool(reasons)
    print(f"live build {live}; hotfix cache sha256 {sha[:12]}; " + ("UPDATE NEEDED: " + "; ".join(reasons) if changed else "up to date"))
    if args.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\nlive_version={live}\n")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="compare the live build and hotfix cache with data/state.json")
    c.add_argument("--cache-out", help="save the downloaded DBCache.bin here for the scan to use")
    c.add_argument("--github-output", action="store_true", help="write changed=true|false to $GITHUB_OUTPUT")
    c.set_defaults(fn=cmd_check)
    l = sub.add_parser("list", help="past builds with their config hashes")
    l.add_argument("--limit", type=int, help="only the newest N")
    l.set_defaults(fn=cmd_list)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
