import { describe, expect, it } from 'vitest';
import { recentUpdates } from './recent.ts';
import type { BuildChange } from './data.ts';

const ch = (k: 'i' | 's', id: number, t: BuildChange['t'], n?: number): BuildChange => ({ k, id, t, n });

describe('recentUpdates', () => {
  const files = [
    { v: 5, changes: [ch('i', 1, 'changed', 2), ch('i', 2, 'changed', 1), ch('s', 9, 'changed', 1)] },
    { v: 6, changes: [ch('i', 1, 'changed', 5), ch('i', 3, 'discovered', 20), ch('i', 4, 'added'), ch('i', 5, 'removed')] },
    { v: 7, changes: [ch('i', 6, 'changed', 1), ch('i', 7, 'changed', 4), ch('s', 8, 'changed', 3)] },
  ];

  it('lists only real edits, not discoveries, additions or removals', () => {
    expect(recentUpdates(files, 'i').map((r) => r.ch.id)).toEqual([7, 6, 1, 2]);
  });

  it('shows an entry edited in several builds once, at its latest version', () => {
    const one = recentUpdates(files, 'i').filter((r) => r.ch.id === 1);
    expect(one).toHaveLength(1);
    expect(one[0].v).toBe(6);
  });

  it('orders by version, then by number of changed fields', () => {
    expect(recentUpdates(files, 'i').slice(0, 2).map((r) => [r.v, r.ch.id])).toEqual([[7, 7], [7, 6]]);
  });

  it('keeps items and spells apart', () => {
    expect(recentUpdates(files, 's').map((r) => r.ch.id)).toEqual([8, 9]);
  });

  it('copes with no changes', () => {
    expect(recentUpdates([], 'i')).toEqual([]);
  });
});
