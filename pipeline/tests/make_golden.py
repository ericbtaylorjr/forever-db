#!/usr/bin/env python3
"""Regenerate pipeline/tests/golden_items.json: real items with expected values from wowsims' Go output.

    make_golden.py <scan.db> <forever/assets/database/db.json>

Run only when the formula or the reference changes. Expected values come from wowsims/forever's generated db.json
(their Go implementation, which they checked against in-game tooltips); each picked item must already match what
build_data.compute_item returns, otherwise this script stops instead of recording a disagreement.
See docs/item-stats-spike.md.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]
import build_data  # noqa: E402
from test_build_data import SIM  # noqa: E402

# (label, predicate on the ItemSparse+Item row) - the first matching item in db.json is taken.
PICKS = [
    ("cloth chest", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 1 and r["InventoryType"] == 5 and r["OverallQualityID"] == 3),
    ("cloth robe", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 1 and r["InventoryType"] == 20 and r["OverallQualityID"] == 4),
    ("leather legs", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 2 and r["InventoryType"] == 7),
    ("mail shoulders", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 3 and r["InventoryType"] == 3),
    ("plate head epic", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 4 and r["InventoryType"] == 1 and r["OverallQualityID"] == 4),
    ("cloak", lambda r: r["ClassID"] == 4 and r["InventoryType"] == 16 and r["OverallQualityID"] >= 3),
    ("neck", lambda r: r["ClassID"] == 4 and r["InventoryType"] == 2 and r["OverallQualityID"] >= 3),
    ("ring", lambda r: r["ClassID"] == 4 and r["InventoryType"] == 11 and r["OverallQualityID"] == 4),
    ("trinket", lambda r: r["ClassID"] == 4 and r["InventoryType"] == 12 and r["OverallQualityID"] >= 3),
    ("shield", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 6 and r["OverallQualityID"] == 3),
    ("shield epic", lambda r: r["ClassID"] == 4 and r["SubclassID"] == 6 and r["OverallQualityID"] == 4),
    ("bonus armor", lambda r: r["ClassID"] == 4 and r["QualityModifier"] > 0),
    ("one-hand sword", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 7 and r["InventoryType"] == 13 and r["OverallQualityID"] == 3),
    ("main-hand dagger", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 15 and r["InventoryType"] == 21),
    ("two-hand axe", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 1 and r["InventoryType"] == 17),
    ("staff", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 10 and r["OverallQualityID"] == 4),
    ("bow", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 2),
    ("gun", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 3),
    ("crossbow", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 18),
    ("thrown", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 16),
    ("wand", lambda r: r["ClassID"] == 2 and r["SubclassID"] == 19),
    ("caster one-hand (reduced dps)", lambda r: r["ClassID"] == 2 and r["InventoryType"] in (13, 21) and json.loads(r["Flags"])[4] & 0x100),
    ("caster two-hand (reduced dps)", lambda r: r["ClassID"] == 2 and r["InventoryType"] == 17 and json.loads(r["Flags"])[4] & 0x100),
    ("caster spell-power weapon", lambda r: r["ClassID"] == 2 and json.loads(r["Flags"])[4] & 0x200),
    ("caster healing weapon", lambda r: r["ClassID"] == 2 and json.loads(r["Flags"])[4] & 0x400),
    ("all resistances", lambda r: 124 in json.loads(r["StatModifier_bonusStat"])),
    ("spell power", lambda r: 45 in json.loads(r["StatModifier_bonusStat"]) and r["ClassID"] == 4),
    ("mana per 5", lambda r: 43 in json.loads(r["StatModifier_bonusStat"])),
]
SPARSE_COLS = ["InventoryType", "OverallQualityID", "ItemLevel", "StatModifier_bonusStat", "StatPercentEditor", "Flags",
               "ItemDelay", "DmgVariance", "QualityModifier"]


def sim(computed):
    out = {}
    for mod, v in computed.get("stats", {}).items():
        for s in SIM.get(int(mod), []):
            out[s] = out.get(s, 0) + v
    if computed.get("armor"):
        out[27] = computed["armor"]
    return out


def main(db_path, json_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    src = build_data.Source(db_path)
    tables = build_data.StatTables(src, build_data.ROOT / "scan" / "gametables")
    theirs = {i["id"]: i["scalingOptions"]["0"] for i in json.load(open(json_path))["items"]}
    rows = db.execute("select s.*, i.ClassID, i.SubclassID from ItemSparse s join Item i on i.ID = s.ID order by s.ID").fetchall()
    items, ilvls = [], set()
    for label, pred in PICKS:
        for r in rows:
            if r["ID"] not in theirs or not pred(r):
                continue
            sp = {c: (json.loads(r[c]) if c in ("StatModifier_bonusStat", "StatPercentEditor", "Flags") else r[c]) for c in SPARSE_COLS}
            computed = build_data.compute_item(sp, r["ClassID"], r["SubclassID"], tables)
            opt = theirs[r["ID"]]
            if sim(computed) != {int(k): v for k, v in opt.get("stats", {}).items()}:
                continue  # a known exception, not golden; try the next candidate
            want_weapon = [opt["weaponDamageMin"], opt["weaponDamageMax"]] if "weaponDamageMin" in opt else None
            have_weapon = [computed["weapon"]["min"], computed["weapon"]["max"]] if "weapon" in computed else None
            if want_weapon != have_weapon:
                continue
            items.append({"label": label, "id": r["ID"], "name": r["Display_lang"], "class": r["ClassID"], "subclass": r["SubclassID"],
                          "sparse": sp, "expectedStats": {str(k): v for k, v in sim(computed).items()}, "expectedWeapon": want_weapon})
            ilvls.add(r["ItemLevel"])
            break
        else:
            sys.exit(f"no matching item for pick '{label}'")
    fixture = {
        "source": "wowsims/forever assets/database/db.json (Go implementation); see docs/item-stats-spike.md",
        "tables": {
            "budget": {str(k): {str(q): v for q, v in tables.budget[k].items()} for k in sorted(ilvls)},
            "damage": {t: {str(k): tables.damage[t][k] for k in sorted(ilvls) if k in tables.damage[t]} for t in tables.damage},
            "armor_total": {str(k): {c: tables.armor_total[k][c] for c in ("Cloth", "Leather", "Mail", "Plate")} for k in sorted(ilvls) if k in tables.armor_total},
            "armor_quality": {str(k): tables.armor_quality[k] for k in sorted(ilvls) if k in tables.armor_quality},
            "armor_shield": {str(k): tables.armor_shield[k] for k in sorted(ilvls) if k in tables.armor_shield},
            "armor_location": {str(k): v for k, v in tables.armor_location.items()},
            "block": {str(k): tables.block[k] for k in sorted(ilvls) if k in tables.block},
        },
        "items": items,
    }
    out = Path(__file__).resolve().parent / "golden_items.json"
    out.write_text(json.dumps(fixture, indent=1, sort_keys=True) + "\n")
    print(f"{len(items)} golden items, {len(ilvls)} item levels -> {out.name} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
