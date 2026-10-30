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
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I does not add the script's folder
import tooltips  # noqa: E402

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
# An ingest changing/removing more than this share of entities is flagged for human review.
MAX_CHANGED_RATIO = 0.10
MAX_REMOVED_RATIO = 0.02

# ITEM_MOD ids (ItemSparse.StatModifier_bonusStat) as the game numbers them; written to data/stat-names.json for the UI.
STAT_NAMES = {
    0: "Mana", 1: "Health", 3: "Agility", 4: "Strength", 5: "Intellect", 6: "Spirit", 7: "Stamina",
    12: "Defense rating", 13: "Dodge rating", 14: "Parry rating", 15: "Block rating",
    16: "Melee hit rating", 17: "Ranged hit rating", 18: "Spell hit rating",
    19: "Melee crit rating", 20: "Ranged crit rating", 21: "Spell crit rating",
    28: "Melee haste rating", 29: "Ranged haste rating", 30: "Spell haste rating",
    31: "Hit rating", 32: "Crit rating", 35: "Resilience rating", 36: "Haste rating", 37: "Expertise rating",
    38: "Attack power", 39: "Ranged attack power", 40: "Feral attack power",
    41: "Healing power", 42: "Spell damage", 43: "Mana per 5 sec", 44: "Armor penetration rating",
    45: "Spell power (damage and healing)", 46: "Health per 5 sec", 47: "Spell penetration", 48: "Block value",
    50: "Bonus armor", 51: "Fire resistance", 52: "Frost resistance", 53: "Holy resistance",
    54: "Shadow resistance", 55: "Nature resistance", 56: "Arcane resistance",
    83: "Weapon damage", 84: "Holy damage", 85: "Fire damage", 86: "Nature damage", 87: "Frost damage",
    88: "Shadow damage", 89: "Arcane damage", 124: "All resistances",
}
# Item stat budgets; see docs/item-stats-spike.md for where each rule comes from.
CLASS_WEAPON, CLASS_ARMOR, SUBCLASS_SHIELD = 2, 4, 6
FLAG1_CASTER_WEAPON = 0x200
FLAG4_REDUCED_CASTER_DPS, FLAG4_CASTER_SPELL_POWER, FLAG4_CASTER_HEALING_POWER = 0x100, 0x200, 0x400
ARMOR_SLOTS = {1, 3, 5, 6, 7, 8, 9, 10, 16, 20}  # head, shoulders, chest, waist, legs, feet, wrists, hands, cloak, robe
INV_ROBE, INV_CHEST = 20, 5
MOD_BLOCK_VALUE, MOD_BONUS_ARMOR, MOD_SPELL_POWER, MOD_HEALING, MOD_SPELL_DAMAGE = 48, 50, 45, 41, 42
GAMETABLE_FILES = ("ShieldBlockRegular.txt",)
DAMAGE_TABLES = ("ItemDamageOneHand", "ItemDamageOneHandCaster", "ItemDamageTwoHand", "ItemDamageTwoHandCaster",
                 "ItemDamageRanged", "ItemDamageThrown", "ItemDamageWand")

# Where a player can get a spell, from the skill-line categories of SkillLine.CategoryID.
SKILL_CATEGORY_TAG = {6: "weapon-skill", 8: "armor-skill", 9: "secondary-skill", 10: "language", 11: "profession"}
CLASS_BITS = {1: "Warrior", 2: "Paladin", 4: "Hunter", 8: "Rogue", 16: "Priest", 32: "Death Knight", 64: "Shaman",
              128: "Mage", 256: "Warlock", 512: "Monk", 1024: "Druid", 2048: "Demon Hunter"}
# SpellClassOptions.SpellClassSet ("spell family"): the class a spell belongs to for talent/modifier purposes.
CLASS_FAMILY = {3: "Mage", 4: "Warrior", 5: "Warlock", 6: "Priest", 7: "Druid", 8: "Rogue", 9: "Hunter", 10: "Paladin", 11: "Shaman"}
OBSOLETE_NAME = re.compile(r"\(OLD\)|DEPRECATED|\[DNT\]|^zz|\btest\b", re.IGNORECASE)

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

    def rows(self, table, raw=False):
        """Rows as dicts. The tool writes array columns twice (JSON text plus
        `Col_0`, `Col_1`, ... copies); keep the JSON form and drop the copies.
        Floats are rounded to 6 decimals unless `raw`: the tooltip model needs the exact float32 values."""
        if table not in self.tables:
            return []
        cols = self.columns[table]
        names = {c for c, _ in cols}
        keep = [(c, t) for c, t in cols if not (_EXPANDED.match(c) and _EXPANDED.match(c).group(1) in names)]
        out = []
        for values in self.db.execute(f'select {",".join(chr(34)+c+chr(34) for c, _ in keep)} from "{table}"'):
            row = {}
            for (c, t), v in zip(keep, values):
                if t == "TEXT" and not c.endswith("_lang") and isinstance(v, str) and v.startswith("["):
                    v = json.loads(v)
                    v = v if raw else [norm(x) for x in v]
                row[c] = v if raw else norm(v)
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


