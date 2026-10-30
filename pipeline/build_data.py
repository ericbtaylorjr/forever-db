#!/usr/bin/env python3
"""Turn a db2tool SQLite dump into versioned spell/item datasets.

    build_data.py ingest --db spike.db [--scan-log scan.log]

Reads the SQLite file that `wowsims/forever` `db2tool` writes, joins the
per-table rows into one record per spell and per item, diffs them against the
records already in data/, and appends what changed to the history files.
See docs/data-model.md for the output contract and docs/update-runbook.md for
the full update procedure. Python stdlib only.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FOREVER_DB_DATA", ROOT / "data"))
SCHEMA_VERSION = 1

QUALITY = {0: "Poor", 1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Artifact", 7: "Heirloom"}
# Spell-keyed tables that are not joined by a `SpellID` column.
SPELL_KEY_OVERRIDES = {"SkillLineAbility": "Spell"}
# Spell-keyed tables whose `Spell*` name matches but are lookups, not per-spell rows.
SPELL_LOOKUP_TABLES = {
    "SpellName", "SpellCategory", "SpellRadius", "SpellRange", "SpellCastTimes", "SpellDuration",
    "SpellMechanic", "SpellShapeshiftForm", "SpellItemEnchantment", "SpellProcsPerMinute",
    "SpellProcsPerMinuteMod", "SpellDescriptionVariables",
}
# Only these ClassIDs carry equippable gear; InventoryType 0 means "not equippable".
GEAR_CLASSES = {2, 4}

_EXPANDED = re.compile(r"^(.*)_(\d+)$")


def norm(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


class Source:
    """Read-only view of the db2tool output with lookup helpers."""

    def __init__(self, path):
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.tables = {r[0] for r in self.db.execute("select name from sqlite_master where type='table'")}
        self.columns = {t: [(r[1], r[2]) for r in self.db.execute(f'pragma table_info("{t}")')] for t in self.tables}

    def rows(self, table):
        """Rows as dicts. The tool writes array columns twice (JSON text plus
        `Col_0`, `Col_1`, ... copies); keep the JSON form and drop the copies."""
        if table not in self.tables:
            return []
        cols = self.columns[table]
        names = {c for c, _ in cols}
        keep = [(c, t) for c, t in cols if not (_EXPANDED.match(c) and _EXPANDED.match(c).group(1) in names)]
        out = []
        for raw in self.db.execute(f'select {",".join(chr(34)+c+chr(34) for c, _ in keep)} from "{table}"'):
            row = {}
            for (c, t), v in zip(keep, raw):
                if t == "TEXT" and not c.endswith("_lang") and isinstance(v, str) and v.startswith("["):
                    v = json.loads(v)
                    v = [norm(x) for x in v]
                row[c] = norm(v)
            out.append(row)
        return out

    def by_key(self, table, key):
        idx = {}
        for r in self.rows(table):
            idx.setdefault(r[key], []).append(r)
        return idx


def is_default(v):
    """Zero, empty and all-zero values are omitted from records; absent means default."""
    return v in (0, "", None) or (isinstance(v, list) and all(x == 0 for x in v))


def strip(row, *drop):
    """Copy of `row` without the `drop` keys and without default-valued fields."""
    return {k: v for k, v in row.items() if k not in drop and not is_default(v)}


def child_rows(rows, *drop):
    """Child-table rows without surrogate IDs, in a deterministic order."""
    cleaned = [strip(r, "ID", *drop) for r in rows]
    return sorted(cleaned, key=lambda r: json.dumps(r, sort_keys=True))


def build_spells(src):
    spell = {r["ID"]: r for r in src.rows("Spell")}
    name = {r["ID"]: r for r in src.rows("SpellName")}
    cast = {r["ID"]: r for r in src.rows("SpellCastTimes")}
    dur = {r["ID"]: r for r in src.rows("SpellDuration")}
    rng = {r["ID"]: r for r in src.rows("SpellRange")}
    related = {}
    for t in sorted(src.tables):
        if not t.startswith("Spell") or t in SPELL_LOOKUP_TABLES or t == "Spell":
            continue
        key = SPELL_KEY_OVERRIDES.get(t, "SpellID")
        if any(c == key for c, _ in src.columns[t]):
            related[t] = src.by_key(t, key)
    related["SkillLineAbility"] = src.by_key("SkillLineAbility", "Spell")

    out = {}
    for sid in sorted(set(spell) | set(name)):
        s, n = spell.get(sid, {}), name.get(sid, {})
        rec = {
            "name": n.get("Name_lang", ""),
            "subtext": s.get("NameSubtext_lang", ""),
            "description": s.get("Description_lang", ""),
            "auraDescription": s.get("AuraDescription_lang", ""),
        }
        misc = related.get("SpellMisc", {}).get(sid, [])
        if misc:
            m = min(misc, key=lambda r: r.get("DifficultyID", 0))
            rec["iconFileDataID"] = m.get("SpellIconFileDataID", 0)
            rec["schoolMask"] = m.get("SchoolMask", 0)
            rec["castTimeMs"] = cast.get(m.get("CastingTimeIndex"), {}).get("Base")
            rec["durationMs"] = dur.get(m.get("DurationIndex"), {}).get("Duration")
            r = rng.get(m.get("RangeIndex"), {})
            rec["range"] = {"name": r.get("DisplayName_lang"), "min": r.get("RangeMin"), "max": r.get("RangeMax")} if r else None
        rec["related"] = {t: child_rows(idx[sid], "SpellID", "Spell") for t, idx in related.items() if sid in idx}
        out[sid] = rec
    return out


def build_items(src):
    item = {r["ID"]: r for r in src.rows("Item")}
    classes = {r["ClassID"]: r["ClassName_lang"] for r in src.rows("ItemClass")}
    subclasses = {(r["ClassID"], r["SubClassID"]): r["DisplayName_lang"] for r in src.rows("ItemSubClass")}
    namedesc = {r["ID"]: r["Description_lang"] for r in src.rows("ItemNameDescription")}
    effects = {r["ID"]: r for r in src.rows("ItemEffect")}
    item_effects = src.by_key("ItemXItemEffect", "ItemID")
    bonus_trees = src.by_key("ItemXBonusTree", "ItemID")
    sets = {r["ID"]: r for r in src.rows("ItemSet")}

    out = {}
    for sp in src.rows("ItemSparse"):
        iid = sp["ID"]
        base = item.get(iid, {})
        cls, sub, inv = base.get("ClassID"), base.get("SubclassID"), sp.get("InventoryType", 0)
        rec = {
            "name": sp.get("Display_lang", ""),
            "description": sp.get("Description_lang", ""),
            "classId": cls,
            "className": classes.get(cls),
            "subclassId": sub,
            "subclassName": subclasses.get((cls, sub)),
            "inventoryType": inv,
            "isGear": cls in GEAR_CLASSES and inv != 0,
            "quality": sp.get("OverallQualityID"),
            "qualityName": QUALITY.get(sp.get("OverallQualityID")),
            "itemLevel": sp.get("ItemLevel"),
            "requiredLevel": sp.get("RequiredLevel"),
            "nameDescription": namedesc.get(sp.get("ItemNameDescriptionID")) or None,
            "iconFileDataID": base.get("IconFileDataID", 0),
            "itemSet": None,
            # Fields already surfaced above are not repeated in the raw rows.
            "sparse": strip(sp, "ID", "Display_lang", "Description_lang", "ItemLevel", "RequiredLevel",
                            "InventoryType", "OverallQualityID", "ItemNameDescriptionID"),
            "item": strip(base, "ID", "ClassID", "SubclassID", "InventoryType", "IconFileDataID"),
            "effects": [],
            "bonusTrees": sorted(r["ItemBonusTreeID"] for r in bonus_trees.get(iid, [])),
        }
        for link in item_effects.get(iid, []):
            e = effects.get(link["ItemEffectID"])
            if e:
                rec["effects"].append(strip(e, "ID"))
        rec["effects"].sort(key=lambda e: json.dumps(e, sort_keys=True))
        s = sets.get(sp.get("ItemSet"))
        if s:
            rec["itemSet"] = {"id": s["ID"], "name": s["Name_lang"]}
        out[iid] = rec
    return out


def flatten(value, prefix=""):
    """Flatten nested data to {path: leaf} so changes are reported per field."""
    if isinstance(value, dict):
        for k in sorted(value):
            yield from flatten(value[k], f"{prefix}.{k}" if prefix else k)
    elif isinstance(value, list) and value and all(isinstance(x, (dict, list)) for x in value):
        for i, x in enumerate(value):
            yield from flatten(x, f"{prefix}[{i}]")
    else:
        yield prefix, value


def diff(old, new):
    a, b = dict(flatten(old)), dict(flatten(new))
    return {p: [a.get(p), b.get(p)] for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)}


def digest(rec):
    return hashlib.sha1(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def read_jsonl(path):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {json.loads(line)["id"]: json.loads(line) for line in f if line.strip()}


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Plain text on purpose: git delta-compresses line changes, a .gz would be re-stored whole each commit.
    with open(path, "w", encoding="utf-8") as f:
        for rid in sorted(records):
            f.write(json.dumps(records[rid], sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def parse_scan_log(path):
    """Pull the build, hotfix push and locked-row counts out of db2tool's stdout."""
    info = {"lockedRows": {}}
    if not path:
        return info
    for line in Path(path).read_text().splitlines():
        m = re.match(r"\s*(\w+): (\d+) rows locked by TACT key (\w+)", line)
        if m:
            info["lockedRows"][m.group(1)] = info["lockedRows"].get(m.group(1), 0) + int(m.group(2))
        m = re.match(r"Hotfixes: (.*)", line)
        if m:
            info["hotfixSummary"] = m.group(1)
    return info


