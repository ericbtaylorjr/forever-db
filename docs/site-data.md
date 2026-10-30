# Site data

`pipeline/site_data.py` turns `data/` into the static JSON the website loads (`site/public/data/`, git-ignored, rebuilt on every deploy). It is a pure function of `data/`: same input, same bytes (tested).

| File | Content | Size (2026-10-30) |
|---|---|---|
| `meta.json` | `versions[]` (one per ingest, oldest first: `i`, build, push, label, counts, discovery totals, hotfix summary, locked rows, `unlocked`/`newlyLocked` keys), `statNames`, `latest` | 5 KB |
| `items.json`, `spells.json` | `cols` + `rows` (positional arrays), icon-name table, class/subclass names, spell tags | ~450 KB gzipped each |
| `items/<n>.json`, `spells/<n>.json` | 250 entities each: `d` data, `f` first seen, `l` last changed, `x` discovered at, `b` baseline, `h` history events, spells also `u`/`un` (items using it) | ≤ 30 KB gzipped |
| `builds/<i>.json` | what changed in version `i`: per entity `{k: "i"|"s", id, t: type, a: areas, d: discovery, n: number of changed fields, c: [[path, old, new] x 8]}`, plus `locked`, `unlocked`, `newlyLocked` | up to 660 KB raw |

Versions are integers everywhere (index in `meta.versions`); `-1` = none. Row columns are named in `cols`, so the UI never depends on positions. Index rows carry what the filters need (quality, item level, class/subclass/slot, gear flag, armor, dps, stat values, set; school, cast time, duration, tags, text status), `enc` (1 = encrypted) and `test` (1 = the name looks like a test or placeholder item: `TEST_NAME` in `site_data.py`, a heuristic for the site's "hide test items" filter that never removes anything).

In a build file the changed fields in `c` are ordered by how informative they are to a reader, not alphabetically (`change_priority` in `site_data.py`: names, levels, stats, armor and weapon first; then rendered text; then cast time/duration/school; then effects; then other spell data; then raw description templates and database columns last), and only the first 8 are kept, so `c[0]` is the best one-line summary. `n` is the full count.

Build-file rows for `removed` events also carry the entity's last `nm` (name) and `ic` (icon name), since removed entities are not in the index. Areas that only restate another (`className`, `subclassName`, `qualityName`) are left out of the `a` lists.

Why shards: the index answers browsing and filtering without loading details; a detail page loads one shard. Adding fields to an index row is cheap; adding to `d` is free (it is just `data`).

`site/public/data/` is deliberately not committed (62 MB, derived). Run `python3 pipeline/site_data.py` before `npm run dev` in `site/`; the deploy workflow does it for you.