def spell_availability(src):
    """{spell id: sorted tags} saying where a spell comes from.

    Tags: class:<Name> / class (class skill lines), class-family:<Name> (SpellClassSet: belongs to that class's spell family,
    which also catches rune-style and proc spells that no skill line teaches), pet, talent, weapon-skill, armor-skill, secondary-skill, language,
    profession, skill, item (an item's use/equip effect), item-set (set bonus), triggered (fired, directly or through
    further triggers, by a spell that has a source of its own), marked-obsolete (name says OLD/DEPRECATED/test). A spell with no tag at all is
    not reachable through any table we read: internal, scripted, or a source we do not extract."""
    tags = {}

    def add(spell, tag):
        if spell:
            tags.setdefault(spell, set()).add(tag)

    lines = {r["ID"]: r for r in src.rows("SkillLine")}
    for r in src.rows("SkillLineAbility"):
        line = lines.get(r["SkillLine"], {})
        category, mask = line.get("CategoryID"), r.get("ClassMask", 0)
        if line.get("DisplayName_lang", "").startswith("Pet -"):
            add(r["Spell"], "pet")
        elif category == 7:
            named = [name for bit, name in CLASS_BITS.items() if mask > 0 and mask & bit]
            for name in named or [None]:
                add(r["Spell"], f"class:{name}" if name else "class")
        else:
            add(r["Spell"], SKILL_CATEGORY_TAG.get(category, "skill"))
    for r in src.rows("Talent"):
        for spell in [r.get("SpellID", 0), *(r.get("SpellRank") or [])]:
            add(spell, "talent")
    for r in src.rows("TraitDefinition"):
        add(r.get("SpellID", 0), "talent")
    linked = {r["ItemEffectID"] for r in src.rows("ItemXItemEffect")}
    for r in src.rows("ItemEffect"):
        if r["ID"] in linked:
            add(r.get("SpellID", 0), "item")
    for r in src.rows("ItemSetSpell"):
        add(r.get("SpellID", 0), "item-set")
    for r in src.rows("SpellClassOptions"):
        if r.get("SpellClassSet") in CLASS_FAMILY:
            add(r["SpellID"], f"class-family:{CLASS_FAMILY[r['SpellClassSet']]}")
    # Spells fired (directly or through further triggers) by a spell that has a source of its own.
    triggers = {}
    for r in src.rows("SpellEffect"):
        if r.get("EffectTriggerSpell"):
            triggers.setdefault(r["SpellID"], set()).add(r["EffectTriggerSpell"])
    queue = list(tags)
    while queue:
        for target in triggers.get(queue.pop(), ()):
            if target not in tags:
                queue.append(target)
            add(target, "triggered")
    for r in src.rows("SpellName"):
        if OBSOLETE_NAME.search(r.get("Name_lang", "")):
            add(r["ID"], "marked-obsolete")
    return {spell: sorted(t) for spell, t in tags.items()}


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

    availability = spell_availability(src)
    renderer = tooltips.Renderer(tooltips.Facts(src))
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
        rec["computed"] = {"availability": availability.get(sid, [])}
        rendered, blocked = renderer.render(renderer.facts.get(sid))
        if rendered:
            rec["computed"]["tooltip"] = rendered           # text, or null where a token could not be rendered exactly
        if blocked:
            rec["computed"]["tooltipBlockedBy"] = blocked
        out[sid] = rec
    return out


def rnd(x):
    """Round half up, as the client does (Go's math.Round); Python's round() is banker's."""
    return math.floor(x + 0.5)


def budget_slot(cls, sub, inv):
    """Column of RandPropPoints an item's stats are budgeted from; -1 = none."""
    if cls == CLASS_WEAPON:
        if sub in (1, 5, 6, 8, 10):  # two-hand axe/mace/polearm/sword, staff
            return 0
        if sub in (2, 3, 16, 18, 19):  # bow, gun, thrown, crossbow, wand
            return 4
        return 3
    if cls == CLASS_ARMOR:
        if inv in (1, 5, 7, 20):
            return 0
        if inv in (3, 6, 8, 10, 12):
            return 1
        if inv in (2, 9, 11, 14, 16, 22, 23, 28):
            return 2
    return -1