def schema_fingerprint(src):
    return {t: [f"{c}:{ty}" for c, ty in cols] for t, cols in sorted(src.columns.items())}


def ingest_entities(kind, new, build, push, baseline):
    """Diff `new` against data/<kind>.jsonl and append to data/history/<kind>.jsonl.

    Returns (current, history, stats)."""
    current = read_jsonl(DATA / f"{kind}.jsonl")
    history = read_jsonl(DATA / "history" / f"{kind}.jsonl")
    stats = {"added": 0, "changed": 0, "removed": 0, "unchanged": 0}
    event_base = {"build": build, "push": push}

    for eid, data in new.items():
        h = digest(data)
        old = current.get(eid)
        if old is None or old.get("removed"):
            stats["added"] += 1
            entry = {"id": eid, "firstSeen": {"build": build, "push": push}, "lastChanged": {"build": build, "push": push},
                     "baseline": baseline, "hash": h, "data": data}
            if not baseline:  # baseline entities carry firstSeen/baseline instead of an event
                history.setdefault(eid, {"id": eid, "events": []})["events"].append({**event_base, "type": "added"})
        elif old["hash"] != h:
            changes = diff(old["data"], data)
            ev = {**event_base, "type": "changed", "changes": changes}
            stats["changed"] += 1
            entry = {**old, "lastChanged": {"build": build, "push": push}, "hash": h, "data": data}
            history.setdefault(eid, {"id": eid, "events": []})["events"].append(ev)
        else:
            stats["unchanged"] += 1
            entry = old
        current[eid] = entry

    for eid, old in list(current.items()):
        if eid not in new and not old.get("removed"):
            stats["removed"] += 1
            current[eid] = {**old, "removed": True, "lastChanged": {"build": build, "push": push}}
            history.setdefault(eid, {"id": eid, "events": []})["events"].append({**event_base, "type": "removed"})
    return current, history, stats


