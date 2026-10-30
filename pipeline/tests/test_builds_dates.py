"""Tests for `builds.py dates` with the network calls stubbed out.

Run from the repo root: python3 -m unittest discover -s pipeline/tests -v
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import builds  # noqa: E402

CACHE = b"hotfix-cache-bytes"
WAGO = json.dumps({"wowf": [
    {"version": "1.60.1.100", "created_at": "2026-10-13 21:18:10"},
    {"version": "1.60.1.200", "created_at": "2026-10-21 16:45:08"},
]}).encode()


def version(build, push):
    return {"version": f"1.60.1.{build}", "build": build, "hotfixPush": push}


class DatesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        builds.DATA = self.dir

    def run_dates(self, ledger, cache_sha=hashlib.sha256(CACHE).hexdigest(), modified="2026-10-30"):
        (self.dir / "state.json").write_text(json.dumps({"builds": ledger, "scan": {"hotfixCacheSha256": cache_sha}}))
        fetch = lambda url: WAGO if "wago" in url else CACHE
        with mock.patch.object(builds, "fetch", fetch), mock.patch.object(builds, "last_modified", lambda url: modified):
            builds.cmd_dates(None)
        return json.loads((self.dir / "build-dates.json").read_text())

    def test_base_builds_are_dated_by_wago_and_a_hotfix_push_by_the_cache(self):
        dates = self.run_dates([version(100, 0), version(200, 0), version(200, 5)])
        self.assertEqual(dates["100:0"], {"date": "2026-10-13", "source": "wago.tools"})
        self.assertEqual(dates["200:5"], {"date": "2026-10-30", "source": "hotfix cache last modified"})

    def test_an_older_hotfix_push_is_left_undated_not_guessed(self):
        dates = self.run_dates([version(100, 0), version(100, 3), version(200, 0)])
        self.assertNotIn("100:3", dates)

    def test_the_cache_date_is_not_used_if_the_cache_has_moved_on(self):
        dates = self.run_dates([version(100, 0), version(100, 3)], cache_sha="not-the-ingested-cache")
        self.assertNotIn("100:3", dates)

    def test_existing_dates_are_never_changed(self):
        (self.dir / "build-dates.json").write_text(json.dumps({"100:0": {"date": "2000-01-01", "source": "manual"}}))
        dates = self.run_dates([version(100, 0)])
        self.assertEqual(dates["100:0"]["date"], "2000-01-01")


if __name__ == "__main__":
    unittest.main()
