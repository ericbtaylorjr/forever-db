# Discovery (encrypted content)

WoW Forever hides items and spells until someone discovers them in game; the community calls this "encrypted" content. This page says exactly what that looks like in the game files, how the dataset records it, and what we can and cannot tell.

**Status of this interpretation:** derived from the files and confirmed only by the pattern below plus the game's published design. It has not been checked against the live game (not live yet). If the design turns out to work differently, the labels change in one place (`discovery` below); the rest of the pipeline does not depend on it.

## What the files show

| Observation (build 1.60.1.70685, hotfix push 113511) | Meaning |
|---|---|
| 12,205 items have a row in the item list (`Item`: class, subclass, equip slot, icon) but **no `ItemSparse` row** (name, level, quality, stats, price...). | The item exists but its details are hidden. |
| 468 of the 478 items that hotfix push 113511 "added" were already in that state in the base build. The hotfix supplied their `ItemSparse` row. | That is a **discovery**: details revealed by a server push, not a new item. |
| 1,362 spells are named by other tables (class skill lines 1,076, talents 845, item effects 158, triggers 67...) but have **no `SpellName`/`Spell` row**. | Hidden spells, known only through what points at them. For class spells the skill line tells us which class. |
| db2tool reports "N rows locked by TACT key K": rows inside encrypted file sections whose key is not public yet (4,850 rows in 4 keys on push 113511). | A second layer: rows we cannot read at all, **not even their ids**. |

## What the dataset records

Every item and spell record has `data.discovery`:

- `"discovered"`: the game files give its name and details. For items: has an `ItemSparse` row. For spells: has a name.
- `"encrypted"`: known to exist, details hidden. **Items** keep what the item list exposes: class, subclass, equip slot (so `isGear` still works), icon, set membership, equip/use effects, bonus trees; `name`, `quality`, `itemLevel`, stats and `computed` are empty. **Spells** keep the tags that come from what references them (`computed.availability`, for example `class:Warlock`); everything else is empty.

Each entity also has `discoveredAt` (`{build, push}` or `null` while encrypted). For entities that were already discovered at the first build we have, `baseline` is true and `discoveredAt` reads "in or before that version".

History:

- A `discovered` event (instead of `changed`) is written when an entity goes from encrypted to discovered. Its `changes` carry the details that appeared (`discovery: ["encrypted", "discovered"]`, `name: [null, "..."]`, ...) and `areas` includes `discovery`.
- An entity that first appears already discovered gets an `added` event with `discovery: "discovered"`; one that first appears hidden gets `discovery: "encrypted"`.
- Per ingest, `state.json` → `builds[i].counts.<kind>.discovered` is the number of discoveries, and `builds[i].discovery.<kind>` is the running total of `discovered` and `encrypted` entities.

### Locked rows (the second layer)

`state.json` → `builds[i].locked` is `{table: {keyHash: rowCount}}` for rows no known key opens. They have no readable id, so they are **not entities**; they only exist as counts. When a key becomes known (the community key list or a server push), its rows are readable on the next scan and show up as ordinary entities (`added`, discovered or encrypted as above). The key vanishing from `locked` between two builds is how we tell "unlocked", and the site shows it on the build page.

## What we cannot tell

- **Which hidden entity is which locked row.** Counts only.
- **Why** an item is hidden: never discovered by anyone, vs. not yet released, vs. removed. All three look the same in the files.
- **When it was discovered**, other than "between two of our scans". The local timeline is our ingest versions, not wall-clock time.
- A hidden item or spell that nothing references (and has no `Item` row) is invisible to us.
- Some of the 12,205 hidden items may be legacy items the game will never reveal.

## Changing it

If the meaning of "encrypted" changes, edit `build_items`/`build_spells` (the `discovery` assignment) and rebuild with `scripts/backfill.sh`. The UI reads only `data.discovery`, `discoveredAt` and the `discovered` events.
