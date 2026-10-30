#!/usr/bin/env python3
"""Write data/icon-names.json: icon FileDataID -> icon name, for every icon the dataset uses.

    icon_names.py <listfile.csv>

The names come from the community listfile that db2tool downloads (`interface/icons/<name>.blp`). They are kept in a side
file, not in the records, so a record stays a pure function of the game files (AGENTS.md rule 3). Re-run after a scan
(scripts/scan.sh does); the site build reads this file. Stdlib only.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX, SUFFIX = "interface/icons/", ".blp"


def used_ids():
    ids = set()
    for kind in ("items", "spells"):
        for line in open(ROOT / "data" / f"{kind}.jsonl", encoding="utf-8"):
            fdid = json.loads(line)["data"].get("iconFileDataID")
            if fdid:
                ids.add(fdid)
    return ids


def main(listfile):
    wanted = used_ids()
    names = {}
    with open(listfile, newline="", encoding="utf-8") as f:
        for fdid, path in csv.reader(f, delimiter=";"):
            if path.startswith(PREFIX) and path.endswith(SUFFIX) and int(fdid) in wanted:
                names[int(fdid)] = path[len(PREFIX):-len(SUFFIX)]
    out = ROOT / "data" / "icon-names.json"
    out.write_text(json.dumps({str(k): names[k] for k in sorted(names)}, separators=(",", ":")) + "\n")
    print(f"{len(names)} of {len(wanted)} icon ids named -> {out.relative_to(ROOT)}; unresolved: {len(wanted - set(names))}")


if __name__ == "__main__":
    main(sys.argv[1])
