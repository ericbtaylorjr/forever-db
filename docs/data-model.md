# Data model

Output contract of `pipeline/build_data.py`. The future browser UI should depend only on this.

## Files

| File | Content |
|---|---|
| `data/spells.jsonl` | One line per spell |
| `data/items.jsonl` | One line per item (gear is the subset with `data.isGear == true`) |
| `data/history/spells.jsonl`, `data/history/items.jsonl` | One line per entity that has had at least one event since the baseline |
| `data/state.json` | Ingest state (see below) |
| `data/build-dates.json` | `"build:push"` → `{date, source}`: when each ingested version was added. Base builds from wago.tools; the newest hotfix push from the cache's Last-Modified; older pushes undated. Written by `builds.py dates` (run by `scan.sh`), never overwritten |
| `data/stat-names.json` | ITEM_MOD id → display name, for `computed.stats` |
| `data/icon-names.json` | icon FileDataID → icon file name (`inv_sword_01`), written by `pipeline/icon_names.py` from the community listfile |

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

## Discovery (both kinds)

Every `data` has `discovery`: `"discovered"` (the game files give its name and details) or `"encrypted"` (known to exist, details hidden; see `docs/discovery.md`). Each entity also has `discoveredAt` (`{build, push}`, `null` while encrypted). Encrypted records are filled only with what the files expose: items keep class, subclass, slot, icon, set, effects; spells keep `computed.availability`. History gets a `discovered` event when an entity goes from encrypted to discovered.

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

`computed` (spells):

```jsonc
"computed": {
  "availability": ["class:Mage", "item"],        // where a player can get it; see below
  "tooltip": {"description": "..." | null, "auraDescription": "..." | null},   // rendered templates, docs/tooltips.md
  "tooltipBlockedBy": ["$s1"]                    // only if some template was refused
}
```

`availability` tags (sorted; empty = no player source found): `class:<Name>` (a class skill line teaches it), `class-family:<Name>` (belongs to that class's spell family, which also catches talent procs and rune-style spells), `pet`, `talent` (Talent/Trait tables), `weapon-skill`, `armor-skill`, `secondary-skill`, `language`, `profession`, `skill`, `item` (an item's use/equip effect), `item-set` (set bonus), `triggered` (fired, directly or through further triggers, by a spell that has a source), `marked-obsolete` (name says OLD/DEPRECATED/[DNT]/test). It describes provenance, not whether a spell is "real": about half the spells have no tag and are mostly NPC/creature and scripted abilities, which are legitimate game content that no player can cast.

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
| `effects` | `ItemEffect` rows linked via `ItemXItemEffect`, ordered by the game's slot (`LegacySlotIndex`), then spell. `SpellID` links to the spell entity, which has its own history. **Equip-effect stats are not folded into `computed`.** |
| `computed` | Stats the client shows, derived from the budget tables (see below) |
| `bonusTrees` | `ItemXBonusTree.ItemBonusTreeID`, sorted |
| `sparse` | remaining `ItemSparse` columns (stats, prices, flags, bonding, delay, sockets, …) |
| `item` | remaining `Item` columns |

### `computed` (items)

```jsonc
"computed": {
  "stats":  {"7": 50, "5": 13},        // ITEM_MOD id -> value; names in data/stat-names.json
  "armor":  55,                         // base armor (armor class only)
  "weapon": {"min": 15, "max": 25, "dps": 10.0, "speed": 2.0}   // weapons only
}
```

Absent keys mean none. Stat ids are the game's raw ITEM_MOD numbers (`data/stat-names.json`; unknown ids appear as numbers only). Some ids overlap by design: `45` spell power means both spell damage and healing, `124` all resistances, and hit/crit/haste each exist as melee, ranged, spell and combined ids. The UI should group them. Bonus armor is `50`, shield block value `48`, caster-weapon spell power is added to `45`/`41`/`42`.

Rules and provenance: `docs/item-stats-spike.md`. Raw inputs remain in `sparse` (`StatModifier_bonusStat`, `StatPercentEditor`), so a change to a stat allocation shows in both `sparse` and `computed`; a hotfix to a budget table shows only in `computed`.

**Not in `computed`:** stats granted by equip-effect spells (many trinkets/runes), random-suffix stats, and anything on items without a quality ≥ Uncommon budget. Block value uses a vendored table (`scan/gametables/README.md`).

An item exists in the dataset iff it has an `ItemSparse` row. `Item` has ~12k more rows (shared with other clients) that Forever does not use.

## History line

```jsonc
{"id": 543, "events": [
  {"build": 70700, "push": 113500, "type": "changed", "areas": ["related"],
   "changes": {"description": ["old", "new"], "related.SpellEffect[1].EffectBasePointsF": [162.0, 99.0]}},
  {"build": 70700, "push": 113500, "type": "removed"},
  {"build": 70701, "push": 113510, "type": "added", "discovery": "encrypted"},   // appeared after the baseline
  {"build": 70707, "push": 113511, "type": "discovered", "areas": ["discovery", "name", ...], "changes": {"discovery": ["encrypted", "discovered"], ...}}
]}
```

`areas` lists the top-level sections of the record that changed (items: `computed`, `effects`, `sparse`, `item`, `name`, …; spells: `related`, `description`, `name`, …). Use it to tell *what kind* of change an event was, e.g. an item's `effects` changed but not its `computed` stats. Effects have their own history too: the spell an effect points to is a separate spell entity. Change paths are dotted with `[n]` list indexes; `null` on either side means "default/absent". The baseline ingest writes no events. Reconstruct an old version of an entity by applying events in reverse to the current `data`; side-by-side comparison of two versions uses the same events.

## `state.json`

`version`, `build`, `hotfixPush` (latest ingested); `baselineBuild`/`baselinePush`; `schema` (column list per table, used for the schema-change guard); `scan` (latest ingest only: `hotfixSummary`, `lockedRows` per table, `hotfixCacheSha256` of the Raidbots cache, which `builds.py check` compares against); `builds` (one entry per ingest: version, push, add/change/remove/discovered counts, `discovery` totals (discovered/encrypted per kind), `locked` (rows no key opens, per table and key), hotfix summary; the ledger of what was ingested and the basis for the sanity check in AGENTS.md).
