"""Tests for builds.py with the network calls stubbed out.

Run from the repo root: python3 -m unittest discover -s pipeline/tests -v
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import builds  # noqa: E402

VERSIONS = (
    "Region!STRING:0|BuildConfig!HEX:16|CDNConfig!HEX:16|KeyRing!HEX:16|BuildId!DEC:4|VersionsName!String:0|ProductConfig!HEX:16\n"
    "## seqn = 1\n"
    "us|aa|bb||70685|1.60.1.70685|cc\n"
    "cn|aa|bb||70707|1.60.1.70707|cc\n"
)


def wago(*versions):
    return json.dumps({"wowf": [{"version": v, "build_config": "b" + v[-5:], "cdn_config": "c" + v[-5:], "is_bgdl": False}
                                for v in versions]}).encode()


class BuildsTest(unittest.TestCase):
    def fetch(self, wago_body):
        def fake(url):
            return VERSIONS.encode() if "version.battle.net" in url else wago_body
        return mock.patch.object(builds, "fetch", fake)

    def test_live_version_uses_the_us_row(self):
        with self.fetch(b""):
            self.assertEqual(builds.live_version(), "1.60.1.70685")

    def test_historical_builds_are_sorted_and_stop_at_the_us_build(self):
        # 70707 is the CN build, ahead of US; it must not be scanned as history.
        with self.fetch(wago("1.60.1.70707", "1.60.1.70685", "1.60.1.70245", "1.60.1.70685")):
            got = [r["version"] for r in builds.historical_builds()]
        self.assertEqual(got, ["1.60.1.70245", "1.60.1.70685"])


if __name__ == "__main__":
    unittest.main()
