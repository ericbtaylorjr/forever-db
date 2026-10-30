# Known limitations and open questions

Keep this current. Add an entry whenever you discover a data quirk.

## Version history

- **History covers 6 builds, 70245 → 70685, plus hotfix push 113511 (2026-10-30).** It was backfilled with `scripts/backfill.sh` from the CDN. Entities untouched since build 70245 still have `baseline: true`; for them "last changed" means "in or before 70245", which is the honest limit of the history. Beta is young, so this covers most of the game's life so far.
- **Builds we cannot get.** The list of past builds and their CDN config hashes comes from wago.tools, which has only 7 `wowf` entries (the newest, 70707, is the CN region and is skipped). `wowsims/gamedata` has data for earlier builds (70009, 70291, 70334, 70338, 70374, 70425, 70450 …) that wago lacks. If those config hashes can be found (Blizzard's Ribbit history, a community archive), add them to `builds.py list` and re-run the backfill. **Not done.**
- **Historical builds are base data without hotfixes** (push 0): Raidbots only mirrors the *current* cache. So a build's own hotfixes show up as a separate version (e.g. 70685 push 0 → 70685 push 113511: +59 spells, +478 items, 141/46 changed). Hotfixes applied and reverted between two of our scans are invisible.
- **Builds 70634 and 70658 contain no spell or item changes** (client-only builds, as far as the data shows). They appear in `state.json` → `builds` with zero counts.
- **Intermediate builds are folded together if a scan is missed.** The check compares with the latest state, so a skipped build is not ingested separately (history cannot be inserted out of order). The 3-hourly schedule makes this rare.
- Ingests are keyed by `(build, push)`. The local client's `DBCache.bin` can lag (it was at push 113441 when Raidbots had 113511); never commit a local-install scan over a CDN one.

## Coverage

- **Locked rows.** Encrypted sections with unknown TACT keys are skipped (4,850 rows at push 113511, mostly `SpellEffect` 1,301, `SpellMisc` 945, `SpellName` 606, `Spell` 473; recorded in `state.json` → `scan.lockedRows`). Those spells/items may be missing or partial, and appear later as `added` once a key is published. Only the latest ingest's counts are kept in `scan`.
- **"Spell" ≠ "spell players can use".** `Spell` has ~32k rows including old/test/internal spells (names like `Word of Recall (OLD)`, `temp` icons). No availability filter exists yet. Candidate signals: appears in `SkillLineAbility`, `Talent`, `ItemEffect`, `ItemSetSpell`, has a non-empty name/description.
- **Items** = `ItemSparse` rows (19,735 live at push 113511), of which 8,257 have `isGear` (weapon or armor class with an equip slot). Counting every item with an equip slot regardless of class gives a larger number (~8.5k) because quivers, bags and similar have slots too. Max `itemLevel` is 100, so Forever uses a classic-style scale.
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

- Extraction depends on wowsims/forever `tools/db2tool` (MIT) and its network downloads (WoWDBDefs, `listfile.csv`, community TACT keys). The tool commit is pinned in `scan/forever-ref.txt`, but the downloads are not, so scans are not bit-for-bit reproducible if those inputs move.
- **We carry a patch to db2tool** (`scan/patches/db2tool-cdn-pin.patch`, adds `--cdn-pin` to extract a historical build). Suggested: upstream it to wowsims/forever so we can drop it; until then a bump of `forever-ref.txt` may need the patch rebased.
- **The `update-data.yml` workflow has not been confirmed on GitHub yet.** Its steps were exercised locally; only `test.yml` has run there. Run it manually once (Actions → *Update data* → *Run workflow*, tick *force*) and record the outcome here. Hands-off merging needs the repo setting *Allow auto-merge*.
- **Runtime downloads are not pinned or checksum-verified by us** (WoWDBDefs, `listfile.csv`, TACT keys, all fetched by db2tool; also wago.tools' build list and the Raidbots cache). A compromised or changed source would flow into `data/`. Mitigations today: the review of every PR's counts and diff, and the schema guard. Possible hardening: vendor/pin the `.dbd` files by commit.
- Re-ingesting the *same* version is a no-op, so a scan taken before the client has finished pulling hotfixes cannot be "topped up" without `--force`.
