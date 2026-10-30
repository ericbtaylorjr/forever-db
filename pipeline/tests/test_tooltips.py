"""Tests for tooltips.py on hand-built spells (no game data needed).

Run from the repo root: python3 -m unittest discover -s pipeline/tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tooltips  # noqa: E402


def world(*spells):
    """Facts holding the given (id, name, description, kwargs) spells; kwargs may include effects=[row dict, ...]."""
    facts = tooltips.Facts.__new__(tooltips.Facts)
    facts.spells = {}
    for sid, name, description, kw in spells:
        s = facts.get(sid)
        s.name, s.description, s.aura_description = name, description, kw.get("aura", "")
        s.duration_ms, s.proc_chance = kw.get("duration_ms", 0), kw.get("proc", 0)
        s.base_level, s.max_level, s.school_mask = kw.get("base_level", 0), kw.get("max_level", 0), kw.get("school", 4)
        s.radii = kw.get("radii", {})
        for i, row in enumerate(kw.get("effects", [])):
            s.effects[i] = tooltips.Effect(row, s)
    return tooltips.Renderer(facts), facts


def render(description, **kw):
    r, facts = world((1, "Test", description, kw))
    return r.render(facts.spells[1])


class RenderTest(unittest.TestCase):
    def ok(self, description, expected, **kw):
        result, blocked = render(description, **kw)
        self.assertEqual((result.get("description"), blocked), (expected, []))

    def blocked(self, description, token, **kw):
        result, blocked = render(description, **kw)
        self.assertEqual((result["description"], blocked), (None, [token]))

    def test_text_without_tokens_is_not_rendered(self):
        self.assertEqual(render("Plain text, 5% more."), ({}, []))

    def test_amount_is_unsigned_and_a_positive_fraction_is_floored(self):
        self.ok("Reduces by $s1 for $d.", "Reduces by 50 for 8 sec.", duration_ms=8000, effects=[{"EffectBasePointsF": -50.0}])
        self.ok("$s1", "50", effects=[{"EffectBasePointsF": 50.9}])
        self.blocked("$s1", "$s1", effects=[{"EffectBasePointsF": -50.9}])   # rounding of a negative fraction is not known

    def test_level_scaling_stops_at_the_spells_max_level(self):
        row = {"EffectBasePointsF": 100.0, "EffectRealPointsPerLevel": 2.0}
        self.ok("$s1", "140", base_level=40, effects=[row])                   # (60 - 40) * 2 = +40
        self.ok("$s1", "120", base_level=40, max_level=50, effects=[row])      # capped at level 50: +20
        self.ok("$s1", "100", base_level=70, effects=[row])                    # below the base level: no gain

    def test_damage_amount_with_a_fraction_is_refused_not_rounded(self):
        self.blocked("Deals $s1.", "$s1", effects=[{"Effect": 2, "EffectBasePointsF": 10.5}])
        self.ok("Deals $s1.", "Deals 10.", effects=[{"Effect": 2, "EffectBasePointsF": 10.0}])

    def test_roll_range_uses_variance(self):
        # 350 +/- 20% (variance 0.4): 280 to 420, the printed range in wowsims/gamedata for Balefire Bolt.
        self.ok("$m1 to $M1", "280 to 420", effects=[{"Effect": 2, "EffectBasePointsF": 350.0, "Variance": 0.4}])

    def test_roll_range_rounds_halves_to_even_in_float32(self):
        # Wrath rank 3: 30 +/- 2.5 ends on halves (27.5 -> 28, 32.5 -> 32), then +3 for levels 14..20: gamedata prints 31-35.
        # Needs the exact stored variance; a value rounded to 6 decimals flips the halves and gives 30-36.
        row = {"Effect": 2, "EffectBasePointsF": 30.0, "Variance": 0.16666667, "EffectRealPointsPerLevel": 0.5}
        self.ok("$m1 to $M1", "31 to 35", base_level=14, max_level=20, effects=[row], school=8)

    def test_math_keeps_the_sign_of_its_inputs(self):
        self.ok("${$m1/-1000} sec", "2 sec", effects=[{"EffectBasePointsF": -2000.0}])
        self.blocked("${$m1/1000}", "${$m1/1000}", effects=[{"EffectBasePointsF": -2000.0}])  # negative result: refused

    def test_math_precedence_and_functions_of_the_grammar(self):
        self.ok("${2+3*4} ${(2+3)*4} ${2^3}", "14 20 8")
        self.blocked("${1/3}", "${1/3}")                       # not a plain decimal: refused, not rounded
        self.blocked("${$sk43*2}", "${$sk43*2}")               # player skill: unknown token

    def test_decimal_places_suffix(self):
        self.ok("${$m1/60000}.1 min", "1.5 min", effects=[{"EffectBasePointsF": 90000.0}])
        self.ok("${$s1}.2%", "5.00%", effects=[{"EffectBasePointsF": 5.0}])

    def test_durations(self):
        for ms, text in ((8000, "8 sec"), (60000, "1 min"), (120000, "2 min"), (3600000, "1 hour"), (7200000, "2 hours")):
            self.ok("$d", text, duration_ms=ms)
        self.blocked("$d", "$d", duration_ms=0)               # no duration: the client's wording is not known
        self.blocked("$d", "$d", duration_ms=90000)           # 1.5 min: format not confirmed

    def test_periodic_total_needs_a_whole_number_of_ticks(self):
        row = {"Effect": 6, "EffectAura": 3, "EffectBasePointsF": 36.0, "EffectAuraPeriod": 3000}
        self.ok("$o1 over $d, $s1 every $t1 sec", "216 over 18 sec, 36 every 3 sec", duration_ms=18000, effects=[row])
        self.blocked("$o1", "$o1", duration_ms=10000, effects=[row])

    def test_plural_follows_the_last_number(self):
        self.ok("$s1 $lpoint:points;", "1 point", effects=[{"EffectBasePointsF": 1.0}])
        self.ok("$s1 $lpoint:points;", "3 points", effects=[{"EffectBasePointsF": 3.0}])
        self.blocked("$lpoint:points;", "$lpoint:points;")     # no number before it

    def test_other_spells_name_description_icon_and_values(self):
        r, facts = world((1, "A", "Casts $@spellname2: $@spelldesc2 $@spellicon2 for $2s1 and $2d.", {}),
                         (2, "Frost Armor", "Gives $s1 armor.", {"effects": [{"EffectBasePointsF": 40.0}], "duration_ms": 30000}))
        result, blocked = r.render(facts.spells[1])
        self.assertEqual(result["description"], "Casts Frost Armor: Gives 40 armor. {icon:2} for 40 and 30 sec.")
        self.assertEqual(blocked, [])

    def test_state_dependent_and_unknown_tokens_are_refused(self):
        for token in ("$?a14748[x][y]", "$g he:she;", "$<frostdamage>", "$SPS", "$/10;s1", "$AP", "$PL"):
            result, blocked = render(f"Text {token} more.", effects=[{"EffectBasePointsF": 5.0}])
            self.assertIsNone(result["description"], token)
            self.assertEqual(len(blocked), 1, token)

    def test_one_blocked_token_blocks_the_whole_text_and_names_it(self):
        result, blocked = render("Gives $s1 and $?a1[more][].", effects=[{"EffectBasePointsF": 5.0}])
        self.assertEqual((result["description"], blocked), (None, ["$?a1"]))

    def test_aura_description_is_rendered_separately(self):
        r, facts = world((1, "A", "Plain.", {"aura": "Slows by $s1%.", "effects": [{"EffectBasePointsF": -30.0}]}))
        result, blocked = r.render(facts.spells[1])
        self.assertEqual(result, {"auraDescription": "Slows by 30%."})   # the plain description needs no rendering

    def test_empty_templates_are_omitted(self):
        r, facts = world((1, "A", "", {}))
        self.assertEqual(r.render(facts.spells[1]), ({}, []))
        self.assertEqual(render("Plain."), ({}, []))


if __name__ == "__main__":
    unittest.main()
