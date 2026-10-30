# Item stats spike

Status: **spike done 2026-10-30; not yet in the pipeline.** Prototype: `pipeline/spikes/item_stats_proto.py`.

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

## What we have not verified

- **Quality 0–1 items with allocations (41 items)** get no stats under this rule, because `RandPropPoints` has no Poor/Common column. The Go code has no obvious special case either, but no reference output covers them. Check a few in-game.
- **Items outside wowsims' list.** `db.json` only has sim-relevant items (5,225 of 19,735). The other ~14.5k use the same formula but have no independent reference. Spot-check a sample against the game or Wowhead-style sources.
- **Heirloom/scaling items and random-suffix items** (stats from "of the Bear"-style suffixes): not computed; suffix stats are a separate problem.
- Equip-effect stats (above) are not parsed from spell effects.

## Productionizing (estimate: 1–2 days)

What changes:
1. **Scan:** add the `ShieldBlockRegular` GameTable to extraction (`GameTables` in `scan/settings.template.json`; db2tool writes it as a `.txt`, so `scan.sh` must hand that file to the ingest). All DB2 tables the formula needs (`RandPropPoints`, `ItemDamage*`, `ItemArmor*`, `ArmorLocation`) are already extracted.
2. **Ingest:** compute a `computed` block on each item: `{stats: {ITEM_MOD id: value}, armor, bonusArmor, blockValue, weapon: {min, max, dps, speed}}`. It stays a pure function of the dump (+ the GameTable file), so history and diffs include real stat changes automatically.
3. **Tests:** unit tests on synthetic tables, plus a small golden set of real items with known values (the 25 mismatches above must be listed explicitly as known exceptions, not silently passing).
4. **Rebuild data:** adding fields changes every item's record, so run `scripts/backfill.sh` once and commit it as a rebuild (the runbook describes this).
5. **Docs:** `data-model.md` (new `computed` fields), `known-limitations.md`.

Decision still open: whether to also pull equip-effect stats into `computed` (what wowsims does) or leave them in `effects`. Recommendation: leave in `effects` and show them separately in the UI, because merging them requires parsing spell effects and would make the stats fragile.
