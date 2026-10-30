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


def make_db(path, version="1.60.1.100", push=1, spells=None, items=None, extra_column=False):
    """Write the handful of tables build_data reads. `spells` maps id -> (name, description)."""
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
               " InventoryType INTEGER, OverallQualityID INTEGER, StatModifier_bonusStat TEXT)")
    db.execute("create table ItemClass (ID INTEGER, ClassName_lang TEXT, ClassID INTEGER)")
    db.execute("insert into ItemClass values (1, 'Weapon', 2)")
    for iid, (name, ilvl, inv) in (items or {}).items():
        db.execute("insert into Item values (?, 2, 7, ?, 0)", (iid, inv))
        db.execute("insert into ItemSparse values (?, ?, '', ?, 1, ?, 2, '[3,-1]')", (iid, name, ilvl, inv))
    db.commit()
    db.close()


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        build_data.DATA = Path(self.tmp.name) / "data"

    def db(self, name, **kw):
        path = Path(self.tmp.name) / name
        make_db(path, **kw)
        return path

    def ingest(self, db, **flags):
        ns = dict(db=str(db), scan_log=None, allow_schema_change=False, force=False, dry_run=False)
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

    def test_default_values_are_omitted(self):
        self.ingest(self.db("a.db", spells={1: ("A", "x")}))
        misc = self.current("spells")[1]["data"]["related"]["SpellMisc"][0]
        self.assertEqual(misc, {"SchoolMask": 4})


if __name__ == "__main__":
    unittest.main()
