import { describe, expect, it } from 'vitest';
import { itemFilter, sortRows, spellFilter } from './filters.ts';
import type { ItemRow, SpellIndex, SpellRow } from './data.ts';

const item = (o: Partial<ItemRow>): ItemRow => ({
  id: 1, name: 'Sword', test: false, enc: false, quality: 2, ilvl: 10, reqLvl: 5, cls: 2, sub: 7, inv: 13, gear: true, icon: 0,
  first: 0, changed: 0, disc: 0, base: true, armor: 0, dps: 0, stats: null, set: 0, shard: 0, ...o,
});
const p = (q: string) => new URLSearchParams(q);

describe('item filters', () => {
  const rows = [
    item({ id: 1, name: 'Plain Sword' }),
    item({ id: 2, name: 'Hidden', enc: true, quality: null, ilvl: null, reqLvl: null }),
    item({ id: 3, name: 'Stamina Helm', quality: 4, inv: 1, stats: { '7': 30, '3': 5 }, armor: 120 }),
    item({ id: 4, name: 'Newly Found', first: 2, disc: 3, changed: 3, base: false }),
    // present (encrypted) from the first version, revealed in version 3: an exact discovery date
    item({ id: 5, name: 'Revealed Later', first: 0, disc: 3, changed: 3, base: true }),
  ];
  const run = (q: string) => rows.filter(itemFilter(p(q))).map((r) => r.id);

  it('shows discovered and encrypted separately', () => {
    expect(run('view=encrypted')).toEqual([2]);
    expect(run('view=discovered')).toEqual([1, 3, 4, 5]);
    expect(run('')).toEqual([1, 2, 3, 4, 5]);
  });
  it('can hide test and placeholder items', () => {
    const withTest = [...rows, item({ id: 9, name: '1500 Test sword', test: true })];
    expect(withTest.filter(itemFilter(p('hideTest=1'))).map((r) => r.id)).toEqual([1, 2, 3, 4, 5]);
    expect(withTest.filter(itemFilter(p(''))).map((r) => r.id)).toEqual([1, 2, 3, 4, 5, 9]);
  });
  it('matches name text or an exact id', () => {
    expect(run('q=helm')).toEqual([3]);
    expect(run('q=4')).toEqual([4]);
  });
  it('filters by quality, slot, stat minimum and armor', () => {
    expect(run('quality=4')).toEqual([3]);
    expect(run('inv=1')).toEqual([3]);
    expect(run('stat=7&statMin=25')).toEqual([3]);
    expect(run('stat=7&statMin=40')).toEqual([]);
    expect(run('armorMin=100')).toEqual([3]);
  });
  it('skips entities that were already discovered at the first version, but not ones revealed later', () => {
    expect(run('discSince=1')).toEqual([4, 5]);   // 5 was encrypted at version 0 and discovered at 3
    expect(run('discSince=0')).toEqual([4, 5]);   // version 0 itself is "unknown", never a real discovery
    expect(run('addedSince=1')).toEqual([4]);     // 5 was *added* at version 0
    expect(run('since=3')).toEqual([4, 5]);
  });
});

describe('spell filters', () => {
  const index: SpellIndex = { rows: [], byId: new Map(), icons: [], tags: ['class:Mage', 'item'] };
  const spell = (o: Partial<SpellRow>): SpellRow => ({
    id: 1, name: 'Fireball', test: false, enc: false, school: 4, castMs: 3000, durMs: 8000, icon: 0, tags: [0], first: 0, changed: 0, disc: 0,
    base: true, text: 1, shard: 0, ...o,
  });
  const rows = [spell({}), spell({ id: 2, name: 'Blink', school: 64, castMs: 0, durMs: null, tags: [1] }), spell({ id: 3, name: '', enc: true, tags: [0], text: 0 })];
  const run = (q: string) => rows.filter(spellFilter(p(q), index)).map((r) => r.id);

  it('filters by class tag, school, cast type and encryption', () => {
    expect(run('tag=class:Mage')).toEqual([1, 3]);
    expect(run('school=64')).toEqual([2]);
    expect(run('cast=instant')).toEqual([2]);
    expect(run('view=encrypted')).toEqual([3]);
    expect(run('tag=class:Mage&view=discovered')).toEqual([1]);
  });
});

describe('sortRows', () => {
  const rows = [item({ id: 1, name: 'b' }), item({ id: 2, name: '' }), item({ id: 3, name: 'a' })];
  it('sorts by name with nameless (encrypted) rows last in both directions', () => {
    expect(sortRows(rows, 'name', 'asc').map((r) => r.id)).toEqual([3, 1, 2]);
    expect(sortRows(rows, 'name', 'desc').map((r) => r.id)).toEqual([1, 3, 2]);
  });
  it('sorts numeric columns, ties by id', () => {
    const r = [item({ id: 5, ilvl: 10 }), item({ id: 4, ilvl: 10 }), item({ id: 6, ilvl: 20 })];
    expect(sortRows(r, 'ilvl', 'desc').map((x) => x.id)).toEqual([6, 4, 5]);
  });
});
