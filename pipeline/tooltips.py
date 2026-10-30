"""Render spell description templates ($s1, ${$m1/60}, $d, ...) to plain text, or refuse.

The rule is that a rendered tooltip never contains a guessed number. A text is rendered only when every token in it
can be computed exactly from the spell's own data; otherwise the whole text stays unrendered (None) and the tokens
that blocked it are reported. See docs/tooltips.md for the supported tokens, the level and power assumptions, and
what has been verified.

Used by build_data.py; stdlib only.
"""
import math
import re
import struct

LEVEL = 60  # character level amounts are evaluated at (wowsims' core.CharacterLevel for Forever)

# SpellEffect.Effect / EffectAura values after which an amount keeps its fraction (damage and healing).
_DAMAGE_EFFECTS = {2, 9, 10, 17, 58, 121}     # school damage, leech, heal, weapon damage (+ no school), normalized weapon
_DAMAGE_AURAS = {3, 8, 15, 43, 53}            # periodic damage/heal, damage shield, proc damage, periodic leech
_PHYSICAL_EFFECTS = {2, 17, 31, 58, 121}
MAX_DEPTH = 3                                 # nested $@spelldesc references


class Unresolved(Exception):
    """A token that cannot be rendered exactly."""

    def __init__(self, token):
        super().__init__(token)
        self.token = token


def f32(x):
    """Round to float32: the game files store these as float32, and the ppl multiplication must happen there."""
    return struct.unpack("f", struct.pack("f", x))[0]


class Effect:
    """One SpellEffect row with the value model of wowsims/forever sim/core/spelldata/effect.go, which they check against
    in-game tooltips. Checked again here against their printed effect lists (docs/tooltips.md)."""

    def __init__(self, row, spell):
        self.row, self.spell = row, spell
        self.base = row.get("EffectBasePointsF", 0.0)
        self.ppl = row.get("EffectRealPointsPerLevel", 0.0)
        self.variance = row.get("Variance", 0.0)
        self.period_ms = row.get("EffectAuraPeriod", 0)
        self.type, self.aura = row.get("Effect", 0), row.get("EffectAura", 0)

    @property
    def keeps_fraction(self):
        return self.type in _DAMAGE_EFFECTS or self.aura in _DAMAGE_AURAS

    @property
    def physical(self):
        return self.type in _PHYSICAL_EFFECTS and self.spell.school_mask == 1

    def _gain(self):
        level = min(LEVEL, self.spell.max_level) if self.spell.max_level > 0 else LEVEL
        return f32(f32(max(level - self.spell.base_level, 0)) * f32(self.ppl))

    def exact(self):
        return f32(f32(self.base) + self._gain())

    def spread(self):
        """(low, high) ends of the roll, as whole numbers."""
        if not self.variance:
            whole = math.floor(self.exact())
            return whole, whole
        base = f32(self.base)
        side = f32(f32(f32(abs(self.base)) * f32(self.variance)) / 2)
        if self.physical:
            side = f32(side * 2)
        gain = self._gain()
        low = f32(round(f32(base - side)) + gain)   # round() is half-to-even, as Go's RoundToEven
        high = f32(round(f32(base + side)) + gain)
        return math.floor(low), math.ceil(high)

    def average(self, token):
        """The signed amount $s stands for. A positive amount that is not whole is floored (as wowsims' model, which
        tracks the in-game tooltip, does); a fractional damage/healing or negative amount is refused."""
        value = self.exact()
        whole = abs(value - round(value)) <= 1e-4
        if whole:
            return round(value)
        # A fractional amount: damage/healing round in a way we cannot confirm, and so does a negative one.
        if self.keeps_fraction or value < 0:
            raise Unresolved(token)
        return math.floor(value)

    def radius(self):
        radii = self.spell.radii
        values = [radii.get(i, 0.0) for i in self.row.get("EffectRadiusIndex") or []]
        return max(values) if values else 0.0


class Spell:
    def __init__(self, sid):
        self.id, self.name, self.description, self.aura_description = sid, "", "", ""
        self.duration_ms, self.school_mask, self.base_level, self.max_level = 0, 0, 0, 0
        self.proc_chance = 0
        self.effects = {}
        self.radii = {}


