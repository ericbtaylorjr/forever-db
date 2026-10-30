#!/usr/bin/env python3
"""Turn data/ into the static JSON files the website loads.

    site_data.py [--out site/public/data]

The full dataset is ~50 MB, too much for a browser, so the site gets:

  meta.json            versions (one per ingest, oldest first), stat names, class/subclass/slot names
  items.json           slim row per item for browsing and filtering (columns named in `cols`)
  spells.json          the same for spells
  items/<n>.json       full records + history for 250 items each (the index row says which shard)
  spells/<n>.json      the same for spells
  builds/<i>.json     one file per version: what changed, per entity, plus locked-key changes

Everything is derived from data/ (no clock, no network), so the output is a pure function of it and can be rebuilt
in CI on every deploy. Versions are referred to by their index in meta.json -> versions. See docs/site-data.md.
Stdlib only.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FOREVER_DB_DATA", ROOT / "data"))   # tests point this at a scratch dir
SHARD_SIZE = 250
MAX_CHANGES_PER_ENTRY = 8       # build pages show a short summary; the entity page has the full history
MAX_VALUE_CHARS = 160
MAX_USED_BY = 200
# Names that mark an item as a test or placeholder ("1500 Test sword", "90 Epic Frost Belt", "... DEPRECATED"): a heuristic for
# the site's "hide test items" filter, never used to drop anything.
TEST_NAME = re.compile(r"\btest\b|deprecated|\(old\)|^old\b|^zz|\bqa\b|\[dnt\]|^\d+ ", re.IGNORECASE)
# Areas that only restate another one (className follows classId...): hidden so "what changed" lists each thing once.
DERIVED_AREAS = {"className", "subclassName", "qualityName"}

ITEM_COLS = ["id", "name", "test", "enc", "quality", "ilvl", "reqLvl", "cls", "sub", "inv", "gear", "icon", "first", "changed", "disc",
             "base", "armor", "dps", "stats", "set", "shard"]
SPELL_COLS = ["id", "name", "test", "enc", "school", "castMs", "durMs", "icon", "tags", "first", "changed", "disc", "base", "text", "shard"]


def read_jsonl(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def clip(value):
    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[:MAX_VALUE_CHARS] + "…"
    return value


class Versions:
    """Ingest versions in order, so an event's (build, push) becomes a small integer."""

    def __init__(self, state):
        self.entries = state["builds"]
        self.index = {(b["build"], b["hotfixPush"]): i for i, b in enumerate(self.entries)}

    def of(self, version):
        return self.index[(version["build"], version["push"])]


def label(entry):
    return f"Build {entry['build']}" + (f" · hotfix {entry['hotfixPush']}" if entry["hotfixPush"] else "")


def locked_changes(entries):
    """Per version: locked rows by table/key, and which keys appeared or disappeared since the previous version."""
    out, previous = [], {}
    for entry in entries:
        locked = entry.get("locked") or {}
        keys = {k for table in locked.values() for k in table}
        before = {k for table in previous.values() for k in table}
        out.append({"locked": locked, "unlocked": sorted(before - keys), "newlyLocked": sorted(keys - before) if out else []})
        previous = locked
    return out


def history_by_id(kind):
    return {h["id"]: h["events"] for h in read_jsonl(DATA / "history" / f"{kind}.jsonl")}