def damage_table(inv, sub, flags1):
    caster = bool(flags1 & FLAG1_CASTER_WEAPON)
    if inv in (13, 21, 22):
        return "ItemDamageOneHandCaster" if caster else "ItemDamageOneHand"
    if inv == 17:
        return "ItemDamageTwoHandCaster" if caster else "ItemDamageTwoHand"
    if inv in (15, 25, 26):
        return {2: "ItemDamageRanged", 3: "ItemDamageRanged", 18: "ItemDamageRanged", 16: "ItemDamageThrown", 19: "ItemDamageWand"}.get(sub)
    return None


def read_gametable(directory, name):
    """Rows of a tab-separated GameTable, keyed by its first (level) column."""
    path = Path(directory) / name
    if not path.exists():
        sys.exit(f"Missing GameTable {path}; see scan/gametables/README.md.")
    rows = {}
    for line in path.read_text().splitlines()[1:]:
        parts = line.split()
        if parts and parts[0].isdigit():
            rows[int(parts[0])] = [float(x) for x in parts[1:]]
    return rows


class StatTables:
    """Level tables the item stat rules need. Missing DB2 tables abort: silently computing nothing would look like a mass change."""

    def __init__(self, src, gametables):
        need = ["RandPropPoints", "ItemArmorTotal", "ItemArmorQuality", "ItemArmorShield", "ArmorLocation", *DAMAGE_TABLES]
        missing = [t for t in need if t not in src.tables]
        if missing:
            sys.exit(f"db2tool dump lacks tables needed for item stats: {', '.join(missing)} (scan/settings.template.json)")
        self.budget = {r["ID"]: {2: r["Good"], 3: r["Superior"], 4: r["Epic"]} for r in src.rows("RandPropPoints")}
        self.damage = {t: {r["ItemLevel"]: r["Quality"] for r in src.rows(t)} for t in DAMAGE_TABLES}
        self.armor_total = {r["ItemLevel"]: r for r in src.rows("ItemArmorTotal")}
        self.armor_quality = {r["ID"]: r["Qualitymod"] for r in src.rows("ItemArmorQuality")}
        self.armor_shield = {r["ItemLevel"]: r["Quality"] for r in src.rows("ItemArmorShield")}
        self.armor_location = {r["ID"]: [r["Clothmodifier"], r["Leathermodifier"], r["Chainmodifier"], r["Platemodifier"]]
                               for r in src.rows("ArmorLocation")}
        self.block = read_gametable(gametables, "ShieldBlockRegular.txt")


