# forever-db – agent guide

Dataset (and, later, browser) of every spell, item and piece of gear in WoW **Forever** (`wowf`), with the build each entry last changed in. This file is the entry point for humans and agents; read the linked docs before changing data or the pipeline.

## What lives where

| Path | What |
|---|---|
| `data/spells.jsonl`, `data/items.jsonl` | Current record per entity, one JSON object per line, sorted by `id`. **Generated – never hand-edit.** |
| `data/history/*.jsonl` | Per-entity change events (field-level old→new). Generated. |
| `data/state.json` | Last ingested build + hotfix push, per-table column layout, locked-row counts, ingest log. Generated. |
| `pipeline/build_data.py` | Reads a db2tool SQLite dump, joins tables into records, diffs against `data/`, writes `data/`. Python stdlib only. |
| `pipeline/tests/` | Unit tests on synthetic dumps. |
| `scan/settings.template.json` | The pinned list of DB2 tables we extract. We own this list (not wowsims). |
| `scripts/scan.sh` | End to end: run `db2tool` → ingest. |
| `docs/` | Data model, update runbook, known limitations. |

Extraction itself is done by `tools/db2tool` from [wowsims/forever](https://github.com/wowsims/forever) (MIT). We do not vendor it; `FOREVER_REPO` points at a checkout.

## Commands

```sh
python3 -m unittest discover -s pipeline/tests          # run before any pipeline change
FOREVER_REPO=~/dev/forever scripts/scan.sh              # scan local install and ingest
FOREVER_REPO=~/dev/forever scripts/scan.sh --cdn        # scan the live build from the CDN
python3 pipeline/build_data.py ingest --db X --dry-run  # preview what would change
```

## Rules that keep the data trustworthy

1. **`data/` is append-only history.** Only `build_data.py ingest` writes it. Never edit it by hand, and never `--force` an ingest to "fix" data without recording why in `docs/known-limitations.md`.
2. **A "version" is `(build, hotfix push)`**, e.g. build 70685 + push 113441. Hotfixes change live data without a new build, so build number alone is not enough. Ordering is by `(build, push)`.
3. **Records must be a pure function of the db2tool dump.** No side files, no network, no clock. (A past mistake: resolving icon names from `listfile.csv` made every icon "change" when the file was omitted. Resolve presentation data at site-build time, not in records.)
4. **Absent field = default** (0, `""`, all-zero array). Records omit default values; in diffs `null` means "was/is default". Don't treat it as "missing data".
5. **Schema changes are guarded.** If a table's columns differ from the last ingest (new WoWDBDefs, new client layout) the ingest aborts, because renamed columns would show up as bogus changes. Follow "Schema changes" in `docs/update-runbook.md`.
6. **Sanity-check every ingest.** Compare the counts printed by ingest to the previous build (`data/state.json` → `builds`). A swing of more than a few percent in `added`/`changed`/`removed` usually means a tool or schema problem, not a game update. Investigate before committing.
7. **Locked rows are unknown, not absent.** Encrypted DB2 sections whose TACT key is unknown are skipped. db2tool prints them (`X: N rows locked by TACT key …`); `scan.sh` saves them in `state.json` → `scan.lockedRows`. Don't report those entities as removed/missing.
8. Update `docs/known-limitations.md` whenever you find a data quirk. Keep docs in step with code in the same commit.

## Conventions

- Python 3, stdlib only, no new dependencies without discussion. Match the surrounding style; keep comments to the non-obvious "why".
- JSONL: `sort_keys`, compact separators, one entity per line (keeps git diffs line-level and small). Files are deliberately uncompressed.
- IDs are the game's own: spell ID = `Spell.ID`; item ID = `ItemSparse.ID`.
- Do not commit `.scan/` (raw SQLite, tool logs).
