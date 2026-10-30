# forever-db – agent guide

Dataset (and, later, browser) of every spell, item and piece of gear in WoW **Forever** (`wowf`), with the build each entry last changed in. This file is the entry point for humans and agents; read the linked docs before changing data or the pipeline.

## What lives where

| Path | What |
|---|---|
| `data/spells.jsonl`, `data/items.jsonl` | Current record per entity, one JSON object per line, sorted by `id`. **Generated – never hand-edit.** |
| `data/history/*.jsonl` | Per-entity change events (field-level old→new). Generated. |
| `data/stat-names.json` | ITEM_MOD id → name for `computed.stats`. Generated. |
| `data/state.json` | Last ingested build + hotfix push, hotfix-cache hash, per-table column layout, locked-row counts, per-ingest log. Generated. |
| `pipeline/build_data.py` | Reads a db2tool SQLite dump, joins tables into records, diffs against `data/`, writes `data/`. Python stdlib only. |
| `pipeline/tooltips.py` | Renders spell description templates, or refuses (`docs/tooltips.md`). |
| `pipeline/builds.py` | `check` (is there a new build/hotfix?) and `list` (historical builds + CDN config hashes from wago.tools). |
| `pipeline/spikes/` | Throwaway prototypes (not production code), each pointing at the doc that explains it. |
| `pipeline/tests/` | Unit tests on synthetic dumps and stubbed network, plus a golden set of real items (`golden_items.json`, regenerated with `make_golden.py`). |
| `scan/settings.template.json` | The pinned list of DB2 tables we extract. We own this list (not wowsims). |
| `scan/gametables/` | Vendored `ShieldBlockRegular.txt` (not in the game files); see its README. |
| `scan/forever-ref.txt`, `scan/patches/` | Pinned wowsims/forever commit, and our small patch to db2tool (historical-build pinning). |
| `scripts/scan.sh` | End to end: run `db2tool` → ingest. Modes: local install, `--cdn` (live), `--pin` (historical). |
| `scripts/backfill.sh` | Destructive: rebuild `data/` from historical builds + live. |
| `.github/workflows/` | `test.yml` (unit tests), `update-data.yml` (scheduled scan → PR). |
| `docs/` | Data model, update runbook, known limitations. |

Extraction itself is done by `tools/db2tool` from [wowsims/forever](https://github.com/wowsims/forever) (MIT). We do not vendor it; `FOREVER_REPO` points at a checkout.

## Commands

```sh
python3 -m unittest discover -s pipeline/tests          # run before any pipeline change
python3 pipeline/builds.py check                        # does data/ lag the live build / hotfix cache?
FOREVER_REPO=~/dev/forever scripts/scan.sh --cdn        # scan the live build (CDN + Raidbots hotfixes) and ingest
FOREVER_REPO=~/dev/forever scripts/scan.sh              # scan the local install instead (its hotfix cache lags)
FOREVER_REPO=~/dev/forever scripts/backfill.sh          # DELETES data/, rebuilds history
python3 pipeline/build_data.py ingest --db X --dry-run  # preview what would change
```

## Rules that keep the data trustworthy

1. **`data/` is append-only history.** Only `build_data.py ingest` writes it. Never edit it by hand, and never `--force` an ingest to "fix" data without recording why in `docs/known-limitations.md`.
2. **A "version" is `(build, hotfix push)`**, e.g. build 70685 + push 113511. Hotfixes change live data without a new build, so build number alone is not enough. Ordering is by `(build, push)`. **Push 0 means base data with no hotfix overlay** (historical builds); it sorts before the same build with hotfixes.
3. **Records must be a pure function of the db2tool dump.** No side files, no network, no clock. (A past mistake: resolving icon names from `listfile.csv` made every icon "change" when the file was omitted. Resolve presentation data at site-build time, not in records.)
4. **Absent field = default** (0, `""`, all-zero array). Records omit default values; in diffs `null` means "was/is default". Don't treat it as "missing data".
5. **Schema changes are guarded.** If a table's columns differ from the last ingest (new WoWDBDefs, new client layout) the ingest aborts, because renamed columns would show up as bogus changes. Follow "Schema changes" in `docs/update-runbook.md`.
6. **Sanity-check every ingest.** Compare the counts printed by ingest to the previous build (`data/state.json` → `builds`). A swing of more than a few percent in `added`/`changed`/`removed` usually means a tool or schema problem, not a game update. Investigate before committing.
7. **Locked rows are unknown, not absent.** Encrypted DB2 sections whose TACT key is unknown are skipped. db2tool prints them (`X: N rows locked by TACT key …`); `scan.sh` saves them in `state.json` → `scan.lockedRows`. Don't report those entities as removed/missing.
8. **Commit what you scan with `--cdn`, not the local install.** The local `DBCache.bin` lags Raidbots' mirror. Never mix: an ingest that silently loses its hotfix overlay would record every hotfixed entity as changed (the ingest refuses this).
9. **Pin, don't float, the extraction tool.** `scan/forever-ref.txt` fixes the wowsims/forever commit. Bump it deliberately and review the first ingest after.
10. **Keep dependencies on the latest stable release, explicitly pinned** (policy, versions and the upgrade routine are in `docs/update-runbook.md` → Dependencies). GitHub Actions are pinned by commit SHA; do not use floating tags like `@v4` or `latest`.
11. **Item stats are derived, equip-effect stats are not merged.** `computed` comes from the budget tables; effects stay in `effects`. If you change the formula, the golden test must still pass and `data/` must be rebuilt (`scripts/backfill.sh`). Read `docs/item-stats-spike.md` first.
12. **Rendered text never contains a guessed number.** `pipeline/tooltips.py` renders a template only if every token is exact; otherwise the text is `null`. Do not "fix" a refusal by guessing; add an exact rule with a test and the gamedata check (`docs/tooltips.md`).
13. Update `docs/known-limitations.md` whenever you find a data quirk. Keep docs in step with code in the same commit.

## Conventions

- Python 3, stdlib only, no new dependencies without discussion. Match the surrounding style; keep comments to the non-obvious "why".
- JSONL: `sort_keys`, compact separators, one entity per line (keeps git diffs line-level and small). Files are deliberately uncompressed.
- IDs are the game's own: spell ID = `Spell.ID`; item ID = `ItemSparse.ID`.
- Do not commit `.scan/` (raw SQLite, tool logs).
- Documentation is part of the change: when behaviour, data shape, a source or a decision changes, update the matching doc in the same commit (`data-model.md` for the output, `update-runbook.md` for procedures, `known-limitations.md` for quirks and open questions, this file for rules). Record *why* decisions were made, not just what.

## Project status (keep current)

- Done: extraction via db2tool, normalized spells/items, field-level history, history for builds 70245 → 70685 (+ hotfix push 113511), update check, scheduled workflow (written, not yet run on GitHub).
- Done: spell tooltips rendered (83.3 % of templated texts, rest refused), spell `availability` tags, in-game checklist (`docs/verification-checklist.md`, not yet run by a person).
- Done: item stats computed in the pipeline (`computed`, validated against wowsims' output: 5,200/5,225 items, 801/801 weapons), history events carry `areas`, effects ordered by game slot.
- Next: confirm the first real auto-update PR (the pushed workflow predates the stats change, push first); run the in-game checklist; the browser UI (GitHub Pages). Open questions live in `docs/known-limitations.md`.
