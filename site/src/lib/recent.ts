import type { BuildChange } from './data.ts';

export interface RecentChange {
  /** index of the version the change happened in */
  v: number;
  ch: BuildChange;
}

/**
 * The most recent real edit to each item or spell across a few builds, newest first. "Real edit" means a `changed`
 * event: an entry that was only added or only revealed (discovered) is not an update, and shows in the discovered list.
 * An entry edited in several of the builds appears once, at its latest version. Ties within a build go to the entry with
 * the most changed fields, then the lowest id, so the order is stable.
 */
export function recentUpdates(files: { v: number; changes: BuildChange[] }[], kind: 'i' | 's'): RecentChange[] {
  const latest = new Map<number, RecentChange>();
  for (const { v, changes } of [...files].sort((a, b) => b.v - a.v)) {
    for (const ch of changes) {
      if (ch.k === kind && ch.t === 'changed' && !latest.has(ch.id)) latest.set(ch.id, { v, ch });
    }
  }
  return [...latest.values()].sort((a, b) => b.v - a.v || (b.ch.n ?? 0) - (a.ch.n ?? 0) || a.ch.id - b.ch.id);
}
