#!/usr/bin/env python3
"""Check tooltips.Effect (the amount and roll-range model) against the effect lists wowsims/gamedata prints.

    check_against_gamedata.py <scan.db> <dir with gamedata spells/<class>/*.txt flattened or nested>

gamedata's spell cards come from wowsims' Go implementation of the same model, which they verify against in-game
tooltips. Not part of the unit tests (needs the scan and a gamedata checkout); run it when tooltips.py changes.
Expected on the 2026-10-30 data: ~1,960 single amounts (2 known odd movement-speed auras differ) and 748/748 ranges.
"""
import glob
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent)]
import build_data  # noqa: E402
import tooltips  # noqa: E402


def cards(root):
    for path in glob.glob(str(Path(root) / "**" / "*.txt"), recursive=True):
        for block in Path(path).read_text().split("=======\n"):
            lines = block.splitlines()
            m = re.match(r"(\d+) ", lines[0]) if lines else None
            if m:
                yield int(m.group(1)), lines


def main(db_path, root):
    facts = tooltips.Facts(build_data.Source(db_path))
    amounts, ranges, bad = Counter(), Counter(), []
    for sid, lines in cards(root):
        for i, line in enumerate(lines[:-1]):
            m = re.match(r"effect (\d+)\s+(.*)", line)
            effect = facts.spells.get(sid) and facts.spells[sid].effects.get(int(m.group(1)) - 1) if m else None
            if not effect:
                continue
            text, detail = m.group(2), lines[i + 1]
            rng = re.match(r"(\d+)–(\d+) ", text)
            if rng and "variance=" in detail:
                ranges["compared"] += 1
                got = effect.spread()
                ranges["exact" if got == (int(rng.group(1)), int(rng.group(2))) else "mismatch"] += 1
            elif "variance=" not in detail and re.match(r"[+-]?\d", text) and not re.match(r"[+-]?\d+(\.\d+)? ?(s|ms|min)\b", text):
                if not any(k in detail for k in ("E_APPLY_AURA", "E_SCHOOL_DAMAGE", "E_HEAL")):
                    continue
                want = abs(float(re.findall(r"-?\d+(?:\.\d+)?", text.split("(")[0])[0]))
                value = effect.exact()
                got = abs(value) if effect.keeps_fraction else abs(math.floor(value))
                amounts["compared"] += 1
                if abs(want - got) < (0.06 if effect.keeps_fraction else 0.01):
                    amounts["match"] += 1
                else:
                    amounts["mismatch"] += 1
                    bad.append((sid, line[:70], got))
    print("amounts:", dict(amounts))
    print("ranges: ", dict(ranges))
    for b in bad[:10]:
        print("  mismatch", b)


if __name__ == "__main__":
    main(*sys.argv[1:])
