"""Tests for build_data.py against tiny synthetic db2tool dumps.

Run from the repo root: python3 -m unittest discover -s pipeline/tests -v
"""
import argparse
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_data  # noqa: E402


# ITEM_MOD id -> wowsims' sim stat ids (tools/database/dbc/maps.go). Only used to compare with their output.
SIM = {0: [30], 1: [29], 3: [1], 4: [0], 5: [3], 6: [13], 7: [2], 12: [22], 13: [25], 14: [26], 15: [23],
       16: [17], 17: [17], 18: [17], 31: [17], 19: [18], 20: [18], 21: [18], 32: [18], 28: [19], 29: [19], 30: [19], 36: [19],
       37: [21], 44: [20], 38: [14], 39: [15], 40: [16], 41: [4], 42: [5], 43: [31], 45: [5, 4], 47: [12], 48: [24], 50: [28],
       51: [33], 52: [34], 54: [36], 55: [35], 56: [32], 83: [37], 84: [9], 85: [7], 86: [10], 87: [8], 88: [11], 89: [6],
       124: [32, 33, 34, 35, 36]}


def make_db(path, version="1.60.1.100", push=1, spells=None, items=None, extra_column=False, effects=None):
    """Write the tables build_data reads. `spells` maps id -> (name, description); `items` maps id -> (name, ilvl, inventory type)
    or a dict of ItemSparse/Item columns overriding the defaults; `effects` maps item id -> [spell ids] (equip effects)."""
    db = sqlite3.connect(path)
    db.execute("create table BuildInfo (Version TEXT, Product TEXT, HotfixPush INTEGER)")
    db.execute("insert into BuildInfo values (?, 'wowf', ?)", (version, push))
    db.execute("create table Spell (ID INTEGER, NameSubtext_lang TEXT, Description_lang TEXT, AuraDescription_lang TEXT)")
    db.execute("create table SpellName (ID INTEGER, Name_lang TEXT)")
    db.execute("create table SpellMisc (ID INTEGER, DifficultyID INTEGER, SchoolMask INTEGER, SpellIconFileDataID INTEGER, SpellID INTEGER"
               + (", NewColumn INTEGER" if extra_column else "") + ")")
    for sid, (name, desc) in (spells or {}).items():
        db.execute("insert into Spell values (?, '', ?, '')", (sid, desc))
        db.execute("insert into SpellName values (?, ?)", (sid, name))
        db.execute("insert into SpellMisc (ID, DifficultyID, SchoolMask, SpellIconFileDataID, SpellID) values (?, 0, 4, 0, ?)", (sid * 10, sid))
    db.execute("create table Item (ID INTEGER, ClassID INTEGER, SubclassID INTEGER, InventoryType INTEGER, IconFileDataID INTEGER)")
    db.execute("create table ItemSparse (ID INTEGER, Display_lang TEXT, Description_lang TEXT, ItemLevel INTEGER, RequiredLevel INTEGER,"
               " InventoryType INTEGER, OverallQualityID INTEGER, StatModifier_bonusStat TEXT, StatPercentEditor TEXT, Flags TEXT,"
               " ItemDelay INTEGER, DmgVariance REAL, QualityModifier REAL)")
    db.execute("create table ItemClass (ID INTEGER, ClassName_lang TEXT, ClassID INTEGER)")
    db.execute("insert into ItemClass values (1, 'Weapon', 2)")
    db.execute("create table ItemEffect (ID INTEGER, LegacySlotIndex INTEGER, TriggerType INTEGER, SpellID INTEGER)")
    db.execute("create table ItemXItemEffect (ID INTEGER, ItemEffectID INTEGER, ItemID INTEGER)")
    for iid, spec in (items or {}).items():
        name, ilvl, inv = spec if isinstance(spec, tuple) else (None, None, None)
        row = dict(Display_lang=name or "Item", ItemLevel=ilvl or 1, InventoryType=inv or 0, ClassID=2, SubclassID=7, OverallQualityID=2,
                   StatModifier_bonusStat=[3, -1], StatPercentEditor=[0, 0], Flags=[0, 0, 0, 0, 0], ItemDelay=0, DmgVariance=0.0,
                   QualityModifier=0.0, RequiredLevel=1)
        if isinstance(spec, dict):
            row.update(spec)
        db.execute("insert into Item values (?, ?, ?, ?, 0)", (iid, row["ClassID"], row["SubclassID"], row["InventoryType"]))
        db.execute("insert into ItemSparse values (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (iid, row["Display_lang"], row["ItemLevel"], row["RequiredLevel"], row["InventoryType"], row["OverallQualityID"],
                    json.dumps(row["StatModifier_bonusStat"]), json.dumps(row["StatPercentEditor"]), json.dumps(row["Flags"]),
                    row["ItemDelay"], row["DmgVariance"], row["QualityModifier"]))
    for n, (iid, spell_ids) in enumerate((effects or {}).items()):
        for k, spell_id in enumerate(spell_ids):
            eid = n * 10 + k + 1
            db.execute("insert into ItemEffect values (?, ?, 1, ?)", (eid, k, spell_id))  # slot = position in the list
            db.execute("insert into ItemXItemEffect values (?, ?, ?)", (eid, eid, iid))
    # Level tables for ilvl 10 (see CLASS_TABLES in the stat tests).
    db.execute("create table RandPropPoints (ID INTEGER, Good TEXT, Superior TEXT, Epic TEXT)")
    db.execute("insert into RandPropPoints values (10, '[50,40,30,20,10]', '[100,80,60,40,20]', '[200,160,120,80,40]')")
    db.execute("create table ItemArmorTotal (ID INTEGER, ItemLevel INTEGER, Cloth REAL, Leather REAL, Mail REAL, Plate REAL)")
    db.execute("insert into ItemArmorTotal values (10, 10, 100, 200, 300, 400)")
    db.execute("create table ItemArmorQuality (ID INTEGER, Qualitymod TEXT)")
    db.execute("insert into ItemArmorQuality values (10, '[0.9,0.95,1,1.1,1.2,1.2,1.2]')")
    db.execute("create table ItemArmorShield (ID INTEGER, ItemLevel INTEGER, Quality TEXT)")
    db.execute("insert into ItemArmorShield values (10, 10, '[5,10,16,27.5,38,38,38]')")
    db.execute("create table ArmorLocation (ID INTEGER, Clothmodifier REAL, Leathermodifier REAL, Chainmodifier REAL, Platemodifier REAL)")
    db.execute("insert into ArmorLocation values (5, 0.5, 0.5, 0.5, 0.5)")
    for t in ("ItemDamageOneHand", "ItemDamageOneHandCaster", "ItemDamageTwoHand", "ItemDamageTwoHandCaster",
              "ItemDamageRanged", "ItemDamageThrown", "ItemDamageWand"):
        db.execute(f"create table {t} (ID INTEGER, ItemLevel INTEGER, Quality TEXT)")
        db.execute(f"insert into {t} values (10, 10, '[1,2,3,10,20,20,20]')")
    db.commit()
    db.close()


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        build_data.DATA = Path(self.tmp.name) / "data"
        self.gametables = Path(self.tmp.name) / "gametables"
        self.gametables.mkdir()
        (self.gametables / "ShieldBlockRegular.txt").write_text("Level\tPoor\tStandard\tGood\tSuperior\tEpic\tLegendary\tArtifact\n"
                                                                "10\t1\t2\t3\t7\t9\t9\t9\n")

    def db(self, name, **kw):
        path = Path(self.tmp.name) / name
        make_db(path, **kw)
        return path

    def ingest(self, db, **flags):
        ns = dict(db=str(db), gametables=str(self.gametables), scan_log=None, hotfix_cache=None, summary_file=None, allow_no_hotfixes=False,
                  allow_schema_change=False, force=False, dry_run=False)
        ns.update(flags)
        return build_data.cmd_ingest(argparse.Namespace(**ns))

    def current(self, kind):
        return build_data.read_jsonl(build_data.DATA / f"{kind}.jsonl")

    def history(self, kind):
        return build_data.read_jsonl(build_data.DATA / "history" / f"{kind}.jsonl")

    def test_baseline_then_change(self):
        self.ingest(self.db("a.db", version="1.60.1.100", push=1,
                            spells={1: ("Fireball", "Old text"), 2: ("Frostbolt", "Stable")},
                            items={10: ("Sword", 5, 21)}))
        spells = self.current("spells")
        self.assertTrue(spells[1]["baseline"])
        self.assertEqual(spells[1]["firstSeen"], {"build": 100, "push": 1})
        self.assertEqual(self.history("spells"), {})  # baseline writes no events

        self.ingest(self.db("b.db", version="1.60.1.200", push=7,
                            spells={1: ("Fireball", "New text"), 2: ("Frostbolt", "Stable")},
                            items={10: ("Sword", 6, 21)}))
        spells, items = self.current("spells"), self.current("items")
        self.assertEqual(spells[1]["lastChanged"], {"build": 200, "push": 7})
        self.assertEqual(spells[2]["lastChanged"], {"build": 100, "push": 1})
        self.assertEqual(spells[1]["firstSeen"], {"build": 100, "push": 1})
        ev = self.history("spells")[1]["events"][0]
        self.assertEqual(ev["type"], "changed")
        self.assertEqual(ev["changes"], {"description": ["Old text", "New text"]})
        self.assertNotIn(2, self.history("spells"))
        self.assertEqual(self.history("items")[10]["events"][0]["changes"], {"itemLevel": [5, 6]})
        self.assertTrue(items[10]["data"]["isGear"])

    def test_added_and_removed(self):
        self.ingest(self.db("a.db", spells={1: ("A", "x"), 2: ("B", "y")}))
        self.ingest(self.db("b.db", version="1.60.1.200", spells={1: ("A", "x"), 3: ("C", "z")}))
        spells = self.current("spells")
        self.assertTrue(spells[2]["removed"])
        self.assertFalse(spells[3].get("baseline"))
        types = {i: [e["type"] for e in h["events"]] for i, h in self.history("spells").items()}
        self.assertEqual(types, {2: ["removed"], 3: ["added"]})

    def test_same_or_older_build_is_refused(self):
        self.ingest(self.db("a.db", version="1.60.1.200", push=5, spells={1: ("A", "x")}))
        self.assertEqual(self.ingest(self.db("same.db", version="1.60.1.200", push=5, spells={1: ("A", "y")})), 0)
        self.assertEqual(self.current("spells")[1]["data"]["description"], "x")  # no-op
        with self.assertRaises(SystemExit):
            self.ingest(self.db("old.db", version="1.60.1.100", push=9, spells={1: ("A", "z")}))

    def test_new_hotfix_push_on_same_build_is_ingested(self):
        self.ingest(self.db("a.db", version="1.60.1.200", push=5, spells={1: ("A", "x")}))
        self.ingest(self.db("b.db", version="1.60.1.200", push=6, spells={1: ("A", "y")}))
        self.assertEqual(self.current("spells")[1]["lastChanged"], {"build": 200, "push": 6})

    def test_schema_change_blocks_ingest(self):
        self.ingest(self.db("a.db", spells={1: ("A", "x")}))
        changed = self.db("b.db", version="1.60.1.200", spells={1: ("A", "x")}, extra_column=True)
        with self.assertRaises(SystemExit):
            self.ingest(changed)
        self.assertEqual(self.ingest(changed, allow_schema_change=True), 0)

    def test_output_is_deterministic(self):
        db = self.db("a.db", spells={2: ("B", "y"), 1: ("A", "x")}, items={10: ("Sword", 5, 21)})
        self.ingest(db)
        first = (build_data.DATA / "spells.jsonl").read_bytes()
        build_data.DATA = Path(self.tmp.name) / "data2"
        self.ingest(db)
        self.assertEqual(first, (build_data.DATA / "spells.jsonl").read_bytes())

    def log(self, text):
        path = Path(self.tmp.name) / "scan.log"
        path.write_text(text)
        return str(path)

    def test_scan_without_hotfixes_is_refused_after_a_hotfixed_one(self):
        self.ingest(self.db("a.db", version="1.60.1.100", push=50, spells={1: ("A", "x")}))
        lost = self.db("b.db", version="1.60.1.200", push=0, spells={1: ("A", "x")})
        log = self.log("Hotfixes: none applied for build 200\n")
        with self.assertRaises(SystemExit):
            self.ingest(lost, scan_log=log)
        self.assertEqual(self.ingest(lost, scan_log=log, allow_no_hotfixes=True), 0)

    def test_mass_change_is_flagged_and_summarised(self):
        many = {i: (f"S{i}", "old") for i in range(1, 21)}
        self.ingest(self.db("a.db", spells=many))
        out = Path(self.tmp.name) / "summary.md"
        self.ingest(self.db("b.db", version="1.60.1.200", spells={i: (f"S{i}", "new") for i in many}),
                    summary_file=str(out), scan_log=self.log("  Spell: 3 rows locked by TACT key AB\nHotfixes: build 200 up to push 9\n"))
        text = out.read_text()
        self.assertIn("Needs review", text)
        self.assertIn("| spells | 0 | 20 | 0 | 0 |", text)
        self.assertIn("Spell 3", text)
        self.assertEqual(build_data.suspicious({"spells": {"changed": 1, "unchanged": 99, "removed": 0}}, {}), [])

    def test_hotfix_cache_hash_is_stored(self):
        cache = Path(self.tmp.name) / "DBCache.bin"
        cache.write_bytes(b"abc")
        self.ingest(self.db("a.db", spells={1: ("A", "x")}), hotfix_cache=str(cache))
        state = json.loads((build_data.DATA / "state.json").read_text())
        self.assertEqual(state["scan"]["hotfixCacheSha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def item(self, **cols):
        """Ingest a single item with the given columns and return its `computed` block."""
        self.ingest(self.db(f"i{len(list(Path(self.tmp.name).glob('i*.db')))}.db", items={1: cols}), force=True)
        return self.current("items")[1]["data"]["computed"]

    def test_stats_come_from_allocation_times_budget(self):
        # Superior epic-ish chest (budget slot 0 = 100): stamina 50%, intellect 12.5% -> 50 and 12.5 rounded half up.
        computed = self.item(ClassID=4, SubclassID=1, InventoryType=5, OverallQualityID=3, ItemLevel=10,
                             StatModifier_bonusStat=[7, 5, -1], StatPercentEditor=[5000, 1250, 0])
        self.assertEqual(computed["stats"], {"5": 13, "7": 50})
        self.assertEqual(computed["armor"], 55)  # cloth 100 * superior 1.1 * chest 0.5

    def test_common_and_poor_items_get_no_budget_stats(self):
        self.assertEqual(self.item(ClassID=4, SubclassID=1, InventoryType=5, OverallQualityID=1, ItemLevel=10,
                                   StatModifier_bonusStat=[7], StatPercentEditor=[5000]).get("stats"), None)

    def test_shield_gets_armor_block_value_and_bonus_armor(self):
        computed = self.item(ClassID=4, SubclassID=6, InventoryType=14, OverallQualityID=3, ItemLevel=10, QualityModifier=40.0)
        self.assertEqual(computed["armor"], 28)  # 27.5 rounds half up
        self.assertEqual(computed["stats"], {"48": 7, "50": 40.0})

    def test_weapon_damage_range(self):
        computed = self.item(ClassID=2, SubclassID=7, InventoryType=13, OverallQualityID=3, ItemLevel=10,
                             ItemDelay=2000, DmgVariance=0.5)
        # dps 10, speed 2: low = floor(20*0.75) = 15, high = floor(20*1.25 + 0.5) = 25
        self.assertEqual(computed["weapon"], {"min": 15, "max": 25, "dps": 10.0, "speed": 2.0})

    def test_reduced_caster_dps_flag_scales_one_hand_damage(self):
        computed = self.item(ClassID=2, SubclassID=7, InventoryType=13, OverallQualityID=3, ItemLevel=10, ItemDelay=2000,
                             DmgVariance=0.0, Flags=[0, 0, 0, 0, 0x100])
        self.assertEqual((computed["weapon"]["min"], computed["weapon"]["max"]), (13, 13))  # floor(10 * 2/3 * 2)

    def test_caster_weapon_spell_power_flag(self):
        computed = self.item(ClassID=2, SubclassID=10, InventoryType=17, OverallQualityID=3, ItemLevel=10, Flags=[0, 0, 0, 0, 0x200])
        self.assertEqual(computed["stats"], {"45": 200})  # 20000 * 100 / 10000

    def test_equip_effect_changes_are_separate_from_stat_changes(self):
        base = dict(ClassID=4, SubclassID=1, InventoryType=5, OverallQualityID=3, ItemLevel=10,
                    StatModifier_bonusStat=[7], StatPercentEditor=[5000])
        self.ingest(self.db("a.db", version="1.60.1.100", items={1: base}, effects={1: [100]}))
        # build 200: only the equip effect changes
        self.ingest(self.db("b.db", version="1.60.1.200", items={1: base}, effects={1: [101]}))
        # build 300: only the stat allocation changes
        self.ingest(self.db("c.db", version="1.60.1.300", items={1: {**base, "StatPercentEditor": [6000]}}, effects={1: [101]}))
        events = self.history("items")[1]["events"]
        # Raising an allocation touches the raw input (sparse) and the result (computed); never effects.
        self.assertEqual([e["areas"] for e in events], [["effects"], ["computed", "sparse"]])
        self.assertEqual(events[0]["changes"], {"effects[0].SpellID": [100, 101]})

    def test_adding_an_effect_does_not_renumber_existing_ones(self):
        base = dict(ClassID=4, SubclassID=1, InventoryType=5)
        self.ingest(self.db("a.db", version="1.60.1.100", items={1: base}, effects={1: [200]}))
        self.ingest(self.db("b.db", version="1.60.1.200", items={1: base}, effects={1: [200, 100]}))  # new effect in slot 1
        event = self.history("items")[1]["events"][0]
        self.assertEqual(sorted(event["changes"]), ["effects[1].LegacySlotIndex", "effects[1].SpellID", "effects[1].TriggerType"])
        self.assertEqual(event["areas"], ["effects"])

    def test_missing_gametable_aborts(self):
        (self.gametables / "ShieldBlockRegular.txt").unlink()
        with self.assertRaises(SystemExit):
            self.ingest(self.db("a.db", items={1: ("A", 10, 5)}))

    def test_default_values_are_omitted(self):
        self.ingest(self.db("a.db", spells={1: ("A", "x")}))
        misc = self.current("spells")[1]["data"]["related"]["SpellMisc"][0]
        self.assertEqual(misc, {"SchoolMask": 4})


class GoldenStatsTest(unittest.TestCase):
    """Real items whose stats, armor and weapon damage equal wowsims' tooltip-checked output (see make_golden.py)."""

    @classmethod
    def setUpClass(cls):
        data = json.loads((Path(__file__).parent / "golden_items.json").read_text())
        t = object.__new__(build_data.StatTables)
        tab = data["tables"]
        t.budget = {int(k): {int(q): v for q, v in row.items()} for k, row in tab["budget"].items()}
        t.damage = {name: {int(k): v for k, v in rows.items()} for name, rows in tab["damage"].items()}
        t.armor_total = {int(k): v for k, v in tab["armor_total"].items()}
        t.armor_quality = {int(k): v for k, v in tab["armor_quality"].items()}
        t.armor_shield = {int(k): v for k, v in tab["armor_shield"].items()}
        t.armor_location = {int(k): v for k, v in tab["armor_location"].items()}
        t.block = {int(k): v for k, v in tab["block"].items()}
        cls.tables, cls.items = t, data["items"]

    def test_every_golden_item(self):
        self.assertGreaterEqual(len(self.items), 25)
        for item in self.items:
            with self.subTest(item=f"{item['id']} {item['name']} ({item['label']})"):
                computed = build_data.compute_item(item["sparse"], item["class"], item["subclass"], self.tables)
                sim = {}
                for mod, value in computed.get("stats", {}).items():
                    for stat in SIM.get(int(mod), []):
                        sim[stat] = sim.get(stat, 0) + value
                if computed.get("armor"):
                    sim[27] = computed["armor"]
                self.assertEqual(sim, {int(k): v for k, v in item["expectedStats"].items()})
                weapon = [computed["weapon"]["min"], computed["weapon"]["max"]] if "weapon" in computed else None
                self.assertEqual(weapon, item["expectedWeapon"])


if __name__ == "__main__":
    unittest.main()
