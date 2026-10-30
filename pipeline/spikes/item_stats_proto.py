#!/usr/bin/env python3
"""SPIKE (not production code): compute item stats from a db2tool dump and compare with wowsims' db.json.

See docs/item-stats-spike.md for what this proves and how to productionize it.

    item_stats_proto.py <scan.db> <forever/assets/database/db.json> <forever/tools/database/dbc/GameTables/ShieldBlockRegular.txt>
"""
import json
import math
import sqlite3
import sys
from collections import Counter

WEAPON, ARMOR = 2, 4
CASTER_WEAPON = 0x200          # Flags[1]
REDUCED_CASTER_DPS = 0x100     # Flags[4]
CASTER_SPELL_POWER = 0x200     # Flags[4]
CASTER_HEALING_POWER = 0x400   # Flags[4]
SHIELD = 6
ROBE = 20


def arr(text):
    return json.loads(text) if text else []


def rnd(x):  # Go math.Round: half away from zero
    return math.floor(x + 0.5)


def budget_slot(cls, sub, inv):
    if cls == WEAPON:
        if sub in (1, 5, 6, 8, 10):
            return 0
        if sub in (2, 3, 16, 18, 19):
            return 4
        return 3
    if cls == ARMOR:
        if inv in (1, 5, 7, 20):
            return 0
        if inv in (3, 6, 8, 10, 12):
            return 1
        if inv in (2, 9, 11, 14, 16, 22, 23, 28):
            return 2
    return -1


def damage_table(inv, sub, flags1):
    caster = bool(flags1 & CASTER_WEAPON)
    if inv in (13, 21, 22):
        return "ItemDamageOneHandCaster" if caster else "ItemDamageOneHand"
    if inv == 17:
        return "ItemDamageTwoHandCaster" if caster else "ItemDamageTwoHand"
    if inv in (15, 25, 26):
        return {2: "ItemDamageRanged", 3: "ItemDamageRanged", 18: "ItemDamageRanged", 16: "ItemDamageThrown", 19: "ItemDamageWand"}.get(sub)
    return None


class Tables:
    def __init__(self, db):
        self.rpp = {}
        for r in db.execute("select ID, Good, Superior, Epic from RandPropPoints"):
            self.rpp[r["ID"]] = {2: arr(r["Good"]), 3: arr(r["Superior"]), 4: arr(r["Epic"])}
        self.dmg = {t: {r["ItemLevel"]: arr(r["Quality"]) for r in db.execute(f"select ItemLevel, Quality from {t}")}
                    for t in ("ItemDamageOneHand", "ItemDamageOneHandCaster", "ItemDamageTwoHand", "ItemDamageTwoHandCaster",
                              "ItemDamageRanged", "ItemDamageThrown", "ItemDamageWand")}
        self.armor_total = {r["ItemLevel"]: r for r in db.execute("select * from ItemArmorTotal")}
        self.armor_quality = {r["ID"]: arr(r["Qualitymod"]) for r in db.execute("select ID, Qualitymod from ItemArmorQuality")}
        self.armor_shield = {r["ItemLevel"]: arr(r["Quality"]) for r in db.execute("select ItemLevel, Quality from ItemArmorShield")}
        self.armor_loc = {r["ID"]: [r["Clothmodifier"], r["Leathermodifier"], r["Chainmodifier"], r["Platemodifier"]]
                          for r in db.execute("select * from ArmorLocation")}


def load_block(path):
    rows = {}
    for line in open(path).read().splitlines()[1:]:
        p = line.split()
        if p and p[0].isdigit():
            rows[int(p[0])] = [float(x) for x in p[1:8]]
    return rows


# ITEM_MOD id -> sim stat ids (wowsims proto Stat enum), as tools/database/dbc/maps.go
SIM = {0: [30], 1: [29], 3: [1], 4: [0], 5: [3], 6: [13], 7: [2], 12: [22], 13: [25], 14: [26], 15: [23],
       16: [17], 17: [17], 18: [17], 31: [17], 19: [18], 20: [18], 21: [18], 32: [18], 28: [19], 29: [19], 30: [19], 36: [19],
       37: [21], 44: [20], 38: [14], 39: [15], 40: [16], 41: [4], 42: [5], 43: [31], 45: [5, 4], 47: [12], 48: [24], 50: [28],
       51: [33], 52: [34], 54: [36], 55: [35], 56: [32], 83: [37], 84: [9], 85: [7], 86: [10], 87: [8], 88: [11], 89: [6],
       124: [32, 33, 34, 35, 36]}


def sim_stats(o):
    res = {}
    for sid, v in o["stats"].items():
        for s in SIM.get(sid, []):
            res[s] = res.get(s, 0) + v
    if o["armor"]:
        res[27] = o["armor"]
    return res