class Facts:
    """Everything the renderer needs, indexed by spell id, built once from a Source."""

    def __init__(self, src):
        self.spells = {}
        radius = {r["ID"]: r.get("RadiusMax", 0.0) for r in src.rows("SpellRadius")}
        durations = {r["ID"]: r.get("Duration", 0) for r in src.rows("SpellDuration")}
        for r in src.rows("Spell"):
            s = self.get(r["ID"])
            s.description, s.aura_description = r.get("Description_lang", ""), r.get("AuraDescription_lang", "")
        for r in src.rows("SpellName"):
            self.get(r["ID"]).name = r.get("Name_lang", "")
        for r in sorted(src.rows("SpellMisc"), key=lambda r: -r.get("DifficultyID", 0)):  # lowest difficulty wins
            s = self.get(r["SpellID"])
            s.duration_ms = durations.get(r.get("DurationIndex", 0), 0) if r.get("DurationIndex") else 0
            s.school_mask = r.get("SchoolMask", 0)
        for r in src.rows("SpellLevels"):
            if r.get("DifficultyID", 0) == 0:
                s = self.get(r["SpellID"])
                s.base_level, s.max_level = r.get("BaseLevel", 0), r.get("MaxLevel", 0)
        for r in src.rows("SpellAuraOptions"):
            if r.get("DifficultyID", 0) == 0:
                self.get(r["SpellID"]).proc_chance = r.get("ProcChance", 0)
        for r in src.rows("SpellEffect", raw=True):
            if r.get("DifficultyID", 0) == 0:
                s = self.get(r["SpellID"])
                s.radii = radius
                s.effects[r.get("EffectIndex", 0)] = Effect(r, s)

    def get(self, sid):
        return self.spells.setdefault(sid, Spell(sid))