def compute_item(sp, cls, sub, t):
    """Stats, armor and weapon damage as the client shows them, from the budget tables.

    Returns {} for items with nothing to show. Equip-effect stats are deliberately not folded in; they stay in `effects`."""
    inv, q, ilvl = sp.get("InventoryType", 0), sp.get("OverallQualityID", 0), sp.get("ItemLevel", 0)
    flags = list(sp.get("Flags") or []) + [0] * 5
    stats = {}

    slot = budget_slot(cls, sub, inv)
    budget = t.budget[ilvl][min(q, 4)][slot] if slot >= 0 and q >= 2 and ilvl in t.budget else 0
    for mod, alloc in zip(sp.get("StatModifier_bonusStat") or [], sp.get("StatPercentEditor") or []):
        if mod >= 0 and alloc > 0 and budget > 0:
            stats[mod] = stats.get(mod, 0) + rnd(alloc * budget * 0.0001)

    armor = 0
    if cls == CLASS_ARMOR and q <= 6:
        if sub == SUBCLASS_SHIELD:
            if ilvl in t.armor_shield:
                armor = rnd(t.armor_shield[ilvl][q])
        elif sub in (1, 2, 3, 4) and inv in ARMOR_SLOTS and ilvl in t.armor_total and ilvl in t.armor_quality:
            total = t.armor_total[ilvl]
            base = (total["Cloth"], total["Leather"], total["Mail"], total["Plate"])[sub - 1]
            location = t.armor_location.get(INV_CHEST if inv == INV_ROBE else inv)
            if location:
                armor = rnd(base * t.armor_quality[ilvl][q] * location[sub - 1])
    if cls == CLASS_ARMOR and sp.get("QualityModifier", 0) > 0:  # "green" bonus armor
        stats[MOD_BONUS_ARMOR] = sp["QualityModifier"]
    if cls == CLASS_ARMOR and sub == SUBCLASS_SHIELD and ilvl in t.block:
        stats[MOD_BLOCK_VALUE] = stats.get(MOD_BLOCK_VALUE, 0) + t.block[ilvl][min(q, 6)]

    # Caster weapons carry spell power that no stat slot states.
    if flags[4] & (FLAG4_CASTER_SPELL_POWER | FLAG4_CASTER_HEALING_POWER) and ilvl in t.budget:
        b = t.budget[ilvl][min(max(q, 2), 4)][0]
        if flags[4] & FLAG4_CASTER_HEALING_POWER:
            healing = 37600 * b // 10000
            stats[MOD_HEALING] = stats.get(MOD_HEALING, 0) + healing
            stats[MOD_SPELL_DAMAGE] = stats.get(MOD_SPELL_DAMAGE, 0) + healing // 3
        else:
            stats[MOD_SPELL_POWER] = stats.get(MOD_SPELL_POWER, 0) + 20000 * b // 10000

    weapon = None
    if cls == CLASS_WEAPON and sp.get("ItemDelay"):
        table = damage_table(inv, sub, flags[1])
        row = t.damage.get(table, {}).get(ilvl) if table else None
        if row:
            speed = sp["ItemDelay"] / 1000
            dps = row[4 if q > 6 else q]
            if flags[4] & FLAG4_REDUCED_CASTER_DPS:
                dps *= (2 / 3) if inv in (13, 21, 22) else (29 / 39) if inv == 17 else 1
            bonus, var = sp.get("QualityModifier", 0) * speed, sp.get("DmgVariance", 0)
            low, high = dps * speed * (1 - var / 2) + bonus, dps * speed * (1 + var / 2) + bonus
            weapon = {"min": math.floor(1 if low < 0 else low), "max": rnd(1 if high < 0 else high),
                      "dps": norm(dps), "speed": norm(speed)}

    computed = {}
    if stats:
        computed["stats"] = {str(k): norm(v) for k, v in sorted(stats.items())}
    if armor:
        computed["armor"] = armor
    if weapon:
        computed["weapon"] = weapon
    return computed


def build_items(src, gametables):
    item = {r["ID"]: r for r in src.rows("Item")}
    classes = {r["ClassID"]: r["ClassName_lang"] for r in src.rows("ItemClass")}
    subclasses = {(r["ClassID"], r["SubClassID"]): r["DisplayName_lang"] for r in src.rows("ItemSubClass")}
    namedesc = {r["ID"]: r["Description_lang"] for r in src.rows("ItemNameDescription")}
    effects = {r["ID"]: r for r in src.rows("ItemEffect")}
    item_effects = src.by_key("ItemXItemEffect", "ItemID")
    bonus_trees = src.by_key("ItemXBonusTree", "ItemID")
    sets = {r["ID"]: r for r in src.rows("ItemSet")}
    tables = StatTables(src, gametables)

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
            "computed": compute_item(sp, cls, sub, tables),
            "effects": [],
            "bonusTrees": sorted(r["ItemBonusTreeID"] for r in bonus_trees.get(iid, [])),
        }
        # Ordered by the game's own slot, then spell: adding or changing one effect doesn't renumber the others in the history.
        linked = [effects[link["ItemEffectID"]] for link in item_effects.get(iid, []) if link["ItemEffectID"] in effects]
        linked.sort(key=lambda e: (e.get("LegacySlotIndex", 0), e.get("SpellID", 0), e.get("TriggerType", 0)))
        rec["effects"] = [strip(e, "ID") for e in linked]
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