def compute(it, t):
    cls, sub, inv, q, ilvl = it["ClassID"], it["SubclassID"], it["InventoryType"], it["OverallQualityID"], it["ItemLevel"]
    flags = arr(it["Flags"]) + [0] * 5
    out = {"stats": {}, "armor": 0, "weapon": None}
    slot = budget_slot(cls, sub, inv)
    budget = 0
    if slot >= 0 and q >= 2 and ilvl in t.rpp:
        budget = t.rpp[ilvl][min(q, 4)][slot]
    for sid, alloc in zip(arr(it["StatModifier_bonusStat"]), arr(it["StatPercentEditor"])):
        if sid >= 0 and alloc > 0 and budget > 0:
            out["stats"][sid] = out["stats"].get(sid, 0) + rnd(alloc * budget * 0.0001)

    # Armor: base armor from the level tables; shields from their own table.
    if cls == ARMOR and q <= 6:
        if sub == SHIELD:
            row = t.armor_shield.get(ilvl)
            out["armor"] = rnd(row[q]) if row else 0
        elif sub in (1, 2, 3, 4) and inv in (1, 3, 5, 6, 7, 8, 9, 10, 16, 20) and ilvl in t.armor_total and ilvl in t.armor_quality:
            total = t.armor_total[ilvl]
            base = [total["Cloth"], total["Leather"], total["Mail"], total["Plate"]][sub - 1]
            loc = t.armor_loc.get(5 if inv == ROBE else inv)
            if loc:
                out["armor"] = rnd(base * t.armor_quality[ilvl][q] * loc[sub - 1])

    # Armor-class items: QualityModifier is "bonus armor" (green armor); shields also carry a block value.
    if cls == ARMOR and it["QualityModifier"] > 0:
        out["stats"][50] = it["QualityModifier"]
    if cls == ARMOR and sub == SHIELD and ilvl in t.block:
        out["stats"][48] = out["stats"].get(48, 0) + t.block[ilvl][min(q, 6)]

    # Caster weapons carry spell power no stat slot states.
    if flags[4] & (CASTER_SPELL_POWER | CASTER_HEALING_POWER) and ilvl in t.rpp:
        b = t.rpp[ilvl][min(max(q, 2), 4)][0]
        if flags[4] & CASTER_HEALING_POWER:
            h = 37600 * b // 10000
            out["stats"][41] = out["stats"].get(41, 0) + h
            out["stats"][42] = out["stats"].get(42, 0) + h // 3
        else:
            out["stats"][45] = out["stats"].get(45, 0) + 20000 * b // 10000

    # Weapon damage.
    if cls == WEAPON and it["ItemDelay"]:
        table = damage_table(inv, sub, flags[1])
        row = t.dmg.get(table, {}).get(ilvl) if table else None
        if row:
            speed = it["ItemDelay"] / 1000
            dps = row[4 if q > 6 else q]
            if flags[4] & REDUCED_CASTER_DPS:
                dps *= (2 / 3) if inv in (13, 21, 22) else (29 / 39) if inv == 17 else 1
            qm, var = it["QualityModifier"], it["DmgVariance"]
            low = dps * speed * (1 - var / 2) + qm * speed
            high = dps * speed * (1 + var / 2) + qm * speed
            out["weapon"] = {"min": math.floor(1 if low < 0 else low), "max": math.floor((1 if high < 0 else high) + 0.5), "dps": dps, "speed": speed}
    return out


def main(db_path, json_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    t = Tables(db)
    t.block = load_block(sys.argv[3])
    ours = {}
    rows = db.execute("select s.*, i.ClassID, i.SubclassID from ItemSparse s join Item i on i.ID = s.ID").fetchall()
    for r in rows:
        ours[r["ID"]] = compute(r, t)
    theirs = {i["id"]: i for i in json.load(open(json_path))["items"]}

    c = Counter()
    bad = {"stats": [], "armor": [], "weapon": [], "reduced": []}
    for iid, th in theirs.items():
        o = ours.get(iid)
        if o is None:
            c["missing in our data"] += 1
            continue
        c["compared"] += 1
        opt = th["scalingOptions"]["0"]
        their_stats = {int(k): v for k, v in opt.get("stats", {}).items()}
        mine = sim_stats(o)
        if mine == their_stats:
            c["all stats match (incl. armor)"] += 1
        else:
            c["stats differ"] += 1
            bad["stats"].append((iid, th["name"], "q", th["quality"], "ilvl", opt.get("ilvl"),
                                 {k: (their_stats.get(k), mine.get(k)) for k in sorted(set(mine) | set(their_stats)) if mine.get(k) != their_stats.get(k)}))
        if "weaponDamageMin" in opt:
            w = o["weapon"]
            ok = w and (w["min"], w["max"]) == (opt["weaponDamageMin"], opt["weaponDamageMax"]) and abs(w["dps"] - opt["unroundedDps"]) < 1e-3 * max(1, opt["unroundedDps"]) * 100 if w else False
            # Their unroundedDps is the table DPS (before the reduced-caster share is shown separately).
            if (w["min"], w["max"]) == (opt["weaponDamageMin"], opt["weaponDamageMax"]) if w else False:
                c["weapon damage match"] += 1
            else:
                c["weapon damage differs"] += 1
                bad["weapon"].append((iid, th["name"], (opt["weaponDamageMin"], opt["weaponDamageMax"]), w and (w["min"], w["max"])))
    print(dict(c))
    for k, v in bad.items():
        print(f"\n-- {k}: {len(v)} mismatches; first 8")
        for x in v[:8]:
            print("  ", x)
    # How much is each piece of the formula worth on our whole item set?
    n_alloc = sum(1 for r in rows if any(a > 0 for a in arr(r["StatPercentEditor"])))
    n_stats = sum(1 for o in ours.values() if o["stats"])
    print(f"\nitems with allocations: {n_alloc}; with computed stats: {n_stats}; with armor: {sum(1 for o in ours.values() if o['armor'])}; with weapon damage: {sum(1 for o in ours.values() if o['weapon'])}")
    by_q = Counter((r["OverallQualityID"]) for r in rows if any(a > 0 for a in arr(r["StatPercentEditor"])) and not ours[r["ID"]]["stats"])
    print("items with allocations but no computed stats, by quality:", dict(by_q))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
