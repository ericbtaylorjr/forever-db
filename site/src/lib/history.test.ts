import { describe, expect, it } from 'vitest';
import { diffFlat, flatAt, flatten } from './history.ts';
import type { EntityRecord } from './data.ts';

// A spell as it is now (version 3) with three recorded events, mirroring what pipeline/build_data.py writes.
const record: EntityRecord = {
  d: {
    discovery: 'discovered',
    name: 'Fireball',
    description: 'New text',
    related: { SpellEffect: [{ EffectBasePointsF: 99, Effect: 2 }, { Effect: 6 }] },
    computed: { availability: ['class:Mage'] },
  },
  f: 0,
  l: 3,
  x: 2,
  b: 1,
  h: [
    { v: 1, t: 'changed', a: ['description'], c: { description: ['Old text', 'Middle text'] } },
    { v: 2, t: 'discovered', a: ['discovery', 'name'], c: { discovery: ['encrypted', 'discovered'], name: [null, 'Fireball'] } },
    {
      v: 3,
      t: 'changed',
      a: ['description', 'related'],
      c: { description: ['Middle text', 'New text'], 'related.SpellEffect[1].Effect': [null, 6], 'related.SpellEffect[0].EffectBasePointsF': [50, 99] },
    },
  ],
};

describe('flatten', () => {
  it('follows the pipeline: dicts recurse, lists of objects are indexed, lists of scalars are leaves', () => {
    const flat = flatten({ a: { b: 1 }, list: [{ x: 1 }, { x: 2 }], tags: ['p', 'q'], none: null, empty: [] });
    expect(Object.fromEntries(flat)).toEqual({ 'a.b': 1, 'list[0].x': 1, 'list[1].x': 2, tags: ['p', 'q'], none: null, empty: [] });
  });
});

describe('flatAt', () => {
  it('is the current data at the latest version', () => {
    expect(flatAt(record, 3)?.get('description')).toBe('New text');
  });

  it('undoes newer events one by one', () => {
    expect(flatAt(record, 2)?.get('description')).toBe('Middle text');
    expect(flatAt(record, 0)?.get('description')).toBe('Old text');
    expect(flatAt(record, 2)?.get('related.SpellEffect[0].EffectBasePointsF')).toBe(50);
  });

  it('treats a field that appeared later as absent earlier (null old value)', () => {
    expect(flatAt(record, 1)?.has('name')).toBe(false);
    expect(flatAt(record, 1)?.get('discovery')).toBe('encrypted');
    expect(flatAt(record, 2)?.has('related.SpellEffect[1].Effect')).toBe(false);
    expect(flatAt(record, 3)?.get('related.SpellEffect[1].Effect')).toBe(6);
  });

  it('returns null before the entity existed', () => {
    expect(flatAt({ ...record, f: 2, b: 0 }, 1)).toBeNull();
  });

  it('returns null while the entity was removed, and its last data again if it was re-added', () => {
    const gone: EntityRecord = { ...record, h: [...record.h, { v: 4, t: 'removed' }] };
    expect(flatAt(gone, 3)).not.toBeNull();
    expect(flatAt(gone, 4)).toBeNull();
    expect(flatAt(gone, 5)).toBeNull();
    const back: EntityRecord = { ...gone, h: [...gone.h, { v: 6, t: 'added' }] };
    expect(flatAt(back, 5)).toBeNull();
    expect(flatAt(back, 6)?.get('name')).toBe('Fireball');
  });
});

describe('diffFlat', () => {
  it('reports only the fields that differ, with their area, and treats null as absent', () => {
    const diff = diffFlat(flatAt(record, 1)!, flatAt(record, 3)!);
    expect(diff.map((d) => [d.path, d.area])).toEqual([
      ['description', 'description'],
      ['discovery', 'discovery'],
      ['name', 'name'],
      ['related.SpellEffect[0].EffectBasePointsF', 'related'],
      ['related.SpellEffect[1].Effect', 'related'],
    ]);
    expect(diffFlat(flatAt(record, 3)!, flatAt(record, 3)!)).toEqual([]);
  });
});
