# Spell tooltips

Spell descriptions in the game files are templates: `Hurls a fiery ball that causes $s1 Fire damage and an additional $o2 Fire damage over $d.` The pipeline renders them into text (`pipeline/tooltips.py`) and stores the result in each spell's `computed.tooltip`, so the UI can show readable text and the history can show when the *displayed* text changed.

## The rule: never show a guessed number

A template is rendered only if **every token in it can be computed exactly** from the spell's own data. If any token cannot, that whole text is `null` and the blocking tokens are listed in `computed.tooltipBlockedBy`. The UI should then show the raw template (`description` / `auraDescription`) or a "not available" note, never partial text.

```jsonc
"computed": {
  "tooltip": {"description": "A word of darkness that causes 108 Shadow damage over 18 sec.",
              "auraDescription": "18 Shadow damage every 3 seconds."},   // null where refused
  "tooltipBlockedBy": ["$s1"]                                            // only when something was refused
}
```

Only templates that contain a `$` appear in `tooltip` (plain text needs no rendering; use `description` as is). `{icon:ID}` in rendered text marks an inline spell icon for the UI to replace.

## What the numbers mean

- **Level 60, base values.** Amounts are evaluated at character level 60 (`tooltips.LEVEL`; the Forever level cap, wowsims' `CharacterLevel`), capped by the spell's own max scaling level. They do **not** include your spell power, attack power or talents, so in-game damage/healing is higher by your power times the spell's coefficient.
- **Amount model** (`tooltips.Effect`): `base points + (min(level, MaxLevel) - BaseLevel) × points-per-level`, in float32 as the game files store it. A positive fraction is floored; a fractional **damage/healing** amount or any fractional **negative** amount is refused (how the client rounds them is not known). `$m`/`$M` are the low/high ends of the roll (`Variance`, round-half-to-even, as wowsims). `$s`, `$w`, `$m`, `$M` print unsigned; inside `${...}` they keep their sign.
- This is a port of the effect model in `wowsims/forever` `sim/core/spelldata/effect.go`, which they check against in-game tooltips.

## Supported tokens

`$sN` `$wN` `$mN` `$MN` (effect amounts), `$oN` (periodic total; only when duration is a whole number of ticks), `$d` (duration: `8 sec`, `2 min`, `1 hour`, `2 hours`), `$tN` (period, seconds), `$aN` (radius), `$xN` (chain targets), `$h` (proc chance), the same with another spell's id in front (`$1279976s1`, `$7922d`), `${expr}` with `+ - * / ^ ( )` over those values, `${expr}.N` (N decimals, like printf `%.Nf`), `$lsingular:plural;` (by the last number written), `$@spellname123`, `$@spelldesc123`, `$@spellaura123` (nested, depth 3), `$@spellicon123` (becomes `{icon:123}`).

## Deliberately not rendered

Anything that depends on **who is looking**: conditionals (`$?a123[..][..]`, `$?s`, `$?p`, `$?j`), gender (`$g`), player stats (`$SPS`, `$AP`, `$PL`, `$sk43`), description variables (`$<frostdamage>`). Anything whose **client formatting is not confirmed**: `$/10;s1` (division suffix; wowsims prints `3.0`, the client may print `3`), durations that are not whole seconds/minutes/hours, math results that are not whole numbers or plain decimals, charges/stacks (`$n`, `$u`), mana/other-resource tokens (`$q`, `$b`, `$e`), and `$s` on a fractional damage amount.

Coverage on build 1.60.1.70685 push 113511: **15,260 of 18,313 templated texts rendered (83.3 %)**; the other 3,053 are refused. Top blockers: `$s` on fractional damage/healing (420), `$/N;` (254), `$?j` mount conditionals (212), `$N` (183), `$o` (128), `$q` (126), cross-spell `$Ns1` (119), `$d` with no duration (112).

## Verification

- **Amounts: 1,959 of 1,961** printed single amounts in wowsims/gamedata's class spell cards match (the 2 misses are movement-speed auras `+0%` where the card shows something unrelated to the amount). **Roll ranges: 748 of 748** exact. Run `python3 pipeline/tests/check_against_gamedata.py .scan/scan.db <gamedata checkout>/spells` after any change to `Effect`. Note gamedata is wowsims' own Go output of the same model, so this proves we ported it correctly, not that the model equals the game.
- **A real bug this caught:** rounding floats to 6 decimals when loading rows (right for records) flipped a half-way rounding in float32 (Wrath rank 3, 31-35 vs 30-36). The renderer reads spell effects with `raw=True`. There is a regression test.
- **Not verified against the live game.** `docs/verification-checklist.md` lists spells to compare in game. Unconfirmed assumptions: the duration wording (`8 sec`, `2 min`, `1 hour`) follows the client's usual style; the `}.N` decimals reading follows wowsims' parser.

## Changing it

Add a token only with: a rule that is exact (or a refusal), a unit test in `pipeline/tests/test_tooltips.py` (including a case that must stay refused), a re-run of the gamedata check, and a doc update here. Then rebuild the data (`scripts/backfill.sh`): rendered text changes for many spells, and the history's `computed.tooltip.*` entries are a function of the renderer version.

Effects of other spells show up too: a spell whose text embeds `$123s1` changes when spell 123's effect changes, with `areas: ["computed"]` and no change to its own fields. That is intended (the displayed text did change).