def build(out_dir):
    state = json.loads((DATA / "state.json").read_text())
    versions = Versions(state)
    icon_names = json.loads((DATA / "icon-names.json").read_text()) if (DATA / "icon-names.json").exists() else {}
    icons, icon_index = [], {}

    def icon_of(fdid):
        name = icon_names.get(str(fdid))
        if not name:
            return -1
        if name not in icon_index:
            icon_index[name] = len(icons)
            icons.append(name)
        return icon_index[name]

    all_items, all_spells = read_jsonl(DATA / "items.jsonl"), read_jsonl(DATA / "spells.jsonl")
    items = [e for e in all_items if not e.get("removed")]
    spells = [e for e in all_spells if not e.get("removed")]
    # A removed entity is not browsable, but a build page that says "removed" should still name it.
    removed = {("i", e["id"]): e["data"] for e in all_items if e.get("removed")} | {("s", e["id"]): e["data"] for e in all_spells if e.get("removed")}
    item_hist, spell_hist = history_by_id("items"), history_by_id("spells")
    names = {"items": {e["id"]: e["data"]["name"] for e in items}, "spells": {e["id"]: e["data"]["name"] for e in spells}}

    # reverse links: which items use a spell
    used_by = defaultdict(list)
    for e in items:
        for effect in e["data"]["effects"]:
            if effect.get("SpellID"):
                used_by[effect["SpellID"]].append(e["id"])

    def ver(v):
        return versions.of(v) if v else -1

    def compact_events(events):
        out = []
        for ev in events:
            row = {"v": versions.of(ev), "t": ev["type"]}
            if ev.get("areas"):
                row["a"] = [a for a in ev["areas"] if a not in DERIVED_AREAS]
            if ev.get("changes"):
                row["c"] = ev["changes"]
            if ev.get("discovery"):
                row["d"] = ev["discovery"]
            out.append(row)
        return out

    def shard_files(kind, entities, history, extra=None):
        shards = defaultdict(dict)
        for position, e in enumerate(entities):
            record = {"d": e["data"], "f": ver(e["firstSeen"]), "l": ver(e["lastChanged"]), "x": ver(e.get("discoveredAt")),
                      "b": 1 if e.get("baseline") else 0, "h": compact_events(history.get(e["id"], []))}
            if extra:
                record.update(extra(e))
            shards[position // SHARD_SIZE][e["id"]] = record
        for n, records in shards.items():
            write_json(out_dir / kind / f"{n}.json", records)

    item_rows, spell_rows = [], []
    for position, e in enumerate(items):
        d, c = e["data"], e["data"]["computed"]
        weapon = c.get("weapon")
        item_rows.append([
            e["id"], d["name"], 1 if TEST_NAME.search(d["name"]) else 0, 1 if d["discovery"] == "encrypted" else 0, d["quality"], d["itemLevel"], d["requiredLevel"],
            d["classId"], d["subclassId"], d["inventoryType"], 1 if d["isGear"] else 0, icon_of(d["iconFileDataID"]),
            ver(e["firstSeen"]), ver(e["lastChanged"]), ver(e.get("discoveredAt")), 1 if e.get("baseline") else 0,
            c.get("armor", 0), round((weapon["min"] + weapon["max"]) / 2 / weapon["speed"], 1) if weapon else 0,
            c.get("stats") or 0, d["itemSet"]["id"] if d["itemSet"] else 0, position // SHARD_SIZE])
    tag_index, tags = {}, []
    for position, e in enumerate(spells):
        d, c = e["data"], e["data"]["computed"]
        ids = []
        for tag in c["availability"]:
            tag_index.setdefault(tag, len(tags))
            if tag_index[tag] == len(tags):
                tags.append(tag)
            ids.append(tag_index[tag])
        tooltip = c.get("tooltip") or {}
        text = 0 if not (d["description"] or d["auraDescription"]) else (1 if all(v is not None for v in tooltip.values()) else 2)
        spell_rows.append([
            e["id"], d["name"], 1 if "marked-obsolete" in c["availability"] else 0, 1 if d["discovery"] == "encrypted" else 0, d.get("schoolMask", 0), d.get("castTimeMs"), d.get("durationMs"),
            icon_of(d.get("iconFileDataID", 0)), ids, ver(e["firstSeen"]), ver(e["lastChanged"]), ver(e.get("discoveredAt")),
            1 if e.get("baseline") else 0, text, position // SHARD_SIZE])

    shard_files("items", items, item_hist)
    shard_files("spells", spells, spell_hist, extra=lambda e: {"u": used_by.get(e["id"], [])[:MAX_USED_BY], "un": len(used_by.get(e["id"], []))})

    classes = {}
    subclasses = {}
    for e in items:
        d = e["data"]
        if d["classId"] is not None and d["className"]:
            classes[d["classId"]] = d["className"]
        if d["classId"] is not None and d["subclassName"]:
            subclasses[f"{d['classId']}:{d['subclassId']}"] = d["subclassName"]
    write_json(out_dir / "items.json", {"cols": ITEM_COLS, "rows": item_rows, "icons": icons, "classes": classes, "subclasses": subclasses})
    write_json(out_dir / "spells.json", {"cols": SPELL_COLS, "rows": spell_rows, "icons": icons, "tags": tags})

    # builds: one file per version
    dates = json.loads((DATA / "build-dates.json").read_text()) if (DATA / "build-dates.json").exists() else {}
    locks = locked_changes(versions.entries)
    changes_by_version = defaultdict(list)
    for kind, history in (("i", item_hist), ("s", spell_hist)):
        for eid, events in history.items():
            for ev in events:
                row = {"k": kind, "id": eid, "t": ev["type"]}
                if ev.get("areas"):
                    row["a"] = [a for a in ev["areas"] if a not in DERIVED_AREAS]
                if ev.get("discovery"):
                    row["d"] = ev["discovery"]
                if ev["type"] == "removed" and (kind, eid) in removed:
                    last = removed[(kind, eid)]
                    row["nm"] = last.get("name", "")
                    row["ic"] = icon_names.get(str(last.get("iconFileDataID", 0)), "")
                changes = ev.get("changes") or {}
                if changes:
                    row["n"] = len(changes)
                    row["c"] = [[path, clip(old), clip(new)] for path, (old, new) in list(changes.items())[:MAX_CHANGES_PER_ENTRY]]
                changes_by_version[versions.of(ev)].append(row)
    version_meta = []
    for i, entry in enumerate(versions.entries):
        rows = changes_by_version.get(i, [])
        rows.sort(key=lambda r: (r["k"], r["id"]))
        write_json(out_dir / "builds" / f"{i}.json", {"changes": rows, **locks[i]})
        dated = dates.get(f"{entry['build']}:{entry['hotfixPush']}", {})
        version_meta.append({"i": i, "build": entry["build"], "push": entry["hotfixPush"], "version": entry["version"],
                             "label": label(entry), "date": dated.get("date"), "dateSource": dated.get("source"), "counts": entry["counts"], "discovery": entry.get("discovery"),
                             "hotfixes": entry.get("hotfixes"), "lockedRows": sum(n for t in locks[i]["locked"].values() for n in t.values()),
                             "unlocked": locks[i]["unlocked"], "newlyLocked": locks[i]["newlyLocked"]})
    write_json(out_dir / "meta.json", {
        "schema": 1, "versions": version_meta, "statNames": json.loads((DATA / "stat-names.json").read_text()),
        "latest": len(version_meta) - 1, "baselineBuild": state["baselineBuild"]})
    return {"items": len(items), "spells": len(spells), "versions": len(version_meta), "icons": len(icons)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(ROOT / "site" / "public" / "data"))
    args = p.parse_args()
    out = Path(args.out)
    result = build(out)
    total = sum(f.stat().st_size for f in out.rglob("*.json"))
    print(f"{result} -> {out} ({total / 1e6:.1f} MB raw, {sum(1 for _ in out.rglob('*.json'))} files)")


if __name__ == "__main__":
    sys.exit(main())
