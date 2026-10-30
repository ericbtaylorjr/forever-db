# Item stats spike

Status: **productionized 2026-10-30** (`computed` in `pipeline/build_data.py`; tests in `pipeline/tests/`). The original prototype is kept in `pipeline/spikes/item_stats_proto.py` for reference. Decision recorded: equip-effect stats stay in `effects` and are not merged into `computed`, so changes to an effect show up separately from stat changes.

## Why

The game files store an item's stats as *allocations*, not numbers: `ItemSparse.StatModifier_bonusStat[i]` (stat type, -1 = unused) and `StatPercentEditor[i]` (share of a budget, in 1/10000). The in-game number comes from combining that with level tables. Until we compute it, the dataset cannot filter or sort on "Stamina ≥ 20", "armor", or weapon DPS, and history cannot show that a hotfix changed an item's real stats.

## Formula (as implemented in the prototype; reference: `wowsims/forever` `tools/database/dbc/item.go`, `item_damage.go`, and `wowsims/gamedata` `scripts/export_items.py`)

Let `q` = `OverallQualityID`, `ilvl` = `ItemLevel`.

1. **Stats.** `value = floor(alloc × budget × 0.0001 + 0.5)` (round half up; Go's `math.Round`).
   `budget = RandPropPoints[ilvl][Good|Superior|Epic by q (2|3|4+)][slot]`, only for `q ≥ 2`.
   `slot` comes from class/subclass/inventory type: two-hand weapons 0; ranged/wands/thrown 4; other weapons 3; head/chest/legs 0; shoulders/waist/feet/hands/trinket 1; neck/finger/cloak/wrists/shield/off-hand/relic 2 (see `budget_slot`).
2. **Armor.** Armor items, `q ≤ 6`: cloth/leather/mail/plate → `ItemArmorTotal[ilvl]` × `ItemArmorQuality[ilvl][q]` × `ArmorLocation[slot][armor type]`, rounded (robe uses the chest row). Shields: `ItemArmorShield[ilvl][q]`.
3. **Bonus armor** ("green armor"): armor-class items with `QualityModifier > 0` get that value as ITEM_MOD 50.
4. **Block value** (shields): `ShieldBlockRegular` **GameTable** row for `ilvl`, column `q`. This is a plain-text file, not a DB2 table (see "What changes" below).
5. **Caster weapons** (`Flags[4]` bit 0x200 / 0x400) carry spell power no stat slot states: `20000 × budget[slot 0] / 10000` spell power, or on healing weapons `37600 × budget / 10000` healing and a third of that as spell damage.
6. **Weapon damage.** Table by inventory type and the caster flag (`Flags[1]` 0x200): `ItemDamageOneHand[Caster]`, `…TwoHand[Caster]`, `…Ranged`, `…Thrown`, `…Wand`. `dps = table[ilvl][q]` (heirloom/artifact+ use the epic column). Weapons with `Flags[4]` 0x100 deal 2/3 (one-hand) or 29/39 (two-hand) of that. `min = floor(dps·speed·(1−var/2) + qm·speed)`, `max = floor(dps·speed·(1+var/2) + qm·speed + 0.5)`, with `speed = ItemDelay/1000`, `var = DmgVariance`, `qm = QualityModifier`.
7. **Special stat ids.** ITEM_MOD 45 (spell power) means both spell damage and healing; 124 means all five resistances; several hit/crit/haste ids collapse into one rating each (wowsims' sim view). We should store the raw ITEM_MOD ids and let the UI group them.

## Result

Compared against `wowsims/forever` `assets/database/db.json` (their Go output; 5,225 sim-relevant items; generated one day before our data):

| Check | Result |
|---|---|
| Stats incl. armor, bonus armor, block value, resistances | **5,200 / 5,225 exact** |
| Weapon damage min/max | **801 / 801 exact** |
| Armor values | all match |

The wowsims code comments say they validated the rules against in-game tooltips (e.g. all 165 reduced-caster weapons, three independent tooltips for "All Resistances"), so we are agreeing with a tooltip-checked reference, not only with another program. We have **not** compared against the live client ourselves.

The 25 differences are all items whose numbers do not come from the budget: trinkets/runes whose stats are granted by an *equip effect spell* (wowsims folds those into the item; we keep them in `effects`), and a few legendaries/uniques (Sulfuras, Thunderfury, Shard of the Defiler) that wowsims hand-patches. That is a design difference, not a formula error, but each of those items deserves a manual look before we claim their stats are right.

### The 25 known differences (committed data vs wowsims' db.json)

`17142 17182 19019 19120 21407 21565 21566 21567 21568 22589 22630 22631 22632 211940 270225 270275 270276 271903 271904 271905 271906 272059 272060 272061 272062`

Shard of the Defiler, Sulfuras, Thunderfury, runes/trinkets ("Rune of the Guard Captain", "Rune of Perfection/Duty"), Mace of Unending Life, the Atiesh staves and a few more. Either their numbers come from an equip-effect spell that wowsims adds to the item, or wowsims hand-patches them (211940, a weapon-class item, has armor 40 in their output and none in ours). None of the 28 golden items is in this list.

## What we have not verified

- **Quality 0–1 items with allocations (41 items)** get no stats under this rule, because `RandPropPoints` has no Poor/Common column. The Go code has no obvious special case either, but no reference output covers them. Check a few in-game.
- **Items outside wowsims' list.** `db.json` only has sim-relevant items (5,225 of 19,735). The other ~14.5k use the same formula but have no independent reference. Spot-check a sample against the game or Wowhead-style sources.
- **Heirloom/scaling items and random-suffix items** (stats from "of the Bear"-style suffixes): not computed; suffix stats are a separate problem.
- Equip-effect stats (above) are not parsed from spell effects.

## How it was productionized

What was done:
1. `compute_item` + `StatTables` in `pipeline/build_data.py` add a `computed` block to every item (documented in `data-model.md`). All DB2 tables needed were already in the scan.
2. **Shield block value needed a table the game does not ship.** The plan was to extract the `ShieldBlockRegular` GameTable with db2tool, but it is a server-side file (`gametablesserver/…`, FileDataID 2200976), absent from the client's files. We vendor wowsims' copy in `scan/gametables/` (provenance and risks in its README); `scan.sh` stops if the pinned wowsims copy differs. Consequence: block value is the one computed stat that will not follow a game hotfix on its own.
3. Tests: synthetic unit tests for each rule (rounding, budgets by quality, armor, shield, bonus armor, weapon damage, caster flags, effects vs stats in history) and a golden set of 28 real items (`pipeline/tests/golden_items.json`, regenerated by `pipeline/tests/make_golden.py` from wowsims' output; the script refuses to record an item the pipeline disagrees on).
4. Data rebuilt with `scripts/backfill.sh`. Effects are now ordered by the game's slot index so adding one effect doesn't renumber the others in the history; history events carry `areas`.

Result on the committed data: identical to the spike (5,200 / 5,225 items, 801 / 801 weapons).

Decision (recorded): equip-effect stats stay in `effects`, not folded into `computed`. Merging them would require parsing spell effects and would make the stats fragile; keeping them separate also means a change to an effect is visible on its own.
