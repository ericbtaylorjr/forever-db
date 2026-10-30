# In-game verification checklist

Generated from `data/` at build 1.60.1.70685, hotfix push 113511. It is a **manual** check: nothing here has been compared with the live game yet. Everything below is what *our data says*; the point is to find where the game disagrees.

## How to check

- **Items:** hover the item (find it with `/run print(select(2, GetItemInfo(ID)))` or any item-link tool). Compare armor, damage range and speed, and every `+N stat` line. `Equip:`/`Use:` lines are not part of the expected values (they live in `effects`).
- **Spells:** open the spell in the spellbook, or `/run GameTooltip:SetOwner(UIParent,'ANCHOR_CURSOR'); GameTooltip:SetSpellByID(ID)`. Our text is the *database view*: amounts at character level 60 **without spell power or attack power**. Check on a character without power gear, or expect game damage/healing to be higher by your power times the spell's coefficient.
- Report differences as: ID, what we show, what the game shows. Where our text is `refused` we deliberately show nothing; wording differences are fine, **number differences are what matter**.

## Items

| ID | Name | Type | ilvl | Our armor / damage / stats |
|---|---|---|---|---|
| 22884 (cloth robe, rare) | Legionnaire's Dreadweave Tunic | Rare Cloth | 68 | 96 Armor; +25 Spell power (damage and healing); +20 Intellect; +20 Stamina |
| 272783 (plate head, epic) | Premier Field Marshal's Chevalier Faceguard | Epic Plate | 65 | 599 Armor; +14 Crit rating; +12 Strength; +14 Spell power (damage and healing); +8 Intellect; +34 Stamina |
| 277257 (shield, rare) | Raven Hill Crest | Rare Shield | 29 | 642 Armor; +5 Health per 5 sec; +13 Block value; +76 Bonus armor |
| 272591 (shield, epic) | Premier High Warlord's Shield Wall | Epic Shield | 65 | 2468 Armor; +9 Strength; +58 Block value; +21 Stamina |
| 22817 (two-hand weapon, epic) | Naxxramas Polearm [PH] | Epic Polearm | 77 | 225 - 338 Damage, Speed 3.70, 76.1 dps; +41 Agility; +31 Stamina |
| 7943 (one-hand weapon, uncommon) | Wicked Mithril Blade | Uncommon Sword | 45 | 46 - 87 Damage, Speed 2.50, 26.6 dps; +4 Agility; +6 Strength |
| 19559 (bow, rare) | Outrider's Bow | Rare Bow | 53 | 46 - 86 Damage, Speed 2.40, 27.5 dps; +3 Agility; +8 Stamina |
| 279246 (wand, rare) | Torch of Light | Epic Wand | 65 | 91 - 170 Damage, Speed 1.70, 76.8 dps; +17 Healing power; +6 Spell damage; +11 Spirit |
| 22707 (ring, epic) | Ramaladni's Icy Grasp | Epic Miscellaneous | 80 | +25 Frost resistance; +15 Stamina |
| 2463 (white chest armor) | Studded Doublet | Common Leather | 37 | 100 Armor |
| 16459 (bonus armor) | Marshal's Dragonhide Boots | Epic Leather | 71 | 146 Armor; +11 Agility; +18 Strength; +16 Spell power (damage and healing); +10 Intellect; +30 Bonus armor; +10 Spirit; +14 Stamina |
| 221518 (caster weapon, spell power) | Whisper | Rare Mace | 53 | 124 - 187 Damage, Speed 3.40, 45.7 dps; +7 Crit rating; +23 Strength; +14 Spell power (damage and healing) |
| 17612 (outside wowsims' list) | Legionnaire's Satin Vestments | Rare Cloth | 63 | 89 Armor; +16 Spell power (damage and healing); +20 Intellect; +20 Stamina |
| 8198 (bonus armor) | Turtle Scale Bracers | Uncommon Mail | 42 | 104 Armor; +6 Spell power (damage and healing); +5 Intellect; +100 Bonus armor; +5 Stamina |

## Spells

| ID | Name | Why | Our rendered text |
|---|---|---|---|
| 970 | Shadow Word: Pain | damage over time: `$o1`, `$d`, `$t1` | A word of darkness that causes 108 Shadow damage over 18 sec. |
| 133 | Fireball | Fireball: description refused on purpose, aura text rendered | (description refused: ['$s1']) aura: 1 Fire damage every 2 seconds. |
| 12312 | Improved Shield Wall | talent: `${$m1/-60000}.1` decimals | Reduces the cooldown of your Shield Wall ability by 11.0 min. |
| 11113 | Blast Wave | roll range `$m1`/`$M1` and radius | A wave of flame radiates outward from the caster, damaging all enemies caught within the blast for 169 Fire damage, and Dazing them for 50% reduced movement speed for 6 sec. |
| 25315 | Renew | random class spell | Heals the target of 830 damage over 15 sec. |
| 9490 | Demoralizing Roar | random class spell | The druid roars, decreasing nearby enemies' melee attack power by 105.  Lasts 30 sec. |
| 410114 | Engrave Belt - Expose Weakness | random class spell | Engrave your belt with the Expose Weakness rune: ⏎  ⏎ {icon:409504} ⏎ Your melee and ranged criticals increase your attack power by 40% of your current Agility for 7 sec. |
| 11269 | Ambush | random class spell | Ambush the target, causing 250% weapon damage plus 290 to the target.  Must be stealthed and behind the target.  Requires a dagger in the main hand.  Awards 1 combo point. |
| 425273 | Renew | random class spell | Heals the target of 400 damage over 15 sec. |
| 403686 | Drain Life | random class spell | Transfers 29 health every second from the target to the caster.  Lasts 15 sec. |
