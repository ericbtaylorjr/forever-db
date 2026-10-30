# Update runbook

How `data/` is kept current, by automation or by hand. Written to be followed by a person or an agent.

## How updates reach `data/`

```
every 3 h (GitHub Action)            you, manually
        │                                  │
 builds.py check ── nothing new → stop     │
        │ new build or hotfix push         │
        ▼                                  ▼
 scripts/scan.sh --cdn  ───────►  scripts/scan.sh (local)  / --cdn
   db2tool → .scan/scan.db → build_data.py ingest → data/ → PR
```

- **What counts as "new":** the US version service reports a different `wowf` build than `data/state.json`, **or** Raidbots' mirror of the live `DBCache.bin` has a different SHA-256 than the one stored at the last ingest (new hotfix push). See `pipeline/builds.py check`.
- **Missed a build?** The check compares with the *latest* state, so a delayed run still picks up the newest build and ingests it; changes from skipped intermediate builds are folded into that one version (history can't be inserted out of order). Running every 3 h keeps this rare. Manual trigger: Actions → *Update data* → *Run workflow* (tick *force* to scan even when nothing looks new).
- **Routine PRs merge themselves** (squash, auto-merge; this needs *Allow auto-merge* enabled in the repo settings, otherwise the PR just waits for you to merge it). If the ingest is flagged (see below) the PR is labelled `needs-review` and waits for a person.

## Sources and why they matter

| Source | Used for | Notes |
|---|---|---|
| Local install (`scan.sh`, no flags) | Quick manual scan | Uses *your* client's `DBCache.bin`, which lags behind: on 2026-10-30 it was at hotfix push 113441 while Raidbots had 113511. Prefer `--cdn` for anything you commit. |
| CDN + Raidbots cache (`scan.sh --cdn`) | CI and normal updates | Build from Blizzard's CDN, hotfixes from `https://storage.googleapis.com/raidbots-static/wow/forever/enUS/DBCache.bin`, applied with `--carry-hotfixes` so a cache one build behind still applies. |
| CDN pinned (`scan.sh --pin VER:BUILDCFG:CDNCFG`) | History backfill | Needs a small patch to db2tool (`scan/patches/db2tool-cdn-pin.patch`, applied automatically). Base data only: Raidbots only has the *current* cache. |

`db2tool` comes from [wowsims/forever](https://github.com/wowsims/forever), pinned by commit in `scan/forever-ref.txt`. Bumping it can change output (new tables, new schema definitions), so bump deliberately: update the file, run `scan.sh --cdn`, and look at the ingest summary.

## Manual update

```sh
export FOREVER_REPO=~/dev/forever            # checkout of wowsims/forever at scan/forever-ref.txt
python3 pipeline/builds.py check             # is there anything new?
scripts/scan.sh --cdn                        # scan + ingest; writes .scan/summary.md
python3 -m unittest discover -s pipeline/tests
git checkout -b data/<version>-push<push> && git add data && git commit -m "data: <version> push <push>"
```

Setup: Go ≥ 1.25 and Python ≥ 3.10 (stdlib only). `scan.sh` needs network for the CDN, WoWDBDefs, the community listfile and TACT key list (db2tool downloads those into its checkout).

`scan.sh` with no flags scans the local install (`WOW_DIR`, default `/mnt/c/Program Files (x86)/World of Warcraft`; the CASC archive and `.build.info` sit one level above `_forever_/`, shared with other clients). Use it when debugging or when the CDN is unreachable.

## Verifying an ingest

The ingest prints and saves (`.scan/summary.md`) added/changed/removed/unchanged per kind and, automatically, flags it **Needs review** when more than 10 % of entities changed or 2 % were removed. That threshold is a tripwire for tool/schema problems, not a statement about normal updates. Typical real updates in the history so far: tens to a few hundred changed entities, and a few hundred new items/spells when a hotfix adds content.

Also check:
1. `Hotfixes: build N up to push P` – not `none applied`. (The ingest refuses a no-hotfix scan after a hotfixed one unless `--allow-no-hotfixes`.)
2. `git diff --stat data/` is small and `git diff data/history` reads like patch notes.
3. Spot check 2–3 changed entries against the game.
4. `state.json` → `scan.lockedRows`: a growing count means new encrypted content whose TACT key isn't public yet; those entities are hidden, not removed (AGENTS.md rule 7).

Commit message: `data: <version> push <push>` plus the counts.

## Schema changes

The ingest aborts with `Table layouts changed since the last ingest` when any extracted table's columns differ from `state.json` → `schema`. Causes: a client patch changed a DB2 layout, WoWDBDefs gained real names for formerly anonymous columns (`Field_5_5_4_…`), or the pinned wowsims commit changed.

1. Compare the listed tables with `state.json` → `schema` to see which columns moved.
2. Purely cosmetic renames: re-run with `INGEST_ARGS=--allow-schema-change`; expect one-off "changes" on the renamed paths for every entity of that table. Say so in the commit message and note it in `known-limitations.md` so nobody reads them as game changes.
3. New columns with real information: make sure `data-model.md` still describes the output; add tests if the pipeline needs special handling.

## Backfilling history

`scripts/backfill.sh` **deletes `data/`** and rebuilds it: every build in wago.tools' list up to the live one (oldest first, base data, push 0), then the live build with hotfixes. Use it to (re)create history, e.g. after a pipeline change that alters record contents. `pipeline/builds.py list` shows what it will use.

Limits (also in `known-limitations.md`): wago.tools' list is the only source of old config hashes and does not have every build (wowsims/gamedata knows of builds that wago lacks); Blizzard prunes old builds from the CDN, so far every listed one still works; historical builds have no hotfix overlay.

Rewriting `data/` this way changes every entity's `firstSeen`/`lastChanged` bookkeeping; commit it as a single `data: rebuild history` commit.

## Dependencies and versions

Policy: run the latest stable release of everything we depend on, and make the choice explicit so a floating "latest" can't change results silently. Checked 2026-10-30:

| Dependency | Version | Notes |
|---|---|---|
| GitHub Actions `checkout`, `setup-python`, `setup-go` | v7.0.1, v7.1.0, v7.0.0 | Pinned by **commit SHA** (a moved tag can't inject code) with the version in a comment. They run on Node 24; the earlier "Node.js 20 is deprecated" warning came from `checkout@v4`. Dependabot (`.github/dependabot.yml`) opens weekly PRs to bump them. |
| Go (CI) | 1.27.3 | The forever repo's `go.mod` says 1.25.0/1.25.4; **Go 1.25 has been end of life since 2026-08-19** (no security fixes), so CI uses a newer toolchain. Verified: db2tool under 1.25.4 and 1.27.3 gives identical data in all 89 tables. |
| Python (CI) | 3.15 | The pipeline is stdlib only. Local development used 3.14; the unit tests must pass on both. |
| wowsims/forever (db2tool) | `scan/forever-ref.txt` | Pinned to a commit; bumped to upstream `master` on 2026-10-30 (no db2tool changes since the previous pin; our patch applies). |
| Runner image | `ubuntu-latest` | GitHub is moving this to Ubuntu 26. |
| Node | not used | There is no Node code yet. When the browser UI lands, use the current LTS (26.x as of this writing) and record it in `.nvmrc`/`engines`. |

Not pinned by us (fetched by db2tool at run time, so they can change between scans): WoWDBDefs `.dbd` files, the community `listfile.csv`, the community TACT key list. See `known-limitations.md`.

**Upgrade routine** (monthly, or when Dependabot/an advisory says so): bump the version, run the scan under old and new and compare the SQLite tables (they must match, as done for Go above), run the tests, then update this table and the date.

## When it breaks

- *`rows locked by TACT key`* – normal (see above).
- *Missing table / decode error after a game patch* – WoWDBDefs may lack the new layout; check which `.dbd` db2tool picked (output names it). Try bumping `scan/forever-ref.txt` to a newer wowsims commit.
- *Counts swing wildly or ingest flagged* – a table failed to decode and dependent entities lost data. Do **not** merge; fix the source first, then re-run.
- *`--cdn` scan has no hotfixes* – the Raidbots mirror is unreachable or empty; the ingest will refuse. Retry later; do not force.
- *Bad data already merged* – revert the commit that wrote it and re-ingest. Never edit `data/` by hand.
- *Workflow itself* – `.github/workflows/update-data.yml` has not run on GitHub yet (its steps were exercised locally; the `Test` workflow has run on GitHub). First thing to check after enabling it: Actions → *Update data* → *Run workflow*.