def format_duration(ms, token):
    """Client style: '8 sec', '2 min', '1 hour'. Only exact units are produced; anything else is refused."""
    if ms <= 0:
        raise Unresolved(token)
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:g} sec" if seconds == int(seconds) else (_ for _ in ()).throw(Unresolved(token))
    if seconds < 3600:
        return f"{int(seconds // 60)} min" if seconds % 60 == 0 else (_ for _ in ()).throw(Unresolved(token))
    if seconds % 3600 == 0:
        hours = int(seconds // 3600)
        return f"{hours} {'hour' if hours == 1 else 'hours'}"
    raise Unresolved(token)


_REF = re.compile(r"\$(\d+)?([A-Za-z]+)(\d+)?")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class Renderer:
    def __init__(self, facts):
        self.facts = facts

    # ---- values --------------------------------------------------------------------------------------------------
    def value(self, match, current):
        """Signed numeric value of a $<spell?><letter><index?> reference. Math uses the sign; plain tokens print it unsigned
        (the template words say whether it is a gain or a loss)."""
        token = match.group(0)
        other, letter, index = match.group(1), match.group(2), match.group(3)
        spell = self.facts.spells.get(int(other)) if other else current
        if spell is None:
            raise Unresolved(token)

        def effect():
            e = spell.effects.get(int(index or 1) - 1)
            if e is None:
                raise Unresolved(token)
            return e

        if letter in ("s", "w") and index:
            return effect().average(token)
        if letter == "m" and index:
            return effect().spread()[0]
        if letter == "M" and index:
            return effect().spread()[1]
        if letter == "o" and index:
            e = effect()
            if e.period_ms <= 0 or spell.duration_ms <= 0 or spell.duration_ms % e.period_ms:
                raise Unresolved(token)
            return e.average(token) * (spell.duration_ms // e.period_ms)
        if letter == "d" and not index:
            if spell.duration_ms <= 0:
                raise Unresolved(token)
            return spell.duration_ms / 1000
        if letter == "t" and index:
            if effect().period_ms <= 0:
                raise Unresolved(token)
            return effect().period_ms / 1000
        if letter == "a" and index:
            radius = effect().radius()
            if radius <= 0:
                raise Unresolved(token)
            return radius
        if letter == "x" and index:
            targets = effect().row.get("EffectChainTargets", 0)
            if targets <= 0:
                raise Unresolved(token)
            return targets
        if letter == "h" and not index and spell.proc_chance > 0:
            return spell.proc_chance
        raise Unresolved(token)

    @staticmethod
    def number_text(value, token):
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        if abs(round(value, 3) - value) < 1e-9:  # a plain decimal such as a 1.5 s period
            return f"{value:.3f}".rstrip("0").rstrip(".")
        raise Unresolved(token)

    # ---- math in ${...} --------------------------------------------------------------------------------------------
    def evaluate(self, expr, current):
        pos = 0

        def peek():
            nonlocal pos
            while pos < len(expr) and expr[pos] == " ":
                pos += 1
            return expr[pos] if pos < len(expr) else ""

        def atom():
            nonlocal pos
            c = peek()
            if c == "(":
                pos += 1
                v = add()
                if peek() != ")":
                    raise Unresolved("${" + expr + "}")
                pos += 1
                return v
            if c == "-":
                pos += 1
                return -atom()
            m = _NUMBER.match(expr, pos)
            if m:
                pos = m.end()
                return float(m.group(0))
            m = _REF.match(expr, pos)
            if m and m.group(2) in ("s", "w", "m", "M", "o", "d", "t", "a", "x", "h"):
                pos = m.end()
                return self.value(m, current)
            raise Unresolved("${" + expr + "}")

        def power():
            nonlocal pos
            v = atom()
            if peek() == "^":
                pos += 1
                v = v ** atom()
            return v

        def mul():
            nonlocal pos
            v = power()
            while peek() in ("*", "/"):
                op = expr[pos]
                pos += 1
                r = power()
                if op == "/" and r == 0:
                    raise Unresolved("${" + expr + "}")
                v = v * r if op == "*" else v / r
            return v

        def add():
            nonlocal pos
            v = mul()
            while peek() in ("+", "-"):
                op = expr[pos]
                pos += 1
                r = mul()
                v = v + r if op == "+" else v - r
            return v

        result = add()
        if peek():
            raise Unresolved("${" + expr + "}")
        return result

    # ---- templates -------------------------------------------------------------------------------------------------
    def render_text(self, template, spell, depth=0):
        """Rendered text; raises Unresolved at the first token that cannot be rendered exactly."""
        out, i, last = [], 0, None   # `last` = the most recent number written, which $l singular:plural; looks at
        while i < len(template):
            c = template[i]
            if c != "$":
                out.append(c)
                i += 1
                continue
            rest = template[i:]
            if rest.startswith("${"):
                end = rest.find("}")
                if end < 0:
                    raise Unresolved("${")
                value = self.evaluate(rest[2:end], spell)
                decimals = re.match(r"\.(\d)", rest[end + 1:end + 3])   # '}.1' = one decimal place, as printf %.1f
                token = rest[:end + 1 + (2 if decimals else 0)]
                if decimals:
                    text = f"{abs(value):.{int(decimals.group(1))}f}"
                else:
                    if value < 0:
                        raise Unresolved(token)
                    text = self.number_text(value, token)
                out.append(text)
                last, i = value, i + len(token)
                continue
            m = re.match(r"\$l([^:;$]*):([^;$]*);", rest)
            if m:
                if last is None:
                    raise Unresolved(m.group(0))
                out.append(m.group(1) if last == 1 else m.group(2))
                i += m.end()
                continue
            m = re.match(r"\$@spellicon(\d+)", rest)
            if m:  # an inline icon; kept as a marker for the UI to replace with the image
                if int(m.group(1)) not in self.facts.spells:
                    raise Unresolved(m.group(0))
                out.append("{icon:" + m.group(1) + "}")
                i += m.end()
                continue
            m = re.match(r"\$@(spellname|spelldesc|spellaura)(\d+)", rest)
            if m:
                target = self.facts.spells.get(int(m.group(2)))
                if target is None or depth >= MAX_DEPTH:
                    raise Unresolved(m.group(0))
                if m.group(1) == "spellname":
                    if not target.name:
                        raise Unresolved(m.group(0))
                    out.append(target.name)
                else:
                    text = target.description if m.group(1) == "spelldesc" else target.aura_description
                    if not text:
                        raise Unresolved(m.group(0))
                    out.append(self.render_text(text, target, depth + 1))
                i += m.end()
                continue
            m = _REF.match(rest)
            if m and m.group(2) in ("s", "w", "m", "M", "o", "d", "t", "a", "x", "h"):
                token = m.group(0)
                if m.group(2) == "d" and not m.group(3):
                    other = self.facts.spells.get(int(m.group(1))) if m.group(1) else spell
                    if other is None:
                        raise Unresolved(token)
                    out.append(format_duration(other.duration_ms, token))
                    last = other.duration_ms / 1000
                else:
                    value = abs(self.value(m, spell))
                    out.append(self.number_text(value, token))
                    last = value
                i += m.end()
                continue
            # Conditionals ($?a123[..][..]), gender, $<variables>, player stats ($SPS, $AP, $PL), $/N;, icons, ...
            raise Unresolved(re.match(r"\$[^\s\d]?[A-Za-z?<@/]*\d*", rest).group(0) or "$")
        return "".join(out)

    def render(self, spell):
        """({"description": text|None, "auraDescription": text|None}, sorted unresolved tokens).

        Only templates that contain tokens appear in the result: a plain text needs no rendering and the record already
        carries it."""
        result, blocked = {}, set()
        for key, template in (("description", spell.description), ("auraDescription", spell.aura_description)):
            if "$" not in template:
                continue
            try:
                result[key] = self.render_text(template, spell)
            except Unresolved as e:
                result[key] = None
                blocked.add(e.token)
        return result, sorted(blocked)