def cmd_ingest(args):
    src = Source(args.db)
    build_info = src.rows("BuildInfo")[0]
    version, push = build_info["Version"], build_info["HotfixPush"]
    build = int(version.rsplit(".", 1)[1])
    scan = parse_scan_log(args.scan_log)

    state_path = DATA / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    fingerprint = schema_fingerprint(src)
    if state:
        if (build, push) == (state["build"], state["hotfixPush"]) and not args.force:
            print(f"Already ingested {version} push {push}; nothing to do.")
            return 0
        if (build, push) < (state["build"], state["hotfixPush"]) and not args.force:
            sys.exit(f"Refusing to ingest older data ({version}/{push}) over {state['version']}/{state['hotfixPush']}.")
        changed_tables = sorted(t for t in set(fingerprint) | set(state["schema"]) if fingerprint.get(t) != state["schema"].get(t))
        if changed_tables and not args.allow_schema_change:
            sys.exit("Table layouts changed since the last ingest, which would show up as bogus field diffs:\n  "
                     + ", ".join(changed_tables) + "\nReview docs/update-runbook.md (\"Schema changes\"), then re-run with --allow-schema-change.")

    baseline = state is None
    results = {}
    for kind, builder in (("spells", build_spells), ("items", build_items)):
        current, history, stats = ingest_entities(kind, builder(src), build, push, baseline)
        results[kind] = stats
        if not args.dry_run:
            write_jsonl(DATA / f"{kind}.jsonl", current)
            write_jsonl(DATA / "history" / f"{kind}.jsonl", history)

    new_state = {
        "schemaVersion": SCHEMA_VERSION, "version": version, "build": build, "hotfixPush": push,
        "product": build_info["Product"], "baselineBuild": state["baselineBuild"] if state else build,
        "baselinePush": state["baselinePush"] if state else push,
        "schema": fingerprint, "scan": scan, "counts": results,
    }
    builds = (state or {}).get("builds", [])
    builds.append({"version": version, "build": build, "hotfixPush": push, "counts": results})
    new_state["builds"] = builds
    if not args.dry_run:
        state_path.write_text(json.dumps(new_state, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"version": version, "push": push, "baseline": baseline, **results}, indent=1))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="diff a db2tool dump against data/ and record the changes")
    i.add_argument("--db", required=True, help="SQLite file written by db2tool")
    i.add_argument("--scan-log", help="saved db2tool stdout (records locked-row counts)")
    i.add_argument("--allow-schema-change", action="store_true")
    i.add_argument("--force", action="store_true", help="re-ingest the same or an older build")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(fn=cmd_ingest)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
