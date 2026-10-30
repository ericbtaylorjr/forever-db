# Known limitations and open questions

Keep this current. Add an entry whenever you discover a data quirk.

## Version history

- **No history before the baseline.** The first ingest (build 70685, push 113441, 2026-10-30) is a snapshot, so every entity has `baseline: true` and "last updated" means "in or before 70685". A local install only holds one build.
  - Backfill options: (a) fetch earlier builds from the CDN if Blizzard still serves them (needs each build's config hash; db2tool's `--cdn` only fetches the current build; wago.tools lists historical build configs), (b) parse `wowsims/gamedata` `patches/` (class spells and items only, text format; builds 70009 → 70685 listed there). **Not decided.**
- Hotfix history is similarly limited to pushes we ingest. A hotfix applied and reverted between two scans is invisible.
- Ingests are keyed by `(build, push)`; the same push read from a different machine's `DBCache.bin` can differ if that client has not received all pushes. Prefer the Raidbots mirror for authoritative data.

## Coverage

- **Locked rows.** Encrypted sections with unknown TACT keys are skipped (the 2026-10-30 scan reported on the order of hundreds of locked rows in `Spell`, `SpellEffect`, `SpellMisc`, `Item`, `ItemSparse`, …). Those spells/items may be missing or partial. The baseline ingest was run without `--scan-log`, so `state.json` has no per-table counts yet; the first `scripts/scan.sh` run that ingests a new version will record them.
- **"Spell" ≠ "spell players can use".** `Spell` has ~32k rows including old/test/internal spells (names like `Word of Recall (OLD)`, `temp` icons). No availability filter exists yet. Candidate signals: appears in `SkillLineAbility`, `Talent`, `ItemEffect`, `ItemSetSpell`, has a non-empty name/description.
- **Items** = `ItemSparse` rows (19,735), of which 8,505 are gear. Max `itemLevel` is 100 in this build, so Forever uses a classic-style scale.
- Not extracted: item drop/vendor sources (`JournalEncounterItem` came back empty), quests, NPCs, spell visuals, and non-`enUS` text.

## Derived values not computed yet

- **Item stat values.** Items carry only raw allocation (`StatModifier_bonusStat`, `StatPercentEditor`); real stats need `RandPropPoints`/curve/squish logic. `wowsims/gamedata` computes them (its README says from stat allocations and item-level budgets; see `scripts/export_items.py`, and the `forever` repo's `tools/database`); not yet reviewed in detail. Porting or consuming that is the main open item for a useful gear browser. Weapon DPS and armor have the same issue (`ItemDamage*`, `ItemArmor*` tables are extracted but not applied).
- **Tooltip text.** `description`/`auraDescription` are raw templates (`$s1`, `${$1279976m1*$d}`, `$?a14748[...]`). Rendering them needs a resolver using `SpellEffect` values; `wowsims/forever` has a `tools/tooltip` directory that may be relevant (not reviewed).
- **Icons.** Only `iconFileDataID` is stored; names come from db2tool's `listfile.csv` (`interface/icons/<name>.blp`) and must be resolved when the site is built. Image files themselves are not extracted.

## Diff semantics

- `null` in a change means default/absent (see AGENTS.md rule 4), so `[null, 99.0]` can mean "was 0".
- List indexes in change paths (`related.SpellEffect[1]…`) come from deterministic sorting of rows; if a spell gains a row that sorts earlier, later rows appear shifted. Treat per-index diffs as indicative and compare whole rows when in doubt.
- Anonymous columns (`Field_5_5_4_67090_014`, `Node__Field_…`) are named by WoWDBDefs build-specific placeholders; they can be renamed upstream (guarded by the schema check).

## Tooling

- Extraction depends on wowsims/forever `tools/db2tool` (MIT) and its network downloads (WoWDBDefs, `listfile.csv`, community TACT keys). Pin and record the commit used per scan; scans are not bit-for-bit reproducible if those inputs move.
- Re-ingesting the *same* version is a no-op, so a scan taken before the client has finished pulling hotfixes cannot be "topped up" without `--force`.
