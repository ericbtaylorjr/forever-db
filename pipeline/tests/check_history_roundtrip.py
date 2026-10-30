#!/usr/bin/env python3
"""Check that history events really rebuild past versions, on the real data.

    check_history_roundtrip.py

For every ingested version we still have the scan database for (.scan/scan-<version>.db for base builds, .scan/scan.db
for the live one), rebuild every entity from that scan and compare it with the same entity reconstructed from the
current data/ by undoing newer history events (the algorithm the website uses, site/src/lib/history.ts).
Manual check: needs the scans from `scripts/backfill.sh`. Exit status 1 on any mismatch.
"""
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent)]
import build_data  # noqa: E402

ROOT = build_data.ROOT


def flat_at(entity, history, version_index, target):
    first = version_index[(entity["firstSeen"]["build"], entity["firstSeen"]["push"])]
    if target < first:
        return None
    exists = True   # a `removed` event hides the entity until an `added` event brings it back
    for ev in sorted(history, key=lambda e: version_index[(e["build"], e["push"])]):
        if version_index[(ev["build"], ev["push"])] > target:
            break
        exists = ev["type"] == "added" if ev["type"] in ("added", "removed") else exists
    if not exists:
        return None
    flat = dict(build_data.flatten(entity["data"]))
    for ev in sorted(history, key=lambda e: -version_index[(e["build"], e["push"])]):
        if version_index[(ev["build"], ev["push"])] <= target:
            continue
        for path, (old, _new) in (ev.get("changes") or {}).items():
            if old is None:
                flat.pop(path, None)
            else:
                flat[path] = old
    return flat


def norm(flat):
    return {k: v for k, v in flat.items() if v is not None}   # null and absent are the same


def main():
    state = json.loads((ROOT / "data" / "state.json").read_text())
    versions = state["builds"]
    index = {(b["build"], b["hotfixPush"]): i for i, b in enumerate(versions)}
    scans = {i: (ROOT / ".scan" / (f"scan-{b['version']}.db" if b["hotfixPush"] == 0 else "scan.db")) for i, b in enumerate(versions)}
    problems = 0
    for kind, builder in (("items", lambda src: build_data.build_items(src, ROOT / "scan" / "gametables")), ("spells", build_data.build_spells)):
        entities = {e["id"]: e for e in build_data.read_jsonl(ROOT / "data" / f"{kind}.jsonl").values()}
        history = {e["id"]: e["events"] for e in build_data.read_jsonl(ROOT / "data" / "history" / f"{kind}.jsonl").values()}
        for i, path in scans.items():
            if i == len(versions) - 1 or not path.exists():
                continue   # the newest version is the data itself
            then = builder(build_data.Source(path))
            checked = bad = 0
            for eid, entity in entities.items():
                rebuilt = flat_at(entity, history.get(eid, []), index, i)
                actual = then.get(eid)
                checked += 1
                if (rebuilt is None) != (actual is None) or (actual is not None and norm(rebuilt) != norm(dict(build_data.flatten(actual)))):
                    bad += 1
                    if bad <= 3:
                        print(f"  MISMATCH {kind} {eid} at version {versions[i]['version']}/{versions[i]['hotfixPush']}")
            problems += bad
            print(f"{kind:7} v{i} {versions[i]['version']} push {versions[i]['hotfixPush']:>6}: {checked} entities checked, {bad} mismatches")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
