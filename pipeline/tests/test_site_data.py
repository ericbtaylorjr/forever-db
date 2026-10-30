"""Tests for site_data.py: build real data from synthetic scans, then check what the website would load.

Run from the repo root: python3 -m unittest discover -s pipeline/tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]
import build_data  # noqa: E402
import site_data  # noqa: E402
import test_build_data as ingest_tests  # noqa: E402  (module import: a bare class import would be collected and re-run)


class SiteDataTest(unittest.TestCase):
    # Borrow the scan-building helpers without inheriting (and re-running) IngestTest's own tests.
    db, ingest, current, history, log = ingest_tests.IngestTest.db, ingest_tests.IngestTest.ingest, ingest_tests.IngestTest.current, ingest_tests.IngestTest.history, ingest_tests.IngestTest.log

    def setUp(self):
        ingest_tests.IngestTest.setUp(self)
        site_data.DATA = build_data.DATA
        (build_data.DATA).mkdir(parents=True, exist_ok=True)
        self.out = Path(self.tmp.name) / "site"

    def test_ingest_stat_names_exist_for_the_site(self):
        self.ingest(self.db("a.db", items={1: ("A", 10, 13)}))
        self.assertTrue((build_data.DATA / "stat-names.json").exists())

    def build_two_versions(self):
        hidden = dict(ClassID=4, SubclassID=1, InventoryType=5, encrypted=True)
        log = self.log("  Spell: 3 rows locked by TACT key AAAA\nHotfixes: build 100 up to push 1\n")
        self.ingest(self.db("a.db", version="1.60.1.100", push=1, items={1: hidden, 2: ("Sword", 10, 13)},
                            spells={5: ("Fireball", "Old")}), scan_log=log)
        self.ingest(self.db("b.db", version="1.60.1.200", push=2, items={1: ("Gloves", 10, 5), 2: ("Sword", 11, 13)},
                            spells={5: ("Fireball", "New")}), scan_log=self.log("Hotfixes: build 200 up to push 2\n"))
        return site_data.build(self.out)

    def test_index_rows_match_their_columns_and_point_at_a_shard(self):
        self.build_two_versions()
        index = json.loads((self.out / "items.json").read_text())
        self.assertTrue(all(len(row) == len(index["cols"]) for row in index["rows"]))
        row = dict(zip(index["cols"], next(r for r in index["rows"] if r[0] == 1)))
        self.assertEqual((row["name"], row["enc"], row["gear"], row["disc"], row["first"], row["changed"]), ("Gloves", 0, 1, 1, 0, 1))
        shard = json.loads((self.out / "items" / f"{row['shard']}.json").read_text())
        self.assertEqual(shard["1"]["d"]["name"], "Gloves")
        self.assertEqual([e["t"] for e in shard["1"]["h"]], ["discovered"])

    def test_builds_list_what_changed_and_what_was_discovered(self):
        self.build_two_versions()
        meta = json.loads((self.out / "meta.json").read_text())
        self.assertEqual([v["label"] for v in meta["versions"]], ["Build 100 · hotfix 1", "Build 200 · hotfix 2"])
        self.assertEqual(meta["versions"][1]["counts"]["items"]["discovered"], 1)
        build = json.loads((self.out / "builds" / "1.json").read_text())
        events = {(c["k"], c["id"]): c["t"] for c in build["changes"]}
        self.assertEqual(events, {("i", 1): "discovered", ("i", 2): "changed", ("s", 5): "changed"})
        first = json.loads((self.out / "builds" / "0.json").read_text())
        self.assertEqual(first["changes"], [])                      # the baseline has no events
        self.assertEqual(first["locked"], {"Spell": {"AAAA": 3}})

    def test_a_removed_entity_keeps_its_last_name_in_the_build_file(self):
        self.ingest(self.db("a.db", version="1.60.1.100", items={1: ("Gone Sword", 10, 13), 2: ("Stays", 10, 13)}))
        self.ingest(self.db("b.db", version="1.60.1.200", items={2: ("Stays", 10, 13)}))
        site_data.build(self.out)
        removed = [c for c in json.loads((self.out / "builds" / "1.json").read_text())["changes"] if c["t"] == "removed"]
        self.assertEqual([(c["k"], c["id"], c["nm"]) for c in removed], [("i", 1, "Gone Sword")])
        index = json.loads((self.out / "items.json").read_text())
        self.assertEqual([r[0] for r in index["rows"]], [2])           # ...but is not in the browsable list

    def test_test_and_placeholder_names_are_flagged_not_dropped(self):
        self.ingest(self.db("a.db", items={1: ("Sword of Truth", 10, 13), 2: ("1500 Test sword 80 purple", 10, 13), 3: ("OLD Axe", 10, 13)}))
        site_data.build(self.out)
        index = json.loads((self.out / "items.json").read_text())
        flags = {r[0]: r[index["cols"].index("test")] for r in index["rows"]}
        self.assertEqual(flags, {1: 0, 2: 1, 3: 1})

    def test_derived_areas_are_not_listed(self):
        self.ingest(self.db("a.db", version="1.60.1.100", items={1: dict(ClassID=2, SubclassID=7, InventoryType=13, OverallQualityID=1)}))
        self.ingest(self.db("b.db", version="1.60.1.200", items={1: dict(ClassID=2, SubclassID=7, InventoryType=13, OverallQualityID=3)}))
        site_data.build(self.out)
        change = json.loads((self.out / "builds" / "1.json").read_text())["changes"][0]
        self.assertIn("quality", change["a"])
        self.assertNotIn("qualityName", change["a"])

    def test_a_key_that_disappears_is_reported_as_unlocked(self):
        self.build_two_versions()
        meta = json.loads((self.out / "meta.json").read_text())
        self.assertEqual(meta["versions"][1]["unlocked"], ["AAAA"])
        self.assertEqual(meta["versions"][0]["unlocked"], [])

    def test_spell_detail_lists_the_items_that_use_it(self):
        self.ingest(self.db("a.db", items={1: ("Trinket", 10, 12)}, effects={1: [5]}, spells={5: ("Proc", "x")}))
        site_data.build(self.out)
        spells = json.loads((self.out / "spells.json").read_text())
        shard = next(r for r in spells["rows"] if r[0] == 5)[spells["cols"].index("shard")]
        record = json.loads((self.out / "spells" / f"{shard}.json").read_text())["5"]
        self.assertEqual((record["u"], record["un"]), ([1], 1))

    def test_output_is_deterministic(self):
        self.build_two_versions()
        first = {p.name: p.read_bytes() for p in self.out.rglob("*.json")}
        other = Path(self.tmp.name) / "site2"
        site_data.build(other)
        self.assertEqual(first, {p.name: p.read_bytes() for p in other.rglob("*.json")})


if __name__ == "__main__":
    unittest.main()
