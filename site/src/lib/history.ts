import type { EntityRecord, HistoryEvent } from './data.ts';

/**
 * Version reconstruction. The data stores each entity as it is *now* plus, per version, the fields that changed
 * (`[old, new]` by flattened path). To see an entity as it was, flatten the current record and undo the newer events.
 * Working on flattened paths (not nested objects) avoids rebuilding shapes: a list element that appeared later simply
 * has no path in the older version.
 *
 * `flatten` mirrors pipeline/build_data.py `flatten`, so paths in events and in the flat map agree. Null and
 * "absent" are the same thing throughout (the pipeline records a default/absent value as null).
 */

export type Flat = Map<string, unknown>;

export function flatten(value: unknown, prefix = '', out: Flat = new Map()): Flat {
  if (Array.isArray(value) && value.length > 0 && value.every((x) => typeof x === 'object' && x !== null)) {
    value.forEach((x, i) => flatten(x, `${prefix}[${i}]`, out));
  } else if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    for (const k of Object.keys(value as object).sort()) flatten((value as Record<string, unknown>)[k], prefix ? `${prefix}.${k}` : k, out);
  } else {
    out.set(prefix, value);
  }
  return out;
}

const isNil = (v: unknown) => v === null || v === undefined;

/** Whether the entity existed at version `target`: seen by then, and not removed (and not re-added) by then. */
export function existsAt(rec: EntityRecord, target: number): boolean {
  if (target < rec.f) return false;
  let exists = true;
  for (const ev of [...rec.h].sort((a, b) => a.v - b.v)) {
    if (ev.v > target) break;
    if (ev.t === 'removed') exists = false;
    else if (ev.t === 'added') exists = true;
  }
  return exists;
}

/** The entity's flattened data as of version `target`, or null if it did not exist then. */
export function flatAt(rec: EntityRecord, target: number): Flat | null {
  if (!existsAt(rec, target)) return null;
  const flat = flatten(rec.d);
  const newer = rec.h.filter((e) => e.v > target).sort((a, b) => b.v - a.v);
  for (const ev of newer) {
    for (const [path, [old]] of Object.entries(ev.c ?? {})) {
      if (isNil(old)) flat.delete(path);
      else flat.set(path, old);
    }
  }
  return flat;
}

export interface FieldDiff {
  path: string;
  a: unknown;
  b: unknown;
  /** which top-level section of the record the field belongs to, e.g. "computed", "effects", "sparse" */
  area: string;
}

export const areaOf = (path: string): string => path.split(/[.[]/, 1)[0];

/** Fields that differ between two flattened versions (null and absent are equal), sorted by path. */
export function diffFlat(a: Flat, b: Flat): FieldDiff[] {
  const out: FieldDiff[] = [];
  for (const path of new Set([...a.keys(), ...b.keys()])) {
    const x = a.get(path) ?? null;
    const y = b.get(path) ?? null;
    if (JSON.stringify(x) !== JSON.stringify(y)) out.push({ path, a: x, b: y, area: areaOf(path) });
  }
  return out.sort((p, q) => (p.path < q.path ? -1 : p.path > q.path ? 1 : 0));
}

/** Versions at which this entity changed, newest first, for a timeline. */
export const timeline = (events: HistoryEvent[]): HistoryEvent[] => [...events].sort((a, b) => b.v - a.v);
