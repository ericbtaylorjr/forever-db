# Vendored GameTables

`ShieldBlockRegular.txt` is a copy of `tools/database/dbc/GameTables/ShieldBlockRegular.txt` from
[wowsims/forever](https://github.com/wowsims/forever) (MIT) at the commit in `../forever-ref.txt`.

**Why a copy.** The shield block value per item level and quality comes from this table. In the game it
lives at `gametablesserver/ShieldBlockRegular.txt` (FileDataID 2200976), a *server-side* file: the Forever client
does not ship it, so no CDN scan can extract it (db2tool reports `fdid 2200976 not found in root`). wowsims keeps
a copy; we use theirs.

**Consequences.**
- A game change to block values will **not** show up in our history until wowsims updates their copy and we
  re-vendor it. Block value is the only computed stat that depends on this file.
- `scripts/scan.sh` compares this file with the one in the pinned wowsims checkout and stops if they differ, so
  bumping `forever-ref.txt` cannot silently change block values. To accept the new table:
  `cp $FOREVER_REPO/tools/database/dbc/GameTables/ShieldBlockRegular.txt scan/gametables/`, then rebuild the
  affected items (re-ingest with `--force`, or `scripts/backfill.sh`) and commit.
