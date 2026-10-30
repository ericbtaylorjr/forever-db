# Known limitations and open questions

Keep this current. Add an entry whenever you discover a data quirk.

## Version history

- **History covers 6 builds, 70245 → 70685, plus hotfix push 113511 (2026-10-30).** It was backfilled with `scripts/backfill.sh` from the CDN. Entities untouched since build 70245 still have `baseline: true`; for them "last changed" means "in or before 70245", which is the honest limit of the history. Beta is young, so this covers most of the game's life so far.
- **Builds we cannot get.** The list of past builds and their CDN config hashes comes from wago.tools, which has only 7 `wowf` entries (the newest, 70707, is the CN region and is skipped). `wowsims/gamedata` has data for earlier builds (70009, 70291, 70334, 70338, 70374, 70425, 70450 …) that wago lacks. If those config hashes can be found (Blizzard's Ribbit history, a community archive), add them to `builds.py list` and re-run the backfill. **Not done.**
- **Historical builds are base data without hotfixes** (push 0): Raidbots only mirrors the *current* cache. So a build's own hotfixes show up as a separate version (e.g. 70685 push 0 → 70685 push 113511: +59 spells, +478 items, 141/46 changed). Hotfixes applied and reverted between two of our scans are invisible.
- **Builds 70634 and 70658 contain no spell or item changes** (client-only builds, as far as the data shows). They appear in `state.json` → `builds` with zero counts.
- **Intermediate builds are folded together if a scan is missed.** The check compares with the latest state, so a skipped build is not ingested separately (history cannot be inserted out of order). The 3-hourly schedule makes this rare.
- Ingests are keyed by `(build, push)`. The local client's `DBCache.bin` can lag (it was at push 113441 when Raidbots had 113511); never commit a local-install scan over a CDN one.

## Discovery and encrypted content

- **Interpretation, not confirmation.** "Encrypted" = an item with an `Item` row but no `ItemSparse` row, or a spell named only by other tables. The pattern (468 items revealed by one hotfix push; 1,076 class spells known only from skill lines) matches the game's design, but it has not been checked in the live game. See `docs/discovery.md`.
- **TACT-locked rows have no ids.** 4,908 rows (build 70707) behind unknown keys can only be counted, per table and key. They are not entities until a key opens them.
- Why an entity is hidden (never found / not released / removed) is not visible in the files.

## Website

- Icons are hot-linked from a public icon host, so they depend on it being up and on it having the icon (a placeholder shows otherwise). `site/src/config.ts` has the single function to change if we self-host.
- Removed items and spells are not in the browsable lists; a build page names them from its own file. Build-page filters use an entity's *current* attributes, not its attributes at that build.
- The compare view is field-level (old value, new value). It does not draw two game-style tooltips side by side.
- Not tested in a live browser on iOS or Firefox; layout was checked at desktop and 390 px widths in Chrome. Dark mode colors were checked for contrast (WCAG AA) but not viewed.
- The "test item" filter is a name-pattern guess (`TEST_NAME` in `pipeline/site_data.py`), off by default.

## Coverage

- **Locked rows.** Encrypted sections with unknown TACT keys are skipped (4,850 rows at push 113511, mostly `SpellEffect` 1,301, `SpellMisc` 945, `SpellName` 606, `Spell` 473; recorded in `state.json` → `scan.lockedRows`). Those spells/items may be missing or partial, and appear later as `added` once a key is published. Only the latest ingest's counts are kept in `scan`.
- **"Spell" ≠ "spell players can use" is now answered by `computed.availability`** (`docs/data-model.md`). 16,883 of 32,031 spells have no tag: NPC/creature and scripted abilities, plus anything reached through a source we do not extract (e.g. rune-style grants outside the skill-line and spell-family tables). Treat "untagged" as "no player source found", not "unused".
- **Items** = `ItemSparse` rows (19,735 live at push 113511), of which 8,257 have `isGear` (weapon or armor class with an equip slot). Counting every item with an equip slot regardless of class gives a larger number (~8.5k) because quivers, bags and similar have slots too. Max `itemLevel` is 100, so Forever uses a classic-style scale.
- Not extracted: item drop/vendor sources (`JournalEncounterItem` came back empty), quests, NPCs, spell visuals, and non-`enUS` text.

## Derived values not computed yet

- **Item stats are computed (`computed`) but incomplete.** Not included: stats granted by equip-effect spells (they stay in `effects`), random-suffix stats, Poor/Common items (no budget column), and 25 items where wowsims' output differs (list in `docs/item-stats-spike.md`). 3,042 of the 8,257 gear items (mostly white/gray and placeholder items) have no independent reference, and nothing has been compared with the live game yet (`docs/verification-checklist.md`). Block value depends on a vendored table that does not follow game hotfixes (`scan/gametables/README.md`).
- **Tooltip text (partly solved).** `computed.tooltip` renders 83.3 % of templated texts and refuses the rest rather than guess (`docs/tooltips.md`). Conditionals on the viewer's talents, gender and player stats can never be rendered in a database view. Original note: `description`/`auraDescription` are raw templates (`$s1`, `${$1279976m1*$d}`, `$?a14748[...]`). Rendering them needs a resolver using `SpellEffect` values; `wowsims/forever` has a `tools/tooltip` directory that may be relevant (not reviewed).
- **Icons.** Only `iconFileDataID` is stored; names come from db2tool's `listfile.csv` (`interface/icons/<name>.blp`) and must be resolved when the site is built. Image files themselves are not extracted.

## Diff semantics

- `null` in a change means default/absent (see AGENTS.md rule 4), so `[null, 99.0]` can mean "was 0".
- List indexes in change paths (`related.SpellEffect[1]…`) come from deterministic sorting of rows; if a spell gains a row that sorts earlier, later rows appear shifted. Treat per-index diffs as indicative and compare whole rows when in doubt.
- Anonymous columns (`Field_5_5_4_67090_014`, `Node__Field_…`) are named by WoWDBDefs build-specific placeholders; they can be renamed upstream (guarded by the schema check).

## Tooling

- Extraction depends on wowsims/forever `tools/db2tool` (MIT) and its network downloads (WoWDBDefs, `listfile.csv`, community TACT keys). The tool commit is pinned in `scan/forever-ref.txt`, but the downloads are not, so scans are not bit-for-bit reproducible if those inputs move.
- **We carry a patch to db2tool** (`scan/patches/db2tool-cdn-pin.patch`, adds `--cdn-pin` to extract a historical build). Suggested: upstream it to wowsims/forever so we can drop it; until then a bump of `forever-ref.txt` may need the patch rebased.
- **`update-data.yml` is confirmed up to the PR step.** A forced manual run on 2026-10-30 passed the check, scan (CDN + Raidbots hotfixes, Go 1.27.3, Python 3.15) and ingest, but found nothing new, so **opening and auto-merging a PR has not run yet.** Confirm on the first real build/hotfix, then update this entry. Hands-off merging needs the repo setting *Allow auto-merge*; if a PR opens but does not merge, check that first.
- **Runtime downloads are not pinned or checksum-verified by us** (WoWDBDefs, `listfile.csv`, TACT keys, all fetched by db2tool; also wago.tools' build list and the Raidbots cache). A compromised or changed source would flow into `data/`. Mitigations today: the review of every PR's counts and diff, and the schema guard. Possible hardening: vendor/pin the `.dbd` files by commit.
- Re-ingesting the *same* version is a no-op, so a scan taken before the client has finished pulling hotfixes cannot be "topped up" without `--force`.