def areas(changes):
    """Top-level record sections a set of changes touches, e.g. ["computed", "effects"]. Lets a UI separate
    'the stats changed' from 'the effect changed' without parsing paths."""
    return sorted({re.split(r"[.\[]", path, maxsplit=1)[0] for path in changes})


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
            ev = {**event_base, "type": "changed", "areas": areas(changes), "changes": changes}
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
    if args.hotfix_cache:
        scan["hotfixCacheSha256"] = hashlib.sha256(Path(args.hotfix_cache).read_bytes()).hexdigest()

    state_path = DATA / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    fingerprint = schema_fingerprint(src)
    if state:
        if (build, push) == (state["build"], state["hotfixPush"]) and not args.force:
            print(f"Already ingested {version} push {push}; nothing to do.")
            return 0
        if (build, push) < (state["build"], state["hotfixPush"]) and not args.force:
            sys.exit(f"Refusing to ingest older data ({version}/{push}) over {state['version']}/{state['hotfixPush']}.")
        # A scan that lost its hotfix overlay would record every hotfixed entity as changed.
        if "none applied" in scan.get("hotfixSummary", "") and state["hotfixPush"] > 0 and not args.allow_no_hotfixes:
            sys.exit("db2tool applied no hotfixes to this build, but the previous ingest had some. Check the hotfix cache "
                     "(docs/update-runbook.md, \"When it breaks\"), or pass --allow-no-hotfixes if that is intended.")
        changed_tables = sorted(t for t in set(fingerprint) | set(state["schema"]) if fingerprint.get(t) != state["schema"].get(t))
        if changed_tables and not args.allow_schema_change:
            sys.exit("Table layouts changed since the last ingest, which would show up as bogus field diffs:\n  "
                     + ", ".join(changed_tables) + "\nReview docs/update-runbook.md (\"Schema changes\"), then re-run with --allow-schema-change.")

    baseline = state is None
    results = {}
    for kind, build_records in (("spells", lambda: build_spells(src)), ("items", lambda: build_items(src, args.gametables))):
        current, history, stats = ingest_entities(kind, build_records(), build, push, baseline)
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
    builds.append({"version": version, "build": build, "hotfixPush": push, "counts": results,
                   "hotfixes": scan.get("hotfixSummary", "unknown")})
    new_state["builds"] = builds
    reasons = [] if baseline else suspicious(results, state["counts"])
    summary = {"version": version, "push": push, "baseline": baseline, "suspicious": reasons, **results}
    if not args.dry_run:
        state_path.write_text(json.dumps(new_state, indent=1, sort_keys=True) + "\n")
        (DATA / "stat-names.json").write_text(json.dumps({str(k): v for k, v in sorted(STAT_NAMES.items())}, indent=1) + "\n")
    if args.summary_file:
        Path(args.summary_file).write_text(render_summary(summary, scan))
    print(json.dumps(summary, indent=1))
    return 0


def suspicious(results, previous):
    """Reasons an ingest looks like a tool/schema problem rather than a game update."""
    reasons = []
    for kind, st in results.items():
        total = sum(st[k] for k in ("changed", "unchanged", "removed")) or 1
        if st["changed"] / total > MAX_CHANGED_RATIO:
            reasons.append(f"{kind}: {st['changed']} of {total} entities changed (>{MAX_CHANGED_RATIO:.0%})")
        if st["removed"] / total > MAX_REMOVED_RATIO:
            reasons.append(f"{kind}: {st['removed']} of {total} entities removed (>{MAX_REMOVED_RATIO:.0%})")
    return reasons


def render_summary(summary, scan):
    lines = [f"## Forever {summary['version']} (hotfix push {summary['push']})", "",
             f"Hotfixes: {scan.get('hotfixSummary', 'unknown')}", "",
             "| | added | changed | removed | unchanged |", "|---|---|---|---|---|"]
    for kind in ("spells", "items"):
        st = summary[kind]
        lines.append(f"| {kind} | {st['added']} | {st['changed']} | {st['removed']} | {st['unchanged']} |")
    if scan.get("lockedRows"):
        lines += ["", "Rows hidden behind unknown TACT keys: "
                  + ", ".join(f"{t} {n}" for t, n in sorted(scan["lockedRows"].items()))]
    if summary["suspicious"]:
        lines += ["", "**Needs review - this looks like a tool or schema problem, not a game update:**"]
        lines += [f"- {r}" for r in summary["suspicious"]]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="diff a db2tool dump against data/ and record the changes")
    i.add_argument("--db", required=True, help="SQLite file written by db2tool")
    i.add_argument("--scan-log", help="saved db2tool stdout (records locked-row counts)")
    i.add_argument("--hotfix-cache", help="DBCache.bin used for the scan; its hash is stored so `builds.py check` can detect new hotfixes")
    i.add_argument("--gametables", default=str(ROOT / "scan" / "gametables"),
                   help="directory with the GameTable .txt files the stat rules need (default: the vendored scan/gametables)")
    i.add_argument("--summary-file", help="write a markdown summary here (used as the PR body)")
    i.add_argument("--allow-no-hotfixes", action="store_true", help="accept a scan with no hotfix overlay (historical builds)")
    i.add_argument("--allow-schema-change", action="store_true")
    i.add_argument("--force", action="store_true", help="re-ingest the same or an older build")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(fn=cmd_ingest)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
