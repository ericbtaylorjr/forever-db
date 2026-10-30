import { config } from '../config.ts';

/** Shapes of the files written by pipeline/site_data.py (docs/site-data.md). Versions are indexes into Meta.versions; -1 = none. */

export interface Counts {
  added: number;
  changed: number;
  removed: number;
  unchanged: number;
  discovered: number;
}
export interface DiscoveryTotals {
  discovered: number;
  encrypted: number;
}
export interface VersionMeta {
  i: number;
  build: number;
  push: number;
  version: string;
  label: string;
  counts: { items: Counts; spells: Counts };
  discovery: { items: DiscoveryTotals; spells: DiscoveryTotals } | null;
  hotfixes: string | null;
  lockedRows: number;
  unlocked: string[];
  newlyLocked: string[];
}
export interface Meta {
  schema: number;
  versions: VersionMeta[];
  statNames: Record<string, string>;
  latest: number;
  baselineBuild: number;
}

export interface ItemRow {
  id: number;
  name: string;
  /** looks like a test/placeholder item (name pattern); a hint for filtering, not a fact about the game */
  test: boolean;
  enc: boolean;
  quality: number | null;
  ilvl: number | null;
  reqLvl: number | null;
  cls: number | null;
  sub: number | null;
  inv: number;
  gear: boolean;
  icon: number;
  first: number;
  changed: number;
  disc: number;
  base: boolean;
  armor: number;
  dps: number;
  stats: Record<string, number> | null;
  set: number;
  shard: number;
}
export interface SpellRow {
  id: number;
  name: string;
  test: boolean;
  enc: boolean;
  school: number;
  castMs: number | null;
  durMs: number | null;
  icon: number;
  tags: number[];
  first: number;
  changed: number;
  disc: number;
  base: boolean;
  /** 0 = no description, 1 = fully rendered, 2 = some text could not be rendered exactly */
  text: number;
  shard: number;
}
export interface ItemIndex {
  rows: ItemRow[];
  byId: Map<number, ItemRow>;
  icons: string[];
  classes: Record<string, string>;
  subclasses: Record<string, string>;
}
export interface SpellIndex {
  rows: SpellRow[];
  byId: Map<number, SpellRow>;
  icons: string[];
  tags: string[];
}

export interface HistoryEvent {
  v: number;
  t: 'added' | 'changed' | 'discovered' | 'removed';
  a?: string[];
  c?: Record<string, [unknown, unknown]>;
  d?: string;
}
/** One entity record from a shard: d = the pipeline's `data`, f/l/x = first seen / last changed / discovered at, b = baseline. */
export interface EntityRecord {
  d: Record<string, any>;
  f: number;
  l: number;
  x: number;
  b: 0 | 1;
  h: HistoryEvent[];
  /** spells only: ids of items that use it (capped) and the full count */
  u?: number[];
  un?: number;
}
export interface BuildChange {
  k: 'i' | 's';
  id: number;
  t: HistoryEvent['t'];
  a?: string[];
  d?: string;
  n?: number;
  c?: [string, unknown, unknown][];
  /** removed entities only: the name and icon they had */
  nm?: string;
  ic?: string;
}
export interface BuildFile {
  changes: BuildChange[];
  locked: Record<string, Record<string, number>>;
  unlocked: string[];
  newlyLocked: string[];
}

const cache = new Map<string, Promise<unknown>>();

/** Fetch a JSON file once; a failed load is forgotten so a retry can succeed. */
function load<T>(path: string): Promise<T> {
  let p = cache.get(path) as Promise<T> | undefined;
  if (!p) {
    p = fetch(config.dataPath + path).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json() as Promise<T>;
    });
    p.catch(() => cache.delete(path));
    cache.set(path, p);
  }
  return p;
}

function rowsToObjects<T>(cols: string[], rows: unknown[][], fix: (o: Record<string, any>) => void): T[] {
  return rows.map((row) => {
    const o: Record<string, any> = {};
    for (let i = 0; i < cols.length; i++) o[cols[i]] = row[i];
    fix(o);
    return o as T;
  });
}

export const getMeta = () => load<Meta>('meta.json');

export const getItems = (): Promise<ItemIndex> =>
  load<{ cols: string[]; rows: unknown[][]; icons: string[]; classes: Record<string, string>; subclasses: Record<string, string> }>('items.json').then((f) => {
    const rows = rowsToObjects<ItemRow>(f.cols, f.rows, (o) => {
      o.enc = o.enc === 1;
      o.test = o.test === 1;
      o.gear = o.gear === 1;
      o.base = o.base === 1;
      o.stats = o.stats || null;
    });
    return { rows, byId: new Map(rows.map((r) => [r.id, r])), icons: f.icons, classes: f.classes, subclasses: f.subclasses };
  });

export const getSpells = (): Promise<SpellIndex> =>
  load<{ cols: string[]; rows: unknown[][]; icons: string[]; tags: string[] }>('spells.json').then((f) => {
    const rows = rowsToObjects<SpellRow>(f.cols, f.rows, (o) => {
      o.enc = o.enc === 1;
      o.test = o.test === 1;
      o.base = o.base === 1;
    });
    return { rows, byId: new Map(rows.map((r) => [r.id, r])), icons: f.icons, tags: f.tags };
  });

export const getBuild = (i: number) => load<BuildFile>(`builds/${i}.json`);

export function getEntity(kind: 'items' | 'spells', id: number, shard: number): Promise<EntityRecord | undefined> {
  return load<Record<string, EntityRecord>>(`${kind}/${shard}.json`).then((s) => s[String(id)]);
}
