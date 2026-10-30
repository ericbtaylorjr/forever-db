# Data model

Output contract of `pipeline/build_data.py`. The future browser UI should depend only on this.

## Files

| File | Content |
|---|---|
| `data/spells.jsonl` | One line per spell |
| `data/items.jsonl` | One line per item (gear is the subset with `data.isGear == true`) |
| `data/history/spells.jsonl`, `data/history/items.jsonl` | One line per entity that has had at least one event since the baseline |
| `data/state.json` | Ingest state (see below) |

All JSONL is sorted by `id`, keys sorted, compact.

## Entity line (`spells.jsonl`, `items.jsonl`)

```jsonc
{
  "id": 10,
  "firstSeen":   {"build": 70245, "push": 0},       // first ingest that contained it
  "lastChanged": {"build": 70532, "push": 0},       // last ingest where any field differed
  "baseline": true,   // true => seen in the very first ingest (build 70245); real firstSeen may be EARLIER
  "removed": true,    // only present when the entity vanished from a later dump
  "hash": "bf66fe819d61b6bc",  // sha1 prefix of `data`; equal hash => no change
  "data": { ... }     // see below
}
```

**Versions.** A version is `{build, push}`. `push` is the server's hotfix push number; **`push: 0` is a build's base data with no hotfix overlay** (all historical builds). `(build, push)` orders versions. History starts at build 70245, so `lastChanged` is exact only after that; for entities with `baseline: true` and `lastChanged` equal to `firstSeen`, read it as "in or before 70245". See `known-limitations.md` for what history exists and what is missing.

## `data` for spells

Scalars (all optional; absent = default):

| Field | From |
|---|---|
| `name` | `SpellName.Name_lang` |
| `subtext`, `description`, `auraDescription` | `Spell.*_lang` (raw tooltip templates, e.g. `$s1`, `${$m1*$d}`) |
| `iconFileDataID` | `SpellMisc.SpellIconFileDataID` (lowest `DifficultyID` row) |
| `schoolMask` | `SpellMisc.SchoolMask` (bitmask: 1 Physical, 2 Holy, 4 Fire, 8 Nature, 16 Frost, 32 Shadow, 64 Arcane) |
| `castTimeMs` | `SpellCastTimes.Base` via `SpellMisc.CastingTimeIndex` |
| `durationMs` | `SpellDuration.Duration` via `SpellMisc.DurationIndex` |
| `range` | `{name, min[], max[]}` from `SpellRange` via `SpellMisc.RangeIndex` |

`related`: `{ "<DB2 table>": [row, ...] }` for every per-spell table keyed by `SpellID` (`SpellEffect`, `SpellPower`, `SpellCooldowns`, `SpellLevels`, `SpellCategories`, `SpellAuraOptions`, `SpellClassOptions`, `SpellReagents`, `SpellMisc`, …) plus `SkillLineAbility` (keyed by `Spell`). Rows keep the DB2 column names, drop the surrogate `ID` and the key column, drop default-valued fields, and are sorted deterministically. Array columns are JSON arrays.

## `data` for items

| Field | From |
|---|---|
| `name`, `description` | `ItemSparse.Display_lang`, `Description_lang` |
| `classId`/`className`, `subclassId`/`subclassName` | `Item.ClassID/SubclassID` + `ItemClass`/`ItemSubClass` |
| `inventoryType` | `ItemSparse.InventoryType` (0 = not equippable) |
| `isGear` | `classId ∈ {2 Weapon, 4 Armor}` and `inventoryType != 0` |
| `quality`, `qualityName` | `ItemSparse.OverallQualityID` (0 Poor … 5 Legendary, 6 Artifact, 7 Heirloom) |
| `itemLevel`, `requiredLevel` | `ItemSparse` |
| `nameDescription` | `ItemNameDescription` (e.g. "Raid Unique (3)") |
| `iconFileDataID` | `Item.IconFileDataID` |
| `itemSet` | `{id, name}` from `ItemSet` |
| `effects` | `ItemEffect` rows linked via `ItemXItemEffect` (`SpellID` links to spells) |
| `bonusTrees` | `ItemXBonusTree.ItemBonusTreeID`, sorted |
| `sparse` | remaining `ItemSparse` columns (stats, prices, flags, bonding, delay, sockets, …) |
| `item` | remaining `Item` columns |

Item stats are **raw**: `sparse.StatModifier_bonusStat[i]` is the stat type and `sparse.StatPercentEditor[i]` its allocation. Resolved stat values are not computed yet (see known limitations).

An item exists in the dataset iff it has an `ItemSparse` row. `Item` has ~12k more rows (shared with other clients) that Forever does not use.

## History line

```jsonc
{"id": 543, "events": [
  {"build": 70700, "push": 113500, "type": "changed",
   "changes": {"description": ["old", "new"], "related.SpellEffect[1].EffectBasePointsF": [162.0, 99.0]}},
  {"build": 70700, "push": 113500, "type": "removed"},
  {"build": 70701, "push": 113510, "type": "added"}   // appeared after the baseline
]}
```

Change paths are dotted with `[n]` list indexes; `null` on either side means "default/absent". The baseline ingest writes no events. Reconstruct an old version of an entity by applying events in reverse to the current `data`; side-by-side comparison of two versions uses the same events.

## `state.json`

`version`, `build`, `hotfixPush` (latest ingested); `baselineBuild`/`baselinePush`; `schema` (column list per table, used for the schema-change guard); `scan` (latest ingest only: `hotfixSummary`, `lockedRows` per table, `hotfixCacheSha256` of the Raidbots cache, which `builds.py check` compares against); `builds` (one entry per ingest: version, push, add/change/remove counts, hotfix summary; the ledger of what was ingested and the basis for the sanity check in AGENTS.md).
