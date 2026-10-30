# Update runbook

How to refresh `data/` after the game updates. Intended to be followed by a person or by an agent.

## 0. One-time setup

- Go ≥ 1.25, Python ≥ 3.10 (stdlib only).
- `git clone https://github.com/wowsims/forever` somewhere; set `FOREVER_REPO` to it. Note its commit; `scan.sh` logs it.
- WSL: the default `WOW_DIR` is `/mnt/c/Program Files (x86)/World of Warcraft`. Override if different. `_forever_/` is the Forever client; the CASC archive and `.build.info` sit one level up and are shared with other clients.

## 1. Choose a source

| Mode | Command | When |
|---|---|---|
| Local install | `scripts/scan.sh` | Game is updated through the launcher on this machine. Uses your own `DBCache.bin` hotfixes (log in and idle first so the client has pulled the latest). |
| CDN | `scripts/scan.sh --cdn` | CI or a machine without the game. Hotfixes come from `--dbcache <file>` or db2tool's `caches/`; wowsims mirrors the live cache at `https://storage.googleapis.com/raidbots-static/wow/forever/enUS/DBCache.bin`. Without a cache for the build you get base data only. |

Local mode loads every `DBCache.bin` under the install (including `_retail_`, `_classic_beta_`); only the one matching the extracted build applies. Check the `Hotfixes:` line in the output says `build <N> up to push <P>`, not `none applied`.

## 2. Run

```sh
FOREVER_REPO=~/dev/forever scripts/scan.sh
```

This writes `.scan/scan.db` + `.scan/scan.log` and runs `pipeline/build_data.py ingest`. Same build + push as the last ingest is a no-op; older data is refused.

## 3. Verify before committing

1. Ingest prints `added / changed / removed / unchanged` per kind. Compare with the previous entries in `data/state.json` → `builds`. A normal hotfix touches tens to a few hundred entities. Thousands means something systemic (tool bug, schema, wrong source) – stop and investigate.
2. `git diff --stat data/` should be small. `git diff data/history` should read like patch notes.
3. Spot check 2–3 changed entries against the game or wowhead-style knowledge.
4. `lockedRows` in `state.json`: a growing count means new encrypted content whose TACT key isn't known yet. Re-scan later (keys are fetched from the community list, refreshed daily).
5. Run `python3 -m unittest discover -s pipeline/tests`.

Commit message: `data: 1.60.1.<build> push <push>` and paste the counts.

## Schema changes

The ingest aborts with `Table layouts changed since the last ingest` when a table's columns differ. Causes: a client patch changed a DB2 layout, WoWDBDefs gained names for formerly anonymous columns (`Field_5_5_4_…` → real name), or the wowsims tool changed.

1. Read the listed tables and compare with `data/state.json` → `schema` to see exactly which columns moved.
2. If purely cosmetic renames: re-run with `--allow-schema-change` and expect one-off "changes" on the renamed paths for every entity of that table. Note it in the commit message and in `known-limitations.md` so nobody reads them as game changes.
3. If new columns carry real information, check `data-model.md` still describes the output, and add tests if the pipeline needs to treat them specially.

## When it breaks

- *`rows locked by TACT key`* – normal; see above.
- *Build parse errors / missing table* – the wowsims tool may need a newer commit (`git pull` in `FOREVER_REPO`), or WoWDBDefs hasn't got the build's layout yet. Check the db2tool output for the `.dbd` it picked.
- *Counts drop sharply* – a table failed to decode and the spells/items depending on it lost data. Do **not** ingest; fix the source first. (The pipeline would record the loss as mass `changed`/`removed`.)
- *Need to correct bad data already ingested* – revert the commit that wrote it, then re-ingest. Don't edit `data/` by hand.

## Automating (planned)

A scheduled GitHub Action: check Blizzard's version service for the `wowf` build and the Raidbots hotfix cache every few hours (wowsims/gamedata does this every 3 h); on change, run the CDN scan, ingest, run tests, open a PR with the counts. Not built yet.
