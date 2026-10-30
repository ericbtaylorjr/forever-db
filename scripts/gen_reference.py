#!/usr/bin/env python3
"""Generate site/src/data/reference.json: numeric game ids -> readable names, from wowsims/forever's dbcenums (MIT).

    FOREVER_REPO=~/dev/forever scripts/gen_reference.py

Spell effect rows carry raw codes (Effect 6, EffectAura 226, PowerType 0 ...); the UI needs names to show them. The
names are TrinityCore-style identifiers; the UI shows them humanized. Commit the output; re-run when forever-ref.txt
is bumped. Attribution is in site/NOTICES.md.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENUMS = {  # key -> (Go type, name prefix to strip)
    "effect": ("SpellEffectType", "E_"), "aura": ("EffectAuraType", "A_"), "power": ("PowerType", "POWER_"),
    "mechanic": ("Mechanic", "MECHANIC_"), "target": ("ImplicitTarget", "TARGET_"), "spellMod": ("SpellModOp", "SPELLMOD_"),
}


def main():
    repo = os.environ.get("FOREVER_REPO") or sys.exit("set FOREVER_REPO")
    source = "\n".join(p.read_text() for p in sorted(Path(repo, "sim/core/dbcenums").glob("*.go")) if not p.name.endswith("_test.go"))
    out = {}
    for key, (gotype, prefix) in ENUMS.items():
        names = {}
        for m in re.finditer(rf"^\s*([A-Z0-9_]+)\s+{gotype}\s*=\s*(-?\d+)", source, re.MULTILINE):
            name = m.group(1)[len(prefix):] if m.group(1).startswith(prefix) else m.group(1)
            names.setdefault(m.group(2), name)
        out[key] = dict(sorted(names.items(), key=lambda kv: int(kv[0])))
        print(f"{key}: {len(out[key])} names")
    dest = ROOT / "site" / "src" / "data" / "reference.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
